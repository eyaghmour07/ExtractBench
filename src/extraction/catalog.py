from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from extraction.paths import (
    FORM_GT,
    FORM_IMAGES,
    FORM_MANIFEST,
    GROUND_TRUTH,
    MANIFEST_PATH,
    PERSONAL_GT,
    PERSONAL_IMAGES,
    PERSONAL_MANIFEST,
    RECEIPTS,
    RUNS,
)

RECEIPT_FIELDS = ("merchant", "date", "total")
FORM_FIELDS = ("title", "date", "reference")

FIELD_LABELS = {
    "merchant": "Merchant",
    "date": "Date",
    "total": "Total",
    "title": "Title",
    "reference": "Reference",
}

DOC_TYPES = {
    "receipt": {
        "fields": RECEIPT_FIELDS,
        "labels": {name: FIELD_LABELS[name] for name in RECEIPT_FIELDS},
        "vlm_prompt": (
            "Extract the merchant (store / company name), transaction date, and grand total "
            "from this receipt image. Use the printed total the customer paid, not subtotal "
            "or change. Return JSON only. If a field is unreadable, use null."
        ),
    },
    "form": {
        "fields": FORM_FIELDS,
        "labels": {name: FIELD_LABELS[name] for name in FORM_FIELDS},
        "vlm_prompt": (
            "Extract the form title (header, issuing office, or document name), any printed "
            "date, and a reference number (form no, file no, registration no, or similar id) "
            "from this scanned form. Return JSON only. If a field is unreadable, use null."
        ),
    },
}


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    display: str
    doc_type: str
    images_dir: Path
    gt_dir: Path
    manifest_path: Path
    runs_dir: Path
    accepts_uploads: bool
    download_hint: str

    @property
    def fields(self) -> tuple[str, ...]:
        return DOC_TYPES[self.doc_type]["fields"]

    @property
    def labels(self) -> dict[str, str]:
        return DOC_TYPES[self.doc_type]["labels"]

    @property
    def vlm_prompt(self) -> str:
        return DOC_TYPES[self.doc_type]["vlm_prompt"]


DATASETS = {
    "sroie": DatasetSpec(
        id="sroie",
        display="SROIE receipts",
        doc_type="receipt",
        images_dir=RECEIPTS,
        gt_dir=GROUND_TRUTH,
        manifest_path=MANIFEST_PATH,
        runs_dir=RUNS / "sroie",
        accepts_uploads=False,
        download_hint="uv run python scripts/download_sroie.py --n 50",
    ),
    "personal": DatasetSpec(
        id="personal",
        display="Personal receipts",
        doc_type="receipt",
        images_dir=PERSONAL_IMAGES,
        gt_dir=PERSONAL_GT,
        manifest_path=PERSONAL_MANIFEST,
        runs_dir=RUNS / "personal",
        accepts_uploads=True,
        download_hint="Upload a JPEG, PNG, or WebP from the gallery.",
    ),
    "funsd": DatasetSpec(
        id="funsd",
        display="FUNSD forms",
        doc_type="form",
        images_dir=FORM_IMAGES,
        gt_dir=FORM_GT,
        manifest_path=FORM_MANIFEST,
        runs_dir=RUNS / "funsd",
        accepts_uploads=False,
        download_hint="uv run python scripts/download_funsd.py --n 10",
    ),
}


def get_dataset(dataset_id: str) -> DatasetSpec:
    key = (dataset_id or "sroie").lower().strip()
    if key not in DATASETS:
        raise ValueError(f"Unknown dataset {dataset_id!r}. Choose from {tuple(DATASETS)}.")
    return DATASETS[key]


def empty_fields(doc_type: str) -> dict[str, None]:
    return {name: None for name in DOC_TYPES[doc_type]["fields"]}
