"""Tests never contend with or alter the user's running local inference lease."""

import pytest
from storycompiler.resources import inference_lease


@pytest.fixture(autouse=True)
def isolated_inference_lease(tmp_path, monkeypatch):
    lease = lambda: inference_lease(tmp_path / "test-inference.lock")
    for module in ("generation", "providers", "soundtrack"):
        monkeypatch.setattr(f"storycompiler.{module}.inference_lease", lease)
