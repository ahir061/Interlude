import json
import pytest

from interlude.config import Settings
from interlude.domain import (Brand, BreakDecision, Interval, Scene, SceneSemantics, Transcript,
                              TranscriptSegment, AnalysisResult, VideoMetadata, AnalysisManifest)
from interlude.services.candidates import CandidateService
from interlude.services.brands import BrandMatchingService, load_brands
from interlude.services.policy import PacingService, WhereService
from interlude.services.manifest import ManifestService


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def scenes():
    return [Scene(id="s1", start_sec=0, end_sec=60),
            Scene(id="s2", start_sec=60, end_sec=120, boundary_score=0.9)]


def semantics(**kw):
    return SceneSemantics(**(dict(dominant_activity="cooking", contexts=["family meal", "cooking"],
        sensitive_contexts=[], mood=["calm"], narrative_state_before="cooking", narrative_state_after="meal ends",
        semantic_transition_score=0.9, confidence=0.95) | kw))


def brand(**kw):
    return Brand(**(dict(brand_id="sample", display_name="Sample", category="food",
                        target_contexts=["cooking", "family meal"], negative_contexts=["grief", "funeral"]) | kw))


def test_active_dialogue_boundary_is_rejected(settings, scenes):
    transcript = Transcript(segments=[TranscriptSegment(start_sec=59, end_sec=62, text="এখন নয়")])
    c = CandidateService(settings).generate(scenes, transcript, [], 120)[0]
    assert c.prefilter_status == "REJECTED"
    assert "asr_active_dialogue" in c.rejection_reasons


def test_vad_speech_boundary_is_rejected(settings, scenes):
    c = CandidateService(settings).generate(scenes, Transcript(), [Interval(start_sec=59, end_sec=61)], 120)[0]
    assert "vad_active_speech" in c.rejection_reasons


def test_safe_boundary_can_survive_prefilter(settings, scenes):
    c = CandidateService(settings).generate(scenes, Transcript(), [], 120)[0]
    assert c.prefilter_status == "SURVIVED"


def test_speech_margin_is_conservative(settings, scenes):
    c = CandidateService(settings).generate(scenes, Transcript(), [Interval(start_sec=58, end_sec=59.8)], 120)[0]
    assert "insufficient_dialogue_separation" in c.rejection_reasons


def test_negative_context_is_hard_block():
    match = BrandMatchingService().evaluate(semantics(sensitive_contexts=["funeral"]), [brand()])[0]
    assert not match.eligible
    assert "negative_context:funeral" in match.hard_block_reasons


def test_positive_relevance_cannot_override_negative_block():
    match = BrandMatchingService().evaluate(semantics(contexts=["cooking", "family meal", "grief"]), [brand()])[0]
    assert not match.eligible and match.final_score == 0


def test_negative_free_text_is_also_blocked():
    match = BrandMatchingService().evaluate(semantics(narrative_state_before="family after a funeral"), [brand()])[0]
    assert not match.eligible


def test_unknown_sensitive_context_rejects_uncertainty():
    match = BrandMatchingService().evaluate(semantics(sensitive_contexts=["unmapped distress"]), [brand()])[0]
    assert not match.eligible


def test_plural_negative_context_in_narrative_is_hard_block():
    match = BrandMatchingService().evaluate(semantics(
        narrative_state_before="The family is mourning after attending funerals"), [brand()])[0]
    assert not match.eligible and match.final_score == 0


def test_mourning_synonym_is_hard_block():
    match = BrandMatchingService().evaluate(semantics(mood=["mourning"]), [brand()])[0]
    assert not match.eligible


def test_new_ninth_brand_is_loaded_without_source_change(tmp_path):
    records = [brand(brand_id=f"b{i}").model_dump() for i in range(9)]
    records[8]["target_contexts"] = ["cooking"]
    path = tmp_path / "brands.json"
    path.write_text(json.dumps(records))
    loaded = load_brands(path)
    evaluated = BrandMatchingService().evaluate(semantics(), loaded)
    assert len(loaded) == 9 and len(evaluated) == 9
    assert next(m for m in evaluated if m.brand_id == "b8").eligible


def test_no_eligible_brand_returns_no_ad():
    matches = BrandMatchingService().evaluate(semantics(sensitive_contexts=["grief"]), [brand()])
    assert BrandMatchingService().select(matches, 0.1) is None


def accepted(timestamp=50, duration=6):
    return BreakDecision(candidate_id="c1", timestamp_sec=timestamp, accepted=True, whether_pass=True,
                         selected_brand_id="sample", selected_creative_id="ad", creative_url="/ad.mp4",
                         creative_duration_sec=duration)


def test_minimum_break_gap_is_enforced(settings):
    result = PacingService(settings).evaluate(70, 6, [accepted()], 120)
    assert not result["pass"] and "minimum_break_gap" in result["reasons"]


def test_max_breaks_per_hour_is_enforced(settings):
    settings.max_breaks_per_hour = 1
    result = PacingService(settings).evaluate(100, 6, [accepted()], 120)
    assert "maximum_breaks_per_hour" in result["reasons"]


def test_max_ad_load_is_enforced(settings):
    result = PacingService(settings).evaluate(100, 10, [accepted(duration=10)], 120)
    assert not result["pass"] and "maximum_ad_load" in result["reasons"]


def test_zero_break_limit_rejects(settings):
    settings.max_breaks_per_hour = 0
    assert not PacingService(settings).evaluate(60, 6, [], 120)["pass"]


def test_hour_limit_is_rolling(settings):
    settings.max_breaks_per_hour = 1
    assert not PacingService(settings).evaluate(3601, 6, [accepted(3590)], 7200)["pass"]


def test_where_cannot_override_dialogue(settings, scenes):
    c = CandidateService(settings).generate(scenes, Transcript(), [Interval(start_sec=59, end_sec=61)], 120)[0]
    assert WhereService(settings).score(c, semantics())["score"] == 0


def test_analysis_output_schema_is_valid(tmp_path, scenes):
    result = AnalysisResult(video=VideoMetadata(id="video", duration_sec=120, width=640, height=360,
        frame_rate=25, codec="h264", has_audio=True, source_url="/source.mp4"), scenes=scenes,
        transcript=Transcript(), vad_intervals=[], candidates=[], decisions=[accepted()])
    ManifestService().write(result, tmp_path)
    payload = AnalysisManifest.model_validate_json((tmp_path / "analysis.json").read_text())
    assert payload.summary["accepted_break_count"] == 1
    assert payload.ad_breaks[0].timestamp_sec == 50
    assert json.loads((tmp_path / "debug.json").read_text())["decisions"][0]["accepted"]
