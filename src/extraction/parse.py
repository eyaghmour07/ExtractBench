"""Deterministic OCR → field parser. Shared by Tesseract and EasyOCR."""

from __future__ import annotations

import re

from extraction.schema import ReceiptFields

_HEADER_SKIP = re.compile(
    r"^(tax\s*invoice|simplified\s*tax\s*invoice|invoice|receipt|cash\s*(bill|sale|receipt)|"
    r"gst\s*invoice|debit\s*note|credit\s*note|duplicate|original|guest\s*check|"
    r"sales\s*receipt|official\s*receipt)\b",
    re.I,
)
_PHONE_OR_FAX = re.compile(r"^(tel|phone|fax|hp|mobile|whatsapp)\b", re.I)
_MOSTLY_DIGITS = re.compile(r"^[\d\s\-()+./]+$")
_DATE_LABEL = re.compile(r"\b(date|dt|tarikh)\b", re.I)
_SUBTOTAL = re.compile(r"\bsub[\s\-]?total\b", re.I)
_TOTAL_LABEL = re.compile(
    r"\b((grand|nett?|net|final|amount)\s+)?total\b|\bamount\s+(due|payable)\b|"
    r"\btotal\s+amount\b|\btotal\s+sales\b",
    re.I,
)
_TOTAL_PENALTY = re.compile(
    r"\b(change|cash|tender(?:ed)?|paid|rounding|qty|quantity|item|gst\s*id|"
    r"invoice\s*no|receipt\s*no|save|discount)\b",
    re.I,
)
_MONEY = re.compile(
    r"(?:(?:rm|myr)\s*)?(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})",
    re.I,
)
# Numeric dates use / or - only. Month names are explicit so "Change 0.20" is not a date.
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE = re.compile(
    rf"\b("
    rf"\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}[/-]\d{{1,2}}[/-]\d{{1,2}}"
    rf"|\d{{1,2}}\s*{_MONTH}\s*,?\s*\d{{2,4}}"
    rf"|{_MONTH}\s+\d{{1,2}},?\s+\d{{2,4}}"
    rf")\b",
    re.I,
)


def parse_document(text: str, doc_type: str = "receipt") -> ReceiptFields:
    if doc_type == "form":
        return parse_form_text(text)
    if doc_type == "receipt":
        return parse_receipt_text(text)
    raise ValueError(f"Unknown document type {doc_type!r}")


def parse_receipt_text(text: str) -> ReceiptFields:
    lines = _nonzero_lines(text)
    return ReceiptFields(
        merchant=_parse_merchant(lines),
        date=_parse_date(lines, text),
        total=_parse_total(lines),
    )


_FORM_SKIP = re.compile(
    r"^(confidential|draft|see\s+reverse|page\s+\d+|continued|internal\s+use)\b",
    re.I,
)
_REF_LABEL = re.compile(
    r"\b(form\s*(no|number|#)|file\s*(no|number|#)|ref(?:erence)?(\s*(no|number|#))?|"
    r"registration\s*(no|number|#)|serial(\s*(no|number|#))?|id\s*(no|number)?)\b",
    re.I,
)
_REF_VALUE = re.compile(r"\b([A-Z]{0,4}\d[\dA-Z./-]{1,16})\b")


def parse_form_text(text: str) -> ReceiptFields:
    lines = _nonzero_lines(text)
    return ReceiptFields(
        title=_parse_form_title(lines),
        date=_parse_date(lines, text),
        reference=_parse_reference(lines),
    )


def _parse_form_title(lines: list[str]) -> str | None:
    picked: list[str] = []
    for line in lines[:16]:
        if _FORM_SKIP.match(line) or _PHONE_OR_FAX.match(line) or _MOSTLY_DIGITS.match(line):
            if picked:
                break
            continue
        if _looks_like_date_line(line) or _REF_LABEL.search(line):
            if picked:
                break
            continue
        if not _has_letters(line, min_letters=4):
            continue
        picked.append(line)
        if len(picked) >= 2 or _looks_complete_company(line):
            break
    return " ".join(picked) if picked else None


