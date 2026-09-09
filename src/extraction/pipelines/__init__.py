from __future__ import annotations

from extraction.pipelines.base import Pipeline
from extraction.pipelines.easyocr import EasyOcrPipeline
from extraction.pipelines.tesseract import TesseractPipeline
from extraction.pipelines.vlm import VlmPipeline

PIPELINE_NAMES = ("tesseract", "easyocr", "vlm")


def get_pipeline(name: str) -> Pipeline:
    key = name.lower().strip()
    if key == "tesseract":
        return TesseractPipeline()
    if key == "easyocr":
        return EasyOcrPipeline()
    if key in {"vlm", "gemini"}:
        return VlmPipeline()
    raise ValueError(f"Unknown pipeline {name!r}. Choose from {PIPELINE_NAMES}.")


__all__ = [
    "PIPELINE_NAMES",
    "EasyOcrPipeline",
    "Pipeline",
    "TesseractPipeline",
    "VlmPipeline",
    "get_pipeline",
]
