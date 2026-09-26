You are the principal engineer for a hackathon project called Interlude.

PROJECT
Interlude — Context-aware multimodal ad placement & intelligent brand matching for long-form media.

We are building Problem Statement 1:

Ingest a long-form Bengali drama, segment it into semantically coherent scenes, score which scene boundaries are safe to interrupt, determine whether an ad break is warranted based on pacing constraints, match each surviving break to the most contextually appropriate synthetic brand, then emit a structured ad-break manifest/debug output and provide a playable demo where the content pauses, the selected ad plays, and the original content resumes.

For this phase, DO NOT build a fancy UI.

The goal is the first complete vertical slice:

VIDEO UPLOAD
→ scene detection
→ Bengali ASR
→ dialogue / silence analysis
→ break candidates
→ Qwen semantic scene understanding
→ WHERE scoring
→ WHETHER rules
→ WHAT / brand matching
→ negative-context hard blocking
→ structured output
→ browser playback:
CONTENT → AD → CONTENT RESUMES

A simple upload/result/player UI is enough.

==================================================
1. FIRST INSPECT THE EXISTING PROJECT
==================================================

Before writing code:

1. Inspect the repository completely.
2. Inspect the `.env` VARIABLE NAMES only.
3. NEVER print, echo, expose, log, commit, reproduce or display any secret values.
4. Confirm the project already has:
   - Qwen3.8-27B API endpoint/configuration
   - MySQL server credentials pointing to an empty database
   - Groq API key
   - Whisper ASR configuration
5. Adapt to the environment variable names already present where possible.
6. Ensure `.env` is ignored by Git.
7. Create `.env.example` containing variable names and safe placeholder/default values only.
8. Check availability of:
   - Python
   - Node.js
   - Git
   - FFmpeg / ffprobe
   - Docker, if installed
9. If FFmpeg or another required local dependency is missing, install/download it where possible without requiring unnecessary global architecture changes.

Do not ask me repeatedly for approval on trivial implementation decisions.
Work autonomously and make sensible engineering choices.

==================================================
2. EXISTING EXTERNAL INFRASTRUCTURE
==================================================

The `.env` already contains configuration for:

A. QWEN MULTIMODAL LLM

Qwen3.8-27B is already hosted externally.

Use the existing endpoint and credentials from `.env`.

Do NOT:
- host Qwen locally
- download Qwen
- change the external Qwen deployment
- invent endpoint URLs
- expose its credentials

Create a provider abstraction:

SemanticVideoProvider

with implementation:

QwenSemanticProvider

If the configured endpoint is OpenAI-compatible, use that protocol.
Otherwise inspect the existing configuration/client requirements and adapt.

Use:
- request timeout
- bounded retry
- exponential backoff
- structured response validation

Qwen must be used as a SEMANTIC PERCEPTION layer.

Qwen should understand:
- what is happening in the scene
- dominant activity
- context
- emotional/narrative state
- sensitive contexts
- whether a meaningful scene/narrative transition occurs

Qwen must NOT be solely responsible for final ad placement decisions.

==================================================
3. MYSQL DATABASE
==================================================

The `.env` already contains credentials for a hosted MySQL server.

The database is currently empty.

You are authorized to:
- connect to it
- create tables
- create indexes
- create migrations
- insert/update/delete application data needed by Interlude

Do NOT:
- create another database server
- introduce PostgreSQL
- introduce vector databases
- introduce RAG

Use:
- SQLAlchemy
- Alembic
- MySQL

Create clean migrations.

Minimum persistence entities:

analysis_jobs
videos
scenes
transcript_segments
break_candidates
break_decisions
brands
creatives
artifacts

Do NOT store MP4/audio/frame binaries inside MySQL.

Store only:
- paths
- metadata
- timestamps
- statuses
- analysis outputs
- scores
- decisions
- brand metadata

==================================================
4. GROQ WHISPER CONFIGURATION
==================================================

The `.env` already contains the Groq API key and Whisper configuration.

Expected configuration conceptually includes:

