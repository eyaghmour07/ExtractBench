from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from extraction.catalog import DATASETS, DatasetSpec, empty_fields, get_dataset
from extraction.ground_truth import load_manifest, load_record, load_verified, save_manifest, save_record
from extraction.metrics import character_error_rate, score_field, summarize_runs
from extraction.paths import ROOT, RUNS, ensure_data_dirs
from extraction.pipelines import get_pipeline
from extraction.schema import GroundTruthRecord, Manifest, ReceiptFields

DISPLAY = {"tesseract": "Tesseract", "easyocr": "EasyOCR", "vlm-gemini": "Gemini"}
ORDER = ("tesseract", "easyocr", "vlm-gemini")


def _image(spec: DatasetSpec, doc_id: str) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        path = spec.images_dir / f"{doc_id}{suffix}"
        if path.exists():
            return path
    return None


def _manifest_ids(spec: DatasetSpec) -> list[str]:
    if not spec.manifest_path.exists():
        return []
    return load_manifest(spec.manifest_path).ids


def list_documents(dataset_id: str = "sroie") -> list[dict]:
    ensure_data_dirs()
    spec = get_dataset(dataset_id)
    ids = _manifest_ids(spec)
    extras = [
        path.stem
        for path in spec.images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    return [_payload(spec, doc_id) for doc_id in dict.fromkeys(ids + extras)]


def list_receipts() -> list[dict]:
    return list_documents("sroie")


def _payload(spec: DatasetSpec, doc_id: str) -> dict:
    record = load_record(doc_id, spec.gt_dir) if (spec.gt_dir / f"{doc_id}.json").exists() else None
    image = _image(spec, doc_id)
    fields = record.fields.model_dump() if record else empty_fields(spec.doc_type)
    return {
        "id": doc_id,
        "dataset": spec.id,
        "doc_type": spec.doc_type,
        "image_url": f"/api/receipts/{doc_id}/image?dataset={spec.id}" if image else None,
        "has_image": bool(image),
        "verified": bool(record and record.verified),
        "scored": bool(record and record.verified),
        "fields": {name: fields.get(name) for name in spec.fields},
        "notes": record.notes if record else None,
    }


def image_path(doc_id: str, dataset_id: str = "sroie") -> Path:
    spec = get_dataset(dataset_id)
    path = _image(spec, doc_id)
    if not path:
        raise FileNotFoundError(f"No image for {doc_id} in {spec.id}")
    return path


def dataset_payload(spec: DatasetSpec) -> dict:
    docs = list_documents(spec.id)
    return {
        "id": spec.id,
        "display": spec.display,
        "doc_type": spec.doc_type,
        "fields": list(spec.fields),
        "labels": spec.labels,
        "accepts_uploads": spec.accepts_uploads,
        "download_hint": spec.download_hint,
        "labeled": sum(1 for doc in docs if doc["scored"]),
        "with_image": sum(1 for doc in docs if doc["has_image"]),
    }


def list_dataset_payloads() -> list[dict]:
    ensure_data_dirs()
    return [dataset_payload(spec) for spec in DATASETS.values()]


def load_summaries(dataset_id: str = "sroie") -> list[dict]:
    spec = get_dataset(dataset_id)
    rows = []
    for path in spec.runs_dir.glob("*_summary.json"):
        rows.append(_public(json.loads(path.read_text())))
    if rows:
        return sorted(rows, key=lambda row: ORDER.index(row["pipeline"]) if row["pipeline"] in ORDER else 99)
    if spec.id == "sroie":
        legacy = list(RUNS.glob("*_summary.json"))
        if legacy:
            return sorted(
                [_public(json.loads(path.read_text())) for path in legacy],
                key=lambda row: ORDER.index(row["pipeline"]) if row["pipeline"] in ORDER else 99,
            )
        return _baseline()
    return []


def save_upload(filename: str, data: bytes, dataset_id: str = "personal") -> dict:
    spec = get_dataset(dataset_id)
    if not spec.accepts_uploads:
        raise ValueError(f"{spec.display} does not accept uploads.")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Upload a JPEG, PNG, or WebP image.")
    ensure_data_dirs()
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in Path(filename).stem).strip("-") or "upload"
    doc_id, n = stem, 2
    while _image(spec, doc_id):
        doc_id, n = f"{stem}-{n}", n + 1
    (spec.images_dir / f"{doc_id}{'.jpg' if suffix == '.jpeg' else suffix}").write_bytes(data)
    ids = _manifest_ids(spec)
    if doc_id not in ids:
        ids.append(doc_id)
        save_manifest(
            Manifest(dataset="personal", split="live", seed=0, ids=ids, doc_type=spec.doc_type),
            spec.manifest_path,
        )
    return _payload(spec, doc_id)


