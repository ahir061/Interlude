# Phase 1 execution evidence — 2026-09-26

> Historical Phase 1 record. Current behavior: [Phase 2 architecture](PHASE2.md) and [Phase 2 verification](PHASE2-VERIFICATION.md).
The actual external-service pipeline and browser insertion path were executed. No fabricated transcripts, semantic outputs or manually inserted break timestamps were used in the live smoke.

## Final real run

Input: `data/samples/indubala_120s.mp4`, a 120-second excerpt beginning at 120 seconds in the supplied `content-sample-assets-folder/indubala_bhaater_hotel.mp4`.

Job: `586b9183-1b49-4f42-b207-02032be4a5f7`.
Video: `b10de8a0-7d47-4d2d-96fe-3123382c9b32`.

| Measure | Observed |
| --- | --- |
| Job status | COMPLETED |
| Scenes | 20 |
| Candidates | 19 |
| Rejected before Qwen | 18 |
| Semantic candidates attempted/validated | 1 / 1 |
| Accepted breaks | 1 |
| Selected brand | `brand_d` (Brand D, telecom/connectivity) |
| Boundary | 58.84 seconds |
| WHERE score | 0.949 |
| Creative duration | 6 seconds |
| Projected ad load | 5% |

The live semantic output identified `family conversation`, `grief`, and `illness`. Seven brands were hard-blocked by their catalog exclusions. Brand D's supplied exclusions are funeral, hospital, medical emergency and violence; grief/illness are not in that brand's exclusion list. Its family-conversation target matched. This is a catalog-policy result, not a claim of editorial suitability for every viewer. Semantic perception remains probabilistic and should receive human evaluation before production use.

Local outputs (ignored by Git):

- `data/outputs/586b9183-1b49-4f42-b207-02032be4a5f7/analysis.json`
- `data/outputs/586b9183-1b49-4f42-b207-02032be4a5f7/debug.json`
- `data/outputs/586b9183-1b49-4f42-b207-02032be4a5f7/smoke.json`
- `data/outputs/586b9183-1b49-4f42-b207-02032be4a5f7/browser-evidence.json`
- `data/outputs/586b9183-1b49-4f42-b207-02032be4a5f7/player.png`

Open the running local demo at `http://localhost:3000/?video=b10de8a0-7d47-4d2d-96fe-3123382c9b32`. Seek to about 57 seconds, then play. Seeking past a slot deliberately skips it.

## Browser observation

Playwright/Chromium used the real manifest and API-served media. It sought just before the accepted boundary, then allowed normal playback. Content paused at **58.880273s**, the actual ad video advanced and ended, and content resumed from that captured position. The subsequent observation was **59.310248s**, with the source playing. Seeking backward across the same boundary did not replay the ad. No ad-ended event was fabricated. Screenshot inspected visually.

The player refuses late events outside the manifest's verified safe-start window (at most 250ms after the boundary), preventing a delayed callback from interrupting later dialogue.

## Executed checks

- MySQL initially connected with zero tables. Alembic revision `0001_phase1` applied to the hosted database.
- Readiness checks all passed: database, migration, FFmpeg, ffprobe, catalog, Groq config, semantic config.
- Hosted model metadata confirmed the configured model exists and identifies Qwen and 27B. The configured alias and endpoint were preserved.
- `pytest -q`: **39 passed**, including real MP4/CPU VAD pipeline coverage and required safety tests.
- `ruff check apps/api tests scripts`: passed.
- `npm test`: **4 passed**.
- `npm run build`: passed with TypeScript compilation.
- Actual-manifest `npm run test:browser`: **1 passed**.

Test output includes upstream deprecation warnings from Starlette's httpx adapter and Silero/PyTorch JIT utilities. They did not fail execution.

## Earlier outcomes and fixes

1. Bhojon Bilashi excerpt (source 240–360s): 37 scenes, 36 candidates; all 36 rejected for insufficient dialogue separation. No Qwen calls and no ad were appropriate under the policy.
2. First Indubala run: 20 scenes, 19 candidates, 18 prefilter rejections. The remaining Qwen request returned HTTP 200 with null final content and `finish_reason=length`; the candidate was rejected. Structure-only diagnosis showed the completion budget was consumed in thinking mode. Per-request `enable_thinking=false` returned schema-valid JSON without modifying the deployment. See [Qwen's documented request control](https://huggingface.co/Qwen/Qwen3.8-27B?chat_template=default).
3. Independent review reproduced late player insertion and plural/synonym exclusion bypass. Regression tests were written, failed, then passed after safe-window and negative-context normalization fixes.
4. A preliminary semantic response described an unconscious person without labeling medical emergency. A regression now maps that observation to the medical-emergency hard exclusion. Final live run above was executed after this fix. It returned different wording, so no unconsciousness cue was present in that final output. The regression verifies the earlier wording remains blocked.

Groq timestamp segmentation varied across identical excerpt runs, changing prefilter survivors between one and two. Each run's raw normalized transcript and decisions remain independently auditable; safety thresholds were not lowered to force ads.

## Unexecuted/deferred

Docker configuration is supplied but unexecuted because Docker is not installed. VMAP is deferred; JSON and actual playback are delivered. Full 45-minute episodes, distributed workers, public multi-user deployment and automatic source retention were not validated. The duration cap remains five minutes.