GROQ_API_KEY
ASR_MODEL=whisper-large-v3
ASR_LANGUAGE=bn
ASR_RESPONSE_FORMAT=verbose_json
ASR_TEMPERATURE=0
ASR_WORD_TIMESTAMPS=true
ASR_SEGMENT_TIMESTAMPS=true
ASR_REQUEST_TIMEOUT_SEC=180
ASR_MAX_RETRIES=3

Do not assume the variable names if existing names differ.
Inspect and reuse the existing configuration.

Use:

whisper-large-v3

NOT the turbo model.

This project prioritizes Bengali ASR quality.

Create an abstraction:

AsrProvider

with implementation:

GroqWhisperProvider

The rest of the application must consume a normalized Transcript model and must not depend directly on raw Groq API response objects.

Required ASR output:

TranscriptSegment:
- start_sec
- end_sec
- Bengali text
- optional word-level timestamps

Use Bengali language hint:
bn

Use timestamp information to help ensure ad breaks never happen mid-dialogue.

If the API fails:
- bounded retries
- clear structured failure
- no fake transcript
- job must fail safely

==================================================
5. LOCAL CPU MODELS / UTILITIES
==================================================

The remaining lightweight components may be downloaded and run locally.

Install/use locally:

A. FFmpeg / ffprobe
Purpose:
- metadata probing
- audio extraction
- frame extraction
- short clip extraction
- placeholder synthetic ad creation
- media processing

B. PySceneDetect
Purpose:
- detect visual shot/scene boundaries

C. Silero VAD
Purpose:
- speech / non-speech detection around candidate timestamps

Download/cache Silero locally.

Run it on CPU.

Do NOT create separate inference servers for these components.

The application should still be modular:

MediaProbeService
SceneDetectionService
VadService
AsrProvider
SemanticVideoProvider
CandidateService
PacingService
BrandMatchingService
ManifestService

==================================================
6. PROJECT STRUCTURE
==================================================

Use a clean production-oriented structure.

Preferred high-level structure:

interlude/
├── apps/
│   ├── web/
│   └── api/
├── data/
│   ├── uploads/
│   ├── work/
│   ├── ads/
│   └── outputs/
├── docs/
├── tests/
├── scripts/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md

Frontend:
- Next.js
- TypeScript

Backend:
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

Keep UI intentionally basic for now.

==================================================
7. CORE DOMAIN CONTRACTS
==================================================

Before implementing pipeline logic, create explicit domain/Pydantic models.

At minimum:

Scene
Transcript
TranscriptSegment
BreakCandidate
SceneSemantics
Brand
Creative
BrandMatch
BreakDecision
AnalysisResult
AnalysisJob

Suggested structures:

Scene:
- id
- start_sec
- end_sec
- duration_sec
- representative_frames

TranscriptSegment:
- start_sec
- end_sec
- text
- optional words

BreakCandidate:
- id
- timestamp_sec
- preceding_scene_id
- following_scene_id
- speech_active
- nearest_speech_start_sec
- nearest_speech_end_sec
- silence_before_sec
- silence_after_sec
- raw_boundary_score
- prefilter_status
- rejection_reasons

SceneSemantics:
- dominant_activity
- contexts[]
- sensitive_contexts[]
- mood[]
- narrative_state_before
- narrative_state_after
- semantic_transition_score
- confidence

Brand:
- brand_id
- display_name
- category
- target_contexts[]
- negative_contexts[]
- creatives[]

BrandMatch:
- brand_id
- eligible
- hard_block_reasons[]
- target_overlap[]
- dominant_activity_match
- contextual_score
- final_score

BreakDecision:
- candidate_id
- timestamp_sec
- accepted
- rejection_reasons[]
- where_score
- whether_pass
- selected_brand_id
- selected_creative_id
- brand_match_score
- debug

Create ONE canonical internal representation.

Future VMAP, debug JSON and browser playback must all derive from the same BreakDecision data.

==================================================
8. BRANDS.JSON
==================================================

The project includes the organizer-provided `brands.json`.

Load it dynamically.

Do not hard-code specific brands anywhere.

ABSOLUTELY DO NOT WRITE LOGIC SUCH AS:

if brand_id == "brand_a":
if brand_id == "brand_b":

