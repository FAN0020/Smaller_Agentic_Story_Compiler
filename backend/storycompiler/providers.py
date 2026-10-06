"""Network adapters own authentication, structured responses, and bounded failures."""

import json
import time
from contextlib import nullcontext

import httpx
from pydantic import ValidationError

from .prompts import BASE, STAGES, VERSION
from .resources import inference_lease


class ProviderError(RuntimeError):
    pass


class JsonLLM:
    def __init__(self, settings, client=None, record=None):
        self.store = settings
        self.settings = settings.get()
        self.client = client or httpx.Client(timeout=httpx.Timeout(600, connect=15))
        self.record = record or (lambda *_: None)

    def generate(self, stage, context, schema):
        lease = inference_lease() if self.settings.llm_provider == "ollama" else nullcontext()
        with lease:
            return self._generate(stage, context, schema)

    def _generate(self, stage, context, schema):
        settings = self.settings
        thinking = settings.llm_reasoning and stage in {"episode-planner", "scene-director", "shot-director"}
        system = BASE + "\n" + STAGES[stage]
        text = json.dumps(context, ensure_ascii=False)
        contract = schema.model_json_schema()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text + "\nJSON schema: " + json.dumps(contract)},
        ]
        start = time.monotonic()
        for attempt in range(3):
            if settings.llm_provider == "ollama":
                url = settings.llm_endpoint + "/api/chat"
                body = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "format": contract,
                    "stream": False,
                    "think": thinking,
                    "keep_alive": 0,
                    "options": {"temperature": 0.2, "num_ctx": 32768, "num_predict": 14000},
                }
                headers = {}
            else:
                provider = settings.llm_provider
                key = self.store.secret(provider)
                if not key:
                    raise ProviderError("Add an API key in Model settings before planning")
                base = "https://api.openai.com/v1" if provider == "openai" else settings.llm_endpoint
                url = base.rstrip("/") + "/chat/completions"
                body = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                }
                headers = {"Authorization": "Bearer " + key}
            try:
                response = self.client.post(url, json=body, headers=headers)
            except httpx.RequestError as e:
                raise ProviderError(
                    "Language model connection failed or timed out. Check Model settings."
                ) from e
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(min(10, float(response.headers.get("retry-after", "2"))))
                continue
            if response.is_error:
                raise ProviderError(
                    f"Language model returned HTTP {response.status_code}; check model, endpoint and credentials"
                )
            try:
                data = response.json()
                raw = (
                    data["message"]["content"]
                    if settings.llm_provider == "ollama"
                    else data["choices"][0]["message"]["content"]
                )
                result = schema.model_validate_json(raw)
            except (ValueError, KeyError, IndexError, ValidationError) as e:
                if attempt == 2:
                    raise ProviderError(
                        "The model failed its structured output contract after 3 attempts"
                    ) from e
                messages.append(
                    {
                        "role": "user",
                        "content": "Repair the JSON to match the schema exactly. No markdown. "
                        + str(e)[:2000],
                    }
                )
                continue
            self.record(
                {
                    "stage": stage,
                    "prompt_version": VERSION,
                    "model": settings.llm_model,
                    "provider": settings.llm_provider,
                    "reasoning_requested": thinking if settings.llm_provider == "ollama" else None,
                    "seconds": round(time.monotonic() - start, 2),
                    "attempts": attempt + 1,
                    "tokens": data.get("eval_count", data.get("usage", {}).get("completion_tokens")),
                }
            )
            return result
        raise ProviderError("Model temporarily unavailable after bounded retries")

    def close(self):
        self.client.close()
