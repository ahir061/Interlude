from dataclasses import dataclass

from interlude.config import Settings
from interlude.domain import BreakDecision, Creative
from interlude.services.policy import PacingService


@dataclass(frozen=True)
class PlacementOption:
    candidate_id: str
    timestamp_sec: float
    brand_id: str
    brand_score: float
    where_score: float
    creative: Creative

    @property
    def quality(self):
        return self.where_score * (0.8 + 0.2 * self.brand_score)


class GlobalBreakOptimizer:
    """Chronological beam search over complete feasible schedules, deterministic ties.

    Exact while the frontier fits beam_width; bounded approximation beyond that size.
    Every returned schedule satisfies all constraints regardless of beam truncation.
    """
    def __init__(self, settings: Settings):
        self.settings = settings

    def optimize(self, options: list[PlacementOption], duration: float) -> tuple[list[PlacementOption], dict]:
        groups = {}
        for option in options:
            if 0 < option.timestamp_sec < duration and option.creative.duration_sec > 0:
                groups.setdefault((option.timestamp_sec, option.candidate_id), []).append(option)
        states = [(0.0, 0.0, ())]
        truncated = False
        for _, alternatives in sorted(groups.items()):
            expanded = list(states)
            for quality, ad_seconds, chosen in states:
                for option in sorted(alternatives, key=lambda o: (o.creative.duration_sec, -o.quality, o.brand_id, o.creative.creative_id)):
                    if chosen and option.timestamp_sec-chosen[-1].timestamp_sec < self.settings.min_break_gap_sec:
                        continue
                    if sum(option.timestamp_sec-o.timestamp_sec < 3600 for o in chosen) >= self.settings.max_breaks_per_hour:
                        continue
                    load = ad_seconds + option.creative.duration_sec
                    if load*100 > duration*self.settings.max_ad_load_percent + 1e-9:
                        continue
                    expanded.append((quality+option.quality, load, (*chosen, option)))
            expanded.sort(key=lambda state: (-state[0], state[1], tuple((o.timestamp_sec, o.brand_id, o.creative.creative_id) for o in state[2])))
            # Dominated identical timing states need only the best score / smallest load.
            unique = {}
            for state in expanded:
                key = (round(state[1], 6), tuple(o.timestamp_sec for o in state[2]))
                unique.setdefault(key, state)
            frontier = list(unique.values())
            truncated |= len(frontier) > self.settings.optimizer_beam_width
            states = frontier[:self.settings.optimizer_beam_width]
        best = states[0]
        return list(best[2]), {"algorithm": "deterministic_beam_search", "beam_width": self.settings.optimizer_beam_width,
            "frontier_truncated": truncated, "total_quality": best[0], "ad_seconds": best[1],
            "ad_load_percent": best[1]*100/duration, "eligible_candidate_count": len(groups)}

    def finalize(self, decisions: list[BreakDecision], options: list[PlacementOption], duration: float) -> dict:
        selected, metadata = self.optimize(options, duration)
        by_id = {o.candidate_id: o for o in selected}
        accepted = []
        for decision in decisions:
            option = by_id.get(decision.candidate_id)
            if option is None:
                continue
            decision.selected_brand_id = option.brand_id
            decision.selected_creative_id = option.creative.creative_id
            decision.creative_url = option.creative.url
            decision.creative_duration_sec = option.creative.duration_sec
            decision.debug["creative_dimensions"] = {"width": option.creative.width, "height": option.creative.height}
            decision.brand_match_score = option.brand_score
            decision.whether_pass = True
            decision.rejection_reasons = []
            decision.accepted = True
            accepted.append(decision)
        pacing = PacingService(self.settings)
        for decision in decisions:
            available = [o for o in options if o.candidate_id == decision.candidate_id]
            if decision.accepted:
                others = [d for d in accepted if d is not decision]
                decision.debug["whether"] = pacing.evaluate(decision.timestamp_sec, decision.creative_duration_sec, others, duration)
                decision.debug["whether"]["selection_reason"] = "global_schedule_quality"
            elif available:
                option = min(available, key=lambda o: o.creative.duration_sec)
                constraint = pacing.evaluate(decision.timestamp_sec, option.creative.duration_sec, accepted, duration)
                decision.debug["whether"] = constraint
                decision.rejection_reasons.extend(constraint["reasons"] or ["global_quality_tradeoff"])
                decision.debug["outcome"] = "NO_AD"
        return metadata
