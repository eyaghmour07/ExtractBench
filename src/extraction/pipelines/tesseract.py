from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytesseract
from PIL import Image

from extraction.parse import parse_document
from extraction.schema import PipelineRun, ReceiptFields


class TesseractPipeline:
    name = "tesseract"

    def __init__(self) -> None:
        cmd = shutil.which("tesseract")
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

    def extract(self, image_path: Path, receipt_id: str, doc_type: str = "receipt") -> PipelineRun:
        started = time.perf_counter()
        try:
            with Image.open(image_path) as image:
                raw = pytesseract.image_to_string(image)
            fields = parse_document(raw, doc_type)
            error = None
        except Exception as exc:  # noqa: BLE001 — surface engine failures in the run record
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
