# Phase 2 architecture and operation

The worker now uses `Phase2Pipeline`; legacy Phase 1 contracts and manifests remain readable. No frontend design or placement timestamps were changed.

## Decision sequence

1. Probe/hash media; reload the supplied brand catalog and probe actual creative durations.
2. Persist PySceneDetect raw shots, Bengali Whisper timestamps and CPU Silero VAD.
3. Reject speech-active cuts, insufficient silence, short shots and edge cuts. Either ASR or VAD can veto a boundary.
4. Request strict, evidence-backed semantics at surviving boundaries and periodic context windows. Ongoing/uncertain dialogue, camera angles, montage, low confidence and missing closure are hard rejections before WHERE scoring.
5. Group shots only at positively confirmed safe semantic transitions. Unconfirmed boundaries remain merged. This intentionally under-segments and does not claim human scene annotation accuracy.
6. Carry recent sensitive observations for 90 seconds by default, extending narratively continuing contexts. Invalid observations, unresolved affirmative sensitivity and stale memory make brand safety uncertain. Periodic windows are ±5 seconds every 20 seconds; short events between windows may be missed.
7. Evaluate each brand's negative contexts before assigning a score. Blocked brands have `score: null`. Unknown sensitivity or uncertain memory blocks eligibility.
8. Rank eligible brands: dominant activity 60%, target overlap 25%, category 10%, secondary context 5%. Configuration requires activity weight to exceed all secondary weights combined. These are conservative starting weights, not empirically calibrated accuracy claims.
9. Independently ask Qwen for SAFE/BLOCKED/UNCERTAIN with evidence. Only SAFE at confidence ≥0.9 proceeds. Otherwise try the next eligible brand; no qualifying brand means NO AD.
10. Optimize chronological schedules with a deterministic bounded beam (default 2048). Evaluate actual creative durations, minimum spacing, rolling hourly cap and total ad load. Search truncation is disclosed; a truncated beam is not guaranteed globally optimal.
11. Serialize the same final decisions to analysis, debug and VMAP 1.0 with embedded VAST 3.0. The existing player continues consuming JSON. Accepted cuts get automatic review clips.

## Semantics and cache

`Phase2Semantics` requires narrative/dialogue state, transition type/confidence, location/character continuity, sensitive carryover and timestamped evidence. Missing fields are never filled in to approve a cut. Malformed output retries once, then abstains. Network/HTTP failures use bounded retries/timeouts. ASR/VAD failure fails the job.

Cache identity includes video and frame hashes, transcript, catalog hash, model identifier, endpoint hash, schema, prompt version and generation controls. Only validated responses are stored and every hit is validated again. Catalog data introduces new context labels automatically. The runtime Brand I regression loads a ninth catalog entry, ranks running, blocks injury and creates its missing synthetic creative.

Debug metadata includes pipeline/policy/prompt versions, hashes, request events, call/cache counts, observations, per-stage timings and optimizer diagnostics. Per-candidate data contains speech measurements, hard-gate reasons, semantic evidence, context memory, score components, brand eligibility and safety verdicts. Logs use safe error codes and job correlation; provider payloads and credentials are excluded.

## Jobs and failure handling

Migration `0002_phase2` adds raw shots, observations, lifecycle state, lease token and heartbeat. Claims lock rows using MySQL `SKIP LOCKED`. Every checkpoint, progress update and artifact registration requires the current token. An independent heartbeat updates long-running jobs; expired ownership becomes FAILED and cannot publish completed output. The API reuses active and completed jobs; `force=true` explicitly requests fresh work.

MySQL connection establishment retries transient errors up to three attempts with 10-second connection and 30-second read/write timeouts. Authentication errors fail immediately. An ambiguous transaction is never blindly replayed. Worker polling recovers after database availability returns; a lost job safely expires. Artifact files are replaced atomically and registered before COMPLETED. SIGTERM stops claiming work and drains the current job within Compose's grace period.

`/health` reports liveness. `/ready` checks MySQL/schema, tools, catalog and configuration; it does not prove external inference availability. Startup validates required settings and writable directories. Upload validation timing is stored with video metadata; pipeline stage timings appear in debug and evaluation reports.

## Docker and retention

Run `docker compose up --build` with a populated `.env`. The application uses existing external MySQL/Groq/Qwen; there is no new database/model service. Images run as non-root users. Linux PyTorch uses the explicit CPU index documented by [uv](https://docs.astral.sh/uv/guides/integration/pytorch/). Dependencies are locked; Docker base tags are not immutable digests.

Named volumes persist `/app/data` and `/app/reports`. Host development data is separate. Run one environment's workers at a time unless all workers share media paths. Stop without deleting volumes: `docker compose down`. `docker compose down -v` destroys retained container media and must not be used for routine shutdown.

`python -m interlude.cleanup` previews expired uploads/work. `--apply` deletes eligible files only, with active-job protection and constrained roots. Ads, output artifacts and inspection clips remain. Cleanup is explicit; schedule it operationally if needed. Deleting an expired source intentionally removes its future playback capability, even though audit artifacts remain.

## Evaluation limits

See `PHASE2-VERIFICATION.md`. Automated checks detect policy violations in model/ASR/VAD output; no human-labeled accuracy is claimed. Full-episode chunking, public authentication and production load testing remain unsupported. Model perception can miss implicit sensitivity. VMAP parity is automated; third-party ad-server certification is unverified. UI and visual design remain Phase 3.
