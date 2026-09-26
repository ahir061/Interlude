You are continuing development of my project, Interlude.

Interlude is a context-aware multimodal ad-placement and intelligent brand-matching system for long-form media.

PHASE 1 IS ALREADY COMPLETE AND WORKING.

==================================================
CURRENT PHASE 1 STATE
==================================================

Repository:
https://github.com/ahir061/Interlude

Current completed branch:
feat/phase1

Phase 1 currently implements:

Video upload
→ MP4 validation
→ PySceneDetect
→ Groq Whisper Large V3 Bengali ASR
→ Silero VAD
→ dialogue-proximity filtering
→ surviving frame windows + transcript sent to hosted Qwen
→ interruption scoring
→ pacing enforcement
→ brand matching
→ analysis.json
→ debug.json
→ playable content → ad → content resume

Current stack:

- FastAPI
- Next.js basic frontend/player
- MySQL
- Groq Whisper Large V3
- Hosted Qwen multimodal model
- PySceneDetect
- Silero VAD
- FFmpeg / ffprobe

Current verified real-video run:

Scenes: 20
Candidates: 19
Rejected before Qwen: 18
Qwen candidates analyzed: 1
Accepted ads: 1
Selected: Brand D @ 58.84 seconds

Current tests already passing:

- 39 Python tests
- 4 player tests
- 1 browser test
- lint
- TypeScript
- production frontend build

The player has already been browser-verified to perform:

content → ad → content resumes

without replaying the same advertisement.

MySQL migrations already exist.

Documentation already exists.

Preserve all Phase 1 functionality.

==================================================
FIRST ACTION: CREATE PHASE 2 BRANCH
==================================================

DO NOT WORK DIRECTLY ON feat/phase1.

Create:

feat/phase2

from the latest feat/phase1 state.

Run the equivalent of:

git checkout feat/phase1
git pull
git checkout -b feat/phase2

Do NOT merge into main.

Do NOT modify feat/phase1.

Work exclusively on feat/phase2.

At the end:

git push -u origin feat/phase2

==================================================
IMPORTANT: NO UI WORK IN PHASE 2
==================================================

Do NOT redesign the frontend.

Do NOT use Impeccable.

Do NOT spend time on visual polish.

Do NOT replace the frontend framework.

The existing basic frontend/player should remain only as a functional regression-testing surface.

UI/UX is Phase 3.

Phase 2 is entirely about:

- intelligence quality
- semantic scene quality
- dialogue safety
- contextual safety
- brand matching correctness
- pacing optimization
- VMAP
- evaluation
- Docker
- reliability
- reproducibility
- production engineering

==================================================
HACKATHON REQUIREMENTS WE MUST OPTIMIZE FOR
==================================================

The required MVP is:

Video in
→ scenes segmented
→ break candidates scored
→ brand matched
→ must generalize to a 9th unseen brand with ZERO source-code changes
→ VMAP manifest
→ debug JSON
→ playable demo that actually cuts to the ad and resumes

The hardest evaluation intentionally punishes naive approaches.

Held-out videos will test:

1. Mid-dialogue cuts.
2. Bad semantic scene segmentation.
3. Poor / naive breakpoint scoring.
4. Incorrect contextual brand matching.
5. Negative-context violations.
6. Generalization to unseen brands.

A negative-context violation is catastrophic.

For example:

funeral / grief scene
→ food brand

must NEVER happen.

Auto-disqualifying behavior includes:

- hard-coded timestamps
- hard-coded sample-specific brand assignments
- negative-context violations
- broken live demo
- replacing synthetic brands with real brands

CORE PRINCIPLE:

IF UNCERTAIN, DO NOT PLACE AN AD.

Precision is more important than recall.

A false positive ad placement is substantially worse than missing a possible ad opportunity.

==================================================
PHASE 2 TARGET ARCHITECTURE
==================================================

The target backend/media pipeline should become approximately:

VIDEO
  ↓
Media ingestion
FFmpeg / ffprobe
  ↓
────────────────────────────────────
VISUAL                        AUDIO
────────────────────────────────────
Shot detection               Whisper ASR
Raw cuts                     Silero VAD
  │                            │
  └─────────────┬──────────────┘
                ↓
       SEMANTIC SCENE BUILDER
                ↓
       BREAK CANDIDATE ENGINE
                ↓
       DIALOGUE SAFETY GATE
                ↓
        unsafe → HARD REJECT
                ↓
         QWEN SEMANTICS
                ↓
