#!/usr/bin/env python3
"""Run one or more pipelines against hand-verified ground truth.

  uv run python scripts/run_benchmark.py --pipelines tesseract --n 15 --eye
  uv run python scripts/run_benchmark.py --pipelines tesseract,easyocr,vlm --n 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction.catalog import get_dataset  # noqa: E402
from extraction.cost import append_cost_event, save_runs  # noqa: E402
from extraction.ground_truth import load_manifest, load_verified  # noqa: E402
from extraction.leaderboard import render_failure_gallery, render_leaderboard  # noqa: E402
from extraction.metrics import summarize_runs  # noqa: E402
from extraction.paths import RUNS, ROOT as REPO_ROOT, ensure_data_dirs  # noqa: E402
from extraction.pipelines import get_pipeline  # noqa: E402
from extraction.pipelines.vlm import VlmPipeline  # noqa: E402
from extraction.runner import image_path  # noqa: E402


def _load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in __import__("os").environ:
            __import__("os").environ[key] = value


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipelines",
        default="tesseract",
        help="Comma-separated: tesseract,easyocr,vlm",
    )
    parser.add_argument("--n", type=int, default=None, help="Use the first N ids from the manifest")
    parser.add_argument("--dataset", default="sroie", help="sroie, personal, or funsd")
    parser.add_argument("--eye", action="store_true", help="Print side-by-side vs GT, skip aggregate table")
    parser.add_argument("--limit-gallery", type=int, default=8)
    args = parser.parse_args()
    ensure_data_dirs()

    spec = get_dataset(args.dataset)
    names = [part.strip() for part in args.pipelines.split(",") if part.strip()]
    if not spec.manifest_path.exists():
        raise SystemExit(f"No manifest for {spec.id}. {spec.download_hint}")
    ids = load_manifest(spec.manifest_path).ids
    if args.n is not None:
        ids = ids[: args.n]
    records = load_verified(ids, spec.gt_dir)
    gt_by_id = {record.id: record.fields for record in records}

    summaries = []
    for name in names:
        pipeline = get_pipeline(name)
        if isinstance(pipeline, VlmPipeline):
            if not getattr(pipeline.client, "api_key", None):
                print(
                    "skip vlm: GEMINI_API_KEY / GOOGLE_API_KEY not set "
                    "(copy .env.example to .env). Other pipelines still run."
                )
                continue
            pipeline.on_call = lambda p=pipeline, **kwargs: append_cost_event(
                pipeline=p.name, **kwargs
            )
        print(f"\n== {pipeline.name} ({len(records)} {spec.id}) ==")
        runs = []
        for record in records:
            path = image_path(record.id, spec.id)
            run = pipeline.extract(path, record.id, spec.doc_type)
            runs.append(run)
            _print_eye(record.fields, run, spec.fields)
            if run.error and _is_fatal_vlm_error(run.error):
                raise SystemExit(f"Stopping VLM after a fatal API error: {run.error}")
        spec.runs_dir.mkdir(parents=True, exist_ok=True)
        save_runs(pipeline.name, runs, spec.runs_dir / f"{pipeline.name}.json")
        summary = summarize_runs(runs, gt_by_id, spec.fields)
        (spec.runs_dir / f"{pipeline.name}_summary.json").write_text(
            json.dumps(summary, indent=2, default=str) + "\n"
        )
        summaries.append(summary)

    if not summaries:
        raise SystemExit("No pipelines produced results.")

    if args.eye:
        return

    summaries = _merge_saved_summaries(summaries, spec.runs_dir)
    table = render_leaderboard(summaries)
    gallery = render_failure_gallery(
        summaries, limit_per_pipeline=args.limit_gallery, image_dir=spec.images_dir
    )
    spec.runs_dir.mkdir(parents=True, exist_ok=True)
    (spec.runs_dir / "leaderboard.md").write_text(table)
    (spec.runs_dir / "failure_gallery.md").write_text(gallery)
    results = REPO_ROOT / "results"
    results.mkdir(exist_ok=True)
    if spec.id == "sroie":
        (results / "leaderboard.md").write_text(table)
        (results / "failure_gallery.md").write_text(gallery)
        dest = results / "leaderboard.md"
    else:
        (results / f"{spec.id}_leaderboard.md").write_text(table)
        (results / f"{spec.id}_failure_gallery.md").write_text(gallery)
        dest = results / f"{spec.id}_leaderboard.md"
    print("\n" + table)
    print(gallery)
    print(f"Wrote {spec.runs_dir / 'leaderboard.md'} and {dest}")


def _merge_saved_summaries(current: list[dict], runs_dir) -> list[dict]:
    """Keep Tesseract/EasyOCR rows when only VLM is re-run."""
    by_name: dict[str, dict] = {}
    search = list(runs_dir.glob("*_summary.json"))
    if not search and runs_dir == RUNS / "sroie":
        search = list(RUNS.glob("*_summary.json"))
    for path in sorted(search):
        data = json.loads(path.read_text())
        if isinstance(data, dict) and data.get("pipeline"):
            by_name[data["pipeline"]] = data
    for summary in current:
        by_name[summary["pipeline"]] = summary
    order = ["tesseract", "easyocr", "vlm-gemini"]
    rest = [name for name in by_name if name not in order]
    return [by_name[name] for name in order + rest if name in by_name]


def _is_fatal_vlm_error(error: str) -> bool:
    text = error.lower()
    return "not_found" in text or "no longer available" in text or "invalid api key" in text or "permission_denied" in text


def _print_eye(gt, run, field_names) -> None:
    status = "ERR" if run.error else "ok"
    print(f"  {run.receipt_id} [{status}] {run.latency_s:.2f}s ${run.cost_usd:.4f}")
    if run.error:
        print(f"    error: {run.error}")
    for name in field_names:
        print(f"    {name:<9} gt={getattr(gt, name)!r:40} pred={getattr(run.fields, name)!r}")


if __name__ == "__main__":
    main()