The solution must support an unseen ninth brand with ZERO source-code changes.

On startup/import:
- parse brands.json
- validate it
- synchronize brand metadata with MySQL if useful

The complete semantic context vocabulary should be generated dynamically from:

all target_contexts
+
all negative_contexts
+
brand categories

Use this vocabulary to guide Qwen's structured semantic output.

If brands.json contains a new ninth brand, the system must automatically evaluate it.

==================================================
9. VIDEO UPLOAD
==================================================

Implement a basic upload endpoint.

Support MP4 first.

When a user uploads a video:

1. validate input
2. create analysis job ID
3. write it to temporary local storage
4. ffprobe:
   - duration
   - resolution
   - frame rate
   - codec
   - audio presence
5. create database rows
6. begin analysis

Status lifecycle should include something like:

QUEUED
INGESTING
SCENE_DETECTION
TRANSCRIBING
CANDIDATE_GENERATION
SEMANTIC_ANALYSIS
BREAK_OPTIMIZATION
BRAND_MATCHING
COMPLETED
FAILED

Persist current stage and meaningful errors.

For the initial vertical slice, use a short approximately 2-minute source video.

Do not optimize for 45-minute episodes yet, but design the pipeline so it can later scale to them.

==================================================
10. SCENE / SHOT DETECTION
==================================================

Use PySceneDetect to produce candidate visual boundaries.

Store scenes such as:

scene_001
start_sec
end_sec

Extract representative frames around promising boundaries using FFmpeg.

Do NOT send the entire video frame-by-frame to Qwen.

The architecture should be:

full video
→ cheap deterministic preprocessing
→ candidate boundaries
→ Qwen only on selected local windows

This is an important optimization.

==================================================
11. AUDIO EXTRACTION + ASR
==================================================

Use FFmpeg to extract mono speech-friendly audio.

Call Groq Whisper Large V3.

Preserve Bengali text.

Normalize returned data into Transcript / TranscriptSegment objects.

Implement utilities such as:

is_speech_active(timestamp)

nearest_speech_start(timestamp)

nearest_speech_end(timestamp)

silence_before(timestamp)

silence_after(timestamp)

Combine ASR timestamps with Silero VAD.

Primary safety requirement:

MID-DIALOGUE BREAKS MUST BE REJECTED.

If ASR says speech spans a boundary:
reject candidate.

If VAD says speech is active:
reject candidate or mark unsafe.

If signals are ambiguous:
prefer rejection.

The system should be conservative.

==================================================
12. BREAK CANDIDATE GENERATION
==================================================

Candidates originate from detected scene / shot boundaries.

No hard-coded timestamps.

For each boundary, build a BreakCandidate.

Before invoking Qwen, cheaply reject obviously poor candidates using:

- active speech
- insufficient dialogue separation
- extremely short surrounding scenes
- duplicate/nearby boundaries
- obviously poor visual cuts
- other sensible cheap rules

Do not delete rejected candidates from debugging.

Store:
- accepted-for-analysis candidates
- rejected candidates
- exact rejection reasons

==================================================
13. QWEN SEMANTIC ANALYSIS
==================================================

For every surviving candidate, create a local window around the boundary.

Start with roughly:

5 seconds before
+
5 seconds after

Sample frames sparsely.

Target approximately:
1–2 FPS

Include exact frame timestamps.

Also include transcript around the same window.

Do NOT prompt Qwen:

"Where should I place an ad?"

Instead ask for structured semantic perception.

Required output:

{
  "dominant_activity": "...",
  "contexts": [...],
  "sensitive_contexts": [...],
  "mood": [...],
  "narrative_state_before": "...",
  "narrative_state_after": "...",
  "semantic_transition_score": 0.0-1.0,
  "confidence": 0.0-1.0
}

Where possible, contexts should use the vocabulary dynamically derived from brands.json.

Qwen may identify additional sensitive concepts when required, but normalized output should be mapped safely.

Use strict JSON / structured output if supported.

Validate with Pydantic.

If invalid:
- retry in a bounded manner

If Qwen ultimately fails:
- candidate must be rejected as uncertain
- never approve an ad placement merely because semantic inference failed

