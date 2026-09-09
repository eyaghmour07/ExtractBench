from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RECEIPTS = DATA / "receipts"
SROIE_DRAFT = DATA / "sroie_draft"
GROUND_TRUTH = DATA / "ground_truth"
RUNS = DATA / "runs"
MANIFEST_PATH = DATA / "manifest.json"
COST_LEDGER = RUNS / "cost_ledger.jsonl"


def ensure_data_dirs() -> None:
    for path in (RECEIPTS, SROIE_DRAFT, GROUND_TRUTH, RUNS):
        path.mkdir(parents=True, exist_ok=True)
