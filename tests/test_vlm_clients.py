import pytest

from extraction.pipelines.vlm_clients import AnthropicClient, OpenAIClient, list_price_usd


def test_openai_and_claude_are_explicit_stubs(tmp_path):
    dummy = tmp_path / "x.jpg"
    dummy.write_bytes(b"not-an-image")
    with pytest.raises(NotImplementedError, match="free"):
        OpenAIClient().extract_fields(dummy)
    with pytest.raises(NotImplementedError, match="free"):
        AnthropicClient().extract_fields(dummy)


def test_gemini_list_price_formula():
    # 1M in + 1M out at published Flash rates
    assert list_price_usd(1_000_000, 1_000_000) == pytest.approx(2.80)
    assert list_price_usd(0, 0) == 0.0
