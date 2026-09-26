from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from interlude.config import Settings
from interlude.domain import (AnalysisResult, Brand, BreakCandidate, BreakDecision, Frame, JobStatus,
                              TranscriptSegment)
from interlude.providers.asr import AsrProvider, GroqWhisperProvider
from interlude.providers.base import ProviderError
from interlude.providers.semantic import QwenSemanticProvider, SemanticVideoProvider
from interlude.services.brands import BrandMatchingService, load_brands, vocabulary
from interlude.services.candidates import CandidateService
from interlude.services.creatives import CreativeService
from interlude.services.media import (MediaError, MediaProbeService, SceneDetectionService,
                                      extract_audio, extract_window)
from interlude.services.policy import PacingService, WhereService
from interlude.services.speech import VadService

STAGES = list(JobStatus)


def transition_allowed(before: JobStatus, after: JobStatus) -> bool:
    if before in (JobStatus.COMPLETED, JobStatus.FAILED):
        return False
    return before == after or after == JobStatus.FAILED or STAGES.index(after) == STAGES.index(before) + 1


def analyze_candidate(candidate: BreakCandidate, frames: list[Frame], transcript: list[TranscriptSegment],
                      brands: list[Brand], provider: SemanticVideoProvider, settings: Settings) -> BreakDecision:
    decision = BreakDecision(candidate_id=candidate.id, timestamp_sec=candidate.timestamp_sec,
                             rejection_reasons=list(candidate.rejection_reasons))
    if candidate.prefilter_status == "REJECTED":
        return decision
    decision.debug["playback"] = {"latest_start_sec": candidate.timestamp_sec + min(0.25, candidate.silence_after_sec / 2)}
    try:
        decision.semantics = provider.analyze(frames, transcript, vocabulary(brands), candidate.timestamp_sec)
    except ProviderError as exc:
        decision.rejection_reasons.append(exc.code)
        return decision
    if decision.semantics.confidence < settings.min_semantic_confidence:
        decision.rejection_reasons.append("semantic_low_confidence")
    where = WhereService(settings).score(candidate, decision.semantics)
    decision.where_score = where["score"]
    decision.debug["where"] = where
    if decision.where_score < settings.min_where_score:
        decision.rejection_reasons.append("where_below_threshold")
    return decision


class AnalysisPipeline:
    def __init__(self, settings: Settings, asr: AsrProvider | None = None,
                 semantic: SemanticVideoProvider | None = None):
        self.settings = settings
        self.asr = asr or GroqWhisperProvider(settings)
        self.semantic = semantic or QwenSemanticProvider(settings)

    def run(self, video_id: str, source: Path, progress: Callable[[JobStatus], None],
            checkpoint: Callable[[str, list], None] = lambda kind, items: None) -> AnalysisResult:
        settings = self.settings
        settings.prepare_dirs()
        progress(JobStatus.INGESTING)
        metadata = MediaProbeService(settings).probe(source, video_id)
        if metadata.duration_sec > settings.max_video_duration_sec:
            raise MediaError("video_exceeds_phase1_duration_limit")
        if not metadata.has_audio:
            raise MediaError("missing_audio_cannot_verify_dialogue")
        brands = CreativeService(settings).ensure(load_brands(settings.brands_path))
        checkpoint("brands", brands)
        with TemporaryDirectory(prefix=f"{video_id}-", dir=settings.data_dir / "work") as directory:
            work = Path(directory)
            progress(JobStatus.SCENE_DETECTION)
            scenes = SceneDetectionService(settings).detect(source)
            checkpoint("scenes", scenes)
            progress(JobStatus.TRANSCRIBING)
            audio = work / "speech.wav"
            extract_audio(settings, source, audio)
            transcript = self.asr.transcribe(audio)
            if any(s.end_sec > metadata.duration_sec + 0.5 for s in transcript.segments):
                raise ProviderError("asr_timestamp_outside_video")
            vad = VadService().detect(audio)
            checkpoint("transcript", transcript.segments)
            progress(JobStatus.CANDIDATE_GENERATION)
            candidates = CandidateService(settings).generate(scenes, transcript, vad, metadata.duration_sec)
            checkpoint("candidates", candidates)
            progress(JobStatus.SEMANTIC_ANALYSIS)
            decisions = []
            for candidate in candidates:
                progress(JobStatus.SEMANTIC_ANALYSIS)
                frames = []
                try:
                    if candidate.prefilter_status == "SURVIVED":
                        frames = extract_window(settings, source, candidate.timestamp_sec, metadata.duration_sec,
                                                work / candidate.id)
                    decision = analyze_candidate(candidate, frames, transcript.around(candidate.timestamp_sec-5,
                        candidate.timestamp_sec+5), brands, self.semantic, settings)
                    decision.debug["frame_timestamps_sec"] = [f.timestamp_sec for f in frames]
                    decision.debug["transient_frames_cleaned"] = True
                except MediaError:
                    decision = BreakDecision(candidate_id=candidate.id, timestamp_sec=candidate.timestamp_sec,
                                             rejection_reasons=["semantic_frame_window_failed"])
                decisions.append(decision)
                checkpoint("decisions", decisions)
            progress(JobStatus.BREAK_OPTIMIZATION)
            decisions.sort(key=lambda d: (-d.where_score, d.timestamp_sec))
            progress(JobStatus.BRAND_MATCHING)
            accepted = []
            matcher, pacing = BrandMatchingService(), PacingService(settings)
            for decision in decisions:
                if decision.semantics is not None:
                    decision.brand_matches = matcher.evaluate(decision.semantics, brands)
                if decision.rejection_reasons:
                    continue
                match = matcher.select(decision.brand_matches, settings.min_brand_score)
                if match is None:
                    decision.rejection_reasons.append("no_safely_relevant_brand")
                    continue
                brand = next(b for b in brands if b.brand_id == match.brand_id)
                creative = min(brand.creatives, key=lambda c: (c.duration_sec, c.creative_id))
                decision.debug["whether"] = pacing.evaluate(decision.timestamp_sec, creative.duration_sec,
                                                            accepted, metadata.duration_sec)
                if not decision.debug["whether"]["pass"]:
                    decision.rejection_reasons.extend(decision.debug["whether"]["reasons"])
                    continue
                decision.whether_pass = True
                decision.selected_brand_id = brand.brand_id
                decision.selected_creative_id = creative.creative_id
                decision.creative_url = creative.url
                decision.creative_duration_sec = creative.duration_sec
                decision.brand_match_score = match.final_score
                decision.debug["creative_generated"] = creative.generated
                decision.accepted = True
                accepted.append(decision)
            decisions.sort(key=lambda d: d.timestamp_sec)
            checkpoint("decisions", decisions)
            return AnalysisResult(video=metadata, scenes=scenes, transcript=transcript, vad_intervals=vad,
                                  candidates=candidates, decisions=decisions)
