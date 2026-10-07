"""Private provider settings. Credentials never enter project snapshots."""

import json
import os
from pathlib import Path
from threading import RLock
from typing import Literal
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator

from .domain import Contract
from .video_models import video_profile

LOCAL_IMAGE_MODELS = {
    "mlx-community/flux2-klein-4b-4bit": "flux2-klein-4b-mlx",
    "black-forest-labs/FLUX.2-klein-4B": "flux2-klein-4b",
    "stabilityai/sd-turbo": "sd-turbo",
}


class ModelSettings(Contract):
    llm_provider: Literal["ollama", "openai", "compatible"] = "ollama"
    llm_model: str = "qwen3.5:4b"
    llm_reasoning: bool = False
    llm_context_tokens: int = Field(default=16384, ge=4096, le=65536)
    llm_endpoint: str = "http://127.0.0.1:11434"
    image_provider: Literal["local", "openai"] = "local"
    image_model: str = "mlx-community/flux2-klein-4b-4bit"
    video_provider: Literal["local", "openai", "animatic"] = "local"
    video_model: str = "Lightricks/LTX-Video-0.9.1"
    voice_provider: Literal["kokoro", "system", "openai", "none"] = "kokoro"
    voice: str = "af_heart"
    character_voices: dict[str, str] = Field(default_factory=dict)
    max_generation_calls: int = Field(default=120, ge=1, le=10000)
    local_steps: int = Field(default=20, ge=8, le=50)
    seed: int = Field(default=42, ge=0, le=2147483647)

    @model_validator(mode="after")
    def supported_local_video(self):
        if self.video_provider == "local":
            video_profile(self.video_model)
        return self

    @field_validator("llm_endpoint")
    @classmethod
    def valid_endpoint(cls, url):
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or u.query:
            raise ValueError("Enter an HTTP(S) endpoint without credentials or query parameters")
        if u.scheme == "http" and u.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote providers require HTTPS")
        return url.rstrip("/")


class SettingsStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        key = self.root / "secret.key"
        if not key.exists():
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        key.chmod(0o600)
        self.cipher = Fernet(key.read_bytes())

    def get(self):
        path = self.root / "settings.json"
        return ModelSettings.model_validate_json(path.read_text()) if path.exists() else ModelSettings()

    def _secrets(self):
        path = self.root / "secrets.enc"
        return json.loads(self.cipher.decrypt(path.read_bytes())) if path.exists() else {}

    def secret(self, provider):
        with self.lock:
            return self._secrets().get(provider, "")

    def public(self):
        with self.lock:
            return {
                **self.get().model_dump(),
                "credentials": {k: bool(v) for k, v in self._secrets().items()},
            }

    def update(self, changes):
        with self.lock:
            changes = dict(changes)
            key = changes.pop("api_key", None)
            credential_provider = changes.pop("credential_provider", None)
            settings = ModelSettings.model_validate({**self.get().model_dump(), **changes})
            if key is not None:
                provider = credential_provider or settings.llm_provider
                if provider not in ("openai", "compatible"):
                    raise ValueError("Select the API credential provider")
                secrets = self._secrets()
                secrets[provider] = key
                encrypted = self.cipher.encrypt(json.dumps(secrets).encode())
                self._write("secrets.enc", encrypted)
            self._write("settings.json", settings.model_dump_json(indent=2).encode())
            return self.public()

    def _write(self, name, data):
        path = self.root / (name + ".tmp")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        path.replace(self.root / name)


class JobSettings:
    """Immutable per-job model selection with credentials resolved only at the provider boundary."""

    def __init__(self, store, snapshot):
        self.store = store
        self.snapshot = ModelSettings.model_validate(snapshot)

    def get(self):
        return self.snapshot.model_copy(deep=True)

    def secret(self, provider):
        return self.store.secret(provider)
