from __future__ import annotations

from pathlib import Path

from extraction.paths import GROUND_TRUTH, MANIFEST_PATH
from extraction.schema import GroundTruthRecord, Manifest


class UnverifiedGroundTruthError(ValueError):
    """Scoring refused because a requested label is missing or not hand-verified."""


def gt_path(receipt_id: str, gt_dir: Path | None = None) -> Path:
    return (gt_dir or GROUND_TRUTH) / f"{receipt_id}.json"


def save_record(record: GroundTruthRecord, gt_dir: Path | None = None) -> Path:
    path = gt_path(record.id, gt_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def load_record(receipt_id: str, gt_dir: Path | None = None) -> GroundTruthRecord:
    path = gt_path(receipt_id, gt_dir)
    if not path.exists():
        raise FileNotFoundError(f"No ground-truth file for {receipt_id}: {path}")
    return GroundTruthRecord.model_validate_json(path.read_text())


def load_verified(
    receipt_ids: list[str],
    gt_dir: Path | None = None,
) -> list[GroundTruthRecord]:
    """Load labels for scoring. Raises if any id is missing or unverified."""
    records: list[GroundTruthRecord] = []
    problems: list[str] = []
    for receipt_id in receipt_ids:
        path = gt_path(receipt_id, gt_dir)
        if not path.exists():
            problems.append(f"{receipt_id}: missing {path}")
            continue
        record = GroundTruthRecord.model_validate_json(path.read_text())
        if not record.verified:
            problems.append(f"{receipt_id}: not verified (SROIE draft is not a referee)")
            continue
        records.append(record)
    if problems:
        joined = "\n  ".join(problems)
        raise UnverifiedGroundTruthError(
            "Refusing to score against unverified or missing labels:\n  " + joined
        )
    return records


def load_manifest(path: Path | None = None) -> Manifest:
    manifest_path = path or MANIFEST_PATH
    return Manifest.model_validate_json(manifest_path.read_text())


def save_manifest(manifest: Manifest, path: Path | None = None) -> Path:
    manifest_path = path or MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")
    return manifest_path
