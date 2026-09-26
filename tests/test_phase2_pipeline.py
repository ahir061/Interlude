import json
import subprocess
import pytest
from interlude.config import Settings
from interlude.domain import Brand, ContextSnapshot, SafetyVerdict, Transcript
from interlude.providers.base import ProviderError
from interlude.phase2_pipeline import Phase2Pipeline
from interlude.services.brands import load_brands, vocabulary
from interlude.services.brand_policy import BrandEligibilityEngine, BrandRankingEngine
from interlude.services.creatives import CreativeService
from interlude.services.manifest import ManifestService
from test_phase2_safety import semantics


@pytest.fixture
def media(tmp_path):
    source = tmp_path/"source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=25:d=30",
        "-f", "lavfi", "-i", "color=blue:s=320x180:r=25:d=30", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-t", "60",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True, capture_output=True)
    catalog = tmp_path/"brands.json"
    catalog.write_text(json.dumps([{"brand_id": b, "display_name": b, "category": "food", "target_contexts": ["cooking"],
                                   "negative_contexts": ["funeral"]} for b in ["one", "two"]]))
    return source, Settings(_env_file=None, brands_path=catalog, data_dir=tmp_path/"data", reports_dir=tmp_path/"reports")


class SilentAsr:
    def transcribe(self, audio):
        return Transcript()


class Perception:
    metrics = {"qwen_calls": 0, "semantic_cache_hits": 0, "semantic_cache_misses": 0}
    events = []

    def __init__(self, verdict="SAFE", continuity="completed"):
        self.verdict, self.continuity = verdict, continuity

    def perceive(self, frames, transcript, vocab, timestamp, *args):
        return semantics(dialogue_continuity=self.continuity,
                         evidence=[{"timestamp_sec": timestamp, "observation": "visible transition"}])

    def verify(self, frames, transcript, scene, memory, brand, timestamp, *args):
        return SafetyVerdict(verdict="UNCERTAIN" if brand.brand_id == "one" else self.verdict,
            confidence=0.95, conflicts=[], evidence=[{"timestamp_sec": timestamp, "observation": "reviewed actual frames"}])


def test_real_phase2_media_pipeline_and_independent_safety_fallback(media):
    source, s = media
    result = Phase2Pipeline(s, SilentAsr(), Perception()).run("test", source, lambda _: None)
    assert len(result.raw_shots) == 2 and len(result.scenes) == 2
    decision = result.decisions[0]
    assert decision.accepted and decision.selected_brand_id == "two"
    assert decision.debug["brand_safety_verification"][0]["verdict"] == "UNCERTAIN"
    assert len(list((s.reports_dir/"inspection").rglob("*.mp4"))) == 1
    paths = ManifestService().write(result, s.data_dir/"outputs"/"test")
    assert paths["vmap"].exists()
    assert not list((s.data_dir/"work").iterdir())


def test_all_safety_uncertain_yields_no_ad(media):
    source, s = media
    result = Phase2Pipeline(s, SilentAsr(), Perception(verdict="UNCERTAIN")).run("test", source, lambda _: None)
    assert not any(d.accepted for d in result.decisions)
    assert "no_safe_brand" in result.decisions[0].rejection_reasons


def test_semantic_dialogue_continuation_never_gets_where_score(media):
    source, s = media
    result = Phase2Pipeline(s, SilentAsr(), Perception(continuity="continuing")).run("test", source, lambda _: None)
    assert result.decisions[0].where_score == 0 and not result.decisions[0].accepted
    assert len(result.scenes) == 1


def test_asr_failure_stops_phase2_without_decisions(media):
    class FailedAsr:
        def transcribe(self, audio):
            raise ProviderError("asr_timeout")
    source, s = media
    with pytest.raises(ProviderError, match="asr_timeout"):
        Phase2Pipeline(s, FailedAsr(), Perception()).run("test", source, lambda _: None)
    assert not list((s.data_dir/"work").iterdir())


def test_runtime_unseen_brand_i_vocabulary_safety_ranking_and_creative(tmp_path):
    s = Settings(_env_file=None, data_dir=tmp_path/"data")
    original = load_brands(s.brands_path)
    path = tmp_path/"brands.json"
    brand_i = Brand(brand_id="brand_i", display_name="Brand I", category="sports/fitness",
        target_contexts=["running", "exercise", "gym", "sports"], negative_contexts=["injury", "hospital"])
    path.write_text(json.dumps([b.model_dump() for b in original]+[brand_i.model_dump()]))
    brands = load_brands(path)
    assert len(brands) == 9 and {"gym", "running", "exercise"} <= set(vocabulary(brands))
    scene = semantics(dominant_activity="running", contexts=["running", "exercise", "gym"])
    snapshot = ContextSnapshot(current_contexts=scene.contexts, current_sensitive_contexts=[], recent_sensitive_contexts=[])
    ranked = BrandRankingEngine(s).rank(scene, brands, BrandEligibilityEngine().evaluate(scene, snapshot, brands))
    assert ranked[0].brand_id == "brand_i"
    snapshot.current_sensitive_contexts = ["injury"]
    blocked = next(b for b in BrandEligibilityEngine().evaluate(scene, snapshot, brands) if b.brand_id == "brand_i")
    assert not blocked.eligible and blocked.score is None
    generated = CreativeService(s).ensure([brand_i])[0].creatives[0]
    assert generated.generated and generated.duration_sec == 6
