from interlude.config import Settings
from interlude.domain import BreakCandidate, BreakDecision, SceneSemantics


class WhereService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def score(self, candidate: BreakCandidate, semantics: SceneSemantics) -> dict:
        safe = not candidate.speech_active and candidate.prefilter_status == "SURVIVED"
        components = {"boundary": candidate.raw_boundary_score, "dialogue": float(safe),
            "silence": min(min(candidate.silence_before_sec, candidate.silence_after_sec) / 2, 1),
            "semantic": semantics.semantic_transition_score}
        weights = self.settings.weights
        normalized = {k: v / sum(weights.values()) for k, v in weights.items()}
        score = sum(components[k] * normalized[k] for k in components) if safe else 0
        return {"score": score, "components": components, "weights": normalized, "dialogue_safe": safe}


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
