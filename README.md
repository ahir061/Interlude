# Interlude

Context-aware multimodal ad placement & intelligent brand matching for long-form media.

Phase 2 uploads a short Bengali H.264 MP4, groups raw shots conservatively, hard-blocks exact ASR-word/VAD speech crossings and scores transition quality, carries recent sensitive context, independently verifies eligible brands, and optimizes a global ad schedule. Canonical decisions produce JSON and VMAP. The plain Next.js player pauses source content, plays the selected MP4 creative and resumes at the captured position. Returning **no ad break** is valid when no safe opportunity clears the combined quality floor. See [ranked placement policy](docs/PHASE2.md).

## Requirements

- Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js 22, npm and Git
- FFmpeg and ffprobe (`brew install ffmpeg` on macOS; `apt install ffmpeg` on Debian/Ubuntu)
- Existing hosted MySQL and OpenAI-compatible Qwen endpoint; Groq account with Whisper Large V3
- Organizer `brands.json` and an approximately two-minute Bengali MP4

PySceneDetect, CPU PyTorch and packaged Silero VAD weights are installed through `uv sync`. Qwen runs only on the existing external service. No PostgreSQL, Redis, RAG, vector database or additional model server is used.

## Setup

```bash
uv sync --python 3.11
cd apps/web
npm ci
cd ../..
cp .env.example .env  # Only for a new setup: do not overwrite an existing .env.
```

Populate `.env` locally. It is ignored by Git and Docker. The existing environment names are reused:

| Names | Purpose |
| --- | --- |
| `LLM_API_URL`, `LLM_MODEL`, `LLM_API_KEY` | Existing external semantic provider. URL ends in `/v1` or `/chat/completions`. |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Existing hosted MySQL database. |
| `GROQ_API_KEY` | Groq authentication. |
| `ASR_MODEL`, `ASR_LANGUAGE`, `ASR_RESPONSE_FORMAT`, `ASR_TEMPERATURE` | Enforced `whisper-large-v3`, `bn`, `verbose_json`, `0`. |
| `ASR_WORD_TIMESTAMPS`, `ASR_SEGMENT_TIMESTAMPS` | Word timestamps optional; segment timestamps mandatory. |
| `ASR_REQUEST_TIMEOUT_SEC`, `ASR_MAX_RETRIES` | Default 180 seconds and 3 retries after initial attempt. |
| `LLM_REQUEST_TIMEOUT_SEC`, `LLM_MAX_RETRIES` | Default 120 seconds and 3 retries. |
| `LLM_JSON_MODE`, `LLM_ENABLE_THINKING`, `LLM_MAX_TOKENS` | Structured JSON, default non-thinking perception, bounded 1200-token completion. |
| `BRANDS_PATH`, `DATA_DIR` | Catalog and local media root. |
| `FFMPEG_BIN`, `FFPROBE_BIN` | Executable paths; default names on PATH. |
| `MAX_BREAKS_PER_HOUR`, `MIN_BREAK_GAP_SEC`, `MAX_AD_LOAD_PERCENT` | Defaults 12, 30 seconds, 10% ad seconds/source seconds. |
| `MIN_DIALOGUE_GAP_SEC`, `MIN_SCENE_SEC`, `MIN_EDGE_GAP_SEC` | Defaults 0.5 seconds each side of speech, 2 seconds scene duration, 10 seconds from content ends. |
| `MIN_WHERE_SCORE`, `MIN_SEMANTIC_CONFIDENCE`, `MIN_BRAND_SCORE` | Defaults 0.65, 0.7, 0.15. |
| `WHERE_BOUNDARY_WEIGHT`, `WHERE_DIALOGUE_WEIGHT`, `WHERE_SILENCE_WEIGHT`, `WHERE_SEMANTIC_WEIGHT` | Defaults 0.2, 0.25, 0.2, 0.35; normalized before scoring. |
| `SCENE_THRESHOLD` | PySceneDetect content threshold, default 27. |
| `MAX_UPLOAD_MB`, `MAX_VIDEO_DURATION_SEC` | Phase 1 limits: 250 MB and 300 seconds. Start with 120 seconds. |
| `CORS_ORIGINS` | JSON array, default `["http://localhost:3000"]`. |
| `WORKER_LEASE_SEC` | Inactive in-progress job expiry, default 900 seconds. |
| `NEXT_PUBLIC_API_BASE` | Browser-accessible API URL; default `http://localhost:8000`. Set in the web process/build environment. |

Default catalog: `content-sample-assets-folder/brands.json`. It supports an array or `{ "brands": [...] }`. Creative `id` is normalized to `creative_id`; referenced local missing MP4s become 6-second synthetic fallback ads under `data/ads/<brand_id>/`. Actual creative duration is probed before pacing. Add another brand to the catalog and restart/reanalyze; no code change is required.

## Migrate and run

```bash
uv run python scripts/migrate.py
uv run python scripts/generate_ads.py
```

Start three terminals from the repository:

```bash
# Terminal 1
uv run uvicorn interlude.main:app --host 127.0.0.1 --port 8000

# Terminal 2
uv run python -m interlude.worker

# Terminal 3
cd apps/web && npm run dev
```

