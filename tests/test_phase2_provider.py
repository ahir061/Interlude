import json
import httpx
import pytest
from interlude.config import Settings
from interlude.providers.perception import PerceptionClient
from interlude.providers.base import ProviderError
from interlude.domain import SafetyVerdict
from test_phase2_safety import semantics


def client(tmp_path, respond):
    return PerceptionClient(Settings(_env_file=None, data_dir=tmp_path, llm_api_url="https://example.test/v1",
                                    llm_model="test", llm_max_retries=3),
                            httpx.Client(transport=httpx.MockTransport(respond)), sleep=lambda _: None)


def test_phase2_malformed_json_retried_once_and_never_cached(tmp_path):
    c = client(tmp_path, lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}))
    with pytest.raises(ProviderError, match="invalid_response"):
        c.perceive([], [], ["gym"], 30, "video", "catalog")
    assert c.metrics["qwen_calls"] == 2
    assert not list((tmp_path/"semantic_cache").glob("*.json"))


def test_validated_cache_hit_and_catalogue_invalidation(tmp_path):
    c = client(tmp_path, lambda r: httpx.Response(200,
        json={"choices": [{"message": {"content": semantics().model_dump_json()}}]}))
    a = c.perceive([], [], ["gym"], 30, "video", "catalog")
    b = c.perceive([], [], ["gym"], 30, "video", "catalog")
    assert a == b and c.metrics["qwen_calls"] == 1 and c.metrics["semantic_cache_hits"] == 1
    c.perceive([], [], ["gym", "running"], 30, "video", "catalog2")
    assert c.metrics["qwen_calls"] == 2


def test_phase2_timeout_abstains(tmp_path):
    def timeout(request):
        raise httpx.ReadTimeout("private detail must not leak")
    c = client(tmp_path, timeout)
    with pytest.raises(ProviderError, match="semantic_timeout"):
        c.perceive([], [], [], 30, "video", "catalog")
    assert c.metrics["qwen_calls"] == 4


def test_safety_uncertain_is_never_safe(tmp_path):
    from interlude.domain import Brand, ContextSnapshot
    verdict = {"verdict": "UNCERTAIN", "confidence": 0.8, "conflicts": [],
               "evidence": [{"timestamp_sec": 30, "observation": "cannot rule out grief"}]}
    c = client(tmp_path, lambda r: httpx.Response(200,
        json={"choices": [{"message": {"content": json.dumps(verdict)}}]}))
    result = c.verify([], [], semantics(), ContextSnapshot(current_contexts=[], current_sensitive_contexts=[],
        recent_sensitive_contexts=[]), Brand(brand_id="new", display_name="New", category="food"), 30, "v", "c")
    assert isinstance(result, SafetyVerdict) and result.verdict == "UNCERTAIN"
