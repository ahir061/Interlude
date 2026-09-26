"""Run actual API jobs and report measured policy diagnostics, never inferred accuracy."""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from interlude.config import get_settings
from interlude.services.brands import load_brands, negative_match
from interlude.services.media import MediaProbeService, run_media


def measured_metrics(debug: dict, brands: list) -> dict:
    decisions = debug["decisions"]
    accepted = [d for d in decisions if d["accepted"]]
    duration = debug["video"]["duration_sec"]
    transcript = debug["transcript"]["segments"]
    vad = debug["vad_intervals"]
    mid_dialogue = sum(any(s["start_sec"] <= d["timestamp_sec"] <= s["end_sec"] for s in transcript+vad)
                      or d["semantics"].get("dialogue_continuity") not in ("completed", "no_dialogue") for d in accepted)
    by_id = {b.brand_id: b for b in brands}
    negative_violations = 0
    for d in accepted:
        sem = d["semantics"]
        observed = [*sem["contexts"], *sem["sensitive_contexts"], *sem["mood"], sem["dominant_activity"],
                    sem["narrative_state_before"], sem["narrative_state_after"],
                    *(c["context"] for c in d["debug"]["context_memory"]["recent_sensitive_contexts"])]
        negative_violations += any(negative_match(o, n) for o in observed for n in by_id[d["selected_brand_id"]].negative_contexts)
    meta = debug["run_metadata"]
    return {"duration_sec": duration, "raw_shots": len(debug["raw_shots"]), "semantic_scenes": len(debug["scenes"]),
        "raw_candidates": len(debug["candidates"]), "dialogue_safety_rejections": sum(
            any("dialogue" in r or "speech" in r for r in d["rejection_reasons"]) for d in decisions),
        "semantic_rejections": sum(any(r in ("semantic_uncertainty", "weak_transition", "not_semantic_scene_boundary", "model_failure")
                                      for r in d["rejection_reasons"]) for d in decisions),
        "qwen_calls": meta["qwen_calls"], "cache_hits": meta["semantic_cache_hits"], "cache_misses": meta["semantic_cache_misses"],
        "accepted_breaks": len(accepted), "ads_per_hour": len(accepted)*3600/duration,
        "ad_load_percent": sum(d["creative_duration_sec"] for d in accepted)*100/duration,
        "processing_time_sec": meta["processing_timings_sec"].get("total_runtime", meta["processing_timings_sec"]["total_pipeline"]),
        "stage_timings_sec": meta["processing_timings_sec"], "detected_mid_dialogue_violations": mid_dialogue,
        "detected_negative_context_violations": negative_violations,
        "human_ground_truth": "UNLABELED: detected violations are policy audits, not measured human accuracy"}


def evaluate_video(client, source, settings, timeout_sec):
    started = time.perf_counter()
    with source.open("rb") as media:
        response = client.post("/api/videos", files={"file": (source.name, media, "video/mp4")}, timeout=180)
    response.raise_for_status()
    upload = response.json()
    job_id, video_id = upload["job"]["id"], upload["video"]["id"]
    previous = None
    deadline = time.monotonic()+timeout_sec
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if previous != job["status"]:
            print(json.dumps({"event": "evaluation_stage", "job_id": job_id, "stage": job["status"]}), flush=True)
            previous = job["status"]
        if job["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(2)
    record = {"source": str(source), "job_id": job_id, "video_id": video_id, "status": job["status"],
              "wall_time_sec": time.perf_counter()-started}
    if job["status"] != "COMPLETED":
        record["error"] = job.get("error_code") or "evaluation_deadline_exceeded"
        return record
    response = client.get(f"/api/videos/{video_id}/debug")
    response.raise_for_status()
    debug = response.json()
    record.update(measured_metrics(debug, load_brands(settings.brands_path)))
    record["artifacts"] = {kind: f"/api/videos/{video_id}/{kind}" for kind in ("analysis", "debug", "vmap")}
    record["inspection_clips"] = [d["debug"].get("inspection_clip") for d in debug["decisions"] if d["accepted"]]
    return record


def write_report(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/"evaluation.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    temp.replace(target)
    lines = ["# Actual Phase 2 evaluation", "", "Policy audits only; no human ground-truth accuracy is claimed.", "",
        "| Video | Status | Seconds | Shots | Scenes | Candidates | Qwen calls | Cache hits | Ads | Runtime | Dialogue violations | Negative violations |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["runs"]:
        columns = [Path(row["source"]).name, row["status"], *(str(row.get(key, "UNVERIFIED")) for key in
            ("duration_sec", "raw_shots", "semantic_scenes", "raw_candidates", "qwen_calls", "cache_hits",
             "accepted_breaks", "processing_time_sec", "detected_mid_dialogue_violations", "detected_negative_context_violations"))]
        lines.append("| " + " | ".join(columns) + " |")
    (directory/"evaluation.md").write_text("\n".join(lines)+"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--clip-duration", type=float, default=120)
    parser.add_argument("--clip-start", type=float, default=0)
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    settings.prepare_dirs()
    directory = args.report_dir or settings.reports_dir
    report = {"schema_version": 1, "runs": []}
    if (directory/"evaluation.json").exists():
        report = json.loads((directory/"evaluation.json").read_text())
    failed = False
    with httpx.Client(base_url=args.api, timeout=30) as client:
        for source in args.videos:
            temporary = None
            try:
                if MediaProbeService(settings).probe(source).duration_sec > args.clip_duration:
                    temporary = settings.data_dir/"work"/f"evaluation-{uuid4()}.mp4"
                    run_media([settings.ffmpeg_bin, "-v", "error", "-y", "-ss", str(args.clip_start), "-i", str(source),
                        "-t", str(args.clip_duration), "-vf", "scale=960:-2", "-c:v", "libx264", "-preset", "veryfast",
                        "-c:a", "aac", "-movflags", "+faststart", str(temporary)])
                row = evaluate_video(client, temporary or source, settings, args.timeout)
                row["source"] = str(source)
                row["excerpt_start_sec"] = args.clip_start if temporary else 0
                report["runs"].append(row)
                failed |= row["status"] != "COMPLETED"
                print(json.dumps(row), flush=True)
            except Exception as exc:
                failed = True
                report["runs"].append({"source": str(source), "status": "FAILED", "error_type": type(exc).__name__})
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
                write_report(report, directory)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
