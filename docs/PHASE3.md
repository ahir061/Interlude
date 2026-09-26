# Interlude Episode Studio

Interlude accepts arbitrary Bengali H.264 MP4 episodes, analyzes semantic scenes and exact speech timing, ranks natural interruption opportunities, applies per-brand contextual exclusions and episode-wide pacing, and produces JSON, VMAP/VAST and real ad playback. The supplied catalog is data; sample media filenames never choose placements or brands.

## Run the protected workspace

1. Populate `.env` using `.env.example` with the existing MySQL, Groq and Qwen configuration.
2. Set `WORKSPACE_PASSWORD` to a strong shared password and `SESSION_SECRET` to at least 32 random characters. These values must remain outside source control.
3. Run `docker compose up -d --build`. The migration is additive and runs before API/worker startup. Open **http://localhost:8080**. The gateway routes uploads/media directly to FastAPI and pages to Next.js; the browser uses same-origin cookies and API paths.
4. Sign in, choose the complete episode, and click **Analyze episode**. Upload progress is real transferred bytes. Keep the page open until upload completes. Analysis then runs independently in the worker; return through Recent episodes to view progress or results.
5. Review the semantic scene timeline, candidate rankings and per-brand safety decisions. Download VMAP, debug JSON, scene JSON or candidate JSON. Play the episode or review a moment just before a selected break to see content → actual MP4 advertisement → content resume.

For localhost development only, an empty workspace password disables authentication. Production mode refuses to start without a password of at least 16 characters and secure cookies. The optional public deployment below terminates TLS. Never expose the development API or unprotected workspace directly to the Internet.

### Public HTTPS deployment

Use your DNS hostname and a TLS reverse proxy to forward to the gateway's localhost port 8080. Set:

```dotenv
ENVIRONMENT=production
WORKSPACE_PASSWORD=<strong shared password>
SESSION_SECRET=<at least 32 random characters>
SESSION_COOKIE_SECURE=true
CORS_ORIGINS=["https://your-hostname.example"]
MEDIA_BASE_URL=https://your-hostname.example
```

The application deliberately has one shared team/judge workspace, not separate customer accounts. Sessions are HttpOnly, SameSite Strict, signed and time-limited. Protected mutations require a custom CSRF header; login attempts are rate-limited at both app and gateway. Rotating the session secret invalidates all sessions. Use an HTTPS endpoint in production so secure cookies can be sent. Back up the existing database and `interlude_data` volume; keep credentials in your deployment secret manager or a restricted env file.

The Compose ports bind to localhost. A host TLS proxy can expose only the gateway. Keep API/worker/database access private. No externally hosted fonts, stock assets or real company advertisements are required for the demo.

## Episode limits and resource controls

Default upload limit: **4096 MiB**. Default duration limit: **7200 seconds (two hours)**. These are configurable safeguards, not a sample-duration restriction. If changing the upload maximum, update both `MAX_UPLOAD_MB` and `client_max_body_size` in `deploy/nginx.conf` (allow 1 MiB multipart overhead). The API checks incoming bytes before full multipart spooling and independently verifies the saved file size, container, codec, duration and audio.

Both published Compose ports, 3000 and 8080, route through the streaming gateway. Next.js is reachable only inside the Compose network; episode uploads bypass its body-buffering proxy. This also keeps existing localhost:3000 bookmarks working for large files. A separately launched Next.js development server is not the episode-upload gateway. The supplied player requires H.264 MP4 with audio; unsupported formats receive an explicit error rather than an unverified playback promise.

Audio is extracted in five-minute cores with two-second overlap. Each bounded WAV remains under hosted ASR file-size limits and is removed after processing. Word and VAD timestamps are translated to episode time; seam evidence is conservatively unioned, not trimmed away. Invalid/out-of-range timings fail closed. Validated audio chunks and semantic responses are cached by content/configuration identities, so retrying a failed episode reuses completed inference. Failed semantic outputs are never cached as safe observations.

`SEMANTIC_CONCURRENCY` defaults to 3 (range 1–8). Independent windows may run concurrently, but results are always consumed in chronological order before context memory and brand verification. At most that many windows are prefetched. Frame directories are cleaned incrementally. Summed inference durations may exceed wall-clock runtime; debug metadata explicitly identifies this distinction. Provider retries/timeouts remain bounded.

