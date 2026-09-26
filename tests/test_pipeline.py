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


def test_real_mp4_pipeline_emits_playable_manifest(tmp_path):
    """Real FFmpeg, PySceneDetect and CPU VAD; only remote inference is isolated."""
    import json
    import subprocess
    from interlude.domain import SceneSemantics, Transcript
    from interlude.pipeline import AnalysisPipeline
    from interlude.services.manifest import ManifestService

    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=25:d=15",
                    "-f", "lavfi", "-i", "color=blue:s=320x180:r=25:d=15", "-f", "lavfi", "-i",
                    "anullsrc=r=16000:cl=mono", "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-map", "2:a", "-t", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(source)], check=True, capture_output=True)
    catalog = tmp_path / "brands.json"
    catalog.write_text(json.dumps([{"brand_id": "test_ninth", "display_name": "Test Ninth", "category": "food",
        "target_contexts": ["cooking"], "negative_contexts": ["funeral"]}]))

    class SilentAsr:
        def transcribe(self, audio):
            assert audio.is_file() and audio.stat().st_size > 100
            return Transcript()

    class Perception:
        def analyze(self, frames, transcript, vocabulary, boundary):
            assert len(frames) == 11 and frames[0].timestamp_sec == 10
            assert boundary == 15 and "funeral" in vocabulary
            return SceneSemantics(dominant_activity="cooking", contexts=["cooking"], sensitive_contexts=[], mood=[],
                narrative_state_before="cooking", narrative_state_after="meal finished",
                semantic_transition_score=0.9, confidence=0.95)

    settings = Settings(_env_file=None, data_dir=tmp_path / "data", brands_path=catalog, max_ad_load_percent=25)
    stages = []
    result = AnalysisPipeline(settings, SilentAsr(), Perception()).run("test", source, stages.append)
    manifest = ManifestService().build(result)
    assert manifest.summary["scene_count"] == 2
    assert manifest.summary["accepted_break_count"] == 1
    assert manifest.ad_breaks[0].brand_id == "test_ninth"
    assert manifest.ad_breaks[0].latest_start_sec == 15.25
    assert stages[0] == JobStatus.INGESTING and stages[-1] == JobStatus.BRAND_MATCHING
    assert list((settings.data_dir / "work").iterdir()) == []
