#!/usr/bin/env python3
"""Download extra SROIE receipts into the personal dataset.

Uses the same seed-42 shuffle as the locked 50, then takes the next N ids so
the personal board never overlaps the published SROIE table. Drafts are not
ground truth — label from the image.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction.ground_truth import save_manifest  # noqa: E402
from extraction.paths import (  # noqa: E402
    PERSONAL,
    PERSONAL_IMAGES,
    PERSONAL_MANIFEST,
    ROOT as REPO_ROOT,
    SROIE_DRAFT,
    ensure_data_dirs,
)
from extraction.schema import Manifest, ReceiptFields  # noqa: E402

DATASET = "jsdnrs/ICDAR2019-SROIE"
SPLIT = "train"
SEED = 42
LOCKED = 50


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=5, help="How many extra receipts after the locked 50")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--skip", type=int, default=LOCKED)
    args = parser.parse_args()
    ensure_data_dirs()
    (PERSONAL / "draft").mkdir(parents=True, exist_ok=True)

    from datasets import load_dataset

    ds = load_dataset(DATASET, split=SPLIT)
    rng = random.Random(args.seed)
    order = list(range(len(ds)))
    rng.shuffle(order)
    selected = order[args.skip : args.skip + args.n]
    if len(selected) < args.n:
        raise SystemExit(f"Not enough leftover receipts after skip={args.skip}")

    ids: list[str] = []
    for index in selected:
        row = ds[index]
        receipt_id = f"train_{index:04d}"
        ids.append(receipt_id)
        image_path = PERSONAL_IMAGES / f"{receipt_id}.jpg"
        row["image"].convert("RGB").save(image_path, format="JPEG", quality=95)
        fields = ReceiptFields(
            merchant=row["entities"].get("company"),
            date=row["entities"].get("date"),
            total=row["entities"].get("total"),
        )
        draft = {"id": receipt_id, "dataset_index": index, "fields": fields.model_dump()}
        (PERSONAL / "draft" / f"{receipt_id}.json").write_text(json.dumps(draft, indent=2) + "\n")
        (SROIE_DRAFT / f"{receipt_id}.json").write_text(json.dumps(draft, indent=2) + "\n")

    save_manifest(
        Manifest(dataset="personal", split="live", seed=args.seed, ids=ids, doc_type="receipt"),
        PERSONAL_MANIFEST,
    )
    print(f"Wrote {len(ids)} receipts to {PERSONAL_IMAGES.relative_to(REPO_ROOT)}")
    print("Manifest ids: " + ", ".join(ids))
    print("Label from the image: uv run python scripts/label.py --dataset personal")


if __name__ == "__main__":
    main()
