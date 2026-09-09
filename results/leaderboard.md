| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | 50 | 59.2% | 48.0% | 0.362 | 0.514 | 0.0000 | 0.0000 |
| easyocr | 50 | 53.1% | 47.3% | 0.353 | 5.711 | 0.0000 | 0.0000 |
| vlm-gemini | 50 | 96.7% | 96.7% | 0.027 | 9.866 | 0.0226 | 0.0000 |

Per-field precision / recall / CER:

| Pipeline | Field | P | R | CER | TP | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | merchant | 33.3% | 32.0% | 0.463 | 16 | 32 | 34 |
| tesseract | date | 88.6% | 62.0% | 0.316 | 31 | 4 | 19 |
| tesseract | total | 55.6% | 50.0% | 0.306 | 25 | 20 | 25 |
| easyocr | merchant | 35.4% | 34.0% | 0.423 | 17 | 31 | 33 |
| easyocr | date | 97.7% | 84.0% | 0.144 | 42 | 1 | 8 |
| easyocr | total | 26.1% | 24.0% | 0.493 | 12 | 34 | 38 |
| vlm-gemini | merchant | 92.0% | 92.0% | 0.062 | 46 | 4 | 4 |
| vlm-gemini | date | 100.0% | 100.0% | 0.000 | 50 | 0 | 0 |
| vlm-gemini | total | 98.0% | 98.0% | 0.020 | 49 | 1 | 1 |

Perfect-score warnings (not results — inspect labels/set):
- date precision is 100% — check ground truth or test set
- date recall is 100% — check ground truth or test set
- date CER is 0 — check ground truth or test set

Precision/recall are exact match after field normalization (date→calendar date, total→Decimal cents, merchant→casefold/punctuation-stripped). CER is mean Levenshtein / max(len(gt), 1) on casefolded whitespace-squeezed strings — a different failure mode, not a restatement of P/R. Latency is wall-clock per document. List cost is published paid Gemini rates applied to usage_metadata even on the free tier; billed is actual charges (0.00 on free tier).
