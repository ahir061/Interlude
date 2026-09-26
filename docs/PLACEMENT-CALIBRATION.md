# Ranked placement calibration — 2026-09-26

Engine commit: `e452b8b` (`fix(engine): balance hard safety gates with ranked break selection`). Policy: `ranked-safety-2.2`. No UI design changes or required ad count.

## Demonstrated false negative

Indubala's 39.40-second cut used to be rejected because a broad Whisper segment crossed it and semantic analysis grouped it with the ongoing conversation. Actual word/VAD speech ends at 37.44 and resumes at 41.50. The images show the video call ending, followed by a cut back to the woman. The new policy selects the opportunity at WHERE **0.624128** with independently verified SAFE Brand D (telecom), confidence **0.95**.

The 58.84-second cut scores higher (**0.896250**) but remains rejected: no brand passed contextual safety. At 6.88 seconds, both a word and VAD speech cross the cut, so it is hard blocked before semantic scoring. This demonstrates that strong quality cannot override speech or brand safety.

## Direct real-provider runs

Both supplied 120-second excerpts were rerun with actual Groq ASR, Silero CPU VAD, Qwen perception, the supplied brand catalog and independent Qwen safety verification.

| Excerpt | Candidates | Speech-blocked | Scored | Accepted | Ad load | Detected speech/negative violations |
|---|---:|---:|---:|---:|---:|---:|
| Indubala | 19 | 16 | 3 | 1 | 5% | 0 / 0 |
| Bhojon Bilashi | 36 | 28 | 7 | 0 | 0% | 0 / 0 |

The prior local runs accepted zero placements in both videos; their dialogue filters rejected 18/19 and 36/36 candidates respectively. The new runs took 74.03 and 97.23 seconds.

Bhojon Bilashi's eighth speech-safe cut, at 22.48 seconds, returned invalid semantic analysis after bounded retries. Context memory therefore remained uncertain for its configured window. A later observation also reported continuing grief; the remaining eligible brand's independent verdict was UNCERTAIN. These safety failures were preserved, rather than lowering the quality floor to force a placement. Its highest-scoring cut at 94.96 seconds scored 0.692250 but could not establish safe targeting.

All candidates, including rejected ones:

- [Indubala candidate scores](../reports/calibration/indubala_120s/candidates.csv)
- [Bhojon Bilashi candidate scores](../reports/calibration/bhojon_bilashi_120s/candidates.csv)

Each CSV includes timestamp, hard block/reason, all six component scores, final WHERE score, rank, final decision, survival/loss reasons and clip path. Unavailable semantic scores/ranks are blank; they are not fabricated for speech-blocked or model-failed cuts. Ranks compare scored opportunities before brand/pacing selection. A high-ranking cut can still lose to safety. Pacing exclusions are schedule-dependent and appear in loss reasons rather than intrinsic safety flags.

## Inspection media

Generated clips stay local and are not committed as source assets:

- Accepted: `reports/calibration/inspection/calibration_indubala_120s/candidate_007.mp4` (39.40s).
- Highest-scoring rejected: `reports/calibration/inspection/calibration_indubala_120s/candidate_011.mp4` (58.84s, brand safety).
- Speech blocked: `reports/calibration/inspection/calibration_indubala_120s/candidate_001.mp4` (6.88s).
- Highest-scoring Bhojon rejection: `reports/calibration/inspection/calibration_bhojon_bilashi_120s/candidate_031.mp4` (94.96s).

Full JSON, transcripts, provider evidence and VMAP remain in the corresponding local report directories. Detected violation counts audit model/timing outputs; they are not human-labeled accuracy measurements.

## Full API and browser verification

The API and worker containers were rebuilt with the committed engine. Both excerpts were uploaded as new jobs against the existing external database/providers. The frontend was unchanged.

| API excerpt | Candidates | Speech-blocked | Scored | Accepted timestamps | Ad load | Detected speech/negative violations |
|---|---:|---:|---:|---|---:|---:|
| Indubala | 19 | 17 | 2 | 39.40s | 5% | 0 / 0 |
| Bhojon Bilashi | 36 | 26 | 10 | 25.16s, 66.76s | 10% | 0 / 0 |

