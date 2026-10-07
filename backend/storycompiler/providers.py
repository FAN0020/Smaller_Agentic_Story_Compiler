"""Network adapters own authentication, structured responses, and bounded failures."""

import json
import time
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from .language_models import LOCAL_CHAT_PROVIDERS, endpoint, local_endpoint, needs_key, quality_guidance
from .prompts import BASE, STAGES, VERSION
from .resources import GIB, RESERVE, ResourceError, inference_lease, snapshot, wait_for_headroom


class ProviderError(RuntimeError):
    pass


class JsonLLM:
    def __init__(self, settings, client=None, record=None):
        self.store = settings
        self.settings = settings.get()
        self.client = client or httpx.Client(timeout=httpx.Timeout(600, connect=15))
        self.record = record or (lambda *_: None)
        self.ollama_capabilities = None

    def generate(self, stage, context, schema):
        lease = (
            inference_lease()
            if self.settings.llm_provider in LOCAL_CHAT_PROVIDERS and local_endpoint(self.settings)
            else nullcontext()
        )
        with lease:
            return self._generate(stage, context, schema)

    def _admit_local(self):
        settings = self.settings
        if urlparse(settings.llm_endpoint).hostname not in ("localhost", "127.0.0.1", "::1"):
            return
        if settings.llm_provider != "ollama":
            state = wait_for_headroom(RESERVE, snapshot(Path.cwd()), lambda: snapshot(Path.cwd()))
            if state.available < RESERVE or state.disk_free < 10:
                raise ResourceError(
                    "Close memory-heavy apps before local planning. Configure model size and context in your language server and keep 10 GiB disk free."
                )
            return
        try:
            response = self.client.get(settings.llm_endpoint + "/api/tags")
            response.raise_for_status()
            model = next(m for m in response.json()["models"] if m["name"] == settings.llm_model)
            required = model["size"] / GIB * 1.2 + 2 * settings.llm_context_tokens / 16384
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"Local model inspection returned HTTP {e.response.status_code}; check the endpoint"
            ) from e
        except (httpx.HTTPError, ValueError, KeyError, TypeError, StopIteration) as e:
            raise ProviderError(
                "Cannot inspect the selected local model. Check Ollama and install the exact selected model tag."
            ) from e
        state = wait_for_headroom(required + RESERVE, snapshot(Path.cwd()), lambda: snapshot(Path.cwd()))
        if state.disk_free < 10 or state.available < required + RESERVE:
            raise ResourceError(
                f"Local planning needs about {required + RESERVE:.1f} GiB available memory; "
                f"{state.available:.1f} GiB available. Choose a smaller model/context or close memory-heavy apps. Keep 10 GiB disk free."
            )

    def _generate(self, stage, context, schema):
        if not self.settings.llm_model.strip():
            raise ProviderError("Choose a language model in Models & production before planning")
        if self.settings.llm_provider in LOCAL_CHAT_PROVIDERS:
            self._admit_local()
        if self.settings.llm_provider == "ollama" and self.ollama_capabilities is None:
            try:
                response = self.client.post(
                    self.settings.llm_endpoint + "/api/show", json={"model": self.settings.llm_model}
                )
                response.raise_for_status()
                self.ollama_capabilities = set(response.json().get("capabilities", []))
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise ProviderError(
                    "Cannot read the selected Ollama model's capabilities. Start Ollama, install the exact model tag, and check Models & production."
                ) from exc
            if "completion" not in self.ollama_capabilities:
                raise ProviderError(
                    "Choose a chat/completion model in Models & production; this model is embedding-only"
                )
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
                    "options": {
                        "temperature": 0.2,
                        "num_ctx": settings.llm_context_tokens,
                        "num_predict": 8192,
                    },
                }
                if "thinking" not in self.ollama_capabilities:
                    body.pop("think")
                headers = {}
            else:
                provider = settings.llm_provider
                key = self.store.secret(provider)
                if not key and needs_key(settings):
                    raise ProviderError(
                        "Save the selected provider’s API key in Models & production before planning"
                    )
                base = endpoint(settings)
                url = base.rstrip("/") + "/chat/completions"
                body = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                }
                if provider == "lmstudio":
                    body["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {"name": schema.__name__, "schema": contract},
                    }
                if provider == "llamacpp":
                    body["response_format"] = {"type": "json_schema", "schema": contract}
                if provider == "openrouter":
                    if not settings.llm_model.endswith(":free"):
                        raise ProviderError("Choose an explicit free model in Models & production")
                    body["provider"] = {
                        "require_parameters": True,
                        "allow_fallbacks": False,
                        "max_price": {"prompt": 0, "completion": 0, "request": 0},
                    }
                headers = {"Authorization": "Bearer " + key} if key else {}
            try:
                response = self.client.post(url, json=body, headers=headers)
            except httpx.RequestError as e:
                raise ProviderError(
                    "Language model connection failed or timed out. Check the server and endpoint in Models & production."
                ) from e
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                try:
                    delay = float(response.headers.get("retry-after", "2"))
                except ValueError:
                    delay = 2
                time.sleep(max(0, min(10, delay)))
                continue
            if response.is_error:
                advice = {
                    401: "Check the saved API key for this provider.",
                    403: "Your account or key cannot access this model.",
                    404: "The selected model or API endpoint was not found.",
                    429: "The provider's quota or rate limit was reached. Wait or choose another available model.",
                    400: "The model rejected the request format or context size. Choose a JSON-capable chat model or check the server's context limit.",
                }.get(
                    response.status_code,
                    "The provider is unavailable or rejected this request. Check its service status and model availability.",
                )
                raise ProviderError(
                    f"Language model returned HTTP {response.status_code}. {advice} Open Models & production to change the selection."
                )
            try:
                data = response.json()
                raw = (
                    data["message"]["content"]
                    if settings.llm_provider == "ollama"
                    else data["choices"][0]["message"]["content"]
                )
                result = schema.model_validate_json(raw)
            except (ValueError, KeyError, IndexError, TypeError, ValidationError) as e:
                if attempt == 2:
                    raise ProviderError(
                        "The model returned invalid structured JSON after 3 attempts. "
                        + quality_guidance(settings)
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
                    "context_tokens": settings.llm_context_tokens
                    if settings.llm_provider == "ollama"
                    else None,
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "seconds": round(time.monotonic() - start, 2),
                    "attempts": attempt + 1,
                    "tokens": data.get("eval_count", data.get("usage", {}).get("completion_tokens")),
                }
            )
            return result
        raise ProviderError("Model temporarily unavailable after bounded retries")

    def close(self):
        self.client.close()
