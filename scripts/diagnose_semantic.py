"""Print structure-only provider diagnostics. Never print URL, key or raw response."""
import json
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import httpx
from pydantic import ValidationError
from interlude.config import get_settings
from interlude.domain import SceneSemantics, TranscriptSegment
from interlude.providers.semantic import QwenSemanticProvider
from interlude.providers.base import ProviderError
from interlude.services.brands import load_brands, vocabulary
from interlude.services.media import extract_window


def response_structure(response):
    response.read()
    try:
        raw = response.json()
        message = raw.get("choices", [{}])[0].get("message", {})
        content = message.get("content")
        info = {"http_status": response.status_code, "top_level_keys": list(raw),
                "message_keys": list(message), "content_type": type(content).__name__,
                "finish_reason": raw.get("choices", [{}])[0].get("finish_reason")}
        if isinstance(content, str):
            info.update(content_length=len(content), contains_code_fence="```" in content,
                        starts_json=content.lstrip().startswith("{"))
            try:
                SceneSemantics.model_validate_json(content)
                info["valid_semantics"] = True
            except ValidationError as exc:
                info["validation_errors"] = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        print(json.dumps(info), flush=True)
    except Exception as exc:
        print(json.dumps({"diagnostic_error_type": type(exc).__name__}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("debug", type=Path)
    args = parser.parse_args()
    s = get_settings()
    s.llm_max_retries = 0
    d = json.loads(args.debug.read_text())
    candidate = next((c for c in d["candidates"] if c["prefilter_status"] == "SURVIVED"), None)
    if candidate is None:
        raise SystemExit("No surviving semantic candidate to diagnose.")
    timestamp = candidate["timestamp_sec"]
    transcript = [TranscriptSegment.model_validate(v) for v in d["transcript"]["segments"]
                  if v["end_sec"] >= timestamp-5 and v["start_sec"] <= timestamp+5]
    with TemporaryDirectory(dir=s.data_dir / "work") as work:
        frames = extract_window(s, args.source, timestamp, d["video"]["duration_sec"], Path(work))
        with httpx.Client(event_hooks={"response": [response_structure]}) as client:
            try:
                QwenSemanticProvider(s, client).analyze(frames, transcript, vocabulary(load_brands(s.brands_path)), timestamp)
            except ProviderError as exc:
                print(exc.code)
