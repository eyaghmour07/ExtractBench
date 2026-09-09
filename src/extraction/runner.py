from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from extraction.ground_truth import load_manifest, load_record, load_verified
from extraction.metrics import FIELD_NAMES, character_error_rate, score_field, summarize_runs
from extraction.paths import GROUND_TRUTH, RECEIPTS, RUNS, ensure_data_dirs
from extraction.pipelines import get_pipeline

DISPLAY = {"tesseract": "Tesseract", "easyocr": "EasyOCR", "vlm-gemini": "Gemini"}
ORDER = ("tesseract", "easyocr", "vlm-gemini")


def _image(receipt_id: str) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        path = RECEIPTS / f"{receipt_id}{suffix}"
        if path.exists():
            return path
    return None


def list_receipts() -> list[dict]:
    ensure_data_dirs()
    ids = load_manifest().ids
    extras = [p.stem for p in RECEIPTS.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    return [_receipt_payload(i) for i in dict.fromkeys(ids + extras)]


def _receipt_payload(receipt_id: str) -> dict:
    record = load_record(receipt_id) if (GROUND_TRUTH / f"{receipt_id}.json").exists() else None
    image = _image(receipt_id)
    return {
        "id": receipt_id,
        "image_url": f"/api/receipts/{receipt_id}/image" if image else None,
        "has_image": bool(image),
        "verified": bool(record and record.verified),
        "scored": bool(record and record.verified),
        "fields": record.fields.model_dump() if record else {"merchant": None, "date": None, "total": None},
    }


def image_path(receipt_id: str) -> Path:
    path = _image(receipt_id)
    if not path:
        raise FileNotFoundError(f"No image for {receipt_id}")
    return path


def load_summaries() -> list[dict]:
    rows = []
    for path in RUNS.glob("*_summary.json"):
        rows.append(_public(json.loads(path.read_text())))
    if rows:
        return sorted(rows, key=lambda row: ORDER.index(row["pipeline"]) if row["pipeline"] in ORDER else 99)
    return _baseline()


def save_upload(filename: str, data: bytes) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Upload a JPEG, PNG, or WebP receipt image.")
    ensure_data_dirs()
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in Path(filename).stem).strip("-") or "upload"
    receipt_id, n = stem, 2
    while _image(receipt_id):
        receipt_id, n = f"{stem}-{n}", n + 1
    (RECEIPTS / f"{receipt_id}{'.jpg' if suffix == '.jpeg' else suffix}").write_bytes(data)
    return _receipt_payload(receipt_id)


def iter_run(pipelines: list[str], ids: list[str]) -> Iterator[dict]:
    if not pipelines or not ids:
        raise ValueError("Choose at least one pipeline and sample.")
    records = load_verified([i for i in ids if (GROUND_TRUTH / f"{i}.json").exists()])
    gt = {r.id: r.fields for r in records}
    yield {"type": "run_started", "pipelines": pipelines, "ids": ids}
    for name in pipelines:
        pipeline = get_pipeline(name)
        if name == "vlm" and not getattr(getattr(pipeline, "client", None), "api_key", None):
            yield {"type": "pipeline_skipped", "pipeline": pipeline.name, "reason": "GEMINI_API_KEY is not set."}
            continue
        yield {"type": "pipeline_started", "pipeline": pipeline.name, "display": DISPLAY.get(pipeline.name, pipeline.name), "n": len(ids)}
        runs = []
        for index, receipt_id in enumerate(ids):
            yield {"type": "document_started", "pipeline": pipeline.name, "receipt_id": receipt_id, "index": index, "n": len(ids)}
            run = pipeline.extract(image_path(receipt_id), receipt_id)
            runs.append(run)
            comparison = {}
            if receipt_id in gt:
                for field in FIELD_NAMES:
                    actual, predicted = getattr(gt[receipt_id], field), getattr(run.fields, field)
                    comparison[field] = {
                        "gt": actual, "pred": predicted,
                        "match": score_field(actual, predicted, field)["tp"] == 1,
                        "cer": character_error_rate(actual, predicted),
                    }
            yield {"type": "document_done", "pipeline": pipeline.name, "receipt_id": receipt_id,
                   "index": index, "n": len(ids), "latency_s": run.latency_s, "error": run.error,
                   "fields": run.fields.model_dump(), "scored": receipt_id in gt, "comparison": comparison}
        scored = [r for r in runs if r.receipt_id in gt]
        summary = _public(summarize_runs(scored, gt)) if scored else None
        if summary:
            RUNS.mkdir(parents=True, exist_ok=True)
            (RUNS / f"{pipeline.name}_summary.json").write_text(json.dumps(summarize_runs(scored, gt), indent=2) + "\n")
        yield {"type": "pipeline_done", "summary": summary, "pipeline": pipeline.name}
    yield {"type": "run_complete", "summaries": load_summaries()}


def _public(s: dict) -> dict:
    return {**s, "display": DISPLAY.get(s["pipeline"], s["pipeline"]), "cost_list_usd": s.get("cost_list_usd", 0)}


def _baseline() -> list[dict]:
    data = [
        ("tesseract", .591534, .48, .361589, .514037, (.32, .62, .50)),
        ("easyocr", .5306, .473333, .3533, 5.711, (.34, .84, .24)),
        ("vlm-gemini", .966667, .966667, .027333, 9.866, (.92, 1.0, .98)),
    ]
    return [{"pipeline": p, "display": DISPLAY[p], "n_documents": 50, "macro_precision": pr,
             "macro_recall": re, "macro_cer": cer, "latency": {"mean_s": lat},
             "fields": {f: {"recall": v} for f, v in zip(FIELD_NAMES, fields)},
             "perfect_metric_warnings": (["date precision is 100%: inspect labels", "date recall is 100%: inspect labels"] if p == "vlm-gemini" else []),
             "documents": [], "cost_list_usd": 0} for p, pr, re, cer, lat, fields in data]