def _parse_reference(lines: list[str]) -> str | None:
    labeled: list[str] = []
    unlabeled: list[str] = []
    for line in lines[:24]:
        match = _REF_VALUE.search(line)
        if not match:
            continue
        value = match.group(1).strip(" ./")
        if _REF_LABEL.search(line):
            labeled.append(value)
        elif not _DATE.search(line):
            unlabeled.append(value)
    if labeled:
        return labeled[0]
    if unlabeled:
        return unlabeled[0]
    return None


def _nonzero_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _parse_merchant(lines: list[str]) -> str | None:
    picked: list[str] = []
    for line in lines[:12]:
        if _is_merchant_noise(line):
            if picked:
                break
            continue
        if _looks_like_date_line(line) or _looks_like_money_only(line):
            if picked:
                break
            continue
        if not _has_letters(line, min_letters=4):
            continue
        if _looks_like_handwritten_noise(line) and not _looks_complete_company(line):
            continue
        picked.append(line)
        # Company names on SROIE often wrap: "FOO SDN" / "BHD"
        if len(picked) >= 2 or _looks_complete_company(line):
            break
    if not picked:
        return None
    return " ".join(picked)


def _is_merchant_noise(line: str) -> bool:
    if _HEADER_SKIP.match(line):
        return True
    if _PHONE_OR_FAX.match(line):
        return True
    if _MOSTLY_DIGITS.match(line):
        return True
    if re.search(r"gst\s*(id|no|reg)", line, re.I):
        return True
    if re.match(r"^(no\.?|lot|jalan|jln|taman|pos\s*code)\b", line, re.I):
        return True
    return False


def _looks_complete_company(line: str) -> bool:
    return bool(
        re.search(r"\b(sdn\.?\s*bhd|bhd|ltd|limited|store|mart|enterprise|trading)\b", line, re.I)
    )


def _has_letters(line: str, min_letters: int) -> bool:
    return sum(ch.isalpha() for ch in line) >= min_letters


def _looks_like_handwritten_noise(line: str) -> bool:
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return True
    upper_ratio = sum(ch.isupper() for ch in letters) / len(letters)
    # SROIE headers are printed caps; mixed-case OCR is usually scribbles on the scan.
    if upper_ratio < 0.55 and not _looks_complete_company(line):
        return True
    junk = sum(ch in "{}[]<>|*~" for ch in line)
    return junk >= 2


def _looks_like_date_line(line: str) -> bool:
    return bool(_DATE.search(line)) and not _has_letters(line, 8)


def _looks_like_money_only(line: str) -> bool:
    stripped = re.sub(r"(rm|myr|\$)", "", line, flags=re.I).strip()
    return bool(re.fullmatch(r"[\d.,\s]+", stripped)) and "." in stripped


def _parse_date(lines: list[str], full_text: str) -> str | None:
    labeled: list[str] = []
    unlabeled: list[str] = []
    for line in lines:
        match = _DATE.search(line)
        if not match:
            continue
        value = match.group(1).strip()
        if _DATE_LABEL.search(line):
            labeled.append(value)
        else:
            unlabeled.append(value)
    if labeled:
        return labeled[0]
    if unlabeled:
        return unlabeled[0]
    match = _DATE.search(full_text)
    return match.group(1).strip() if match else None


def _parse_total(lines: list[str]) -> str | None:
    scored: list[tuple[float, int, str]] = []
    for idx, line in enumerate(lines):
        if _SUBTOTAL.search(line):
            continue
        amounts = [m.group(1) for m in _MONEY.finditer(line)]
        if not amounts:
            continue
        amount = _prefer_decimal_amount(amounts)
        if amount is None:
            continue
        score = 0.0
        if _TOTAL_LABEL.search(line):
            score += 5.0
        if re.search(r"\b(rm|myr)\b", line, re.I):
            score += 0.5
        if _TOTAL_PENALTY.search(line) and not _TOTAL_LABEL.search(line):
            score -= 4.0
        # Totals sit near the bottom of a receipt.
        score += idx / max(len(lines), 1)
        scored.append((score, idx, amount))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1]))
    best = scored[-1]
    if best[0] < 0:
        return None
    return best[2]


def _prefer_decimal_amount(amounts: list[str]) -> str | None:
    decimals = [a for a in amounts if re.search(r"\.\d{2}$", a)]
    if decimals:
        return decimals[-1].replace(",", "")
    return None
