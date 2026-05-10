# Cleaning decisions

This document records the cleaning rules applied in `src/clean_data.py`
and the reasoning behind each. Cleaning is intentionally **non-destructive**:
the raw streamed JSONL stays untouched in `data/raw/`; cleaned views are
materialized on demand.

## 1. Whitespace normalization

OFF is contributor-edited and contains many records with leading/trailing
whitespace, embedded tabs, or duplicated spaces from copy-paste artefacts.
We collapse all internal whitespace runs to a single space and strip the
result. Empty results become `NULL`.

## 2. Country and tag lower-casing

`countries`, `countries_tags`, `categories_tags`, `brands_tags` are
lower-cased and stripped. We dedupe lists while preserving order.

## 3. Barcode parsing

`code` (the barcode) is treated as text and may include hyphens, spaces, or
prefixes. We strip all non-digit characters via regex `\D+`. We do **not**
zero-pad shorter codes — that would silently rewrite identifiers. Length
validation (`is_valid_barcode_length`) accepts only EAN-8 (8), UPC-A (12),
EAN-13 (13), and ITF-14 (14).

## 4. Product name language prefix

Some OFF records carry a `xx:` language prefix in the free-text
`product_name` (e.g. `fr:Yaourt nature`). We strip the leading `[a-z]{2}:`
when present.

## 5. Empty-vs-null

OFF stores missing values as both empty string `""` and SQL `NULL`. All
cleaning routines coerce empty strings to `None`. The SQL quality checks
do the same with `TRIM(...) = ''` predicates.

## 6. What we do NOT do

- We do **not** dedupe by `code` automatically. Duplicate barcodes are
  flagged as a data quality issue (`qc_duplicate_barcodes`), not silently
  removed — they often signal a contributor merging or a regional fork.
- We do **not** clip implausible nutrient values to 100. They are flagged
  and left in place; clipping would hide the upstream data error.
- We do **not** translate or normalize free-text fields like
  `ingredients_text` — language detection and ingredient parsing are out
  of scope.