activity / mood / context / narrative transition /
sensitive context / dialogue continuity
                ↓
          CONTEXT MEMORY
                ↓
           WHERE ENGINE
                ↓
      BRAND ELIGIBILITY ENGINE
                ↓
   negative contexts → HARD BLOCK
                ↓
          BRAND RANKING
                ↓
     FINAL BRAND SAFETY CHECK
                ↓
      GLOBAL BREAK OPTIMIZER
                ↓
 max-breaks/hour / min-gap / ad-load
                ↓
           FINAL BREAKS
                ↓
        ┌───────┼────────┐
        ↓       ↓        ↓
 analysis   debug      VMAP
  JSON      JSON        XML
        │
        ↓
existing playable content → ad → content flow

==================================================
TASK 1 — SEMANTIC SCENE SEGMENTATION
==================================================

Phase 1 currently uses PySceneDetect boundaries.

Harden this.

DO NOT assume:

shot boundary == semantic scene boundary.

Example:

man speaking
→ camera cuts to woman
→ camera cuts back to man

This may be THREE shots but ONE semantic conversation scene.

Build a semantic scene grouping layer.

Persist both:

raw shots
semantic scenes

Use signals including:

- dialogue continuity
- transcript continuity
- temporal proximity
- visual continuity
- characters / activity continuity
- location continuity where inferable
- Qwen semantic adjudication only where useful

Expected behavior:

camera-angle switches during the same conversation
→ same semantic scene

genuine location / narrative transition after completed dialogue
→ new semantic scene

rapid montage
→ should not blindly create one ad opportunity per cut

Add regression tests for these cases.

==================================================
TASK 2 — HARDEN DIALOGUE SAFETY
==================================================

This is one of the most important Phase 2 tasks.

For every candidate timestamp T, compute and persist:

- speech_active_at_cut
- last_speech_end_before_cut
- first_speech_start_after_cut
- silence_before_cut
- silence_after_cut
- ASR segment crossing boundary
- VAD region crossing boundary
- semantic dialogue continuity

Do not rely only on "ASR segment ended nearby."

Add configuration-driven dialogue safety policy.

Example structure:

dialogue_safety:
  min_pre_cut_silence_ms: 450
  min_post_cut_silence_ms: 450
  reject_if_speech_crosses_boundary: true
  reject_if_dialogue_continues_semantically: true

These values should be tunable from configuration rather than scattered as magic numbers.

Protect against cases like:

"Where are you—"
[short pause]
"—going?"

A brief silence inside a sentence or ongoing conversation must NOT become an ad breakpoint.

Use:

ASR
+
VAD
+
semantic dialogue continuity

Hard reject unsafe cuts.

==================================================
TASK 3 — SENSITIVE CONTEXT MEMORY
==================================================

This is critical for negative-context safety.

Do not evaluate brand safety using only the exact scene at the cut.

Example:

Scene 1:
funeral / death / grief

Scene 2:
family walking outside after funeral

A naive matcher could see:

family

and choose a food brand.

That must not happen.

Implement context carryover.

Each candidate should have access to:

- current contexts
- current sensitive contexts
- recent sensitive contexts
- how recently each sensitive context occurred
- whether that context is narratively continuing

Example internal representation:

{
  "current_contexts": ["family", "walking"],
  "current_sensitive_contexts": [],
  "recent_sensitive_contexts": [
    {
      "context": "funeral",
      "last_seen_sec": 812.4,
      "distance_sec": 12.8
    },
    {
      "context": "grief",
      "last_seen_sec": 817.2,
      "distance_sec": 8.0
    }
  ]
}

Sensitive contexts may include things such as:

funeral
death
grief
hospital
medical emergency
violence
accident
injury
illness
financial distress

Use both:

- semantic carryover
- configurable temporal safety windows

Do not instantly forget a sensitive context because the camera changes.

==================================================
TASK 4 — STRICT QWEN CONTRACT
==================================================

Qwen is the semantic perception layer.

Qwen must NOT make the final ad-placement decision.

DO NOT prompt:

"Where should an ad go?"

Instead require strict structured semantics.

Return fields equivalent to:

