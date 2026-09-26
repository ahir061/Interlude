import json
import re
import unicodedata
from pathlib import Path

from pydantic import TypeAdapter
from interlude.domain import Brand, BrandMatch, SceneSemantics


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", value).casefold()).split())


def contains(text: str, concept: str) -> bool:
    return bool(normalize(concept)) and f" {normalize(concept)} " in f" {normalize(text)} "


# Semantic aliases, never brand-specific rules. New catalog labels still use generic phrase/plural matching.
SENSITIVE_ALIASES = {
    "grief": ("mourning", "bereavement", "bereaved", "grieving"),
    "funeral": ("burial", "cremation", "last rites"),
    "violence": ("violent", "assault", "fighting", "murder", "stabbing", "shooting"),
    "illness": ("sick", "disease", "unwell"),
    "hospital": ("hospitalized", "hospitalised", "medical ward"),
    "accident": ("crash", "collision"),
    "injury": ("injured", "wounded", "bleeding"),
    "financial distress": ("bankruptcy", "bankrupt", "debt crisis"),
    "medical emergency": ("unconscious", "unresponsive", "resuscitation", "critical condition", "severe injury"),
}


def negative_match(text: str, concept: str) -> bool:
    label = normalize(concept)
    aliases = (label, *SENSITIVE_ALIASES.get(label, ()))
    for alias in aliases:
        if contains(text, alias):
            return True
        # Plural inflection at the final word of arbitrary catalog concepts.
        forms = (alias + "s", alias + "es", alias[:-1] + "ies" if alias.endswith("y") else alias)
        if any(contains(text, form) for form in forms):
            return True
    return False


def load_brands(path: Path) -> list[Brand]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brands = TypeAdapter(list[Brand]).validate_python(raw.get("brands") if isinstance(raw, dict) else raw)
    if not brands or len({b.brand_id for b in brands}) != len(brands):
        raise ValueError("catalog must have unique nonempty brands")
    for brand in brands:
        if len({c.creative_id for c in brand.creatives}) != len(brand.creatives):
            raise ValueError("duplicate creative id")
    return brands


def vocabulary(brands: list[Brand]) -> list[str]:
    return sorted({normalize(t) for b in brands for t in [*b.target_contexts, *b.negative_contexts,
                                                        *b.category.split("/")] if normalize(t)})


class BrandMatchingService:
    def evaluate(self, semantics: SceneSemantics, brands: list[Brand]) -> list[BrandMatch]:
        observed = [semantics.dominant_activity, *semantics.contexts, *semantics.sensitive_contexts,
                    *semantics.mood, semantics.narrative_state_before, semantics.narrative_state_after]
        known_negative = {normalize(c) for b in brands for c in b.negative_contexts}
        unknown_sensitive = [c for c in semantics.sensitive_contexts
                             if not any(negative_match(c, n) for n in known_negative)]
        matches = []
        for brand in brands:
            blocked = [f"negative_context:{c}" for c in brand.negative_contexts if any(negative_match(o, c) for o in observed)]
            blocked += [f"unmapped_sensitive_context:{c}" for c in unknown_sensitive]
            overlap = [c for c in brand.target_contexts if any(contains(o, c) for o in observed)]
            activity = float(any(contains(semantics.dominant_activity, c) for c in brand.target_contexts))
            context = min(len(overlap) / 3, 1)
            category = float(any(contains(o, c) for c in brand.category.split("/") for o in observed))
            score = 0 if blocked else 0.6 * activity + 0.3 * context + 0.1 * category
            matches.append(BrandMatch(brand_id=brand.brand_id, eligible=not blocked,
                hard_block_reasons=blocked, target_overlap=overlap, dominant_activity_match=activity,
                contextual_score=context, category_relevance=category, final_score=score))
        return sorted(matches, key=lambda m: (-m.final_score, m.brand_id))

    def select(self, matches: list[BrandMatch], min_score: float) -> BrandMatch | None:
        return next((m for m in sorted(matches, key=lambda m: (-m.final_score, m.brand_id))
                     if m.eligible and m.final_score >= min_score and m.final_score > 0), None)
