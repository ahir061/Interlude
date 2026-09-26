import csv
import json
from pathlib import Path

from interlude.domain import AdBreak, AnalysisManifest, AnalysisResult


class ManifestService:
    def __init__(self, media_base_url: str = "http://localhost:8000"):
        self.media_base_url = media_base_url

    def build(self, result: AnalysisResult) -> AnalysisManifest:
        accepted = sorted((d for d in result.decisions if d.accepted), key=lambda d: d.timestamp_sec)
        return AnalysisManifest(video=result.video, summary={
            "scene_count": len(result.scenes), "candidate_count": len(result.candidates),
            "raw_shot_count": len(result.raw_shots) if result.raw_shots else len(result.scenes),
            "prefilter_rejected_count": sum(c.prefilter_status == "REJECTED" for c in result.candidates),
            "semantic_candidates_analyzed": sum(d.semantics is not None for d in result.decisions),
            "semantic_candidates_attempted": sum(c.prefilter_status == "SURVIVED" for c in result.candidates),
            "accepted_break_count": len(accepted)}, ad_breaks=[
                AdBreak(candidate_id=d.candidate_id, timestamp_sec=d.timestamp_sec, brand_id=d.selected_brand_id,
                        latest_start_sec=d.debug.get("playback", {}).get("latest_start_sec", d.timestamp_sec),
                        creative_id=d.selected_creative_id, creative_url=d.creative_url,
                        duration_sec=d.creative_duration_sec, where=d.debug.get("where", {}),
                        whether=d.debug.get("whether", {}), what={"score": d.brand_match_score,
                            "brand_matches": [m.model_dump() for m in d.brand_matches],
                            "brands": d.debug.get("brands", []),
                            "safety_verification": d.debug.get("brand_safety_verification", [])}) for d in accepted])

    def write(self, result: AnalysisResult, output: Path) -> dict[str, Path]:
        output.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for name, payload in (("analysis", self.build(result).model_dump(mode="json")),
                              ("debug", result.model_dump(mode="json"))):
            target = output / f"{name}.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(target)
            artifacts[name] = target
        from interlude.services.placement_report import candidate_rows
        rows = candidate_rows(result)
        (output / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        if rows:
            with (output / "candidates.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                                 for k, v in row.items()} for row in rows)
        from interlude.services.vmap import VMAPSerializer
        vmap = output / "manifest.vmap.xml"
        temporary = vmap.with_suffix(".tmp")
        temporary.write_bytes(VMAPSerializer(self.media_base_url).serialize(result.decisions))
        temporary.replace(vmap)
        artifacts["vmap"] = vmap
        return artifacts
