from interlude.config import Settings
from interlude.domain import Brand, BrandEvaluation, ContextSnapshot, Phase2Semantics
from interlude.services.brands import contains, negative_match, normalize


class BrandEligibilityEngine:
    def evaluate(self, semantics: Phase2Semantics, snapshot: ContextSnapshot, brands: list[Brand]) -> list[BrandEvaluation]:
        observed = [semantics.dominant_activity, *semantics.contexts, *semantics.mood,
                    semantics.narrative_state_before, semantics.narrative_state_after,
                    *snapshot.current_sensitive_contexts, *(c.context for c in snapshot.recent_sensitive_contexts)]
        vocabulary = {normalize(c) for b in brands for c in b.negative_contexts}
        unknown = [c for c in [*snapshot.current_sensitive_contexts, *(r.context for r in snapshot.recent_sensitive_contexts)]
                   if not any(negative_match(c, n) for n in vocabulary)]
        results = []
        for brand in brands:
            blocks = [n for n in brand.negative_contexts if any(negative_match(o, n) for o in observed)]
            blocks += [f"unmapped_sensitive_context:{c}" for c in unknown]
            if snapshot.uncertain:
                blocks.append("context_memory_uncertain")
            results.append(BrandEvaluation(brand_id=brand.brand_id, eligible=not blocks, hard_blocks=blocks))
        return results


class BrandRankingEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def rank(self, semantics: Phase2Semantics, brands: list[Brand], eligibility: list[BrandEvaluation]) -> list[BrandEvaluation]:
        s = self.settings
        weights = {"dominant_activity": s.brand_activity_weight, "target_overlap": s.brand_target_weight,
                   "category_relevance": s.brand_category_weight, "secondary_relevance": s.brand_secondary_weight}
        by_id = {b.brand_id: b for b in brands}
        results = []
        for entry in eligibility:
            entry = entry.model_copy(deep=True)
            if entry.eligible:
                brand = by_id[entry.brand_id]
                activity = float(any(contains(semantics.dominant_activity, t) for t in brand.target_contexts))
                overlap = sum(any(contains(c, t) for c in semantics.contexts) for t in brand.target_contexts)
                components = {"dominant_activity": activity, "target_overlap": min(overlap/3, 1),
                    "category_relevance": float(any(contains(semantics.dominant_activity, c) for c in brand.category.split("/"))),
                    "secondary_relevance": float(overlap > 0)}
                entry.components = components
                relevance = sum(components[k]*weights[k] for k in components)/sum(weights.values())
                # Perception confidence changes ranking strength, never eligibility.
                confidence_factor = 0.5 + 0.5 * semantics.confidence
                entry.score = relevance * confidence_factor
                entry.components["confidence_factor"] = confidence_factor
            results.append(entry)
        return sorted(results, key=lambda m: (-(m.score if m.score is not None else -1), m.brand_id))
