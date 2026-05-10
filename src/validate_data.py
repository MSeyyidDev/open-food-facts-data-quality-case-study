"""Validation rules over OFF records.

Each rule reads a record-like mapping and returns a list of `Issue` instances.
The same rules are mirrored as SQL in `sql/quality_checks.sql`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .clean_data import is_valid_barcode_length, parse_barcode

# Plausibility caps for nutrient values per 100 g — anything above is almost
# certainly a unit-of-measure error or a typo. 900 kcal / 100 g is the
# theoretical max (pure fat), and macros can never exceed 100 g / 100 g.
ENERGY_KCAL_MAX_PER_100G = 900.0
GRAMS_MAX_PER_100G = 100.0

# Recognized OFF country tag prefixes (the dataset uses `en:` for English
# canonical names like `en:france`).
VALID_TAG_PREFIXES = ("en:",)


@dataclass(frozen=True)
class Issue:
    rule: str
    message: str
    field: str | None = None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_product_name(record: dict) -> list[Issue]:
    name = record.get("product_name")
    if name is None or (isinstance(name, str) and not name.strip()):
        return [Issue("missing_product_name", "product_name is empty", "product_name")]
    return []


def check_brand(record: dict) -> list[Issue]:
    brand = record.get("brands")
    if brand is None or (isinstance(brand, str) and not brand.strip()):
        return [Issue("missing_brand", "brands is empty", "brands")]
    return []


def check_country(record: dict) -> list[Issue]:
    countries = record.get("countries")
    tags = record.get("countries_tags")
    if (not countries) and (not tags):
        return [Issue("missing_country", "no countries info", "countries")]
    return []


def check_categories(record: dict) -> list[Issue]:
    cats = record.get("categories")
    tags = record.get("categories_tags")
    if (not cats) and (not tags):
        return [Issue("missing_categories", "no categories info", "categories")]
    return []


def check_barcode(record: dict) -> list[Issue]:
    code = parse_barcode(record.get("code"))
    if not code:
        return [Issue("missing_barcode", "code is empty", "code")]
    if not is_valid_barcode_length(code):
        return [
            Issue(
                "invalid_barcode_length",
                f"barcode length {len(code)} not in (8,12,13,14)",
                "code",
            )
        ]
    return []


def check_nutrition_block(record: dict) -> list[Issue]:
    fields = (
        "energy-kcal_100g",
        "fat_100g",
        "sugars_100g",
        "salt_100g",
        "proteins_100g",
        "fiber_100g",
    )
    if all(record.get(f) in (None, "") for f in fields):
        return [
            Issue(
                "missing_nutrition_block",
                "no nutrient-100g values present",
                "nutriments",
            )
        ]
    return []


def _bound_check(
    record: dict, field: str, lo: float, hi: float, rule: str
) -> list[Issue]:
    val = _to_float(record.get(field))
    if val is None:
        return []
    if val < lo:
        return [Issue(rule, f"{field}={val} below {lo}", field)]
    if val > hi:
        return [Issue(rule, f"{field}={val} above {hi}", field)]
    return []


def check_implausible_energy(record: dict) -> list[Issue]:
    return _bound_check(
        record, "energy-kcal_100g", 0.0, ENERGY_KCAL_MAX_PER_100G, "implausible_energy"
    )


def check_implausible_fat(record: dict) -> list[Issue]:
    return _bound_check(record, "fat_100g", 0.0, GRAMS_MAX_PER_100G, "implausible_fat")


def check_implausible_sugars(record: dict) -> list[Issue]:
    return _bound_check(
        record, "sugars_100g", 0.0, GRAMS_MAX_PER_100G, "implausible_sugars"
    )


def check_implausible_salt(record: dict) -> list[Issue]:
    return _bound_check(record, "salt_100g", 0.0, GRAMS_MAX_PER_100G, "implausible_salt")


def check_implausible_proteins(record: dict) -> list[Issue]:
    return _bound_check(
        record, "proteins_100g", 0.0, GRAMS_MAX_PER_100G, "implausible_proteins"
    )


def check_country_tags(record: dict) -> list[Issue]:
    tags = record.get("countries_tags") or []
    if not tags:
        return []
    issues: list[Issue] = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if not tag.startswith(VALID_TAG_PREFIXES):
            issues.append(
                Issue(
                    "invalid_country_tag",
                    f"tag '{tag}' missing canonical en: prefix",
                    "countries_tags",
                )
            )
    return issues


ALL_RULES: tuple[Callable[[dict], list[Issue]], ...] = (
    check_product_name,
    check_brand,
    check_country,
    check_categories,
    check_barcode,
    check_nutrition_block,
    check_implausible_energy,
    check_implausible_fat,
    check_implausible_sugars,
    check_implausible_salt,
    check_implausible_proteins,
    check_country_tags,
)


def validate_record(record: dict) -> list[Issue]:
    """Apply every rule to one record. Returns a (possibly empty) list of Issues."""
    issues: list[Issue] = []
    for rule in ALL_RULES:
        issues.extend(rule(record))
    return issues


def validate_records(records: Iterable[dict]) -> list[tuple[int, Issue]]:
    """Iterate records and return (row_index, issue) pairs."""
    out: list[tuple[int, Issue]] = []
    for idx, rec in enumerate(records):
        for issue in validate_record(rec):
            out.append((idx, issue))
    return out
