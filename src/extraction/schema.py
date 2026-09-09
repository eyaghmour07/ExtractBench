from __future__ import annotations

from pydantic import BaseModel, Field


class ReceiptFields(BaseModel):
    """Extracted fields. Receipts use merchant/date/total; forms use title/date/reference."""

    merchant: str | None = None
    date: str | None = None
    total: str | None = None
    title: str | None = None
    reference: str | None = None


class ReceiptTargets(BaseModel):
    """VLM JSON schema for receipts. Kept separate so Gemini is not asked for form fields."""

    merchant: str | None = None
    date: str | None = None
    total: str | None = None


class FormFields(BaseModel):
    title: str | None = None
    date: str | None = None
    reference: str | None = None


class GroundTruthRecord(BaseModel):
    id: str
    source: str = "sroie"
    doc_type: str = "receipt"
    image: str
    fields: ReceiptFields
    verified: bool = False
    sroie_draft: ReceiptFields | None = None
    draft: ReceiptFields | None = None
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
    doc_type: str = "receipt"
