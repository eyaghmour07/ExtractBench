from __future__ import annotations

from pydantic import BaseModel, Field


class ReceiptFields(BaseModel):
    """The three v1 extraction targets. All optional so a pipeline can miss a field."""

    merchant: str | None = None
    date: str | None = None
    total: str | None = None


class GroundTruthRecord(BaseModel):
    id: str
    source: str = "sroie"
    image: str
    fields: ReceiptFields
    verified: bool = False
    sroie_draft: ReceiptFields | None = None
    notes: str | None = None
    corrections: list[str] = Field(default_factory=list)


class PipelineRun(BaseModel):
    pipeline: str
    receipt_id: str
    fields: ReceiptFields
    latency_s: float
    cost_usd: float = 0.0
    raw_text: str | None = None
    error: str | None = None
    billed_usd: float = 0.0


class Manifest(BaseModel):
    dataset: str
    split: str
    seed: int
    ids: list[str]
