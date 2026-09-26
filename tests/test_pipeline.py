from interlude.config import Settings
from interlude.domain import JobStatus, BreakCandidate
from interlude.pipeline import analyze_candidate, transition_allowed
from interlude.providers.base import ProviderError


def test_job_state_machine_rejects_skipped_and_terminal_transitions():
    assert transition_allowed(JobStatus.QUEUED, JobStatus.INGESTING)
    assert transition_allowed(JobStatus.TRANSCRIBING, JobStatus.FAILED)
    assert not transition_allowed(JobStatus.QUEUED, JobStatus.COMPLETED)
    assert not transition_allowed(JobStatus.COMPLETED, JobStatus.FAILED)


def test_qwen_failure_rejects_candidate_safely():
    class FailingSemantic:
        def analyze(self, *args):
            raise ProviderError("semantic_timeout")
    c = BreakCandidate(id="c1", timestamp_sec=60, preceding_scene_id="s1", following_scene_id="s2",
        speech_active=False, silence_before_sec=2, silence_after_sec=2, raw_boundary_score=0.9,
        prefilter_status="SURVIVED")
    decision = analyze_candidate(c, [], [], [], FailingSemantic(), Settings(_env_file=None))
    assert not decision.accepted and "semantic_timeout" in decision.rejection_reasons


def test_low_semantic_confidence_rejects_candidate():
    from interlude.domain import SceneSemantics
    class Uncertain:
        def analyze(self, *args):
            return SceneSemantics(dominant_activity="cooking", contexts=["cooking"], sensitive_contexts=[],
                mood=[], narrative_state_before="meal", narrative_state_after="meal ends",
                semantic_transition_score=1, confidence=0.2)
    c = BreakCandidate(id="c1", timestamp_sec=60, preceding_scene_id="s1", following_scene_id="s2",
        speech_active=False, silence_before_sec=2, silence_after_sec=2, raw_boundary_score=1,
        prefilter_status="SURVIVED")
    decision = analyze_candidate(c, [], [], [], Uncertain(), Settings(_env_file=None))
    assert "semantic_low_confidence" in decision.rejection_reasons
