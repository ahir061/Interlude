"""One audit row per candidate, including candidates stopped before semantics."""
from interlude.domain import AnalysisResult


def candidate_rows(result: AnalysisResult) -> list[dict]:
    candidates = {c.id: c for c in result.candidates}
    rows = []
    for decision in result.decisions:
        candidate = candidates.get(decision.candidate_id)
        components = decision.debug.get("where", {}).get("components", {})
        rows.append({
            "candidate_id": decision.candidate_id, "timestamp_sec": decision.timestamp_sec,
            "hard_blocked": decision.debug.get("hard_blocked", candidate.speech_active if candidate else None),
            "hard_block_reason": decision.debug.get("hard_block_reason", candidate.rejection_reasons if candidate else []),
            "visual_score": candidate.raw_boundary_score if candidate else None,
            "dialogue_gap_score": components.get("dialogue_gap", 0 if candidate and candidate.speech_active else None),
            "semantic_transition_score": components.get("semantic_transition"),
            "narrative_closure_score": components.get("narrative_closure"),
            "shot_stability_score": components.get("shot_stability", min(candidate.surrounding_shot_sec / 4, 1) if candidate else None),
            "confidence_score": components.get("confidence"),
            "where_score": decision.where_score,
            "rank": decision.debug.get("rank"),
            "final_decision": "AD" if decision.accepted else "NO_AD",
            "why_survived": decision.debug.get("why_survived", []),
            "why_lost": decision.rejection_reasons,
            "selected_brand_id": decision.selected_brand_id,
            "inspection_clip": decision.debug.get("inspection_clip"),
        })
    return rows
