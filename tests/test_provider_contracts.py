"""Provider protocol tests: offline contracts, not live account verification."""

import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image
from storycompiler.generation import OpenAIGenerator
from storycompiler.providers import ProviderError
from storycompiler.settings import SettingsStore


def adapter(tmp_path, handler):
    settings = SettingsStore(tmp_path / "settings")
    settings.update({"credential_provider": "openai", "api_key": "sk-test-private"})
    result = OpenAIGenerator(settings, lambda: False)
    result.client.close()
    result.client = httpx.Client(base_url="https://api.openai.com/v1", transport=httpx.MockTransport(handler))
    return result


def png():
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_generation_and_reference_edit_contract(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png()).decode()}]})

    api = adapter(tmp_path, handler)
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    api.image("A tree", tmp_path / "first.png")
    api.image("Same tree", tmp_path / "second.png", references=[reference])
    assert calls[0].url.path == "/v1/images/generations"
    assert calls[1].url.path == "/v1/images/edits"
    assert b'name="image[]"' in calls[1].content
    assert Image.open(tmp_path / "second.png").size == (16, 16)
    api.close()


def test_video_receipt_is_saved_before_polling_and_resume_never_resubmits(tmp_path):
    receipt, saved, calls = {}, [], []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            assert saved[-1] == {"submission_pending": True}
            assert b'name="seconds"\r\n\r\n4' in request.content
            assert b'name="input_reference"' in request.content
            return httpx.Response(200, json={"id": "video_123"})
        assert saved[-1]["provider_id"] == "video_123"
        if request.url.path.endswith("content"):
            return httpx.Response(200, content=b"test-video-bytes")
        return httpx.Response(200, json={"id": "video_123", "status": "completed"})

    api = adapter(tmp_path, handler)
    reference = tmp_path / "reference.png"
    reference.write_bytes(png())
    output = tmp_path / "clip.mp4"
    save = lambda: saved.append(dict(receipt))
    api.video("Tree sways", reference, output, "sora-2", receipt, save)
    api.video("Tree sways", reference, output, "sora-2", receipt, save)
    assert sum(method == "POST" for method, _ in calls) == 1
    assert output.read_bytes() == b"test-video-bytes"
    assert Image.open(output.with_suffix(".reference.png")).size == (1280, 720)
    api.close()


def test_uncertain_video_submission_cannot_trigger_another_charge(tmp_path):
    api = adapter(tmp_path, lambda _: pytest.fail("An ambiguous submission must not send a request"))
    with pytest.raises(ProviderError, match="unknown outcome"):
        api.video(
            "Prompt",
            tmp_path / "ref.png",
            tmp_path / "clip.mp4",
            "sora-2",
            {"submission_pending": True},
            lambda: None,
        )
    api.close()


def test_provider_errors_do_not_expose_remote_response_or_credentials(tmp_path):
    api = adapter(tmp_path, lambda _: httpx.Response(401, text="sk-test-private internal detail"))
    with pytest.raises(ProviderError) as failure:
        api.speech("Hello", tmp_path / "speech.wav")
    assert "401" in str(failure.value)
    assert "sk-test" not in str(failure.value) and "internal detail" not in str(failure.value)
    api.close()


@pytest.mark.parametrize("stage,thinking", [("scene-director", True), ("narrative-critic", False)])
def test_local_reasoning_is_an_explicit_per_job_model_option(tmp_path, stage, thinking):
    from storycompiler.contracts import CriticReport
    from storycompiler.providers import JsonLLM

    store = SettingsStore(tmp_path)
    store.update({"llm_reasoning": True})

    def handler(request):
        import json

        body = json.loads(request.content)
        assert body["think"] is thinking
        return httpx.Response(
            200, json={"message": {"content": '{"findings":[],"strengths":[],"summary":"Checked"}'}}
        )

    llm = JsonLLM(store, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert llm.generate(stage, {}, CriticReport).findings == []
    llm.close()
