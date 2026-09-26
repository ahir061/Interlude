# Phase 2 verification

Measured on 2026-09-26. Real hosted ASR/Qwen and existing MySQL; no substituted inference for these runs.

## Real supplied media

| Run | Duration | Raw shots | Semantic scenes | Candidates | Qwen calls | Cache hits | Accepted | Processing seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| indubala_120s | 120.0 | 20 | 1 | 19 | 9 | 0 | 0 | 74.66 |
| bhojon_bilashi_120s | 120.0 | 37 | 1 | 36 | 6 | 0 | 0 | 62.71 |
| Indubala repeat | 120.0 | 20 | 1 | 19 | 7 | 2 | 0 | 68.18 |

Indubala excerpt comes from source seconds 120–240; Bhojon Bilashi from 240–360. The CLI inputs were already extracted 120-second MP4s, so their internal excerpt offsets are zero.

All three runs detected zero mid-dialogue and negative-context violations because they accepted zero placements. This is safe abstention, not evidence of human-level accuracy or useful recall. Periodic model responses were validated; an invalid boundary response was retried then rejected. Ongoing dialogue and weak closure also rejected surviving cuts. Conservative grouping merged each excerpt into one unconfirmed semantic scene.

Local job IDs:

- `4ba5d4c9-d3e1-4854-abf0-ffb4dfb9360d` / video `06320bc8-837a-4e11-a193-0963087529be`
- `26fd5332-95fc-4f8d-b6d5-b19cbcf66deb` / video `0f188bce-ccba-4682-bcd3-2456d5bff4ad`
- `7d5d58af-232c-4b02-ae3f-dd983869f0c0` / video `83534d01-9710-42dc-97c6-4c05bd7b7e63`

Reports: `reports/local/evaluation.json`, `reports/local/evaluation.md`, `reports/cache-repeat/evaluation.json`. Local artifacts: `data/outputs/<job_id>/analysis.json`, `debug.json`, `manifest.vmap.xml`. Reports/media are generated locally and ignored by Git.

## Automated verification

- Python: 78 passed; lint passed. Existing dependency deprecation warnings remain.
- Player: 4 passed; TypeScript and production web build passed.
- Browser: 1 passed using the genuine Phase 1 accepted manifest on the Phase 2 API. Actual MP4 playback, ad-ended event, exact resume and no replay were checked. This is explicitly a saved-manifest compatibility regression; new real Phase 2 runs accepted no ads.
- Adversarial cases cover ongoing sentences, camera-angle grouping, valid transitions, funeral/grief/accident/hospital carryover, driving versus phone, video call, payment/shopping, runtime Brand I, malformed/timeout inference, ASR failure/disagreement, missing creatives and global pacing.
- Full real-media fixture exercises Phase 2 acceptance, independent safety fallback, VMAP export and inspection clip creation using injected test inference. It does not claim live-model positive-placement quality.
- Independent bounded code review found and verified fixes for unresolved continuing sensitivity and incorrect supplied-creative dimensions.
- Container cleanup dry run passed with no deletion targets; API/worker user `interlude`, web user `node` were verified.
- Live `/health`, `/ready`, VMAP export returned HTTP 200; two analyze requests reused the completed job. Migration `0002_phase2` applied to hosted MySQL.

## Docker

Build succeeded with CPU-only Linux PyTorch on ARM64 Colima. API, web and worker all reached healthy status, and migration exited successfully. A real Indubala 120-second excerpt completed inside the container worker using hosted ASR/Qwen/MySQL: 20 shots, 1 semantic scene, 19 candidates, 7 Qwen calls, 0 cache hits, 0 accepted breaks, 72.73 processing seconds. Automated policy audits detected zero violations; zero accepted ads limits what this proves.

Job `abc43d45-83da-4262-8e78-f09cd9cac1c5`, video `dd1ab88e-907e-4a2b-a8b6-ff03419799e3`. Report: `reports/docker/evaluation.json`. Exported artifacts: `reports/docker/artifacts/analysis.json`, `debug.json`, `manifest.vmap.xml`. Container originals persist under `/app/data/outputs/abc43d45-83da-4262-8e78-f09cd9cac1c5/` in the named volume. Host and Docker workers were never run together during processing.

The first Docker attempt exposed insufficient host disk space and a GPU-enabled Linux torch dependency. The disposable failed build VM was removed, host free space recovered, and Linux dependencies were locked to the CPU index; the clean build and processing then succeeded. No source assets or database records were deleted.

The final reviewed Docker image also completed Bhojon Bilashi: 120 seconds, 37 shots, 1 semantic scene, 36 candidates, 6 Qwen calls, 0 cache hits, 0 accepted ads, 74.51 processing seconds. Job `db097ab3-b60e-41f0-a279-342eef0ad93e`, video `c9c3f4e5-3914-427e-a91a-75c3e29f8af3`. Final reports/artifacts: `reports/docker-final/evaluation.json` and `reports/docker-final/artifacts/`. JSON/debug/VMAP accepted-break parity was checked against these real outputs. All containers remained healthy.

## Limits and unverified claims

- Human-labeled placement precision/recall and negative-context detection accuracy: **UNVERIFIED**.
- Live Phase 2 positive placement and associated human inspection: **UNVERIFIED** (all tested real clips abstained). Automatic review generation is covered by real FFmpeg integration fixtures.
- External VMAP/VAST ad-server certification: **UNVERIFIED**.
- Public deployment security, multi-host load tests and full-episode chunking: unsupported in this local short-clip demo.
- Semantic grouping under-segments; periodic sparse monitoring can miss brief events. Ranking weights have not been tuned on labeled examples.
- Beam search may truncate and reports that fact; no optimality guarantee after truncation.
