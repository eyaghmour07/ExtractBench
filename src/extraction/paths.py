from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RECEIPTS = DATA / "receipts"
SROIE_DRAFT = DATA / "sroie_draft"
GROUND_TRUTH = DATA / "ground_truth"
PERSONAL = DATA / "personal"
PERSONAL_IMAGES = PERSONAL / "images"
PERSONAL_GT = PERSONAL / "ground_truth"
FORMS = DATA / "forms"
FORM_IMAGES = FORMS / "images"
FORM_DRAFT = FORMS / "draft"
FORM_GT = FORMS / "ground_truth"
RUNS = DATA / "runs"
MANIFEST_PATH = DATA / "manifest.json"
PERSONAL_MANIFEST = PERSONAL / "manifest.json"
FORM_MANIFEST = FORMS / "manifest.json"
COST_LEDGER = RUNS / "cost_ledger.jsonl"


def ensure_data_dirs() -> None:
    for path in (
        RECEIPTS,
        SROIE_DRAFT,
        GROUND_TRUTH,
        PERSONAL_IMAGES,
        PERSONAL_GT,
        FORM_IMAGES,
        FORM_DRAFT,
        FORM_GT,
        RUNS,
    ):
        path.mkdir(parents=True, exist_ok=True)
