import pytest
from pydantic import ValidationError
from interlude.domain import Scene, SceneSemantics, Brand, TranscriptSegment
from interlude.config import Settings


def test_dotenv_numeric_values_parse():
    assert Settings(_env_file=None, asr_temperature="0", asr_segment_timestamps="true").asr_temperature == 0


def test_intervals_must_be_ordered():
    with pytest.raises(ValidationError):
        TranscriptSegment(start_sec=5, end_sec=4, text="না")
    with pytest.raises(ValidationError):
        Scene(id="scene_001", start_sec=5, end_sec=4)


def test_brand_ids_cannot_escape_storage():
    with pytest.raises(ValidationError):
        Brand(brand_id="../escape", display_name="Example", category="food")


def test_invalid_semantic_score_is_rejected():
    with pytest.raises(ValidationError):
        SceneSemantics(dominant_activity="eating", contexts=[], sensitive_contexts=[], mood=[],
                       narrative_state_before="meal", narrative_state_after="leaving",
                       semantic_transition_score=2, confidence=1)
