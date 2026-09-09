from extraction.metrics import (
    character_error_rate,
    fields_match,
    normalize_date,
    normalize_merchant,
    normalize_total,
    precision,
    recall,
    score_field,
    summarize_runs,
)
from extraction.schema import PipelineRun, ReceiptFields


def test_normalize_merchant_strips_punct_and_case():
    assert normalize_merchant("STARBUCKS STORE #10208") == "starbucks store 10208"
    assert normalize_merchant("  Foo,  Bar  ") == "foo bar"


def test_normalize_date_day_first():
    assert str(normalize_date("09/01/2019")) == "2019-01-09"
    assert str(normalize_date("9-1-19")) == "2019-01-09"
    assert normalize_date("not a date") is None
    assert fields_match("date", "09/01/2019", "2019-01-09")


def test_normalize_total_currency_and_cents():
    assert normalize_total("RM 31.00") == normalize_total("31")
    assert normalize_total("$4.95") == normalize_total("4.95")
    assert normalize_total("1,234.50") == normalize_total("1234.50")
    assert not fields_match("total", "9.00", "9.10")


def test_score_field_wrong_counts_as_fp_and_fn():
    assert score_field("ACME", "ACME", "merchant") == {"tp": 1, "fp": 0, "fn": 0}
    assert score_field("ACME", "OTHER", "merchant") == {"tp": 0, "fp": 1, "fn": 1}
    assert score_field("ACME", None, "merchant") == {"tp": 0, "fp": 0, "fn": 1}
    assert score_field(None, "ACME", "merchant") == {"tp": 0, "fp": 1, "fn": 0}
    assert score_field(None, None, "merchant") == {"tp": 0, "fp": 0, "fn": 0}


def test_precision_recall():
    assert precision(2, 2) == 0.5
    assert recall(2, 2) == 0.5
    assert precision(0, 0) is None


def test_cer_empty_pred_is_one():
    assert character_error_rate("hello", None) == 1.0
    assert character_error_rate("abc", "abc") == 0.0
    assert character_error_rate("abc", "axc") == 1 / 3


def test_summarize_runs_flags_perfect_scores():
    gt = {"r1": ReceiptFields(merchant="ACME", date="01/01/2018", total="1.00")}
    run = PipelineRun(
        pipeline="tesseract",
        receipt_id="r1",
        fields=ReceiptFields(merchant="ACME", date="01/01/2018", total="1.00"),
        latency_s=0.5,
    )
    summary = summarize_runs([run], gt)
    assert summary["macro_precision"] == 1.0
    assert summary["macro_recall"] == 1.0
    assert summary["macro_cer"] == 0.0
    assert summary["perfect_metric_warnings"]
    assert any("100%" in w or "CER is 0" in w for w in summary["perfect_metric_warnings"])


def test_summarize_runs_partial_miss():
    gt = {"r1": ReceiptFields(merchant="ACME SDN BHD", date="25/12/2018", total="9.00")}
    run = PipelineRun(
        pipeline="tesseract",
        receipt_id="r1",
        fields=ReceiptFields(merchant="ACME SDN BHD", date="25/12/2018", total="8.00"),
        latency_s=1.2,
        cost_usd=0.0,
    )
    summary = summarize_runs([run], gt)
    assert summary["fields"]["merchant"]["precision"] == 1.0
    assert summary["fields"]["total"]["precision"] == 0.0
    assert summary["fields"]["total"]["recall"] == 0.0
    assert summary["macro_precision"] < 1.0