Open **http://localhost:3000**. Choose a short MP4 and click **Analyze**. Upload validates and probes the media, then creates a persisted QUEUED job. The worker performs analysis. The page polls status, shows all decisions and JSON, and loads the playable result. `?video=<id>` reopens a completed analysis. In production mode use `npm run build` followed by `npm run start`.

Docker: `docker compose up --build` uses the same external database and providers. Migration runs first; API, worker and web run as non-root users with healthchecks. Named volumes retain container media and reports separately from host development data. Stop with `docker compose down` (without `-v`). Do not run host and container workers together against the same database unless they share identical media paths. See [Phase 2 verification](docs/PHASE2-VERIFICATION.md) for measured results.

## Sample flow

The supplied assets contain full episodes. Extract a short excerpt without altering the original:

```bash
mkdir -p data/samples
ffmpeg -ss 120 -i content-sample-assets-folder/indubala_bhaater_hotel.mp4 \
  -t 120 -c:v libx264 -preset veryfast -crf 25 -vf scale=960:-2 \
  -c:a aac -movflags +faststart data/samples/indubala_120s.mp4
uv run python scripts/smoke.py data/samples/indubala_120s.mp4
```

The smoke script performs a real multipart upload, waits for the persisted job, and reports actual counts. It uses real Groq, CPU VAD and the configured semantic endpoint; it never substitutes transcripts or semantic outputs. Artifacts are under `data/outputs/<job_id>/analysis.json` and `debug.json`, with smoke evidence alongside them. A completed job may have no ads, including when all semantic candidates fail validation.

## API

| Method/path | Behavior |
| --- | --- |
| `POST /api/videos` | Multipart field `file`; returns video and queued job (202). |
| `POST /api/videos/{video_id}/analyze` | Reuse active/completed analysis; `?force=true` explicitly queues a fresh completed-video analysis. |
| `GET /api/jobs/{job_id}` | Current state and safe error code/stage. |
| `GET /api/videos/{video_id}/analysis` | Latest job's canonical analysis manifest. |
| `GET /api/videos/{video_id}/vmap` | VMAP XML from the same final decisions. |
| `GET /api/videos/{video_id}/debug` | Completed debug or partial failure/progress data. |
| `GET /api/videos/{video_id}/media` | Source MP4 with byte-range support. |
| `GET /api/ads/{brand_id}/{creative_id}` | Generated/provided local creative. |
| `GET /api/brands` | Validated catalog. |
| `GET /health` | Process liveness. |
| `GET /ready` | Database/migration, media-tool, catalog and provider-configuration checks. |

Readiness does not claim provider network availability or worker liveness. These are proved by actual jobs. Never expose this unauthenticated local demo directly to the public internet.

## Tests and verification

```bash
uv run pytest -q
uv run ruff check apps/api tests scripts
cd apps/web
npm test
npm run build
npx playwright install chromium
# With API + worker + built web running, after a real job accepted a break:
INTERLUDE_MANIFEST=/absolute/path/to/data/outputs/JOB_ID/analysis.json npm run test:browser
```

Provider tests inject HTTP failures for retry/validation cases; policy tests inject explicit semantic fixtures. Live evaluation uses the configured services. Real media tests create MP4s with FFmpeg, detect cuts, run CPU Silero and validate playable generated creatives. Browser verification uses the actual accepted manifest, actual served MP4s and a genuine ad-ended event. It writes `browser-evidence.json` and `player.png` next to the manifest. Without `INTERLUDE_MANIFEST`, that browser test is skipped, not claimed passed.

## Architecture and limits

See [architecture](docs/ARCHITECTURE.md), [ADRs](docs/DECISIONS.md), and [execution evidence](docs/VERIFICATION.md). The canonical decisions drive both JSON and playback. No ad times are hard-coded. Model confidence and lexical safety mapping are conservative safeguards, not a guarantee of perfect scene understanding.

The default duration cap remains 300 seconds; full-episode chunking and multi-user authentication remain limitations. Phase 2 includes independent worker heartbeats, VMAP and explicit retention cleanup. UI/visual design is reserved for Phase 3. See [Phase 2 architecture and controls](docs/PHASE2.md).

## Phase 2 evaluation and cleanup

```bash
uv run python -m interlude.evaluate data/samples/indubala_120s.mp4 data/samples/bhojon_bilashi_120s.mp4 --report-dir reports/local
# Full episode inputs are excerpted; selection is recorded in the report.
uv run python -m interlude.evaluate content-sample-assets-folder/indubala_bhaater_hotel.mp4 --clip-start 120 --clip-duration 120
# Dry-run by default; --apply explicitly deletes only expired eligible media.
uv run python -m interlude.cleanup
```

Each accepted breakpoint generates a ±10-second review clip under `reports/inspection/`. Zero-ad runs produce no review clips. Evaluation counts automated policy violations; human ground-truth accuracy requires separate annotation. New safety, memory, ranking, cache and retention settings are listed in `.env.example`.
