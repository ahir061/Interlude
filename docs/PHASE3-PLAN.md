# Phase 3 implementation plan

Goal: arbitrary Bengali episode upload → semantic scenes → safe ranked ad schedule → VMAP/debug exports → verified playback. Preserve ranked-safety-2.2 and dynamic synthetic brand catalog. No filename, timestamp or brand-assignment rules tied to supplied videos.

1. Episode media: configurable two-hour/4 GiB limits; bounded overlapping speech chunks; absolute ASR-word/VAD timestamps; chunk caches and failure fencing; media timeouts scaled for episodes. Verify seam crossings, timestamps and actual episode input.
2. Semantic segmentation: inspect every raw boundary independently of ad safety; retain periodic sensitive-context monitoring; segment on positive location/time/activity evidence even when speech continues, without allowing an ad across that speech. Bound frame working storage and checkpoint frequency. Persist progress counts and scene evidence.
3. Operations/API: durable stage progress, episode library/detail, retry/cancel, candidate/scene exports, consistent configured limits; streamed upload rejection before oversized bodies exhaust storage; protected single-workspace deployment unless user specifies multi-account scope.
4. Workspace UI: episode upload/progress/history, scene timeline, ranked opportunities with safety/relevance/pacing explanations, brand catalog, downloads and working player. Responsive accessible design; no fabricated analytics.
5. Verification/deployment: tests for safety, chunk seams, scene grouping and lifecycle; real episode through hosted providers and application; browser upload/playback; Docker, docs and incremental GitHub commits.

Production readiness means a deployable protected workspace with bounded resources, failure handling and evidence. It does not promise perfect model interpretation or untested multi-tenant scale. External inference errors must never authorize a targeted ad.
