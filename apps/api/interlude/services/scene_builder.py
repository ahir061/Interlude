from interlude.config import Settings
from interlude.domain import Interval, Phase2Semantics, Scene, Transcript
from interlude.services.candidates import SpeechTimeline


class DialogueSafetyGate:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, timestamp: float, transcript: Transcript, vad: list[Interval], duration: float,
                 semantics: Phase2Semantics | None = None) -> dict:
        asr, voice = SpeechTimeline(transcript.speech_words, duration), SpeechTimeline(vad, duration)
        both = SpeechTimeline([*transcript.speech_words, *vad], duration)
        crossing_asr, crossing_vad = asr.is_speech_active(timestamp), voice.is_speech_active(timestamp)
        pre, post = both.silence_before(timestamp), both.silence_after(timestamp)
        reasons = []
        if crossing_asr or crossing_vad:
            reasons.append("unsafe_dialogue")
        return {"safe": not reasons, "reasons": reasons, "speech_active_at_cut": crossing_asr or crossing_vad,
                "last_speech_end_before_cut": both.nearest_speech_end(timestamp),
                "first_speech_start_after_cut": both.nearest_speech_start(timestamp),
                "silence_before_cut": pre, "silence_after_cut": post,
                "asr_word_crossing_boundary": crossing_asr,
                "asr_segment_crossing_boundary": SpeechTimeline(transcript.segments, duration).is_speech_active(timestamp),
                "vad_region_crossing_boundary": crossing_vad,
                "semantic_dialogue_continuity": semantics.dialogue_continuity if semantics else "not_analyzed"}


def scene_grouping_reasons(semantics: Phase2Semantics, settings: Settings) -> list[str]:
    reasons = []
    if semantics.confidence < settings.min_semantic_confidence or semantics.transition_confidence < settings.min_transition_confidence:
        reasons.append("semantic_uncertainty")
    if semantics.transition_type in ("camera_angle", "montage", "none", "uncertain"):
        reasons.append("not_semantic_scene_boundary")
    if semantics.semantic_transition_score < settings.min_transition_score:
        reasons.append("weak_transition")
    return reasons


class SemanticSceneBuilder:
    """Only positive transition evidence splits shots; uncertain boundaries are merged."""
    def __init__(self, settings: Settings):
        self.settings = settings

    def group(self, shots: list[Scene], boundaries: dict[float, Phase2Semantics]) -> list[Scene]:
        scenes = []
        for shot in shots:
            semantics = boundaries.get(shot.start_sec)
            split = semantics is not None and not scene_grouping_reasons(semantics, self.settings)
            if not scenes or split:
                scenes.append(Scene(id=f"scene_{len(scenes)+1:03d}", start_sec=shot.start_sec, end_sec=shot.end_sec,
                    boundary_score=shot.boundary_score, shot_ids=[shot.id],
                    grouping_reasons=["confirmed_semantic_transition" if split else "initial_scene"]))
            else:
                scenes[-1].end_sec = shot.end_sec
                scenes[-1].shot_ids.append(shot.id)
                scenes[-1].grouping_reasons.append("dialogue_or_visual_continuity" if semantics else "unconfirmed_transition")
        return scenes
