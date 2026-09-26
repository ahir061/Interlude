"""Actual upload/provider/DB smoke; never substitutes fake inference."""
import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, timeout=180) as client:
        ready = client.get("/ready")
        print(json.dumps(ready.json()), flush=True)
        ready.raise_for_status()
        with args.video.open("rb") as source:
            response = client.post("/api/videos", files={"file": (args.video.name, source, "video/mp4")})
        response.raise_for_status()
        uploaded = response.json()
        job_id, video_id = uploaded["job"]["id"], uploaded["video"]["id"]
        print(json.dumps({"job_id": job_id, "video_id": video_id}), flush=True)
        status = None
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            response = client.get(f"/api/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if status != job["status"]:
                print(json.dumps(job), flush=True)
                status = job["status"]
            if status in ("COMPLETED", "FAILED"):
                break
            time.sleep(2)
        output = Path("data/outputs") / job_id
        output.mkdir(parents=True, exist_ok=True)
        (output / "smoke.json").write_text(json.dumps({"input": str(args.video), "job": job,
            "player_url": f"http://localhost:3000/?video={video_id}",
            "external_providers": True, "browser_verified": False}, indent=2))
        if status != "COMPLETED":
            raise SystemExit("Real analysis did not complete; inspect job/debug output.")
        response = client.get(f"/api/videos/{video_id}/analysis")
        response.raise_for_status()
        analysis = response.json()
        print(json.dumps({"summary": analysis["summary"],
                          "selected_brands": [b["brand_id"] for b in analysis["ad_breaks"]],
                          "output_path": str(output)}), flush=True)


if __name__ == "__main__":
    main()
