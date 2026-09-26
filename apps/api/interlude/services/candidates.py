from interlude.config import Settings
from interlude.domain import BreakCandidate, Interval, Scene, Transcript


class SpeechTimeline:
    def __init__(self, intervals: list[Interval], duration: float):
        self.intervals = intervals
        self.duration = duration

    def is_speech_active(self, timestamp: float) -> bool:
        return any(s.start_sec <= timestamp <= s.end_sec for s in self.intervals)

    def nearest_speech_start(self, timestamp: float) -> float | None:
        return min((s.start_sec for s in self.intervals if s.start_sec >= timestamp), default=None)

    def nearest_speech_end(self, timestamp: float) -> float | None:
        return max((s.end_sec for s in self.intervals if s.end_sec <= timestamp), default=None)

    def silence_before(self, timestamp: float) -> float:
        if self.is_speech_active(timestamp):
            return 0
        end = self.nearest_speech_end(timestamp)
        return timestamp - (end if end is not None else 0)

    def silence_after(self, timestamp: float) -> float:
        if self.is_speech_active(timestamp):
            return 0
        start = self.nearest_speech_start(timestamp)
        return (start if start is not None else self.duration) - timestamp


class CandidateService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, scenes: list[Scene], transcript: Transcript, vad: list[Interval],
                 duration: float) -> list[BreakCandidate]:
        asr = SpeechTimeline(transcript.speech_words, duration)
        voice = SpeechTimeline(vad, duration)
        combined = SpeechTimeline([*transcript.speech_words, *vad], duration)
        candidates = []
        for before, after in zip(scenes, scenes[1:]):
            t = after.start_sec
            reasons = []
            if asr.is_speech_active(t):
                reasons.append("asr_active_dialogue")
            if voice.is_speech_active(t):
                reasons.append("vad_active_speech")
            candidates.append(BreakCandidate(id=f"candidate_{len(candidates)+1:03d}", timestamp_sec=t,
                preceding_scene_id=before.id, following_scene_id=after.id,
                speech_active=asr.is_speech_active(t) or voice.is_speech_active(t),
                nearest_speech_start_sec=combined.nearest_speech_start(t),
                nearest_speech_end_sec=combined.nearest_speech_end(t),
                silence_before_sec=combined.silence_before(t), silence_after_sec=combined.silence_after(t),
                surrounding_shot_sec=min(before.duration_sec, after.duration_sec),
                raw_boundary_score=after.boundary_score, prefilter_status="REJECTED" if reasons else "SURVIVED",
                rejection_reasons=reasons))
        return candidates
