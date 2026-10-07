"""Language runtime catalog and read-only discovery. Discovery never invokes inference."""

from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import httpx

LOCAL_CHAT_PROVIDERS = {"ollama", "lmstudio", "llamacpp"}
LANGUAGE_PROVIDERS = [
    {
        "id": "ollama",
        "label": "Ollama · local, free",
        "endpoint": "http://127.0.0.1:11434",
        "model": "qwen3.5:4b",
        "description": "Download a model once; run it on your machine without an API fee.",
        "setup": "ollama serve",
        "docs": "https://ollama.com/library",
    },
    {
        "id": "lmstudio",
        "label": "LM Studio · local, free",
        "endpoint": "http://127.0.0.1:1234/v1",
        "model": "",
        "description": "Download and load a chat model in LM Studio, then start its local server. Set context size there.",
        "setup": "lms server start",
        "docs": "https://lmstudio.ai/docs/developer/openai-compat",
    },
    {
        "id": "llamacpp",
        "label": "llama.cpp · local, free",
        "endpoint": "http://127.0.0.1:8080/v1",
        "model": "",
        "description": "Serve a downloaded GGUF chat model. The server controls context size and memory use.",
        "setup": "llama-server -m /path/to/model.gguf --host 127.0.0.1 --port 8080 -c 8192",
        "docs": "https://github.com/ggml-org/llama.cpp/tree/master/tools/server",
    },
    {
        "id": "openrouter",
        "label": "OpenRouter · free public models",
        "endpoint": "https://openrouter.ai/api/v1",
        "model": "",
        "description": "Choose a currently listed free model with JSON output. Requires an OpenRouter key; quotas and availability vary. Story text is sent to the selected service. Paid routing is disabled.",
        "setup": "",
        "docs": "https://openrouter.ai/docs/quickstart",
    },
    {
        "id": "openai",
        "label": "OpenAI · paid API",
        "endpoint": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "description": "Uses your OpenAI API account. Story text is sent to OpenAI.",
        "setup": "",
        "docs": "https://platform.openai.com/docs/models",
    },
    {
        "id": "compatible",
        "label": "Other OpenAI-compatible server",
        "endpoint": "http://127.0.0.1:8000/v1",
        "model": "",
        "description": "Connect another chat server, such as vLLM. Remote endpoints require HTTPS and a key; pricing depends on the provider.",
        "setup": "",
        "docs": "",
    },
]

LLM_MODEL_OPTIONS = [
    {"id": f"{family}:{size}", "label": f"{label} · {size.upper()}", "tier": tier, "description": description}
    for family, label, sizes in [
        ("qwen3.5", "Qwen 3.5", ["0.8b", "2b", "4b", "9b", "27b"]),
        ("qwen3", "Qwen 3", ["4b", "8b", "14b"]),
        ("gemma3", "Gemma 3", ["1b", "4b", "12b", "27b"]),
        ("llama3.2", "Llama 3.2", ["1b", "3b"]),
        ("qwen2.5", "Qwen 2.5", ["1.5b-instruct"]),
    ]
    for size in sizes
    for tier, description in [
        ("small", "Lower memory use; complex planning may need more repairs.")
        if float(size.split("b")[0]) < 4
        else ("balanced", "Moderate memory use. Story complexity and context size affect results.")
        if float(size.split("b")[0]) <= 8
        else (
            "large",
            "More model capacity and memory use. Quality is not guaranteed; keep enough memory for context.",
        )
    ]
]


def local_endpoint(settings):
    return urlparse(settings.llm_endpoint).hostname in ("localhost", "127.0.0.1", "::1")


def endpoint(settings):
    return {"openai": "https://api.openai.com/v1", "openrouter": "https://openrouter.ai/api/v1"}.get(
        settings.llm_provider, settings.llm_endpoint
    )


def needs_key(settings):
    return settings.llm_provider in ("openai", "openrouter") or (
        settings.llm_provider != "ollama" and not local_endpoint(settings)
    )


def quality_guidance(settings):
    context = f", {settings.llm_context_tokens // 1024}K context" if settings.llm_provider == "ollama" else ""
    return (
        f"Language model: {settings.llm_model} ({settings.llm_provider}{context}). "
        "Please choose a more capable language model in Models & production, save, then use "
        "Retry with selected language model. If you must keep this model, enable compact planning recovery "
        "and retry. A larger server context may also help if memory allows."
    )


def _free_json_model(row):
    try:
        pricing = row.get("pricing", {})
        return (
            row["id"].endswith(":free")
            and Decimal(str(pricing.get("prompt", "-1"))) == 0
            and Decimal(str(pricing.get("completion", "-1"))) == 0
            and Decimal(str(pricing.get("request", "0"))) == 0
            and "response_format" in row.get("supported_parameters", [])
            and "text" in row.get("architecture", {}).get("output_modalities", ["text"])
        )
    except (KeyError, TypeError, AttributeError, InvalidOperation):
        return False


def discover_language_models(settings, store, client=None):
    owns_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(8, connect=3))
    provider = settings.llm_provider
    key = store.secret(provider) if provider != "ollama" else ""
    required = needs_key(settings) and not key
    status = {
        "provider": provider,
        "models": [],
        "options": [],
        "available": False,
        "reachable": False,
        "verified": False,
        "credential_required": required,
        "capabilities": {},
    }
    try:
        if provider == "ollama":
            response = client.get(endpoint(settings) + "/api/tags")
            response.raise_for_status()
            for row in response.json()["models"]:
                name = row["name"]
                try:
                    info = client.post(endpoint(settings) + "/api/show", json={"model": name})
                    info.raise_for_status()
                    caps = info.json().get("capabilities", [])
                except (httpx.HTTPError, ValueError, KeyError):
                    continue
                status["capabilities"][name] = caps
                if "completion" in caps:
                    status["options"].append({"id": name, "label": name})
        else:
            if required and provider != "openrouter":
                status["error"] = "Save this provider's API key in Models & production, then refresh models."
                return status
            # The public free-model catalog needs no credentials.
            headers = {"Authorization": "Bearer " + key} if key and provider != "openrouter" else {}
            response = client.get(endpoint(settings) + "/models", headers=headers)
            response.raise_for_status()
            rows = response.json()["data"]
            status["options"] = [
                {
                    "id": row["id"],
                    "label": row.get("name", row["id"]),
                    "context_length": row.get("context_length"),
                }
                for row in rows
                if provider != "openrouter" or _free_json_model(row)
            ]
        status["models"] = [row["id"] for row in status["options"]]
        status["reachable"] = True
        status["available"] = settings.llm_model in status["models"] and not required
        if required:
            status["error"] = "Free models found. Save an OpenRouter API key before planning."
        elif not status["available"]:
            status["error"] = "Selected model is not listed. Load or install it, or choose a listed model."
        # Catalog membership is not an inference/quality check.
    except httpx.HTTPStatusError as exc:
        status["error"] = (
            f"Model discovery returned HTTP {exc.response.status_code}. Check endpoint and saved credentials in Models & production."
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        status["error"] = (
            "Cannot read the model catalog. Start the server and check the endpoint in Models & production."
        )
    finally:
        if owns_client:
            client.close()
    return status
