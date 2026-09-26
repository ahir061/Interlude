import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from interlude.config import Settings
from interlude.domain import AnalysisResult, BreakDecision, JobStatus, Phase2Semantics
from interlude.providers.asr import GroqWhisperProvider
from interlude.providers.base import ProviderError
from interlude.providers.perception import PerceptionClient, PROMPT_VERSION, digest, file_digest
from interlude.services.brand_policy import BrandEligibilityEngine, BrandRankingEngine
from interlude.services.brands import load_brands, vocabulary
from interlude.services.candidates import CandidateService
from interlude.services.context import ContextMemory
from interlude.services.creatives import CreativeService
from interlude.services.media import (MediaError, MediaProbeService, SceneDetectionService,
                                      extract_audio, extract_window, run_media)
from interlude.services.optimizer import GlobalBreakOptimizer, PlacementOption
from interlude.services.policy import WhereService
from interlude.services.scene_builder import DialogueSafetyGate, SemanticSceneBuilder, semantic_hard_gates
from interlude.services.speech import VadService

PIPELINE_VERSION = "2.0.0"
POLICY_VERSION = "precision-2.1"
logger = logging.getLogger("interlude.pipeline")


@contextmanager
def measure(timings: dict, name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[name] = timings.get(name, 0) + time.perf_counter()-start


class Phase2Pipeline:
    def __init__(self, settings: Settings, asr=None, perception=None):
        self.settings = settings
        self.asr = asr or GroqWhisperProvider(settings)
        self.perception_override = perception

    def run(self, video_id, source: Path, progress, checkpoint=lambda kind, items: None, job_id=None):
        s = self.settings
        started = time.perf_counter()
        timings = {}
        correlation = job_id or video_id
        s.prepare_dirs()
        perception = self.perception_override or PerceptionClient(s)
        progress(JobStatus.INGESTING)
        with measure(timings, "media_probe"):
            metadata = MediaProbeService(s).probe(source, video_id)
            if metadata.duration_sec > s.max_video_duration_sec:
                raise MediaError("video_exceeds_configured_duration_limit")
            if not metadata.has_audio:
                raise MediaError("missing_audio_cannot_verify_dialogue")
            video_hash = file_digest(source)
            brands = load_brands(s.brands_path)
            catalogue_hash = digest([b.model_dump(mode="json") for b in brands])
            brands = CreativeService(s).ensure(brands)
            checkpoint("brands", brands)
        observations, decisions, semantics_by_time = [], [], {}
        memory = ContextMemory(s, [n for b in brands for n in b.negative_contexts])
        options = []
        with TemporaryDirectory(prefix=f"{video_id}-", dir=s.data_dir/"work") as directory:
            work = Path(directory)
            progress(JobStatus.SCENE_DETECTION)
            with measure(timings, "shot_detection"):
                shots = SceneDetectionService(s).detect(source)
                for i, shot in enumerate(shots):
                    shot.id = f"shot_{i+1:04d}"
                checkpoint("shots", shots)
            progress(JobStatus.TRANSCRIBING)
            audio = work/"speech.wav"
            with measure(timings, "audio_extraction"):
                extract_audio(s, source, audio)
            with measure(timings, "asr"):
                transcript = self.asr.transcribe(audio)
                if any(t.end_sec > metadata.duration_sec+0.5 for t in transcript.segments):
                    raise ProviderError("asr_timestamp_outside_video")
                checkpoint("transcript", transcript.segments)
            with measure(timings, "vad"):
                vad = VadService().detect(audio)
            progress(JobStatus.CANDIDATE_GENERATION)
            with measure(timings, "candidate_filtering"):
                candidates = CandidateService(s).generate(shots, transcript, vad, metadata.duration_sec)
                for candidate in candidates:
                    candidate.dialogue_safety = DialogueSafetyGate(s).evaluate(candidate.timestamp_sec, transcript, vad, metadata.duration_sec)
                    candidate.rejection_reasons = list(dict.fromkeys(candidate.rejection_reasons + candidate.dialogue_safety["reasons"]))
                    if candidate.rejection_reasons:
                        candidate.prefilter_status = "REJECTED"
                    decisions.append(BreakDecision(candidate_id=candidate.id, timestamp_sec=candidate.timestamp_sec,
                        rejection_reasons=list(candidate.rejection_reasons), debug={"dialogue_safety": candidate.dialogue_safety,
                            "outcome": "NO_AD", "scene": {"before": candidate.preceding_scene_id, "after": candidate.following_scene_id}}))
                checkpoint("candidates", candidates)
            survivors = {c.timestamp_sec: c for c in candidates if c.prefilter_status == "SURVIVED"}
            decision_map = {d.candidate_id: d for d in decisions}
            # Monitoring includes regions with unsafe/no cuts: sensitive memory cannot depend on ad candidacy.
            events = set(survivors)
            t = min(5.0, metadata.duration_sec/2)
            while t < metadata.duration_sec:
                events.add(round(t, 3))
                t += s.context_sample_interval_sec
            progress(JobStatus.SEMANTIC_ANALYSIS)
            for index, timestamp in enumerate(sorted(events)):
                progress(JobStatus.SEMANTIC_ANALYSIS)
                candidate = survivors.get(timestamp)
                nearby = transcript.around(timestamp-5, timestamp+5)
                frames = []
                semantic = None
                try:
                    with measure(timings, "qwen_semantic_analysis"):
                        frames = extract_window(s, source, timestamp, metadata.duration_sec, work/f"window_{index}")
                        semantic = perception.perceive(frames, nearby, vocabulary(brands), timestamp,
                            video_hash, catalogue_hash, "boundary" if candidate else "context_monitor")
                        if not isinstance(semantic, Phase2Semantics):
                            raise ProviderError("semantic_invalid_contract")
                    memory.observe(timestamp, semantic if semantic.confidence >= s.min_semantic_confidence else None)
                    observations.append({"timestamp_sec": timestamp, "purpose": "boundary" if candidate else "context_monitor",
                                         "semantics": semantic.model_dump(), "error_code": None})
                except (ProviderError, MediaError) as exc:
                    memory.observe(timestamp, None)
                    code = exc.code if isinstance(exc, ProviderError) else "semantic_frame_window_failed"
                    observations.append({"timestamp_sec": timestamp, "semantics": None, "error_code": code})
                    if candidate:
                        decision_map[candidate.id].rejection_reasons.extend(["model_failure", code])
                checkpoint("observations", observations)
                if not candidate or semantic is None:
                    continue
                decision = decision_map[candidate.id]
                decision.semantics = semantic
                gate = DialogueSafetyGate(s).evaluate(timestamp, transcript, vad, metadata.duration_sec, semantic)
                candidate.dialogue_safety = gate
                decision.debug["dialogue_safety"] = gate
                decision.debug["frame_timestamps_sec"] = [f.timestamp_sec for f in frames]
                snapshot = memory.snapshot(timestamp, semantic)
                decision.debug["context_memory"] = snapshot.model_dump()
                decision.rejection_reasons = list(dict.fromkeys(gate["reasons"] + semantic_hard_gates(semantic, s)))
                if not decision.rejection_reasons:
                    semantics_by_time[timestamp] = semantic
                if decision.rejection_reasons:
                    continue
                with measure(timings, "where_scoring"):
                    where = WhereService(s).score(candidate, semantic)
                    decision.where_score = where["score"]
                    where.update(narrative_closure=semantic.narrative_state, dialogue_continuity=semantic.dialogue_continuity,
                                 hard_gates_passed=True)
                    decision.debug["where"] = where
                    if decision.where_score < s.min_where_score:
                        decision.rejection_reasons.append("weak_transition")
                        continue
                decision.debug["playback"] = {"latest_start_sec": timestamp + min(0.25, candidate.silence_after_sec/2)}
                with measure(timings, "brand_matching"):
                    eligible = BrandEligibilityEngine().evaluate(semantic, snapshot, brands)
                    ranked = BrandRankingEngine(s).rank(semantic, brands, eligible)
                    decision.debug["brands"] = [r.model_dump() for r in ranked]
                    for r in ranked:
                        if not r.eligible:
                            logger.info(json.dumps({"event": "brand_hard_blocked", "job_id": correlation,
                                "brand_id": r.brand_id, "timestamp_sec": timestamp, "contexts": r.hard_blocks}))
                verifications = []
                with measure(timings, "brand_safety_verification"):
                    for match in ranked:
                        if not match.eligible or match.score is None or match.score < s.min_brand_score:
                            continue
                        brand = next(b for b in brands if b.brand_id == match.brand_id)
                        try:
                            verdict = perception.verify(frames, nearby, semantic, snapshot, brand, timestamp, video_hash, catalogue_hash)
                            verifications.append({"brand_id": brand.brand_id, **verdict.model_dump()})
                            if verdict.verdict != "SAFE" or verdict.confidence < s.safety_min_confidence:
                                continue
                        except ProviderError as exc:
                            verifications.append({"brand_id": brand.brand_id, "verdict": "UNCERTAIN", "error_code": exc.code})
                            continue
                        # Enumerate all durations for the globally selected slot, not the first catalogue creative.
                        for creative in brand.creatives:
                            options.append(PlacementOption(candidate.id, timestamp, brand.brand_id, match.score,
                                                           decision.where_score, creative))
                        break
                decision.debug["brand_safety_verification"] = verifications
                if not any(o.candidate_id == candidate.id for o in options):
                    decision.rejection_reasons.append("no_safe_brand")
                checkpoint("decisions", decisions)
            with measure(timings, "semantic_scene_grouping"):
                scenes = SemanticSceneBuilder(s).group(shots, semantics_by_time)
                for candidate in candidates:
                    before = next(scene for scene in scenes if scene.start_sec < candidate.timestamp_sec <= scene.end_sec)
                    after = next(scene for scene in scenes if scene.start_sec <= candidate.timestamp_sec < scene.end_sec)
                    candidate.preceding_scene_id, candidate.following_scene_id = before.id, after.id
                    decision_map[candidate.id].debug["scene"] = {"before": before.id, "after": after.id}
                checkpoint("scenes", scenes)
                checkpoint("candidates", candidates)
            progress(JobStatus.BREAK_OPTIMIZATION)
            with measure(timings, "global_optimization"):
                optimization = GlobalBreakOptimizer(s).finalize(decisions, options, metadata.duration_sec)
            progress(JobStatus.BRAND_MATCHING)
            for decision in decisions:
                decision.debug["outcome"] = "AD" if decision.accepted else "NO_AD"
                if not decision.accepted:
                    logger.info(json.dumps({"event": "candidate_rejected", "job_id": correlation,
                        "timestamp_sec": decision.timestamp_sec, "reasons": decision.rejection_reasons}))
            checkpoint("decisions", decisions)
            with measure(timings, "inspection_clips"):
                for decision in decisions:
                    if decision.accepted:
                        review = s.reports_dir/"inspection"/video_id/f"{decision.candidate_id}.mp4"
                        review.parent.mkdir(parents=True, exist_ok=True)
                        start = max(0, decision.timestamp_sec-10)
                        run_media([s.ffmpeg_bin, "-v", "error", "-y", "-ss", str(start), "-i", str(source),
                            "-t", str(min(20, metadata.duration_sec-start)), "-c:v", "libx264", "-preset", "veryfast",
                            "-c:a", "aac", "-movflags", "+faststart", str(review)])
                        decision.debug["inspection_clip"] = str(review)
                        decision.debug["inspection_boundary_offset_sec"] = decision.timestamp_sec-start
        timings["total_pipeline"] = time.perf_counter()-started
        return AnalysisResult(video=metadata, raw_shots=shots, scenes=scenes, transcript=transcript, vad_intervals=vad,
            candidates=candidates, decisions=decisions, run_metadata={"pipeline_version": PIPELINE_VERSION,
                "policy_version": POLICY_VERSION, "prompt_version": PROMPT_VERSION, "catalogue_hash": catalogue_hash,
                "video_hash": video_hash, "processing_timings_sec": timings, "optimizer": optimization,
                "semantic_observations": observations, "provider_requests": perception.events, **perception.metrics})