{
  "dominant_activity": "video call",
  "contexts": [
    "phone",
    "communication",
    "family conversation"
  ],
  "sensitive_contexts": [],
  "mood": ["calm"],
  "narrative_state": "scene_concluding",
  "dialogue_continuity": "completed",
  "transition_type": "location_change",
  "transition_confidence": 0.91,
  "evidence": [
    {
      "timestamp_sec": 57.3,
      "observation": "conversation concludes"
    }
  ]
}

Use deterministic / low-temperature generation where supported.

Prefer:

temperature = 0

Validate Qwen responses using Pydantic.

Behavior:

malformed response
→ retry once

still malformed
→ reject candidate safely

Never silently invent missing required fields.

Persist:

- model identifier
- prompt version
- confidence
- evidence
- request duration

==================================================
TASK 5 — DYNAMIC BRAND CONTEXT VOCABULARY
==================================================

The brand system must remain entirely data-driven.

Build context vocabulary dynamically from the loaded catalogue:

all target_contexts
+
all negative_contexts

Do not create static enums containing only Brand A–H concepts.

If Brand I introduces:

gym
running
exercise
injury

those concepts must automatically become available to semantic analysis.

No source-code changes should be required.

==================================================
TASK 6 — HARD GATES BEFORE WHERE SCORING
==================================================

Refactor breakpoint evaluation into:

1. HARD GATES
2. QUALITY SCORE

A high numeric score must never override an unsafe condition.

Appropriate hard rejection examples:

- speech active
- speech crosses candidate boundary
- semantic dialogue continues
- clearly not a semantic scene boundary
- semantic model output invalid
- semantic confidence below safety threshold

Only surviving candidates receive a WHERE quality score.

Use configurable weights for soft scoring.

Possible factors:

semantic transition
dialogue completion
silence quality
visual boundary quality
narrative closure

Persist every component in debug.json.

==================================================
TASK 7 — BRAND ELIGIBILITY BEFORE RANKING
==================================================

Refactor brand matching into two explicit stages:

STAGE A:
eligibility

STAGE B:
ranking

Eligibility must happen first.

Compare:

current sensitive contexts
+
recent sensitive contexts

against:

brand.negative_contexts

If any hard conflict exists:

eligible = false

That brand must NOT receive a ranking score.

Represent this explicitly in debug output:

{
  "brand_id": "brand_a",
  "eligible": false,
  "hard_blocks": [
    "funeral",
    "grief"
  ]
}

Negative context is NOT a soft penalty.

Negative context is a HARD BLOCK.

==================================================
TASK 8 — DOMINANT ACTIVITY MUST DOMINATE BRAND MATCHING
==================================================

The problem statement explicitly says:

dominant scene activity wins.

Make this structurally true.

Example:

dominant activity:
driving

secondary contexts:
phone
family conversation
travel

Automotive should generally outrank telecom because driving is dominant.

Use explicit, configurable weighting.

A reasonable starting concept could be:

55% dominant activity
25% target-context overlap
15% category semantic similarity
5% secondary context relevance

Do not assume these exact values are optimal.

Tune using actual evaluation.

Persist the entire score breakdown.

==================================================
TASK 9 — SECOND-PASS BRAND SAFETY VERIFIER
==================================================

Because negative-context violations are catastrophic, add one final verification layer for the selected brand.

For the top brand candidate evaluate:

- scene context
- recent sensitive context
- representative frames
- transcript window
- brand negative contexts

Use Qwen sparingly here if useful.

Return one of:

SAFE
BLOCKED
UNCERTAIN

Behavior:

SAFE
→ proceed

BLOCKED
→ eliminate and try next eligible brand

UNCERTAIN
→ eliminate and try next eligible brand

Never treat UNCERTAIN as SAFE.

Persist verifier evidence.

==================================================
TASK 10 — FIRST-CLASS NO-AD DECISION
==================================================

Interlude must be allowed to output:

NO AD

Valid rejection reasons should include:

unsafe_dialogue
weak_transition
pacing_violation
no_safe_brand
semantic_uncertainty
model_failure
ad_load_limit
negative_context_conflict

An episode may legitimately contain zero advertisements.

Never force an ad merely to satisfy output count.

==================================================
TASK 11 — GLOBAL EPISODE-LEVEL BREAK OPTIMIZER
==================================================

Do not greedily select candidates independently.

After safe candidates are available, optimize the overall episode schedule.

Constraints:

- minimum gap between advertisements
- maximum breaks per hour
- maximum ad-load percentage
- episode duration
- selected creative duration
- candidate quality

