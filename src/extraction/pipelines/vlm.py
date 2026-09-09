from __future__ import annotations

import os
import random
import time
from pathlib import Path

from extraction.pipelines.vlm_clients import VlmClient, get_vlm_client
from extraction.schema import PipelineRun, ReceiptFields


class VlmPipeline:
    name = "vlm"

    def __init__(
        self,
        client: VlmClient | None = None,
        min_interval_s: float = 7.5,
        max_retries: int = 5,
        on_call=None,
    ) -> None:
        self.client = client or get_vlm_client()
        self.name = f"vlm-{self.client.name}"
        self.min_interval_s = min_interval_s
        self.max_retries = max_retries
        self.on_call = on_call
        self._last_call_at = 0.0

    def extract(self, image_path: Path, receipt_id: str, doc_type: str = "receipt") -> PipelineRun:
        started = time.perf_counter()
        last_error: str | None = None
        for attempt in range(self.max_retries):
            self._respect_rate_limit()
            try:
                result = self.client.extract_fields(image_path, doc_type=doc_type)
                self._last_call_at = time.monotonic()
                if self.on_call is not None:
                    self.on_call(
                        receipt_id=receipt_id,
                        model=getattr(self.client, "model", ""),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        list_price_usd=result.list_price_usd,
                        billed_usd=result.billed_usd,
                    )
                return PipelineRun(
                    pipeline=self.name,
                    receipt_id=receipt_id,
                    fields=result.fields,
                    latency_s=time.perf_counter() - started,
                    cost_usd=result.list_price_usd,
                    billed_usd=result.billed_usd,
                    raw_text=result.raw_text,
                    error=result.error,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if _is_rate_limit(exc) and attempt < self.max_retries - 1:
                    time.sleep(_backoff_s(attempt))
                    continue
                break
        return PipelineRun(
            pipeline=self.name,
            receipt_id=receipt_id,
            fields=ReceiptFields(),
            latency_s=time.perf_counter() - started,
            cost_usd=0.0,
            billed_usd=0.0,
            raw_text=None,
            error=last_error,
        )

    def _respect_rate_limit(self) -> None:
        if self.min_interval_s <= 0:
            return
        elapsed = time.monotonic() - self._last_call_at
        remaining = self.min_interval_s - elapsed
        if remaining > 0:
            time.sleep(remaining)


def _is_rate_limit(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "rate" in text


def _backoff_s(attempt: int) -> float:
    return min(60.0, (2**attempt) + random.random())


def default_min_interval_s() -> float:
    raw = os.environ.get("VLM_MIN_INTERVAL_S")
    if raw:
        return float(raw)
    return 7.5
