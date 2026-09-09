#!/usr/bin/env python3
"""Hand-verify SROIE drafts against the receipt image.

SROIE bundled labels are a draft only. This script never auto-accepts them.
Scoring refuses unverified files.

Interactive:
  uv run python scripts/label.py
  uv run python scripts/label.py --id train_0042

Non-interactive (after you looked at the image):
  uv run python scripts/label.py --write-verified train_0042 \\
      --merchant "FOO SDN BHD" --date 25/12/2018 --total 9.00
  uv run python scripts/label.py --write-verified train_0042 --from-draft --notes "matches image"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction.catalog import get_dataset  # noqa: E402
from extraction.ground_truth import load_manifest, save_record  # noqa: E402
from extraction.paths import GROUND_TRUTH, RECEIPTS, ROOT as REPO_ROOT, SROIE_DRAFT  # noqa: E402
from extraction.schema import GroundTruthRecord, ReceiptFields  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", dest="only_id", help="Label a single receipt")
    parser.add_argument("--write-verified", metavar="ID", help="Write a verified record without prompts")
    parser.add_argument("--from-draft", action="store_true", help="With --write-verified, copy draft fields")
    parser.add_argument("--dataset", default="sroie", help="sroie, personal, or funsd")
    parser.add_argument("--merchant")
    parser.add_argument("--date")
    parser.add_argument("--total")
    parser.add_argument("--title")
    parser.add_argument("--reference")
    parser.add_argument("--notes")
    parser.add_argument("--no-open", action="store_true", help="Do not open the image in Preview")
    args = parser.parse_args()

    if args.write_verified:
        _write_verified(args)
        return

    spec = get_dataset(args.dataset)
    if args.dataset != "sroie":
        if not spec.manifest_path.exists():
            raise SystemExit(f"No manifest for {spec.id}. {spec.download_hint}")
        ids = [args.only_id] if args.only_id else load_manifest(spec.manifest_path).ids
        for receipt_id in ids:
            existing = spec.gt_dir / f"{receipt_id}.json"
            if existing.exists():
                record = GroundTruthRecord.model_validate_json(existing.read_text())
                if record.verified:
                    print(f"skip {receipt_id}: already verified")
                    continue
            _label_generic(spec, receipt_id, open_image=not args.no_open)
        return

    ids = [args.only_id] if args.only_id else load_manifest().ids
    for receipt_id in ids:
        existing = GROUND_TRUTH / f"{receipt_id}.json"
        if existing.exists():
            record = GroundTruthRecord.model_validate_json(existing.read_text())
            if record.verified:
                print(f"skip {receipt_id}: already verified")
                continue
        _label_one(receipt_id, open_image=not args.no_open)


def _load_draft(receipt_id: str) -> dict:
    path = SROIE_DRAFT / f"{receipt_id}.json"
    if not path.exists():
        raise SystemExit(f"No SROIE draft for {receipt_id}. Run scripts/download_sroie.py first.")
    return json.loads(path.read_text())


def _label_generic(spec, receipt_id: str, open_image: bool) -> None:
    image_path = None
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = spec.images_dir / f"{receipt_id}{suffix}"
        if candidate.exists():
            image_path = candidate
            break
    if image_path is None:
        raise SystemExit(f"Missing image for {receipt_id} in {spec.images_dir}")
    draft_path = spec.gt_dir.parent / "draft" / f"{receipt_id}.json"
    draft_fields = ReceiptFields()
    if spec.id == "funsd" and draft_path.exists():
        draft_fields = ReceiptFields.model_validate(json.loads(draft_path.read_text())["fields"])
    print("\n" + "=" * 60)
    print(f"{spec.display} {receipt_id}")
    print(f"Image: {image_path}")
    print("Draft (not ground truth until you accept/edit):")
    for name in spec.fields:
        print(f"  {name}: {getattr(draft_fields, name)}")
    if open_image:
        _open_image(image_path)
    choice = input("[a]ccept draft  [e]dit  [s]kip  [q]uit > ").strip().lower()
    if choice in {"q", "quit"}:
        raise SystemExit(0)
    if choice in {"s", "skip", ""}:
        print("skipped (still unverified)")
        return
    fields = draft_fields.model_copy()
    notes = None
    if choice in {"e", "edit"}:
        for name in spec.fields:
            setattr(fields, name, _prompt(name, getattr(fields, name)))
        notes = input("notes (optional) > ").strip() or None
    elif choice not in {"a", "accept"}:
        print(f"unknown choice {choice!r}; skipped")
        return
    try:
        image_rel = str(image_path.relative_to(REPO_ROOT))
    except ValueError:
        image_rel = str(image_path)
    save_record(
        GroundTruthRecord(
            id=receipt_id,
            source=spec.id,
            doc_type=spec.doc_type,
            image=image_rel,
            fields=fields,
            verified=True,
            draft=draft_fields,
            notes=notes,
            corrections=_diff_corrections(draft_fields, fields, spec.fields),
        ),
        spec.gt_dir,
    )
    print(f"saved verified label for {receipt_id}")


def _write_verified(args: argparse.Namespace) -> None:
    if args.dataset != "sroie":
        spec = get_dataset(args.dataset)
        values = {
            "merchant": args.merchant,
            "date": args.date,
            "total": args.total,
            "title": args.title,
            "reference": args.reference,
        }
        fields = ReceiptFields.model_validate({name: values.get(name) for name in spec.fields})
        if spec.doc_type == "receipt" and any(getattr(fields, name) is None for name in spec.fields):
            raise SystemExit(f"--write-verified for {spec.id} requires {', '.join('--' + n for n in spec.fields)}")
        image_path = next(
            (spec.images_dir / f"{args.write_verified}{suffix}"
             for suffix in (".jpg", ".jpeg", ".png", ".webp")
             if (spec.images_dir / f"{args.write_verified}{suffix}").exists()),
            None,
        )
        if image_path is None:
            raise SystemExit(f"Missing image for {args.write_verified}")
        save_record(
            GroundTruthRecord(
                id=args.write_verified,
                source=spec.id,
                doc_type=spec.doc_type,
                image=str(image_path.relative_to(REPO_ROOT)),
                fields=fields,
                verified=True,
                notes=args.notes,
            ),
            spec.gt_dir,
        )
        print(f"verified {args.write_verified} -> {spec.gt_dir / (args.write_verified + '.json')}")
        return
    receipt_id = args.write_verified
    draft = _load_draft(receipt_id)
    draft_fields = ReceiptFields.model_validate(draft["fields"])
    if args.from_draft:
        fields = draft_fields
        if args.merchant:
            fields.merchant = args.merchant
        if args.date:
            fields.date = args.date
        if args.total:
            fields.total = args.total
    else:
        if not (args.merchant and args.date and args.total):
            raise SystemExit("--write-verified without --from-draft requires --merchant --date --total")
        fields = ReceiptFields(merchant=args.merchant, date=args.date, total=args.total)
    corrections = _diff_corrections(draft_fields, fields)
    record = GroundTruthRecord(
        id=receipt_id,
        source="sroie",
        image=str(Path("data/receipts") / f"{receipt_id}.jpg"),
        fields=fields,
        verified=True,
        sroie_draft=draft_fields,
        notes=args.notes,
        corrections=corrections,
    )
    path = save_record(record)
    print(f"verified {receipt_id} -> {path}")


def _label_one(receipt_id: str, open_image: bool) -> None:
    draft = _load_draft(receipt_id)
    draft_fields = ReceiptFields.model_validate(draft["fields"])
    image_path = RECEIPTS / f"{receipt_id}.jpg"
    if not image_path.exists():
        raise SystemExit(f"Missing image {image_path}")
    print("\n" + "=" * 60)
    print(f"Receipt {receipt_id}")
    print(f"Image: {image_path}")
    print("SROIE draft (not ground truth until you accept/edit):")
    print(f"  merchant: {draft_fields.merchant}")
    print(f"  date:     {draft_fields.date}")
    print(f"  total:    {draft_fields.total}")
    if open_image:
        _open_image(image_path)
    choice = input("[a]ccept draft  [e]dit  [s]kip  [q]uit > ").strip().lower()
    if choice in {"q", "quit"}:
        raise SystemExit(0)
    if choice in {"s", "skip", ""}:
        print("skipped (still unverified)")
        return
    fields = draft_fields.model_copy()
    notes = None
    if choice in {"e", "edit"}:
        fields.merchant = _prompt("merchant", fields.merchant)
        fields.date = _prompt("date", fields.date)
        fields.total = _prompt("total", fields.total)
        notes = input("notes (optional) > ").strip() or None
    elif choice not in {"a", "accept"}:
        print(f"unknown choice {choice!r}; skipped")
        return
    record = GroundTruthRecord(
        id=receipt_id,
        source="sroie",
        image=str(Path("data/receipts") / f"{receipt_id}.jpg"),
        fields=fields,
        verified=True,
        sroie_draft=draft_fields,
        notes=notes,
        corrections=_diff_corrections(draft_fields, fields),
    )
    save_record(record)
    print(f"saved verified label for {receipt_id}")


def _prompt(name: str, current: str | None) -> str | None:
    typed = input(f"{name} [{current}] > ").strip()
    if typed == "":
        return current
    if typed.lower() in {"none", "null"}:
        return None
    return typed


def _diff_corrections(
    draft: ReceiptFields,
    final: ReceiptFields,
    field_names: tuple[str, ...] = ("merchant", "date", "total"),
) -> list[str]:
    notes: list[str] = []
    for name in field_names:
        before = getattr(draft, name)
        after = getattr(final, name)
        if before != after:
            notes.append(f"{name}: {before!r} -> {after!r}")
    return notes


def _open_image(path: Path) -> None:
    try:
        subprocess.run(["open", str(path)], check=False)
    except OSError:
        print(f"(could not open image; view {path} yourself)")


if __name__ == "__main__":
    main()