The goal should maximize total placement quality while satisfying all constraints.

A deterministic algorithm such as:

dynamic programming
beam search
or another lightweight combinatorial optimizer

is sufficient.

Avoid unnecessary heavyweight dependencies.

Persist:

- why a candidate was selected
- why another strong candidate was skipped
- which global constraint caused the outcome

==================================================
TASK 12 — CREATIVE SELECTION
==================================================

The supplied catalogue contains creative durations such as:

15 seconds
20 seconds
30 seconds

Creative selection must consider:

- remaining ad-load allowance
- pacing policy
- available creative durations
- slot feasibility

Do NOT blindly use the first creative.

Continue supporting generated placeholder ads because real creatives were not provided.

For unseen brands with no supplied creative:

generate a simple neutral synthetic placeholder automatically.

Never substitute any real-world brand.

==================================================
TASK 13 — UNSEEN BRAND I REGRESSION TEST
==================================================

Create an automated runtime regression test using something like:

{
  "brand_id": "brand_i",
  "display_name": "Brand I",
  "category": "sports/fitness",
  "target_contexts": [
    "running",
    "exercise",
    "gym",
    "sports"
  ],
  "negative_contexts": [
    "injury",
    "hospital"
  ],
  "creatives": []
}

Verify:

data-only Brand I insertion
→ catalogue reload
→ vocabulary updates
→ Brand I participates in matching
→ negative-context rules apply
→ fallback creative generated
→ NO source-code modifications

This test must exist in the automated suite.

==================================================
TASK 14 — IMPROVE analysis.json AND debug.json
==================================================

analysis.json should remain compact and consumer-friendly.

debug.json should become deeply explainable.

For each candidate include information equivalent to:

{
  "timestamp_sec": 58.84,

  "scene": {
    "before": "scene_004",
    "after": "scene_005"
  },

  "where": {
    "accepted": true,
    "score": 0.917,
    "speech_active": false,
    "silence_before_sec": 0.72,
    "silence_after_sec": 1.47,
    "dialogue_continuity": "completed",
    "semantic_transition": 0.94
  },

  "whether": {
    "accepted": true,
    "previous_break_gap_sec": null,
    "breaks_this_hour": 0,
    "projected_ad_load": 0.006
  },

  "semantics": {
    "dominant_activity": "video call",
    "contexts": [
      "phone",
      "communication"
    ],
    "sensitive_contexts": [],
    "recent_sensitive_contexts": [],
    "confidence": 0.95
  },

  "brands": [
    {
      "brand_id": "brand_a",
      "eligible": true,
      "score": 0.12
    },
    {
      "brand_id": "brand_d",
      "eligible": true,
      "score": 0.91
    }
  ],

  "decision": {
    "accepted": true,
    "brand_id": "brand_d",
    "creative_id": "d_20s_bn"
  }
}

Also include run-level metadata:

pipeline_version
policy_version
prompt_version
catalogue_hash
Qwen call count
semantic cache hits
semantic cache misses
processing timings

==================================================
TASK 15 — IMPLEMENT VMAP
==================================================

VMAP is required for Phase 2.

Use the SAME normalized final BreakDecision objects used by:

analysis.json
debug.json
player

Architecture:

BreakDecision[]
    ├── analysis.json
    ├── debug.json
    └── VMAPSerializer
             ↓
       manifest.vmap.xml

Do NOT create separate placement logic for VMAP.

Create an isolated VMAP serializer module/class.

Add tests ensuring:

VMAP accepted break count
==
analysis.json accepted break count

VMAP timestamps
==
analysis.json timestamps

VMAP brand / creative references
==
final normalized decisions

The existing player may continue consuming normalized JSON.

VMAP is an export/standards integration format.

==================================================
TASK 16 — BUILD EVALUATION HARNESS
==================================================

Create a CLI such as:

python -m interlude.evaluate

or equivalent.

It should run supplied videos and generate:

reports/evaluation.json
reports/evaluation.md

For each video report actual measured:

- duration
- raw shot count
- semantic scene count
- raw candidate count
- dialogue safety rejections
- semantic rejections
- Qwen calls
- semantic cache hits
- accepted breaks
- processing time
- ads/hour
- ad-load percentage
- detected mid-dialogue violations
- negative-context violations

DO NOT fabricate metrics.

Only report real execution results.

==================================================
TASK 17 — GENERATE HUMAN INSPECTION CLIPS
==================================================

