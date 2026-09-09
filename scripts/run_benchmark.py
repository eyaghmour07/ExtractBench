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

from extraction.cost import append_cost_event, save_runs  # noqa: E402
from extraction.ground_truth import load_manifest, load_verified  # noqa: E402
from extraction.leaderboard import render_failure_gallery, render_leaderboard  # noqa: E402
from extraction.metrics import summarize_runs  # noqa: E402
from extraction.paths import RECEIPTS, RUNS, ROOT as REPO_ROOT, ensure_data_dirs  # noqa: E402
from extraction.pipelines import get_pipeline  # noqa: E402
from extraction.pipelines.vlm import VlmPipeline  # noqa: E402


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
    parser.add_argument("--eye", action="store_true", help="Print side-by-side vs GT, skip aggregate table")
    parser.add_argument("--limit-gallery", type=int, default=8)
    args = parser.parse_args()
    ensure_data_dirs()

    names = [part.strip() for part in args.pipelines.split(",") if part.strip()]
    ids = load_manifest().ids
    if args.n is not None:
        ids = ids[: args.n]
    records = load_verified(ids)
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
        print(f"\n== {pipeline.name} ({len(records)} receipts) ==")
        runs = []
        for record in records:
            image_path = RECEIPTS / f"{record.id}.jpg"
            if not image_path.exists():
                raise SystemExit(f"Missing image {image_path}")
            run = pipeline.extract(image_path, record.id)
            runs.append(run)
            _print_eye(record.fields, run)
            if run.error and _is_fatal_vlm_error(run.error):
                raise SystemExit(f"Stopping VLM after a fatal API error: {run.error}")
        save_runs(pipeline.name, runs)
        summary = summarize_runs(runs, gt_by_id)
        (RUNS / f"{pipeline.name}_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
        summaries.append(summary)

    if not summaries:
        raise SystemExit("No pipelines produced results.")

    if args.eye:
        return

    summaries = _merge_saved_summaries(summaries)
    table = render_leaderboard(summaries)
    gallery = render_failure_gallery(summaries, limit_per_pipeline=args.limit_gallery)
    (RUNS / "leaderboard.md").write_text(table)
    (RUNS / "failure_gallery.md").write_text(gallery)
    results = REPO_ROOT / "results"
    results.mkdir(exist_ok=True)
    (results / "leaderboard.md").write_text(table)
    (results / "failure_gallery.md").write_text(gallery)
    print("\n" + table)
    print(gallery)
    print(f"Wrote {RUNS / 'leaderboard.md'} and {results / 'leaderboard.md'}")


def _merge_saved_summaries(current: list[dict]) -> list[dict]:
    """Keep Tesseract/EasyOCR rows when only VLM is re-run."""
    by_name: dict[str, dict] = {}
    for path in sorted(RUNS.glob("*_summary.json")):
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


def _print_eye(gt, run) -> None:
    status = "ERR" if run.error else "ok"
    print(f"  {run.receipt_id} [{status}] {run.latency_s:.2f}s ${run.cost_usd:.4f}")
    if run.error:
        print(f"    error: {run.error}")
    print(f"    merchant  gt={gt.merchant!r:40} pred={run.fields.merchant!r}")
    print(f"    date      gt={gt.date!r:40} pred={run.fields.date!r}")
    print(f"    total     gt={gt.total!r:40} pred={run.fields.total!r}")


if __name__ == "__main__":
    main()
