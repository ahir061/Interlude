"""Rerun supplied excerpts through real providers; retain complete candidate evidence."""
import argparse
import json
from pathlib import Path

from interlude.config import Settings
from interlude.evaluate import measured_metrics, write_report
from interlude.phase2_pipeline import Phase2Pipeline
from interlude.services.brands import load_brands
from interlude.services.manifest import ManifestService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--report-dir", type=Path, default=Path("reports/calibration"))
    args = parser.parse_args()
    settings = Settings(reports_dir=args.report_dir)
    report = {"schema_version": 2, "runs": []}
    for source in args.videos:
        identifier = "calibration_" + source.stem
        directory = args.report_dir/source.stem
        directory.mkdir(parents=True, exist_ok=True)
        def checkpoint(kind, items):
            (directory/f"checkpoint-{kind}.json").write_text(json.dumps(
                [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items],
                ensure_ascii=False, indent=2))
        result = Phase2Pipeline(settings).run(identifier, source,
            lambda stage: print(json.dumps({"video": source.stem, "stage": stage.value}), flush=True), checkpoint)
        paths = ManifestService(settings.media_base_url).write(result, directory)
        metrics = measured_metrics(result.model_dump(mode="json"), load_brands(settings.brands_path))
        row = {"source": str(source), "status": "COMPLETED", **metrics,
               "artifacts": {key: str(path) for key, path in paths.items()},
               "placements": [{"timestamp_sec": d.timestamp_sec, "brand": d.selected_brand_id,
                               "where_score": d.where_score} for d in result.decisions if d.accepted]}
        report["runs"].append(row)
        write_report(report, args.report_dir)
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
