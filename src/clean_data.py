"""Cleaning routines for OFF records — stateless, deterministic, unit-tested."""

from __future__ import annotations

import re
from typing import Any, Iterable


_BARCODE_RE = re.compile(r"\D+")


def normalize_whitespace(value: Any) -> str | None:
    """Collapse internal whitespace and strip. Returns None for empty/None."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def normalize_country_code(value: Any) -> str | None:
    """Lower-case + strip. Drop empty results."""
    cleaned = normalize_whitespace(value)
    return cleaned.lower() if cleaned else None


def parse_barcode(value: Any) -> str | None:
    """Strip non-digits; return the canonical numeric barcode string.

    OFF barcodes (`code`) are typically EAN-13/UPC-A/EAN-8/ITF-14. We don't
    pad here — we only return digits. Empty results return None.
    """
    if value is None:
        return None
    digits = _BARCODE_RE.sub("", str(value))
    return digits or None


def is_valid_barcode_length(barcode: str | None) -> bool:
    """OFF accepts EAN-8, UPC-A (12), EAN-13, ITF-14."""
    if not barcode:
        return False
    return len(barcode) in (8, 12, 13, 14)


def normalize_product_name(value: Any) -> str | None:
    """Whitespace + tag-marker stripping. Returns None for empty after cleaning."""
    name = normalize_whitespace(value)
    if name is None:
        return None
    # Some OFF entries embed lang prefixes like 'fr:Yaourt' — drop the prefix.
    if re.match(r"^[a-z]{2}:", name):
        name = name.split(":", 1)[1].strip()
    return name or None


def normalize_tags(values: Iterable[Any] | None) -> list[str]:
    """Lowercase + dedupe + drop empties. Stable order."""
    if not values:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = normalize_country_code(v)
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def clean_record(record: dict) -> dict:
    """Apply the cleaning rules above to a single OFF record. Non-destructive."""
    cleaned = dict(record)
    if "product_name" in cleaned:
        cleaned["product_name"] = normalize_product_name(cleaned.get("product_name"))
    if "brands" in cleaned:
        cleaned["brands"] = normalize_whitespace(cleaned.get("brands"))
    if "code" in cleaned:
        cleaned["code"] = parse_barcode(cleaned.get("code"))
    if "countries" in cleaned:
        cleaned["countries"] = normalize_country_code(cleaned.get("countries"))
    if "countries_tags" in cleaned:
        cleaned["countries_tags"] = normalize_tags(cleaned.get("countries_tags"))
    if "categories_tags" in cleaned:
        cleaned["categories_tags"] = normalize_tags(cleaned.get("categories_tags"))
    if "brands_tags" in cleaned:
        cleaned["brands_tags"] = normalize_tags(cleaned.get("brands_tags"))
    return cleaned