==================================================
14. WHERE ENGINE
==================================================

The problem asks:

WHERE:
Is this timestamp a natural, non-jarring place to cut?

Implement this independently.

Combine explainable components such as:

- visual boundary confidence
- dialogue safety
- silence
- semantic/narrative transition

Weights should be configurable.

Example conceptual structure:

where_score =
  boundary_weight * boundary_score
+ dialogue_weight * dialogue_safety
+ silence_weight * silence_score
+ semantic_weight * semantic_transition_score

Do NOT blindly implement those exact weights without considering signal ranges.

Store every component separately.

IMPORTANT:

A high Qwen semantic score MUST NOT override active dialogue.

Dialogue safety is effectively a hard safety condition.

==================================================
15. WHETHER ENGINE
==================================================

The problem asks:

WHETHER:
Should an ad break happen here at all?

Implement deterministic pacing constraints.

Config should support:

MAX_BREAKS_PER_HOUR
MIN_BREAK_GAP_SEC
MAX_AD_LOAD_PERCENT

Use sensible development defaults and make them configurable.

Rules:
- enforce minimum gap between accepted breaks
- enforce max breaks/hour
- enforce total/projected ad-load percentage
- do not force a break just because a candidate exists

It is valid for the system to return:
NO AD BREAK

==================================================
16. WHAT / BRAND MATCHING
==================================================

The problem asks:

WHAT:
Which brand belongs in this slot?

Dominant scene activity must matter strongly.

NEGATIVE CONTEXTS ARE A HARD BLOCK.

This is critical.

Algorithm:

STEP 1:
Evaluate brand eligibility.

Determine whether scene semantics conflict with brand.negative_contexts.

If any meaningful negative conflict exists:

brand.eligible = false

record exact reason

DO NOT merely subtract score.

DO NOT allow relevance to override a negative-context block.

Example:

scene:
funeral + grief

food brand:
target = family/eating
negative = funeral/grief

RESULT:
HARD BLOCK

regardless of positive similarity.

STEP 2:
Rank ONLY eligible brands.

Use explainable factors:

- dominant activity match
- target_context overlap
- category relevance
- contextual relevance

Keep matching generic and data-driven.

If no brand is safely eligible:
return NO_AD for that slot.

==================================================
17. SYNTHETIC AD CREATIVE GENERATION
==================================================

The organizers confirmed that:

- creative paths in brands.json are indicative
- participants may create their own brands/creatives
- real company names must NOT be substituted

Therefore create a development utility that automatically generates simple synthetic video creatives from brands.json when the referenced MP4 does not exist.

Do NOT manually hard-code eight separate videos.

Generate them programmatically.

For each brand:
- synthetic brand display name only
- category
- neutral branded background
- simple text
- 5–10 second MP4 is sufficient for Phase 1
- use FFmpeg / generated frames / another lightweight deterministic method

Store under:

data/ads/<brand_id>/

If a ninth brand appears:
the same generator should be capable of generating a fallback creative automatically.

The quality only needs to be sufficient to demonstrate:

CONTENT
→ SYNTHETIC AD
→ CONTENT

Do not spend excessive time designing ads.

==================================================
18. STRUCTURED OUTPUT
==================================================

Generate:

analysis.json

and:

debug.json

Minimum `analysis.json` structure:

{
  "video": {
    ...
  },
  "summary": {
    "scene_count": ...,
    "candidate_count": ...,
    "accepted_break_count": ...
  },
  "ad_breaks": [
    {
      "timestamp_sec": ...,
      "brand_id": "...",
      "creative_id": "...",
      "creative_url": "...",
      "where": {...},
      "whether": {...},
      "what": {...}
    }
  ]
}

debug.json must include:

- scenes
- transcript segments
- all candidates
- rejected candidates
- rejection reasons
- Qwen semantic output
- WHERE component scores
- WHETHER rules
- every brand considered
- hard-blocked brands
- hard-block reasons
- selected brand
- creative
- errors/fallbacks if any

The debug output should make the decision auditable.

==================================================
19. VMAP
==================================================

VMAP is part of the original problem statement.

However, the organizers explicitly confirmed that structured JSON may be used instead if VMAP is unfamiliar.

