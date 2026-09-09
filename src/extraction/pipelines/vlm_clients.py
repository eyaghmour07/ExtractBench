from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Protocol

from extraction.schema import ReceiptFields

# Published Gemini 3.5 Flash-Lite paid rates (USD / million tokens). Used as list
# price even when the free tier bills $0, so cost-per-document is comparable.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FLASH_INPUT_PER_M = 0.30
GEMINI_FLASH_OUTPUT_PER_M = 2.50


class VlmClient(Protocol):
    name: str
    model: str

    def extract_fields(self, image_path: Path) -> VlmResponse: ...


class VlmResponse:
    def __init__(
        self,
        fields: ReceiptFields,
        raw_text: str | None,
        input_tokens: int,
        output_tokens: int,
        list_price_usd: float,
        billed_usd: float,
        error: str | None = None,
    ) -> None:
        self.fields = fields
        self.raw_text = raw_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.list_price_usd = list_price_usd
        self.billed_usd = billed_usd
        self.error = error


class OpenAIClient:
    name = "openai"

    def __init__(self) -> None:
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    def extract_fields(self, image_path: Path) -> VlmResponse:
        raise NotImplementedError(
            "OpenAI GPT-4o is a Phase 3 drop-in. Implement VlmClient.extract_fields."
        )


class AnthropicClient:
    name = "anthropic"

    def __init__(self) -> None:
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def extract_fields(self, image_path: Path) -> VlmResponse:
        raise NotImplementedError(
            "Claude vision is a Phase 3 drop-in. Implement VlmClient.extract_fields."
        )


class GeminiClient:
    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. Copy .env.example to .env."
            )
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def extract_fields(self, image_path: Path) -> VlmResponse:
        from google.genai import types

        mime = _image_mime(image_path)
        image_bytes = image_path.read_bytes()
        prompt = (
            "Extract the merchant (store / company name), transaction date, and grand total "
            "from this receipt image. Use the printed total the customer paid, not subtotal "
            "or change. Return JSON only. If a field is unreadable, use null."
        )
        response = self._get_client().models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReceiptFields,
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        list_price = list_price_usd(input_tokens, output_tokens)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ReceiptFields):
            fields = parsed
        elif parsed is not None and hasattr(parsed, "model_dump"):
            fields = ReceiptFields.model_validate(parsed.model_dump())
        elif response.text:
            fields = ReceiptFields.model_validate_json(response.text)
        else:
            fields = ReceiptFields()
        return VlmResponse(
            fields=fields,
            raw_text=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            list_price_usd=list_price,
            billed_usd=0.0,
        )


def list_price_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_PER_M + (
        output_tokens / 1_000_000
    ) * GEMINI_FLASH_OUTPUT_PER_M


def _image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def get_vlm_client(backend: str | None = None) -> VlmClient:
    key = (backend or os.environ.get("VLM_BACKEND", "gemini")).lower().strip()
    if key in {"gemini", "google"}:
        return GeminiClient()
    if key in {"openai", "gpt", "gpt-4o"}:
        return OpenAIClient()
    if key in {"anthropic", "claude"}:
        return AnthropicClient()
    raise ValueError(f"Unknown VLM backend {backend!r}")
