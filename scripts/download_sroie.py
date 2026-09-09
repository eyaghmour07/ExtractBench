#!/usr/bin/env python3
"""Download a frozen SROIE slice. Default n=15; pass --n 50 for the Phase 1 set."""

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

from extraction.paths import RECEIPTS, ROOT as REPO_ROOT, SROIE_DRAFT, ensure_data_dirs  # noqa: E402
from extraction.schema import Manifest, ReceiptFields  # noqa: E402
from extraction.ground_truth import save_manifest  # noqa: E402

DATASET = "jsdnrs/ICDAR2019-SROIE"
SPLIT = "train"
SEED = 42


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=15, help="How many train receipts to freeze")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    ensure_data_dirs()

    from datasets import load_dataset

    ds = load_dataset(DATASET, split=SPLIT)
    if args.n > len(ds):
        raise SystemExit(f"--n {args.n} exceeds split size {len(ds)}")

    rng = random.Random(args.seed)
    order = list(range(len(ds)))
    rng.shuffle(order)
    selected = order[: args.n]

    ids: list[str] = []
    for index in selected:
        row = ds[index]
        receipt_id = f"train_{index:04d}"
        ids.append(receipt_id)
        image = row["image"]
        image_path = RECEIPTS / f"{receipt_id}.jpg"
        image.convert("RGB").save(image_path, format="JPEG", quality=95)
        entities = row["entities"]
        draft = {
            "id": receipt_id,
            "dataset_index": index,
            "fields": ReceiptFields(
                merchant=entities.get("company"),
                date=entities.get("date"),
                total=entities.get("total"),
            ).model_dump(),
            "address_ignored": entities.get("address"),
        }
        (SROIE_DRAFT / f"{receipt_id}.json").write_text(json.dumps(draft, indent=2) + "\n")

    manifest = Manifest(dataset=DATASET, split=SPLIT, seed=args.seed, ids=ids)
    save_manifest(manifest)
    print(f"Wrote {len(ids)} receipts to {RECEIPTS.relative_to(REPO_ROOT)}")
    print(f"Drafts (not ground truth) in {SROIE_DRAFT.relative_to(REPO_ROOT)}")
    print("Manifest ids: " + ", ".join(ids))


if __name__ == "__main__":
    main()