def save_label(dataset_id: str, doc_id: str, fields: dict, notes: str | None = None) -> dict:
    spec = get_dataset(dataset_id)
    image = _image(spec, doc_id)
    if not image:
        raise FileNotFoundError(f"No image for {doc_id} in {spec.id}")
    cleaned = {
        name: (value.strip() if isinstance(value := fields.get(name), str) and value.strip() else None)
        for name in spec.fields
    }
    if spec.doc_type == "receipt" and any(value is None for value in cleaned.values()):
        raise ValueError(f"Label every field: {', '.join(spec.fields)}")
    existing = load_record(doc_id, spec.gt_dir) if (spec.gt_dir / f"{doc_id}.json").exists() else None
    try:
        image_rel = str(image.relative_to(ROOT))
    except ValueError:
        image_rel = str(image)
    record = GroundTruthRecord(
        id=doc_id,
        source=spec.id,
        doc_type=spec.doc_type,
        image=image_rel,
        fields=ReceiptFields.model_validate(cleaned),
        verified=True,
        sroie_draft=existing.sroie_draft if existing else None,
        draft=existing.draft if existing else None,
        notes=notes or (existing.notes if existing else "labeled from the image in the web bench"),
        corrections=existing.corrections if existing else [],
    )
    save_record(record, spec.gt_dir)
    ids = _manifest_ids(spec)
    if doc_id not in ids:
        ids.append(doc_id)
        save_manifest(
            Manifest(
                dataset=spec.id,
                split="live" if spec.id == "personal" else "train",
                seed=0 if spec.id == "personal" else 42,
                ids=ids,
                doc_type=spec.doc_type,
            ),
            spec.manifest_path,
        )
    return _payload(spec, doc_id)


def iter_run(pipelines: list[str], ids: list[str], dataset_id: str = "sroie") -> Iterator[dict]:
    if not pipelines or not ids:
        raise ValueError("Choose at least one pipeline and sample.")
    spec = get_dataset(dataset_id)
    labeled_ids = [doc_id for doc_id in ids if (spec.gt_dir / f"{doc_id}.json").exists()]
    records = load_verified(labeled_ids, spec.gt_dir) if labeled_ids else []
    gt = {record.id: record.fields for record in records}
    yield {"type": "run_started", "dataset": spec.id, "pipelines": pipelines, "ids": ids}
    for name in pipelines:
        pipeline = get_pipeline(name)
        if name == "vlm" and not getattr(getattr(pipeline, "client", None), "api_key", None):
            yield {"type": "pipeline_skipped", "pipeline": pipeline.name, "reason": "GEMINI_API_KEY is not set."}
            continue
        yield {
            "type": "pipeline_started",
            "pipeline": pipeline.name,
            "display": DISPLAY.get(pipeline.name, pipeline.name),
            "n": len(ids),
        }
        runs = []
        for index, doc_id in enumerate(ids):
            yield {
                "type": "document_started",
                "pipeline": pipeline.name,
                "receipt_id": doc_id,
                "index": index,
                "n": len(ids),
            }
            run = pipeline.extract(image_path(doc_id, spec.id), doc_id, spec.doc_type)
            runs.append(run)
            comparison = {}
            if doc_id in gt:
                for field in spec.fields:
                    actual, predicted = getattr(gt[doc_id], field), getattr(run.fields, field)
                    comparison[field] = {
                        "gt": actual,
                        "pred": predicted,
                        "match": score_field(actual, predicted, field)["tp"] == 1,
                        "cer": character_error_rate(actual, predicted),
                    }
            yield {
                "type": "document_done",
                "pipeline": pipeline.name,
                "receipt_id": doc_id,
                "index": index,
                "n": len(ids),
                "latency_s": run.latency_s,
                "error": run.error,
                "fields": {field: getattr(run.fields, field) for field in spec.fields},
                "scored": doc_id in gt,
                "comparison": comparison,
            }
        scored = [run for run in runs if run.receipt_id in gt]
        summary = _public(summarize_runs(scored, gt, spec.fields)) if scored else None
        if summary:
            spec.runs_dir.mkdir(parents=True, exist_ok=True)
            (spec.runs_dir / f"{pipeline.name}_summary.json").write_text(
                json.dumps(summarize_runs(scored, gt, spec.fields), indent=2) + "\n"
            )
        yield {"type": "pipeline_done", "summary": summary, "pipeline": pipeline.name}
    yield {"type": "run_complete", "summaries": load_summaries(spec.id)}


def _public(s: dict) -> dict:
    return {**s, "display": DISPLAY.get(s["pipeline"], s["pipeline"]), "cost_list_usd": s.get("cost_list_usd", 0)}


def _baseline() -> list[dict]:
    data = [
        ("tesseract", .591534, .48, .361589, .514037, (.32, .62, .50)),
        ("easyocr", .5306, .473333, .3533, 5.711, (.34, .84, .24)),
        ("vlm-gemini", .966667, .966667, .027333, 9.866, (.92, 1.0, .98)),
    ]
    fields = ("merchant", "date", "total")
    return [
        {
            "pipeline": pipeline,
            "display": DISPLAY[pipeline],
            "n_documents": 50,
            "macro_precision": precision,
            "macro_recall": recall,
            "macro_cer": cer,
            "latency": {"mean_s": latency},
            "fields": {name: {"recall": value} for name, value in zip(fields, field_recalls)},
            "perfect_metric_warnings": (
                ["date precision is 100%: inspect labels", "date recall is 100%: inspect labels"]
                if pipeline == "vlm-gemini"
                else []
            ),
            "documents": [],
            "cost_list_usd": 0,
        }
        for pipeline, precision, recall, cer, latency, field_recalls in data
    ]