For every accepted breakpoint, automatically generate an FFmpeg review clip approximately:

10 seconds before
+
break boundary
+
10 seconds after

Save under something similar to:

reports/inspection/<video>/<break-id>.mp4

The goal is to allow rapid blind manual inspection of every accepted ad placement.

Do not retain unnecessary intermediate frames forever.

==================================================
TASK 18 — ADVERSARIAL TEST SUITE
==================================================

Add tests targeting likely held-out failures.

Must cover at least:

1. Short pause inside ongoing sentence
→ reject.

2. Camera angle change during same conversation
→ same semantic scene / no naive breakpoint.

3. Dialogue completes followed by genuine location transition
→ may survive as candidate.

4. Funeral followed immediately by family outside
→ food/spice brand remains blocked.

5. Grief context carryover
→ inappropriate brands blocked.

6. Accident followed by road/driving scene
→ automotive remains blocked while sensitive context is active.

7. Hospital scene
→ applicable brands blocked.

8. Video call scene
→ telecom strongly relevant.

9. Driving scene with phone usage
→ automotive should beat telecom when driving is dominant.

10. Shopping/payment scene
→ e-commerce / fintech appropriately considered.

11. No eligible brand
→ NO AD.

12. Brand I dynamically inserted
→ works without source changes.

13. Malformed Qwen JSON
→ candidate rejected safely.

14. Qwen timeout
→ candidate rejected safely.

15. ASR failure
→ safe job failure / no unsafe ad decision.

16. ASR/VAD disagreement
→ conservative result.

17. Missing creative
→ generated synthetic fallback.

18. Global pacing conflict
→ optimizer chooses valid schedule.

==================================================
TASK 19 — SEMANTIC QWEN CACHE
==================================================

Avoid recomputing identical Qwen requests.

Generate deterministic cache keys using relevant inputs such as:

- video content hash
- candidate timestamp
- sampled-frame hashes
- transcript window
- catalogue hash
- prompt version
- model version

Cache ONLY validated structured semantic responses.

Track:

Qwen requests
cache hits
cache misses

Do not cache malformed/error responses.

==================================================
TASK 20 — EXTERNAL SERVICE RESILIENCE
==================================================

Every external service call must have:

- timeout
- bounded retry
- structured error
- conservative failure behavior

Especially:

- Qwen
- Groq
- MySQL

Never allow:

Qwen failed
→ automatically approve candidate

Correct behavior:

Qwen unavailable / uncertain
→ reject candidate / abstain

==================================================
TASK 21 — JOB IDEMPOTENCY AND RECOVERY
==================================================

Harden persisted jobs.

Ensure:

- same job cannot accidentally process twice
- crashed PROCESSING jobs can be detected/recovered safely
- COMPLETED jobs do not rerun unexpectedly
- artifact generation is idempotent
- partial outputs cannot appear as completed analysis
- failed jobs store useful structured failure information

Use clear state transitions such as:

QUEUED
PROCESSING
COMPLETED
FAILED

Also persist current processing stage.

==================================================
TASK 22 — STRUCTURED LOGGING
==================================================

Use structured operational logs.

Examples:

{
  "event": "candidate_rejected",
  "job_id": "...",
  "timestamp_sec": 58.84,
  "reason": "dialogue_continuation"
}

{
  "event": "brand_hard_blocked",
  "job_id": "...",
  "brand_id": "brand_a",
  "contexts": [
    "funeral",
    "grief"
  ]
}

Include correlation/job IDs.

Never log API keys, tokens, database credentials, or secrets.

==================================================
TASK 23 — HEALTH / READINESS
==================================================

Provide:

GET /health
GET /ready

/health:
process liveness.

/ready:
verify critical local/runtime dependencies including:

- MySQL reachable
- FFmpeg installed
- ffprobe installed
- brand catalogue loads
- configuration valid

External AI dependencies may be reported separately rather than unnecessarily making readiness fail.

==================================================
TASK 24 — STARTUP ENVIRONMENT VALIDATION
==================================================

Fail fast during startup for critical bad configuration.

Detect things like:

missing Qwen endpoint
missing Groq key
invalid DB configuration
missing FFmpeg
missing ffprobe
invalid brand JSON
unwritable media/output directories

Update .env.example.

Never commit secrets.

==================================================
TASK 25 — FULL DOCKER VERIFICATION
==================================================

