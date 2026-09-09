from pathlib import Path

import pytest

from extraction.ground_truth import UnverifiedGroundTruthError, load_verified, save_record
from extraction.schema import GroundTruthRecord, ReceiptFields


def test_load_verified_rejects_unverified(tmp_path: Path):
    record = GroundTruthRecord(
        id="train_0001",
        image="data/receipts/train_0001.jpg",
        fields=ReceiptFields(merchant="A", date="01/01/2018", total="1.00"),
        verified=False,
    )
    save_record(record, gt_dir=tmp_path)
    with pytest.raises(UnverifiedGroundTruthError, match="not verified"):
        load_verified(["train_0001"], gt_dir=tmp_path)


def test_load_verified_rejects_missing(tmp_path: Path):
    with pytest.raises(UnverifiedGroundTruthError, match="missing"):
        load_verified(["nope"], gt_dir=tmp_path)


def test_load_verified_returns_hand_labeled(tmp_path: Path):
    record = GroundTruthRecord(
        id="train_0001",
        image="data/receipts/train_0001.jpg",
        fields=ReceiptFields(merchant="A", date="01/01/2018", total="1.00"),
        verified=True,
    )
    save_record(record, gt_dir=tmp_path)
    loaded = load_verified(["train_0001"], gt_dir=tmp_path)
    assert loaded[0].fields.merchant == "A"
    assert loaded[0].verified
