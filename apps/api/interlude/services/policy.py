from interlude.config import Settings
from interlude.domain import BreakCandidate, BreakDecision, SceneSemantics, Phase2Semantics


class WhereService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def score(self, candidate: BreakCandidate, semantics: SceneSemantics) -> dict:
        safe = not candidate.speech_active and candidate.prefilter_status == "SURVIVED"
        # A short clear gap is useful; it is never a separate eligibility threshold.
        gap = candidate.silence_before_sec + candidate.silence_after_sec
        anchors = [(0, 0), (0.2, 0.35), (0.5, 0.65), (1, 1)]
        gap_score = 1.0
        for (left, low), (right, high) in zip(anchors, anchors[1:]):
            if gap <= right:
                gap_score = low + (high-low) * max(0, gap-left)/(right-left)
                break
        transition = semantics.semantic_transition_score
        closure = transition
        confidence = semantics.confidence
        confirmed_boundary = False
        if isinstance(semantics, Phase2Semantics):
            from interlude.services.scene_builder import scene_grouping_reasons
            confirmed_boundary = not scene_grouping_reasons(semantics, self.settings)
            transition = min(1, transition + (0.2 if confirmed_boundary else 0))
            closure = {"scene_concluding": 1.0, "ongoing": 0.5, "uncertain": 0.35}[semantics.narrative_state]
            if semantics.dialogue_continuity in ("completed", "no_dialogue"):
                closure = max(closure, 0.65)
            elif semantics.dialogue_continuity == "continuing":
                closure *= 0.3
            confidence = (confidence + semantics.transition_confidence)/2
        components = {"visual": candidate.raw_boundary_score,
            "dialogue_gap": gap_score if not candidate.speech_active else 0,
            "semantic_transition": transition, "narrative_closure": closure,
            "shot_stability": min(candidate.surrounding_shot_sec / 4, 1), "confidence": confidence}
        weights = self.settings.weights
        normalized = {k: v / sum(weights.values()) for k, v in weights.items()}
        score = sum(components[k] * normalized[k] for k in components) if safe else 0
        return {"score": score, "components": components, "weights": normalized, "dialogue_safe": safe,
                "confirmed_semantic_boundary": confirmed_boundary, "nearby_gap_sec": gap,
                "quality_floor": self.settings.min_where_score,
                "survival_reasons": ["no_exact_speech_crossing", "quality_signals_combined"] if safe else []}



class PacingService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, timestamp: float, ad_duration: float, accepted: list[BreakDecision],
                 duration: float) -> dict:
        reasons = []
        accepted = [d for d in accepted if d.accepted]
        if any(abs(d.timestamp_sec - timestamp) < self.settings.min_break_gap_sec for d in accepted):
            reasons.append("minimum_break_gap")
        # Any rolling 3600-second window containing the new point must satisfy the cap.
        times = sorted([timestamp, *(d.timestamp_sec for d in accepted)])
        peak = max(sum(t <= other < t + 3600 for other in times) for t in times)
        if peak > self.settings.max_breaks_per_hour:
            reasons.append("maximum_breaks_per_hour")
        projected = 100 * (ad_duration + sum(d.creative_duration_sec for d in accepted)) / duration
        if projected > self.settings.max_ad_load_percent + 1e-9:
            reasons.append("maximum_ad_load")
        return {"pass": not reasons, "reasons": reasons, "projected_ad_load_percent": projected,
                "ad_duration_sec": ad_duration, "limits": {
                    "min_break_gap_sec": self.settings.min_break_gap_sec,
                    "max_breaks_per_hour": self.settings.max_breaks_per_hour,
                    "max_ad_load_percent": self.settings.max_ad_load_percent}}