For the vertical slice:

PRIORITY:
analysis.json + debug.json + playable demo

If the core system is working and VMAP serialization is straightforward, also generate:

manifest.vmap

Do NOT delay the working vertical slice because of VMAP.

Architect ManifestService so VMAP can be added cleanly.

==================================================
20. MINIMAL WEB UI
==================================================

DO NOT make a polished UI.

No Impeccable yet.

Build only what is needed to prove the vertical slice.

Page should include:

1. video upload
2. Analyze button
3. current job status
4. basic analysis summary
5. list of accepted/rejected candidates
6. selected brand
7. raw/formatted analysis JSON
8. basic video player

The UI may be visually plain.

Functional correctness matters more than styling.

==================================================
21. PLAYABLE DEMO
==================================================

This is mandatory.

The browser player must:

1. load the source content video
2. load accepted ad-break decisions
3. play the source normally
4. when currentTime reaches an accepted break:
   - capture exact resume position
   - pause source content
   - play selected synthetic ad
5. when ad ends:
   - restore source content
   - resume automatically from the correct position

Track played breaks in the session.

Do not replay the same ad break repeatedly if the playback time oscillates.

Handle seeking reasonably.

The MVP proof is:

CONTENT PLAYS
→ REACHES BREAK
→ CONTENT PAUSES
→ SELECTED AD PLAYS
→ AD ENDS
→ CONTENT RESUMES

Do not simply show a timestamp and call that a demo.

==================================================
22. API
==================================================

Provide a clean minimal API.

Suggested:

POST /api/videos
POST /api/videos/{video_id}/analyze
GET /api/jobs/{job_id}
GET /api/videos/{video_id}/analysis
GET /api/videos/{video_id}/debug
GET /api/brands
GET /health
GET /ready

Adapt if a cleaner REST structure emerges.

Health:
process alive.

Ready:
check safely where practical:

- database
- ffmpeg
- brands.json
- Groq configuration
- Qwen configuration

Never expose secrets in health endpoints.

==================================================
23. FILE STORAGE
==================================================

Use local filesystem for Phase 1.

Configurable paths:

data/uploads
data/work
data/ads
data/outputs

Uploaded source videos are temporary.

Do NOT store source videos permanently in MySQL.

Keep generated synthetic ad creatives persistently.

Cleanup:
- extracted audio
- temporary frames
- temporary candidate clips

after processing where safe.

Do not delete the source video before the browser demo can use it.

==================================================
24. PRODUCTION ENGINEERING REQUIREMENTS
==================================================

Even though the UI is basic, the code should be production-quality.

Use:

- typed settings/configuration
- Pydantic validation
- clean service boundaries
- dependency injection where useful
- structured logging
- safe filenames
- upload validation
- explicit job state machine
- timeouts
- bounded retries
- database migrations
- transactions where appropriate
- indexes where useful
- deterministic temp-file cleanup
- clean exception handling
- clear external-provider abstractions

No 1000-line route handlers.

Do not put all pipeline logic in a single endpoint.

==================================================
25. SAFETY / CONSERVATIVE DECISION POLICY
==================================================

This challenge strongly penalizes:

- mid-dialogue cuts
- negative-context violations

Therefore adopt this general policy:

UNCERTAIN => REJECT

Examples:

Qwen unavailable:
reject semantic candidate

ASR/VAD disagree substantially:
reject candidate

brand has negative-context conflict:
hard reject brand

no safely eligible brand:
NO_AD

pacing constraint violated:
reject break

Do not optimize for maximum number of ads.

Optimize for safe, defensible placements.

==================================================
26. TESTS
==================================================

Add meaningful tests.

Required:

test_active_dialogue_boundary_is_rejected

test_vad_speech_boundary_is_rejected

test_safe_boundary_can_survive_prefilter

test_negative_context_is_hard_block

test_positive_relevance_cannot_override_negative_block

test_new_ninth_brand_is_loaded_without_source_change

test_no_eligible_brand_returns_no_ad

test_minimum_break_gap_is_enforced

test_max_breaks_per_hour_is_enforced

test_max_ad_load_is_enforced