Indubala job `97129b20-0ef2-4b29-a6f3-f44c59bd6734`, video `9b9ea57b-a80c-4579-a2d9-6c3e8b66e3b4`, completed with one six-second Brand D placement at **39.40s** (WHERE **0.591036**, rank 2). Its higher-scoring **58.84s** cut (WHERE **0.807500**, rank 1) still failed independent brand safety. Seventeen of nineteen cuts were blocked by exact speech; both remaining cuts were scored. Ad load was 5%, with zero detected word/VAD or negative-context violations. Runtime was 86.91 seconds.

The fresh ASR/Qwen outputs and platform-dependent visual measurements differ from the direct run; both runs independently selected the same safe cut. No cached or manually edited decision was substituted for this API result.

The existing Playwright test passed against that real manifest and real media: source paused at **39.447219s**, the actual MP4 ad advanced and emitted its genuine ended event, source resumed (observed at **39.534164s**), and seeking back did not replay the break. No mocked network or synthetic ended event was used. [Browser evidence](../reports/calibration-api/indubala_120s/browser-evidence.json).

- [Open the verified video in the running app](http://localhost:3000/?video=9b9ea57b-a80c-4579-a2d9-6c3e8b66e3b4).
- [All API-run Indubala candidates](../reports/calibration-api/indubala_120s/candidates.csv).
- Local accepted clip: `reports/calibration-api/indubala_120s/inspection/candidate_007.mp4`.
- Local strongest rejected clip: `reports/calibration-api/indubala_120s/inspection/candidate_011.mp4`.

Bhojon Bilashi job `34ac9eb4-9b40-4e6c-ae68-f677eba8564d`, video `103137b6-f0f3-4462-b5a7-d57d8042be8b`, completed with two six-second Brand D slots at **25.16s** (WHERE **0.673250**, rank 3) and **66.76s** (WHERE **0.686500**, rank 2). Both independently received SAFE confidence **0.95**. The slots are 41.60 seconds apart and exactly meet the 10% total-load cap. The higher-scoring 94.96-second cut remained blocked by brand safety; 22.48, 71.52 and 77.96 lost to spacing/ad-load constraints. Runtime was 169.04 seconds.

Unlike its earlier direct run, this fresh run successfully resolved context at the early boundaries; the earlier abstention was not overridden or reused. Frames around the selected cuts show a move from the street/church exterior to a stall, and from one interview to another location/interview. Both slots passed the real browser playback/resume/replay-prevention test. The second has just **0.14s** of post-cut silence; the player inserted before its **66.83s** deadline. Actual speech begins at 66.90s, so this does not require a broad silence veto.

- [Open Bhojon in the running app](http://localhost:3000/?video=103137b6-f0f3-4462-b5a7-d57d8042be8b).
- [All API-run Bhojon candidates](../reports/calibration-api/bhojon_bilashi_120s/candidates.csv).
- [25.16s browser evidence](../reports/calibration-api/bhojon_bilashi_120s/browser-evidence.json) and [66.76s browser evidence](../reports/calibration-api/bhojon_bilashi_120s/browser-evidence-candidate_023.json).
- Local accepted clips: `reports/calibration-api/bhojon_bilashi_120s/inspection/candidate_008.mp4` and `candidate_023.mp4`.
- Local highest-scoring rejected clip: `reports/calibration-api/bhojon_bilashi_120s/inspection/candidate_031.mp4`.

The browser test now accepts `INTERLUDE_CANDIDATE` to exercise any actual selected slot and checks the safe start deadline. Its resume assertion compares the application-captured value, allowing a separately observed browser clock to settle by milliseconds after pause. This fixes a test-only rounding failure; no player implementation or UI styling changed.

Artifact audits confirmed exact speech gating, independent brand safety, pacing constraints, all-candidate coverage, and VMAP/JSON placement agreement.

Browser reproduction after uploading/running the excerpt through the API:

```sh
cd apps/web
INTERLUDE_MANIFEST=/absolute/path/to/analysis.json npm run test:browser
```

## Reproduction

```sh
.venv/bin/pytest -q
.venv/bin/ruff check apps/api tests scripts
.venv/bin/python scripts/calibrate_placement.py \
  data/samples/indubala_120s.mp4 data/samples/bhojon_bilashi_120s.mp4 \
  --report-dir reports/calibration
```

The direct calibration command uses the configured real providers and generates the complete candidate audits and clips. No synthetic model responses or fabricated placements are used in those reports.

Backend validation: **89 tests passed**. Existing player unit tests: **4 passed**. Real browser checks covered **all three accepted slots**. TypeScript typecheck passed. Lint and `git diff --check` passed. The backend test run reports existing dependency deprecation warnings from Starlette, Silero and Torch.
