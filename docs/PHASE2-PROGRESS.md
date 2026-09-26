# Phase 2 execution ledger

Base: `ac7facc` (latest `origin/feat/phase1`). Work/push exclusively on `feat/phase2`; no merge to main.
Requirements: `docs/PROJECT-Spec-PHASE2.md`. Existing player/UI remains unchanged.

## Milestones
- [ ] Strict semantic contract, explicit dialogue gates, raw-shot/semantic-scene grouping and sensitive memory.
- [ ] Validated inference cache, eligibility/ranking separation, independent final brand safety verification.
- [ ] Global schedule/creative optimizer, normalized decisions, JSON/VMAP parity.
- [ ] Integrated pipeline instrumentation, evaluation CLI, review clips, adversarial real-media coverage.
- [ ] MySQL migration, token-owned jobs/heartbeats, idempotent artifacts, startup validation and cleanup.
- [ ] Docker build/startup and real video processing; existing browser/player regression.
- [ ] Final evaluation, honest verification/docs and clean pushed branch.

## Decisions
- Phase 2 extends canonical contracts and keeps legacy analysis readable. Strict new semantic fields are required at the Phase 2 provider boundary; never infer missing safety fields.
- Context monitoring samples local windows across the entire clip, including regions without eligible cuts. Candidate-only perception would miss prior grief/violence.
- Semantic grouping merges cuts unless a completed dialogue and confident real narrative/location/activity transition is established. Unknown means no breakpoint.
- Global deterministic beam optimization evaluates complete schedules and actual creative durations; bounded beam approximation is disclosed.
- Evaluation counts detected policy violations, not human ground-truth error rates. Keep this distinction explicit.
- User-renamed specs are retained on Phase 2. No edits to Phase 1/main refs.
