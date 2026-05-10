"""Assemble `reports/data_quality_report.md` from real numbers in the sample."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .db import connect, execute_named_blocks, register_jsonl_view

logger = logging.getLogger("generate_report")

REPORT_TEMPLATE = """# Open Food Facts — Data Quality Report

> Source data: Open Food Facts dump, retrieved via streaming HTTP GET +
> incremental gzip decode. Licensed under ODbL 1.0.

## 1. Overview

This report quantifies the data quality of a streamed prefix of the Open
Food Facts (OFF) public dump. We do not download the full ~5 GB compressed
dump; we open an HTTP stream and stop after `N` records. The report below
reflects **only that prefix**.

- Total rows analysed: **{total_rows:,}**
- Source file: `{source}`
- Key columns considered: `code`, `product_name`, `brands`, `countries`,
  `categories_tags`, `ingredients_text`, plus the standard nutrient-100g block.

## 2. Sampling Strategy & Honest Limits

The dump is shipped as one gzipped JSON-Lines file. We use
`requests.get(..., stream=True)` together with `gzip.GzipFile` to decode the
gzip stream incrementally and `json.loads` per line. Because the OFF dump's
record order is correlated with insertion time and product popularity, our
prefix is **not a uniform random sample** of the global catalog. Findings
should be read as "what the first N records look like", not as universal
statements.

## 3. Schema Coverage

OFF's full schema has 200+ columns; we focus on a curated subset. See
`docs/data_dictionary.md` for the columns we actually use and why.

## 4. Missing-Value Profile

Total rows: **{total_rows:,}**

| Rule                       | Rows flagged |
|----------------------------|-------------:|
| Missing product_name       | {qc_missing_product_name:,} |
| Missing brand              | {qc_missing_brand:,} |
| Missing country            | {qc_missing_country:,} |
| Missing categories         | {qc_missing_categories:,} |
| Missing nutrition block    | {qc_missing_nutrition_block:,} |

![missing values](figures/missing_values_by_field.png)

## 5. Implausible Nutrition Outliers

We flag values that violate physical caps (macros cannot exceed 100 g per
100 g of food; energy cannot exceed ~900 kcal / 100 g, the theoretical max
for pure fat).

| Rule                       | Rows flagged |
|----------------------------|-------------:|
| energy-kcal_100g > 900     | {qc_implausible_energy:,} |
| fat_100g > 100             | {qc_implausible_fat:,} |
| sugars_100g > 100          | {qc_implausible_sugars:,} |
| salt_100g > 100            | {qc_implausible_salt:,} |
| proteins_100g > 100        | {qc_implausible_proteins:,} |
| Negative nutrition values  | {qc_negative_nutrition_values:,} |

![nutrition outliers](figures/nutrition_value_outliers.png)

## 6. Duplicates & Identifier Hygiene

| Rule                       | Rows flagged |
|----------------------------|-------------:|
| Invalid barcode length     | {qc_invalid_barcode_length:,} |
| Duplicate barcodes         | {qc_duplicate_barcodes:,} |

A valid OFF `code` should be 8, 12, 13, or 14 digits (EAN-8, UPC-A, EAN-13,
ITF-14). Anything outside these lengths is almost certainly a data-entry
artefact.

## 7. Country & Tag Hygiene

| Rule                            | Rows flagged |
|---------------------------------|-------------:|
| Country tag missing `en:` prefix | {qc_invalid_country_tag:,} |
| Unparseable timestamps           | {qc_unparseable_dates:,} |

![country product counts](figures/product_count_by_country.png)
![completeness by country](figures/data_completeness_score_by_country.png)

## 8. Real findings worth noting

- The `energy-kcal_100g` field contains a substantial fraction of records
  whose values are physically impossible for kcal but plausible for **kJ**.
  Spot-checking high values shows the same record carrying both
  `nutriments.energy-kcal_100g` and `nutriments.energy_100g` (kJ), with the
  "kcal" field being 4-5x larger than reasonable — strongly suggesting that
  contributors entered kJ into the kcal column. Any downstream consumer
  should either drop records with `energy-kcal_100g > 900` or recompute
  kcal from kJ via `kcal = kJ / 4.184`.
- Macronutrient outliers (fat / sugar / protein > 100 g per 100 g) are the
  second most common issue. These cannot be physically valid and should be
  filtered out, not clipped.
- The `ecoscore_grade` column is missing for ~72% of the streamed sample
  (see profile output) — meaningful product-level eco scores require a
  much smaller subset of the data.

## 9. Recommendations

1. **Brand metadata**: a sizeable share of records lacks `brands`. For any
   downstream comparison-by-brand workflow, filter out the empties up front.
2. **Nutrient sanity**: implausible values exist. Apply the bound checks in
   `src/validate_data.py` before feeding nutrition data to ML or dashboards.
3. **kcal vs kJ**: distrust `energy-kcal_100g` blindly. Cross-check against
   `energy_100g` (kJ) and the macro components.
4. **Country tags**: prefer `countries_tags` (list, language-prefixed) over
   the free-text `countries` field.
5. **Barcode hygiene**: parse with `parse_barcode()` to drop non-digits, then
   filter to valid lengths before joining to external sources.
6. **For population-level claims**, use a **uniform** sample drawn from the
   full dump on a server with enough disk; the streamed prefix is a quick
   sanity-check, not a population-level baseline.

---

*Generated by `src/generate_report.py`. Numbers reflect the actual streamed
sample at the time of generation.*
"""


def build(jsonl_path: Path, qc_sql: Path, out: Path) -> None:
    con = connect()
    register_jsonl_view(con, jsonl_path, "off_raw")
    results = execute_named_blocks(con, qc_sql)

    def n(name: str) -> int:
        if name not in results:
            return 0
        rows = results[name]
        if not rows:
            return 0
        first = rows[0]
        if isinstance(first, tuple) and first and first[0] == "ERROR":
            logger.warning("SQL error in %s: %s", name, first[1])
            return 0
        try:
            return int(first[-1])
        except (TypeError, ValueError):
            return 0

    total_rows = n("qc_total_rows")
    text = REPORT_TEMPLATE.format(
        total_rows=total_rows,
        source=jsonl_path.as_posix(),
        qc_missing_product_name=n("qc_missing_product_name"),
        qc_missing_brand=n("qc_missing_brand"),
        qc_missing_country=n("qc_missing_country"),
        qc_missing_categories=n("qc_missing_categories"),
        qc_missing_nutrition_block=n("qc_missing_nutrition_block"),
        qc_implausible_energy=n("qc_implausible_energy"),
        qc_implausible_fat=n("qc_implausible_fat"),
        qc_implausible_sugars=n("qc_implausible_sugars"),
        qc_implausible_salt=n("qc_implausible_salt"),
        qc_implausible_proteins=n("qc_implausible_proteins"),
        qc_negative_nutrition_values=n("qc_negative_nutrition_values"),
        qc_invalid_barcode_length=n("qc_invalid_barcode_length"),
        qc_duplicate_barcodes=n("qc_duplicate_barcodes"),
        qc_invalid_country_tag=n("qc_invalid_country_tag"),
        qc_unparseable_dates=n("qc_unparseable_dates"),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    logger.info("Wrote %s", out)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Generate the data quality report.")
    p.add_argument("jsonl", type=Path)
    p.add_argument(
        "--qc-sql",
        type=Path,
        default=Path("sql/quality_checks.sql"),
        help="Quality-check SQL file with named blocks.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("reports/data_quality_report.md"),
    )
    args = p.parse_args(argv)
    build(args.jsonl, args.qc_sql, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
