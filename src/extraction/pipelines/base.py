from __future__ import annotations

from pathlib import Path
from typing import Protocol

from extraction.schema import PipelineRun


class Pipeline(Protocol):
    name: str

    def extract(self, image_path: Path, receipt_id: str) -> PipelineRun: ...
