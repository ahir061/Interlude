# Interlude Phase 1 design

Authority: `docs/PROJECT-Spec.md`, supplied by the user. Build and execute the entire vertical slice; basic UI only. Implementation decisions are authorized by the brief.

## Architecture
Next.js upload/result/player calls a FastAPI API. MySQL stores job states and canonical Pydantic analysis documents alongside normalized scene, transcript, candidate, decision, brand, creative and artifact records. A separate single CPU worker polls persisted QUEUED jobs, claims one transactionally, and processes it synchronously. No extra queue server or inference server is required. A crashed worker's job is marked FAILED after its lease expires; it is never silently approved or endlessly stuck.

The worker probes MP4, detects visual cuts with PySceneDetect, extracts mono 16kHz WAV, requests Bengali Groq Whisper Large V3, and runs packaged Silero VAD on CPU. Scene boundaries are rejected if either speech signal overlaps or if dialogue separation is too short. VLM inference uses only surviving boundaries, 1 FPS over ±5 seconds, timestamps and nearby transcript. Each provider has bounded retries, timeouts, strict normalization and secret-safe errors.

WHERE uses normalized visual strength, speech safety, silence and semantic transition. Dialogue safety is a hard gate. Brand conflicts are hard exclusions across all observed semantic fields; unknown sensitive contexts cause rejection. Dynamic vocabulary and catalog parsing allow new brands without source changes. Pacing greedily chooses the strongest safe eligible candidate, enforces separation, rolling hourly count and projected ad seconds/content seconds, then sorts chronologically. A started hour permits the configured number of breaks, including short demos; ad load bounds short-video density. Creative duration is probed, never assumed.

The canonical BreakDecision carries all component scores, brand evaluations, pacing reasons and media identifiers. Analysis/debug JSON are derived from these decisions. Browser playback keeps content and ad elements separate, preserves exact content time, tracks played IDs, skips breaks crossed by seeking and resumes on ad end. Errors are visible and content can resume explicitly.

## Scope and verification
Local filesystem media; UUID names and constrained paths; size/duration limits; no binary data in MySQL. Source stays available for playback, transient audio/frames are cleaned. Migrations target hosted MySQL. Readiness reports boolean checks without credentials. No polished UI, RAG, vector database or local Qwen.

Required tests cover speech safety, negative blocking, unseen brands, pacing, invalid semantic responses, real FFmpeg media, normalized manifests and browser insertion/resume. Real external-provider smoke verification is separate from isolated tests, records actual counts, and cannot be claimed before execution. Organizer brands and source MP4 were absent at initial inspection; requested their paths.