Phase 1 already has Docker config but it is UNTESTED.

Phase 2 must actually verify Docker.

Desired setup should be close to:

git clone ...
cp .env.example .env
docker compose up --build

Containerize current:

- FastAPI API
- processing worker
- existing basic frontend/player

Existing MySQL, Qwen, and Groq may remain external.

Persist appropriate directories through volumes:

/data/uploads
/data/ads
/data/outputs

Add:

- healthchecks
- graceful shutdown
- non-root execution where practical
- sensible restart behavior

Most importantly:

RUN A REAL VIDEO THROUGH THE PIPELINE INSIDE DOCKER.

Do not mark Docker as complete merely because images build.

==================================================
TASK 26 — TEMPORARY MEDIA CLEANUP
==================================================

Implement safe cleanup policies.

Temporary:

- uploads
- extracted audio
- sampled frames
- intermediate clips

Persistent:

- synthetic ad catalogue
- final analysis artifacts
- VMAP
- necessary reports

Never delete media belonging to an active job.

Cleanup behavior must be testable/configurable.

==================================================
TASK 27 — PERFORMANCE INSTRUMENTATION
==================================================

Measure actual stage durations:

- upload validation
- shot detection
- semantic scene grouping
- ASR
- VAD
- candidate filtering
- Qwen semantic analysis
- brand matching
- brand safety verification
- global optimization
- artifact generation
- total runtime

Persist and expose these in evaluation/debug output.

Do not optimize based on guesses.

==================================================
TASK 28 — DOCUMENTATION
==================================================

Update/create:

docs/ARCHITECTURE.md
docs/PHASE2.md
docs/EVALUATION.md
docs/DECISIONS.md
docs/VERIFICATION.md

Explain:

- raw shots vs semantic scenes
- Qwen as semantic perception rather than decision authority
- why hard gates precede scoring
- why negative contexts are eligibility constraints
- why sensitive context carries across transitions
- why uncertainty causes abstention
- why episode-level optimization is used
- why JSON is normalized internal representation
- why VMAP is generated from the same final decisions
- how unseen brands work without code changes
- how processing failures remain safe

Document actual limitations honestly.

If something is untested, mark it UNVERIFIED.

==================================================
DO NOT ADD IN PHASE 2
==================================================

Do NOT:

- redesign UI
- use Impeccable
- introduce RAG
- introduce vector databases
- introduce Kubernetes
- create unnecessary microservices
- train custom models
- replace MySQL
- hard-code sample timestamps
- hard-code brand mappings
- use real brand/company names
- force advertisements during uncertainty
- remove existing working Phase 1 behavior without replacement

==================================================
PHASE 2 ACCEPTANCE GATES
==================================================

Do not declare Phase 2 finished until ALL applicable items are verified:

[ ] feat/phase2 exists and is based on latest feat/phase1
[ ] feat/phase1 remains untouched
[ ] main remains untouched

[ ] raw shots and semantic scenes are separate
[ ] conversation camera cuts do not automatically become scene breaks
[ ] semantic scene grouping has regression tests

[ ] dialogue safety uses ASR + VAD + semantic continuity
[ ] speech-crossing cuts are hard rejected
[ ] short pauses inside dialogue are not considered safe

[ ] recent sensitive-context carryover works
[ ] negative-context violations remain hard blocks
[ ] no negative-context ranking penalty workaround exists

[ ] structured Qwen contract exists
[ ] malformed Qwen output fails safely
[ ] Qwen timeout fails safely

[ ] dynamic context vocabulary derives from brands
[ ] Brand I works without source changes
[ ] Brand I vocabulary automatically appears
[ ] Brand I safety rules work
[ ] Brand I missing creative gets fallback

[ ] brand eligibility happens before ranking
[ ] dominant activity receives highest ranking importance
[ ] selected brand receives second-pass safety verification
[ ] UNCERTAIN brand safety results are rejected

[ ] explicit NO AD outcome exists
[ ] no-safe-brand yields NO AD

[ ] episode-wide break optimizer exists
[ ] min gap enforced
[ ] max breaks/hour enforced
[ ] ad-load percentage enforced
[ ] creative duration participates in constraints

[ ] analysis.json generated
[ ] detailed debug.json generated
[ ] VMAP generated
[ ] VMAP matches normalized decisions exactly

[ ] existing content → ad → content resume tests still pass
[ ] ad does not replay unexpectedly

