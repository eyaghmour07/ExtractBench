| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | 5 | 51.1% | 26.7% | 0.623 | 0.446 | 0.0000 | 0.0000 |
| easyocr | 5 | 53.3% | 26.7% | 0.584 | 4.780 | 0.0000 | 0.0000 |
| vlm-gemini | 5 | 93.3% | 93.3% | 0.015 | 7.504 | 0.0022 | 0.0000 |

Per-field precision / recall / CER:

| Pipeline | Field | P | R | CER | TP | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | merchant | 20.0% | 20.0% | 0.588 | 1 | 4 | 4 |
| tesseract | date | 100.0% | 40.0% | 0.600 | 2 | 0 | 3 |
| tesseract | total | 33.3% | 20.0% | 0.680 | 1 | 2 | 4 |
| easyocr | merchant | 60.0% | 60.0% | 0.201 | 3 | 2 | 2 |
| easyocr | date | 100.0% | 20.0% | 0.800 | 1 | 0 | 4 |
| easyocr | total | 0.0% | 0.0% | 0.750 | 0 | 4 | 5 |
| vlm-gemini | merchant | 80.0% | 80.0% | 0.044 | 4 | 1 | 1 |
| vlm-gemini | date | 100.0% | 100.0% | 0.000 | 5 | 0 | 0 |
| vlm-gemini | total | 100.0% | 100.0% | 0.000 | 5 | 0 | 0 |

Perfect-score warnings (not results — inspect labels/set):
- date precision is 100% — check ground truth or test set
- date precision is 100% — check ground truth or test set
- date precision is 100% — check ground truth or test set
- date recall is 100% — check ground truth or test set
- date CER is 0 — check ground truth or test set
- total precision is 100% — check ground truth or test set
- total recall is 100% — check ground truth or test set
- total CER is 0 — check ground truth or test set

Precision/recall are exact match after field normalization (date→calendar date, total→Decimal cents, merchant→casefold/punctuation-stripped). CER is mean Levenshtein / max(len(gt), 1) on casefolded whitespace-squeezed strings — a different failure mode, not a restatement of P/R. Latency is wall-clock per document. List cost is published paid Gemini rates applied to usage_metadata even on the free tier; billed is actual charges (0.00 on free tier).
