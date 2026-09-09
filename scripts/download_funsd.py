#!/usr/bin/env python3
"""Download a frozen FUNSD forms slice. Draft labels are not ground truth."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction.ground_truth import save_manifest  # noqa: E402
from extraction.paths import FORM_DRAFT, FORM_IMAGES, FORM_MANIFEST, ROOT as REPO_ROOT, ensure_data_dirs  # noqa: E402
from extraction.schema import Manifest, ReceiptFields  # noqa: E402

DATASET = "nielsr/funsd-layoutlmv3"
SPLIT = "train"
SEED = 42
_DATE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})\b",
    re.I,
)
_REF = re.compile(r"\b([A-Z]{0,4}\d[\dA-Z./-]{1,16})\b")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10, help="How many train forms to freeze")
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
        form_id = f"form_{index:04d}"
        ids.append(form_id)
        image = row["image"]
        image_path = FORM_IMAGES / f"{form_id}.jpg"
        image.convert("RGB").save(image_path, format="JPEG", quality=95)
        fields = _draft_fields(row)
        draft = {
            "id": form_id,
            "dataset_index": index,
            "hf_id": row.get("id"),
            "fields": fields.model_dump(),
        }
        (FORM_DRAFT / f"{form_id}.json").write_text(json.dumps(draft, indent=2) + "\n")

    save_manifest(
        Manifest(dataset=DATASET, split=SPLIT, seed=args.seed, ids=ids, doc_type="form"),
        FORM_MANIFEST,
    )
    print(f"Wrote {len(ids)} forms to {FORM_IMAGES.relative_to(REPO_ROOT)}")
    print(f"Drafts (not ground truth) in {FORM_DRAFT.relative_to(REPO_ROOT)}")
    print("Manifest ids: " + ", ".join(ids))
    print("Verify from the image before scoring: uv run python scripts/label.py --dataset funsd")


def _draft_fields(row: dict) -> ReceiptFields:
    tokens = list(row.get("tokens") or [])
    tags = [int(tag) for tag in (row.get("ner_tags") or [])]
    headers: list[str] = []
    answers: list[str] = []
    current_header: list[str] = []
    current_answer: list[str] = []
    for token, tag in zip(tokens, tags):
        if tag == 1:
            if current_header:
                headers.append(" ".join(current_header))
            current_header = [token]
        elif tag == 2 and current_header:
            current_header.append(token)
        else:
            if current_header:
                headers.append(" ".join(current_header))
                current_header = []
        if tag == 5:
            if current_answer:
                answers.append(" ".join(current_answer))
            current_answer = [token]
        elif tag == 6 and current_answer:
            current_answer.append(token)
        else:
            if current_answer and tag != 6:
                answers.append(" ".join(current_answer))
                current_answer = []
    if current_header:
        headers.append(" ".join(current_header))
    if current_answer:
        answers.append(" ".join(current_answer))
    date = next((match.group(1) for answer in answers if (match := _DATE.search(answer))), None)
    if date is None:
        date = next((match.group(1) for header in headers if (match := _DATE.search(header))), None)
    reference = next((match.group(1) for answer in answers if (match := _REF.search(answer))), None)
    return ReceiptFields(
        title=headers[0] if headers else None,
        date=date,
        reference=reference,
    )


if __name__ == "__main__":
    main()
