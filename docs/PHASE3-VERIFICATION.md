# Phase 3 measured verification

Verified on 2026-09-26, branch `feat/phase3`.

## Complete episode, real providers

The untrimmed `bhojon_bilashi.mp4` ran through the actual Phase 3 pipeline with hosted ASR/Qwen and local Silero. Its filename does not participate in placement rules.

| Measurement | Result |
|---|---:|
| Duration | 1,227.413 seconds |
| Audio chunks | 5, with overlapping seams |
| Raw shots | 430 |
| Semantic scenes | 58 |
| Candidate cuts | 429 |
| Speech-safety rejections | 345 |
| Selected breaks | 10 |
| Minimum selected spacing | 30 seconds |
| Total ad load | 4.888% |
| Detected speech-crossing violations | 0 |
| Detected negative-context violations | 0 |

Selected timestamps: 139.40, 176.16, 215.32, 456.04, 513.28, 548.84, 578.84, 904.96, 1119.36 and 1167.88 seconds. These are observed results, not configuration or required counts. Ten actual breaks fit the configured twelve-break rolling-hour cap; the report's extrapolated ads/hour statistic is not that cap.

The completed pass took 1,215.5 seconds and reused five audio chunks and 115 semantic cache hits from the earlier interrupted pass. This is **not a cold-start benchmark**. Summed concurrent model timings exceed wall time. All accepted clips, the two highest-scored rejected clips and a speech-blocked clip were extracted under `reports/phase3-episode/inspection/`.

The candidate CSV contains all 429 decisions, hard-block reasons, score components, rank and outcome. The local debug JSON retains complete perception and safety evidence. Automated zero-violation checks compare against detected evidence; they do not establish human-labeled accuracy or perfect safety on unseen footage.

## Protected web workflow

Four actual Chromium checks passed through the gateway at localhost:8080:

- Password-form sign-in, sign-out and unauthorized API rejection.
- A real accepted excerpt placement pauses content, plays the MP4 advertisement and resumes once within its safe timing window.
- Browser upload accepts the complete 106,334,250-byte, 1,227-second episode; cancellation invalidates its background job.
- Scene timeline, ranked decisions, contextual catalogue and mobile layout use actual API artifacts.

The full web-upload test deliberately cancels its duplicate analysis. Complete-episode inference above was a separate direct pipeline run; a full episode has not yet been verified from web upload all the way through worker completion and browser playback in one uninterrupted job. The existing excerpt path has passed actual API/worker/playback end to end.

The first cancellation browser attempt exposed an upload-state race. The UI now switches to background-job state immediately after upload completes; the repeated test passed. Gateway upstream DNS refresh was also tested with successful sign-in after configuration reload.

## Automated checks and deployment limits

- Backend: 102 tests passed, with 17 dependency deprecation warnings.
- Player: 4 tests passed.
- TypeScript, Ruff and production web build passed.
- Container build/start and additive database migration succeeded.

Public HTTPS deployment, multi-user load testing, two-hour maximum-size uploads and third-party ad-server certification remain unverified. The protected local workspace is usable; these results should not be described as universal production certification. See [operations guide](PHASE3.md).
