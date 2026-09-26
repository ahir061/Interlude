"""Regression coverage for real false negatives without relaxing safety."""
import pytest

from interlude.config import Settings
from interlude.domain import Interval, Scene, Transcript, TranscriptSegment, Word
from interlude.services.candidates import CandidateService
from interlude.services.policy import WhereService
from interlude.services.scene_builder import DialogueSafetyGate, SemanticSceneBuilder, scene_grouping_reasons
from test_phase2_safety import semantics


def candidate(transcript=None, vad=None, boundary=0.95, before=30, after=30):
    shots = [Scene(id="before", start_sec=30-before, end_sec=30),
             Scene(id="after", start_sec=30, end_sec=30+after, boundary_score=boundary)]
    return CandidateService(Settings(_env_file=None)).generate(shots, transcript or Transcript(), vad or [], 60)[0]


def test_whisper_envelope_is_not_exact_speech():
    transcript = Transcript(segments=[TranscriptSegment(start_sec=20, end_sec=40, text="broad envelope",
        words=[Word(start_sec=28, end_sec=29.9, text="ends"), Word(start_sec=30.2, end_sec=32, text="starts")])])
    c = candidate(transcript)
    assert c.prefilter_status == "SURVIVED" and not c.speech_active
    gate = DialogueSafetyGate(Settings(_env_file=None)).evaluate(30, transcript, [], 60)
    assert gate["safe"] and not gate["asr_word_crossing_boundary"]
    assert gate["asr_segment_crossing_boundary"]  # diagnostic only


@pytest.mark.parametrize("source", ["word", "vad"])
def test_exact_speech_cannot_be_compensated_by_perfect_quality(source):
    word = Word(start_sec=29.9, end_sec=30.1, text="crossing")
    transcript = Transcript(segments=[TranscriptSegment(start_sec=20, end_sec=40, text="speech", words=[word])])
    c = candidate(transcript if source == "word" else Transcript(),
                  [Interval(start_sec=29.9, end_sec=30.1)] if source == "vad" else [])
    assert c.prefilter_status == "REJECTED"
    assert WhereService(Settings(_env_file=None)).score(c, semantics())["score"] == 0


def test_short_clear_gap_and_short_shots_are_scored_not_vetoed():
    c = candidate(vad=[Interval(start_sec=28, end_sec=29.9), Interval(start_sec=30.2, end_sec=32)],
                  before=1.5, after=1.5)
    assert c.prefilter_status == "SURVIVED"
    result = WhereService(Settings(_env_file=None)).score(c, semantics(
        narrative_state="ongoing", transition_type="camera_angle", semantic_transition_score=0.6,
        transition_confidence=0.6, confidence=0.65))
    assert result["score"] >= Settings(_env_file=None).min_where_score
    assert 0 < result["components"]["dialogue_gap"] < 1
    assert 0 < result["components"]["shot_stability"] < 1


def test_same_scene_local_closure_can_survive():
    sem = semantics(transition_type="camera_angle", narrative_state="ongoing", confidence=0.6,
                    transition_confidence=0.55, semantic_transition_score=0.6)
    assert scene_grouping_reasons(sem, Settings(_env_file=None))  # grouping remains conservative
    shots = [Scene(id="one", start_sec=0, end_sec=30), Scene(id="two", start_sec=30, end_sec=60)]
    assert len(SemanticSceneBuilder(Settings(_env_file=None)).group(shots, {30: sem})) == 1
    assert WhereService(Settings(_env_file=None)).score(candidate(), sem)["score"] >= 0.55


def test_weak_combination_stays_below_floor():
    c = candidate(vad=[Interval(start_sec=28, end_sec=29.99), Interval(start_sec=30.01, end_sec=32)],
                  boundary=0.1, before=0.5, after=0.5)
    assert c.prefilter_status == "SURVIVED"
    result = WhereService(Settings(_env_file=None)).score(c, semantics(narrative_state="ongoing",
        dialogue_continuity="continuing", transition_type="none", semantic_transition_score=0.1,
        transition_confidence=0.2, confidence=0.5))
    assert result["score"] < Settings(_env_file=None).min_where_score
