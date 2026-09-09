from __future__ import annotations

from pathlib import Path

from extraction.metrics import FIELD_NAMES
from extraction.paths import RECEIPTS


def render_leaderboard(summaries: list[dict]) -> str:
    lines = [
        "| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        lines.append(
            "| {pipeline} | {n} | {p} | {r} | {cer} | {lat} | {cost} | {billed} |".format(
                pipeline=summary["pipeline"],
                n=summary["n_documents"],
                p=_pct(summary["macro_precision"]),
                r=_pct(summary["macro_recall"]),
                cer=_num(summary["macro_cer"]),
                lat=_num(summary["latency"]["mean_s"]),
                cost=_money(summary["cost_list_usd"]),
                billed=_money(summary["cost_billed_usd"]),
            )
        )
    lines.append("")
    lines.append("Per-field precision / recall / CER:")
    lines.append("")
    lines.append("| Pipeline | Field | P | R | CER | TP | FP | FN |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for summary in summaries:
        for name in FIELD_NAMES:
            row = summary["fields"][name]
            lines.append(
                f"| {summary['pipeline']} | {name} | {_pct(row['precision'])} | "
                f"{_pct(row['recall'])} | {_num(row['cer'])} | {row['tp']} | {row['fp']} | {row['fn']} |"
            )

    warnings = [w for summary in summaries for w in summary["perfect_metric_warnings"]]
    if warnings:
        lines.append("")
        lines.append("Perfect-score warnings (not results — inspect labels/set):")
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.append("")
    lines.append(
        "Precision/recall are exact match after field normalization (date→calendar date, "
        "total→Decimal cents, merchant→casefold/punctuation-stripped). CER is mean "
        "Levenshtein / max(len(gt), 1) on casefolded whitespace-squeezed strings — a "
        "different failure mode, not a restatement of P/R. Latency is wall-clock per "
        "document. List cost is published paid Gemini rates applied to usage_metadata "
        "even on the free tier; billed is actual charges (0.00 on free tier)."
    )
    return "\n".join(lines) + "\n"


def render_failure_gallery(summaries: list[dict], limit_per_pipeline: int = 8) -> str:
    lines = ["# Failure gallery", ""]
    for summary in summaries:
        misses = [
            doc
            for doc in summary["documents"]
            if any(not doc["fields"][name]["match"] for name in FIELD_NAMES)
        ]
        lines.append(f"## {summary['pipeline']} ({len(misses)} documents with at least one miss)")
        lines.append("")
        if not misses:
            lines.append("No field misses on this set.")
            lines.append("")
            continue
        # Worst first: most missed fields, then highest mean CER.
        misses.sort(
            key=lambda doc: (
                -sum(0 if doc["fields"][n]["match"] else 1 for n in FIELD_NAMES),
                -sum(doc["fields"][n]["cer"] for n in FIELD_NAMES),
            )
        )
        for doc in misses[:limit_per_pipeline]:
            image = RECEIPTS / f"{doc['receipt_id']}.jpg"
            lines.append(f"### {doc['receipt_id']}")
            lines.append("")
            lines.append(f"- image: `{_rel(image)}`")
            if doc["error"]:
                lines.append(f"- error: {doc['error']}")
            for name in FIELD_NAMES:
                cell = doc["fields"][name]
                mark = "ok" if cell["match"] else "MISS"
                lines.append(
                    f"- {name} [{mark}]: gt={cell['gt']!r} pred={cell['pred']!r} cer={cell['cer']:.3f}"
                )
            lines.append("")
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.4f}"


def _rel(path: Path) -> str:
    try:
        from extraction.paths import ROOT

        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
