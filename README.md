# ExtractBench

Compare **Tesseract**, **EasyOCR**, and a **Gemini** vision-language model on the same hand-labeled receipts. The referee is ground truth verified from the image — never a pipeline output, and never an unverified SROIE JSON dump.

v1 fields: **merchant**, **date**, **total**. Dataset: [ICDAR 2019 SROIE](https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE) (CC-BY-4.0). Frozen 50-id slice in `data/manifest.json` (train split, seed 42).

This is its own data point. Septiawan et al. (2025) compared GPT-4o to EasyOCR+LLaMA. Default here is Gemini plus a deterministic OCR parser, not that setup.

## Latest numbers (50 verified receipts)

Gemini **3.5 Flash-Lite** (image → JSON) vs Tesseract/EasyOCR + the same regex parser. Not a Septiawan reproduction: that paper used GPT-4o vs EasyOCR+LLaMA.

| Pipeline | Docs | Macro P | Macro R | Macro CER | Latency mean (s) | List cost (USD) | Billed (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tesseract | 50 | 59.2% | 48.0% | 0.362 | 0.514 | 0.0000 | 0.0000 |
| easyocr | 50 | 53.1% | 47.3% | 0.353 | 5.711 | 0.0000 | 0.0000 |
| vlm-gemini | 50 | 96.7% | 96.7% | 0.027 | 9.866 | 0.0226 | 0.0000 |

Gemini wins every accuracy axis. EasyOCR is the best **date** OCR engine (84% recall vs Tesseract 62%) but the worst **total** picker (24%). Tesseract is faster (0.5s vs 5.7s vs 9.9s). Gemini list price for this run is **$0.0226**; billed was $0 on the free tier.

Gemini **date** is 50/50 — the code flagged that 100% as a cue to inspect labels, not a trophy. Dates on these receipts are unambiguous printed fields, so a strong VLM can actually clear them. Merchant is 46/50: the four misses are brand name vs legal entity (IKEA vs IKANO HANDEL, myNEWS.com vs MYNEWS RETAIL SB, SUSHI MENTAI vs MIZU MENTAI, BHPetrol vs ESJAY FUEL). One total miss is 20.80 vs 20.90 (rounding).

Full table + side-by-side misses: [results/leaderboard.md](results/leaderboard.md), [results/failure_gallery.md](results/failure_gallery.md).

One SROIE draft was wrong on the image and was corrected: `train_0414` merchant `UHAT` → `UBAT`.

## Setup

```bash
brew install tesseract          # classical OCR binary
uv sync --group dev             # Python 3.12 env
cp .env.example .env            # then put GEMINI_API_KEY in .env
```

## Data and labeling

```bash
uv run python scripts/download_sroie.py --n 50
uv run python scripts/label.py                   # opens each image; accept/edit/skip
```

SROIE `company` / `date` / `total` are copied as a **draft**. `scripts/label.py` will not mark a record verified unless you accept or edit it. Scoring refuses unverified files.

After you have looked at an image you can write a label non-interactively:

```bash
uv run python scripts/label.py --write-verified train_0042 --from-draft --notes "matches image"
uv run python scripts/label.py --write-verified train_0042 \
  --merchant "FOO SDN BHD" --date 25/12/2018 --total 9.00
```

## Run

By-eye Tesseract loop (no aggregate table):

```bash
uv run python scripts/run_benchmark.py --pipelines tesseract --n 15 --eye
```

All three pipelines + comparison table (VLM is skipped if no API key):

```bash
uv run python scripts/run_benchmark.py --pipelines tesseract,easyocr,vlm --n 50
```

Writes `data/runs/` (gitignored) and copies the table to `results/`.

Live bench UI (upload, run, leaderboard, failure gallery):

```bash
uv run python scripts/serve.py
```

Open http://127.0.0.1:8765. Gemini is skipped unless `GEMINI_API_KEY` is set in `.env`. Unlabeled uploads extract only; they do not enter the leaderboard.

## What the numbers mean

| Number | Meaning |
| --- | --- |
| Field precision / recall | Exact match after normalization (date → calendar date, total → cents, merchant → casefold + punctuation stripped). Wrong prediction is both an FP and an FN. |
| CER | Mean Levenshtein / max(len(gt), 1) on casefolded, whitespace-squeezed strings. Near-misses that P/R treats as total failures. |
| Latency | Wall-clock seconds per document. Local OCR cost is time, not $0. |
| List cost | Gemini token usage × published paid rates ($0.30/M input, $2.50/M output for 3.5 Flash-Lite), even on the free tier. |
| Billed | Actual API charges (0.00 on free tier). |

A 100% score on any metric prints a warning. Treat that as a cue to inspect labels, not a result.

OCR pipelines share `parse.py` (regex/heuristics). The VLM is image → JSON. GPT-4o and Claude clients exist as `NotImplementedError` stubs behind the same `VlmClient` protocol.

## Tests

```bash
uv run pytest
```
