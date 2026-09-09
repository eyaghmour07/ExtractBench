from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from extraction.paths import COST_LEDGER, RUNS


def append_cost_event(
    *,
    pipeline: str,
    receipt_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    list_price_usd: float,
    billed_usd: float,
    path: Path | None = None,
) -> None:
    ledger = path or COST_LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pipeline": pipeline,
        "receipt_id": receipt_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "list_price_usd": list_price_usd,
        "billed_usd": billed_usd,
    }
    with ledger.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def save_runs(pipeline: str, runs: list, path: Path | None = None) -> Path:
    out = path or (RUNS / f"{pipeline}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [run.model_dump() for run in runs]
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return out
