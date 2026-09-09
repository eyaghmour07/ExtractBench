from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from statistics import mean, quantiles
import re

from dateutil import parser as date_parser
from Levenshtein import distance as levenshtein_distance

from extraction.catalog import RECEIPT_FIELDS
from extraction.schema import PipelineRun, ReceiptFields

FIELD_NAMES = RECEIPT_FIELDS
TEXT_FIELDS = {"merchant", "title", "reference", "authors"}


def normalize_merchant(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_date(value: str | None) -> date | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    # ISO-like strings are year-first. SROIE printed dates are day-first (Malaysia).
    year_first = bool(re.match(r"^\d{4}\D", text))
    try:
        parsed = date_parser.parse(text, dayfirst=not year_first, yearfirst=year_first)
        return parsed.date()
    except (ValueError, OverflowError, TypeError):
        return None


def normalize_total(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"(rm|myr|usd|\$)", "", text, flags=re.I)
    text = text.replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def cer_normalize(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).casefold()).strip()


def character_error_rate(gt: str | None, pred: str | None) -> float:
    gt_n = cer_normalize(gt)
    pred_n = cer_normalize(pred)
    if not gt_n:
        return 0.0 if not pred_n else 1.0
    if not pred_n:
        return 1.0
    return levenshtein_distance(gt_n, pred_n) / max(len(gt_n), 1)


def normalize_reference(value: str | None) -> str | None:
    text = normalize_merchant(value)
    return text.replace(" ", "") if text else None


def fields_match(name: str, gt: str | None, pred: str | None) -> bool:
    if name == "reference":
        left, right = normalize_reference(gt), normalize_reference(pred)
        return left is not None and left == right
    if name in TEXT_FIELDS:
        left, right = normalize_merchant(gt), normalize_merchant(pred)
        return left is not None and left == right
    if name == "date":
        left, right = normalize_date(gt), normalize_date(pred)
        return left is not None and left == right
    if name == "total":
        left, right = normalize_total(gt), normalize_total(pred)
        return left is not None and left == right
    raise ValueError(name)


def score_field(gt: str | None, pred: str | None, name: str) -> dict[str, int]:
    gt_present = _present(gt)
    pred_present = _present(pred)
    if not gt_present and not pred_present:
        return {"tp": 0, "fp": 0, "fn": 0}
    if gt_present and pred_present and fields_match(name, gt, pred):
        return {"tp": 1, "fp": 0, "fn": 0}
    if pred_present and not gt_present:
        return {"tp": 0, "fp": 1, "fn": 0}
    if gt_present and not pred_present:
        return {"tp": 0, "fp": 0, "fn": 1}
    # Both present but wrong: false alarm and a miss.
    return {"tp": 0, "fp": 1, "fn": 1}


def _present(value: str | None) -> bool:
    return value is not None and str(value).strip() != ""


def precision(tp: int, fp: int) -> float | None:
    denom = tp + fp
    return (tp / denom) if denom else None


def recall(tp: int, fn: int) -> float | None:
    denom = tp + fn
    return (tp / denom) if denom else None


def summarize_runs(
    runs: list[PipelineRun],
    ground_truth: dict[str, ReceiptFields],
    field_names: tuple[str, ...] = FIELD_NAMES,
) -> dict:
    per_field = {name: {"tp": 0, "fp": 0, "fn": 0, "cers": []} for name in field_names}
    latencies: list[float] = []
    list_cost = 0.0
    billed_cost = 0.0
    errors = 0
    documents: list[dict] = []

    for run in runs:
        gt = ground_truth[run.receipt_id]
        latencies.append(run.latency_s)
        list_cost += run.cost_usd
        billed_cost += run.billed_usd
        if run.error:
            errors += 1
        doc_fields = {}
        for name in field_names:
            gt_val = getattr(gt, name)
            pred_val = getattr(run.fields, name)
            counts = score_field(gt_val, pred_val, name)
            for key in ("tp", "fp", "fn"):
                per_field[name][key] += counts[key]
            cer = character_error_rate(gt_val, pred_val)
            per_field[name]["cers"].append(cer)
            doc_fields[name] = {
                "gt": gt_val,
                "pred": pred_val,
                "match": counts["tp"] == 1,
                "cer": cer,
            }
        documents.append(
            {
                "receipt_id": run.receipt_id,
                "latency_s": run.latency_s,
                "cost_usd": run.cost_usd,
                "error": run.error,
                "fields": doc_fields,
            }
        )

    field_rows = {}
    for name, bucket in per_field.items():
        field_rows[name] = {
            "tp": bucket["tp"],
            "fp": bucket["fp"],
            "fn": bucket["fn"],
            "precision": precision(bucket["tp"], bucket["fp"]),
            "recall": recall(bucket["tp"], bucket["fn"]),
            "cer": mean(bucket["cers"]) if bucket["cers"] else None,
        }

    macro_p = _mean_defined([row["precision"] for row in field_rows.values()])
    macro_r = _mean_defined([row["recall"] for row in field_rows.values()])
    macro_cer = _mean_defined([row["cer"] for row in field_rows.values()])

    summary = {
        "pipeline": runs[0].pipeline if runs else "",
        "n_documents": len(runs),
        "errors": errors,
        "fields": field_rows,
        "macro_precision": macro_p,
        "macro_recall": macro_r,
        "macro_cer": macro_cer,
        "latency": _latency_stats(latencies),
        "cost_list_usd": list_cost,
        "cost_billed_usd": billed_cost,
        "cost_list_per_doc_usd": (list_cost / len(runs)) if runs else 0.0,
        "perfect_metric_warnings": _perfect_warnings(field_rows, macro_p, macro_r, macro_cer),
        "documents": documents,
    }
    return summary


def _mean_defined(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return mean(present) if present else None


def _latency_stats(values: list[float]) -> dict:
    if not values:
        return {"mean_s": None, "p50_s": None, "p95_s": None}
    ordered = sorted(values)
    p50 = ordered[len(ordered) // 2]
    if len(ordered) >= 2:
        qs = quantiles(ordered, n=20, method="inclusive")
        p95 = qs[18]
    else:
        p95 = ordered[0]
    return {"mean_s": mean(values), "p50_s": p50, "p95_s": p95}


def _perfect_warnings(
    field_rows: dict,
    macro_p: float | None,
    macro_r: float | None,
    macro_cer: float | None,
) -> list[str]:
    warnings: list[str] = []
    for name, row in field_rows.items():
        if row["precision"] == 1.0:
            warnings.append(f"{name} precision is 100% — check ground truth or test set")
        if row["recall"] == 1.0:
            warnings.append(f"{name} recall is 100% — check ground truth or test set")
        if row["cer"] == 0.0:
            warnings.append(f"{name} CER is 0 — check ground truth or test set")
    if macro_p == 1.0:
        warnings.append("macro precision is 100% — check ground truth or test set")
    if macro_r == 1.0:
        warnings.append("macro recall is 100% — check ground truth or test set")
    if macro_cer == 0.0:
        warnings.append("macro CER is 0 — check ground truth or test set")
    return warnings
