| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | 10 | 0.0% | 0.0% | 0.955 | 0.347 | 0.0000 | 0.0000 |
| easyocr | 10 | 11.1% | 3.7% | 0.776 | 3.509 | 0.0000 | 0.0000 |
| vlm-gemini | 10 | 85.2% | 80.5% | 0.325 | 8.595 | 0.0044 | 0.0000 |

Per-field precision / recall / CER:

| Pipeline | Field | P | R | CER | TP | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | title | 0.0% | 0.0% | 1.060 | 0 | 10 | 10 |
| tesseract | date | 0.0% | 0.0% | 0.840 | 0 | 5 | 9 |
| tesseract | reference | 0.0% | 0.0% | 0.964 | 0 | 10 | 8 |
| easyocr | title | 0.0% | 0.0% | 0.548 | 0 | 10 | 10 |
| easyocr | date | 33.3% | 11.1% | 0.857 | 1 | 2 | 8 |
| easyocr | reference | 0.0% | 0.0% | 0.922 | 0 | 9 | 8 |
| vlm-gemini | title | 100.0% | 90.0% | 0.100 | 9 | 0 | 1 |
| vlm-gemini | date | 100.0% | 88.9% | 0.100 | 8 | 0 | 1 |
| vlm-gemini | reference | 55.6% | 62.5% | 0.775 | 5 | 4 | 3 |

Perfect-score warnings (not results — inspect labels/set):
- title precision is 100% — check ground truth or test set
- date precision is 100% — check ground truth or test set

Precision/recall are exact match after field normalization (date→calendar date, total→Decimal cents, merchant→casefold/punctuation-stripped). CER is mean Levenshtein / max(len(gt), 1) on casefolded whitespace-squeezed strings — a different failure mode, not a restatement of P/R. Latency is wall-clock per document. List cost is published paid Gemini rates applied to usage_metadata even on the free tier; billed is actual charges (0.00 on free tier).
