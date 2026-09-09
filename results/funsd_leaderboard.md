| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | 10 | 0.0% | 0.0% | 0.955 | 0.309 | 0.0000 | 0.0000 |

Per-field precision / recall / CER:

| Pipeline | Field | P | R | CER | TP | FP | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | title | 0.0% | 0.0% | 1.060 | 0 | 10 | 10 |
| tesseract | date | 0.0% | 0.0% | 0.840 | 0 | 5 | 9 |
| tesseract | reference | 0.0% | 0.0% | 0.964 | 0 | 10 | 8 |

Precision/recall are exact match after field normalization (date→calendar date, total→Decimal cents, merchant→casefold/punctuation-stripped). CER is mean Levenshtein / max(len(gt), 1) on casefolded whitespace-squeezed strings — a different failure mode, not a restatement of P/R. Latency is wall-clock per document. List cost is published paid Gemini rates applied to usage_metadata even on the free tier; billed is actual charges (0.00 on free tier).