Raw shot detection remains distinct from semantic segmentation. Every raw boundary is evaluated for grouping, including speech-blocked cuts; location/time/activity transitions can split scenes even under voiceover. Uncertain continuity merges conservatively. Scene segmentation never authorizes an ad across speech. Periodic monitoring also covers regions without a cut.

## Safety and ranking

The Phase 2 calibrated placement policy remains authoritative: exact ASR-word or Silero crossings are hard rejected; broad segment envelopes are context only. Visual quality, clear gap, transition, closure, stability and confidence combine into a configurable WHERE score. A candidate need not be a confirmed semantic scene boundary. Ongoing sequences without completed dialogue receive a configurable score deduction (`SEQUENCE_INTERRUPTION_PENALTY`, default 0.12). The deduction gradually relaxes for gaps between 8 and 20 seconds (`SEQUENCE_LONG_PAUSE_SEC`, default 20); these are quality heuristics, not safety gates. No dialogue alone does not imply narrative closure. Per-brand negative contexts and unresolved sensitive context remain hard blocks, with independent SAFE verification required. Moderate relevance does not eliminate safely eligible brands. Dominant activity remains the largest relevance weight.

`MAX_BREAKS_PER_HOUR` counts actual breaks in every rolling 3600-second content window, not a normalized extrapolation from a short excerpt. Minimum spacing and total ad-load percentage are enforced with probed creative durations. The bounded global optimizer reports if its beam was truncated; no exact-optimum claim is made after truncation.

The player skips a missed safe-start window instead of inserting late into resumed speech. Seeking forward skips crossed breaks; seeking backward does not replay consumed breaks. Clicking the right-hand schedule explicitly previews that advertisement every time and resumes at its selected timestamp. Synthetic creatives are loaded from the catalog paths when present; missing creatives are visibly labeled generated synthetic demo ads, with their actual duration used for pacing.

## Jobs, cancellation and recovery

Progress counts are stored in MySQL. Cancel invalidates the worker lease immediately, preventing it from publishing a completed manifest. An in-flight external request may finish before the process observes cancellation, but cannot publish results. Retry creates a new job and reuses validated caches. Lost workers are fenced and the job becomes failed after its lease expires; users can retry from the library. Active duplicate enqueue requests reuse the current job.

The library fetches latest jobs in one query and reports when retained source media has expired. Retry rejects expired sources rather than starting an impossible analysis. `/health` proves liveness; `/ready` checks database schema, storage/tool configuration and provider configuration, not provider inference availability.

Use `python -m interlude.cleanup` for a retention preview and `--apply` to delete expired inactive source/scratch files. Active jobs protect their sources. Cache/output/inspection storage is retained for audit and retry; monitor disk use and back it up. Full episode workloads still require provisioned disk, CPU and sufficient external inference quota. Do not remove volumes during routine upgrades.

## Verification and reproducibility

```sh
.venv/bin/pytest -q
.venv/bin/ruff check apps/api tests scripts
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
.venv/bin/python scripts/calibrate_placement.py path/to/episode.mp4 --report-dir reports/episode
.venv/bin/python scripts/browser_verify.py --manifest path/to/analysis.json
```

`browser_verify.py` reads the local workspace password into the child process environment without printing it or putting it in command arguments. `--episode path/to/episode.mp4` additionally verifies the full web upload and cancellation path; that test deliberately cancels its duplicate job to avoid double inference charges. Actual complete-episode processing is independently measured in the evaluation report.

The new workspace tests use real API responses, manifests and videos. No model outcomes are faked in real evaluation. Unit tests cover chunk seams, speech gates, scene grouping, unseen brands, hard negative contexts, pacing, CSRF/session boundaries, incoming upload size and cancelled-worker fencing.

Model perception is probabilistic; no unlabeled automatic audit can prove zero semantic mistakes on every unseen video. Use the evidence and inspection workflow for editorial sign-off. Full episode segmentation and safe brand placement are implemented; multi-tenant isolation, distributed object storage, autoscaling and third-party ad-server certification are outside this single-workspace deployment.
