import json
import httpx
import pytest
from interlude.config import Settings
from interlude.domain import Frame, SceneSemantics
from interlude.providers.semantic import QwenSemanticProvider
from interlude.providers.asr import GroqWhisperProvider
from interlude.providers.base import ProviderError


def settings(**kwargs):
    return Settings(_env_file=None, llm_api_url="https://example.test/v1/chat/completions",
                    llm_api_key="test", llm_model="test", groq_api_key="test",
                    llm_max_retries=1, asr_max_retries=1, **kwargs)


def test_invalid_qwen_json_is_not_trusted():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200,
        json={"choices": [{"message": {"content": '{"confidence": 1}'}}]})))
    with pytest.raises(ProviderError, match="semantic_invalid_response"):
        QwenSemanticProvider(settings(), client, sleep=lambda _: None).analyze([], [], ["cooking"], 5)


def test_qwen_failure_rejects_candidate_safely():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503, text="SECRET")))
    with pytest.raises(ProviderError) as failure:
        QwenSemanticProvider(settings(), client, sleep=lambda _: None).analyze([], [], [], 5)
    assert "SECRET" not in str(failure.value)
    assert failure.value.code == "semantic_http_503"


def test_qwen_receives_frames_and_timestamps(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"sample-jpeg")
    def respond(request):
        body = json.loads(request.content)
        assert body["chat_template_kwargs"]["enable_thinking"] is False
        assert any(p["type"] == "image_url" for p in body["messages"][1]["content"])
        assert "4.000" in str(body)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "dominant_activity": "cooking", "contexts": ["cooking"], "sensitive_contexts": [],
            "mood": ["calm"], "narrative_state_before": "cooking", "narrative_state_after": "finished",
            "semantic_transition_score": 0.8, "confidence": 0.9})}}]})
    result = QwenSemanticProvider(settings(), httpx.Client(transport=httpx.MockTransport(respond))).analyze(
        [Frame(timestamp_sec=4, path=str(frame))], [], ["cooking"], 5)
    assert isinstance(result, SceneSemantics) and result.dominant_activity == "cooking"


def test_asr_normalizes_bengali_and_word_timestamps(tmp_path):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"test")
    def respond(request):
        assert b"whisper-large-v3" in request.content and b"verbose_json" in request.content
        assert b"timestamp_granularities[]" in request.content
        return httpx.Response(200, json={"text": "চলো যাই", "segments": [
            {"start": 1, "end": 3, "text": "চলো যাই"}], "words": [{"start": 1, "end": 2, "word": "চলো"}]})
    transcript = GroqWhisperProvider(settings(), httpx.Client(transport=httpx.MockTransport(respond))).transcribe(path)
    assert transcript.segments[0].text == "চলো যাই"
    assert transcript.segments[0].words[0].start_sec == 1


def test_asr_missing_timestamps_fails_safely(tmp_path):
    path = tmp_path / "audio.wav"
    path.write_bytes(b"test")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"text": "কথা"})))
    with pytest.raises(ProviderError):
        GroqWhisperProvider(settings(), client, sleep=lambda _: None).transcribe(path)
