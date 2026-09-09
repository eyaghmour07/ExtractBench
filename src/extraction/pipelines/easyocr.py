from __future__ import annotations

import time
from pathlib import Path

from extraction.parse import parse_document
from extraction.schema import PipelineRun, ReceiptFields


class EasyOcrPipeline:
    name = "easyocr"

    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            import easyocr

            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self._reader

    def extract(self, image_path: Path, receipt_id: str, doc_type: str = "receipt") -> PipelineRun:
        started = time.perf_counter()
        try:
            rows = self._get_reader().readtext(str(image_path), detail=1, paragraph=False)
            # EasyOCR returns (bbox, text, conf); keep reading order.
            raw = "\n".join(str(row[1]) for row in rows)
            fields = parse_document(raw, doc_type)
            error = None
        except Exception as exc:  # noqa: BLE001
            raw = None
            fields = ReceiptFields()
            error = str(exc)
        return PipelineRun(
            pipeline=self.name,
            receipt_id=receipt_id,
            fields=fields,
            latency_s=time.perf_counter() - started,
            cost_usd=0.0,
            billed_usd=0.0,
            raw_text=raw,
            error=error,
        )
