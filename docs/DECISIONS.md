# Architecture decisions

## ADR-001 — Candidate-first VLM processing
Accepted. Detect visual cuts and reject dialogue/poor boundaries on CPU before sending sparse ±5-second windows to the external VLM. This bounds inference cost and preserves rejected candidates for audit.

## ADR-002 — Semantic perception is separate from policy
Accepted. Qwen describes activity, context, sensitivity and transition. Deterministic WHERE, pacing and brand code decide placements. Provider failure means candidate rejection; ASR/VAD failure means failed analysis.

## ADR-003 — Negative contexts are hard exclusions
Accepted. Any meaningful normalized negative match makes a brand ineligible before relevance ranking. No positive score offsets it. Unknown sensitive concepts reject uncertain placements.

## ADR-004 — Brands are data-driven
Accepted. Catalog parsing, vocabulary, ranking, creative generation and database synchronization enumerate validated JSON. No brand IDs appear in policy branches. A ninth brand requires only new catalog data.

## ADR-005 — Uploaded media is temporary filesystem data
Accepted. MySQL retains paths, metadata and decisions. Temporary audio and frames are removed after work; source media remains until explicitly removed so the player works. Synthetic creatives persist. Automated source retention is deferred.

## ADR-006 — Dynamic player insertion
Accepted. Browser content/ad elements preserve an exact resume position. Ads are not permanently burned into an episode. Played IDs and seeking rules prevent duplicate insertion in a session.

## ADR-007 — MySQL polling worker
Accepted for Phase 1. A single independent worker polls persisted jobs and claims transactionally. No Redis, separate model server or database server is needed. An expired stage lease fails abandoned jobs explicitly. Longer media needs chunked ASR and independent heartbeats before the duration cap is raised.

## ADR-008 — JSON before VMAP
Accepted. Canonical BreakDecision generates analysis and debug JSON. VMAP is deferred until the required real pipeline and browser playback are verified. No second placement model is introduced for serialization.