[ ] evaluation CLI implemented
[ ] multiple supplied videos actually evaluated where practical
[ ] evaluation output contains only real measurements
[ ] accepted breakpoint inspection clips generated

[ ] adversarial test suite implemented and passing

[ ] semantic Qwen cache works
[ ] cache metrics are reported

[ ] external service retries/timeouts exist
[ ] failure paths are conservative

[ ] job idempotency/recovery hardened
[ ] structured logs exist
[ ] health endpoint works
[ ] readiness endpoint works
[ ] startup environment validation works

[ ] Docker build succeeds
[ ] Docker application starts
[ ] REAL video successfully processes inside Docker

[ ] media cleanup exists
[ ] performance metrics exist

[ ] Python tests pass
[ ] player tests pass
[ ] browser regression passes
[ ] lint passes
[ ] TypeScript passes
[ ] production frontend build passes

[ ] documentation updated
[ ] working tree clean
[ ] feat/phase2 pushed to GitHub

==================================================
PRIORITY ORDER
==================================================

Prioritize implementation in exactly this spirit:

1. Prevent mid-dialogue cuts.
2. Prevent ALL negative-context violations.
3. Improve semantic scene quality.
4. Guarantee unseen-brand generalization.
5. Improve global pacing / break optimization.
6. Produce correct JSON and VMAP artifacts.
7. Add adversarial evaluation.
8. Make Docker/reproducibility solid.
9. Improve resilience / caching / performance.

Do not sacrifice correctness to generate more breaks.

Prefer:

fewer highly defensible advertisements

over:

many questionable advertisements.

==================================================
GIT / COMMIT QUALITY
==================================================

Make meaningful incremental commits.

Use commit messages similar to:

feat(scenes): add semantic grouping across shot boundaries

feat(speech): harden dialogue-safe break detection

feat(context): carry sensitive context across scene transitions

feat(ai): enforce structured evidence-backed scene semantics

feat(engine): separate hard breakpoint gates from scoring

feat(brands): enforce eligibility before contextual ranking

feat(safety): add final brand-context verification

feat(brands): support runtime unseen-brand catalogue updates

feat(engine): optimize episode-wide break schedule

feat(artifacts): generate VMAP from normalized decisions

feat(eval): add multi-video evaluation and inspection clips

test: add adversarial placement and unseen-brand regressions

perf(ai): cache validated semantic analysis

feat(worker): harden job idempotency and recovery

chore(docker): verify containerized end-to-end processing

docs: document phase 2 architecture and evaluation

Avoid meaningless commits like:

update
fix
working
final
changes

==================================================
EXECUTION INSTRUCTIONS
==================================================

Do not merely write a plan.

First inspect the existing repository and understand Phase 1.

Preserve good abstractions.

Implement Phase 2 directly.

Run tests throughout development.

Do not invent performance metrics.

Do not fake evaluation results.

Do not weaken existing tests merely to make new code pass.

When a bug is found:

1. identify the root cause
2. fix the root cause
3. add a regression test

Use actual supplied media for real verification where feasible.

Do not stop after implementing only unit tests.

Run at least one genuine end-to-end Phase 2 video analysis.

==================================================
FINAL REPORT FORMAT
==================================================

When Phase 2 is complete, give me a concise but complete report in this exact structure:

Branch:
Commit count:
Latest commit:
GitHub URL:

Architecture improvements:
- ...

Dialogue safety:
- ...

Semantic scene improvements:
- ...

Negative-context safety:
- ...

Brand matching:
- ...

Unseen Brand I test:
- ...

Global optimizer:
- ...

Artifacts:
analysis.json:
debug.json:
VMAP:

Tests:
Python:
Player:
Browser:
Adversarial:

Evaluation:
Videos tested:
Durations:
Raw shots:
Semantic scenes:
Candidates:
Qwen calls:
Cache hits:
Accepted breaks:
Processing times:
Detected mid-dialogue violations:
Negative-context violations:

Docker:
Build:
Startup:
Real video processing:

Reliability:
- ...

Known limitations:
- ...

Deferred to Phase 3:
UI / visual design / Impeccable polish only.

If ANYTHING is not actually verified, mark it:

UNVERIFIED

Do not claim success for an unverified component.

FINAL CORE RULE:

Interlude must never allow a high semantic/relevance score to override a hard dialogue-safety, contextual-safety, pacing, or negative-context rule.

When uncertain:

NO AD.