test_qwen_failure_rejects_candidate_safely

test_invalid_qwen_json_is_not_trusted

test_analysis_output_schema_is_valid

test_generated_fallback_creative_exists

Also create at least one integration/smoke test:

short real MP4
→ analysis pipeline
→ analysis result

If feasible, test player state logic:

content time reaches break
→ switch to ad
→ ad ends
→ resume stored content position

==================================================
27. GIT / COMMIT DISCIPLINE
==================================================

Maintain a clean Git history.

Do not build everything and make one giant commit.

Make real commits as milestones become working.

Suggested sequence:

chore: initialize Interlude application structure

feat(core): define analysis and decision contracts

feat(db): add MySQL persistence and migrations

feat(video): add media probing and scene detection

feat(speech): integrate Bengali Whisper transcription and VAD

feat(engine): generate dialogue-safe break candidates

feat(ai): add structured Qwen scene semantics

feat(engine): score natural interruption boundaries

feat(engine): enforce pacing and ad-load constraints

feat(brands): add dynamic matching and negative-context blocks

test(brands): cover unseen brands and hard exclusions

feat(ads): generate synthetic fallback creatives

feat(api): expose analysis workflow

feat(player): add content-to-ad-to-content playback

test: add vertical-slice smoke coverage

docs: document Phase 1 architecture

Only commit a milestone after it reasonably works.

Do not fabricate meaningless commits.

==================================================
28. README
==================================================

Create/update README with:

# Interlude

Context-aware multimodal ad placement & intelligent brand matching for long-form media.

Document:

- what it does
- current Phase 1 scope
- architecture
- external services
- local CPU dependencies
- environment variable NAMES
- setup
- MySQL migration
- running backend
- running frontend
- running tests
- sample analysis flow

Do NOT include any real credential.

==================================================
29. ARCHITECTURE DOCUMENTATION
==================================================

Create:

docs/ARCHITECTURE.md

and:

docs/DECISIONS.md

Document at least:

ADR-001
Candidate-first VLM processing rather than sending the entire episode to Qwen.

ADR-002
Qwen is semantic perception; deterministic code owns policy decisions.

ADR-003
Negative brand contexts are hard exclusions, not score penalties.

ADR-004
Brand definitions are data-driven to support unseen brands.

ADR-005
Uploaded video is temporary media, not database content.

ADR-006
Dynamic player ad insertion is used instead of permanently rendering ads into the source episode.

==================================================
30. DEFINITION OF DONE
==================================================

DO NOT tell me "done" merely because code was written.

The vertical slice is complete only if you ACTUALLY execute:

REAL SHORT MP4
↓
UPLOAD
↓
MEDIA PROBE
↓
SCENE DETECTION
↓
BENGALI WHISPER ASR
↓
SILERO VAD
↓
CANDIDATE GENERATION
↓
QWEN SEMANTIC ANALYSIS
↓
WHERE
↓
WHETHER
↓
BRAND HARD-BLOCK FILTER
↓
BRAND RANKING
↓
ANALYSIS.JSON
↓
DEBUG.JSON
↓
BROWSER PLAYER
↓
CONTENT
↓
AD
↓
CONTENT RESUMES

At completion:

1. run database migrations
2. run tests
3. run one real end-to-end smoke test
4. report:
   - scenes detected
   - candidates generated
   - candidates rejected before Qwen
   - semantic candidates analyzed
   - accepted ad breaks
   - selected brands
   - output file paths
5. report failures honestly
6. do not claim parts worked if they were not executed

==================================================
31. CURRENT PRIORITIES
==================================================

Priority order:

1. Working pipeline
2. Mid-dialogue safety
3. Negative-context safety
4. Dynamic unseen-brand support
5. Playable content → ad → content
6. Structured JSON/debug output
7. Tests
8. Clean code
9. Basic UI
10. VMAP if time remains

DO NOT work on visual polish yet.

DO NOT add unnecessary architecture.

DO NOT add RAG.

DO NOT add vector search.

DO NOT introduce more foundation models unless there is a clearly demonstrated need.

Build the smallest production-quality system that genuinely satisfies this vertical slice.

