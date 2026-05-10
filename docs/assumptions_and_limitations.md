# Assumptions and limitations

## 1. Streamed prefix, not random sample

The Open Food Facts dump is shipped as a single gzipped JSONL file. We use
HTTP range-streaming + incremental gzip decoding, then stop at `--limit`
records (default 50,000). **The result is the first N records**, not a
uniform random sample of the global catalog.

OFF records are dumped roughly in insertion-time order. That means our
prefix is biased toward older or earlier-contributed products and away
from the most recently added ones. **Population-level statements such as
"X% of all OFF products lack a brand" are not justified by this sample**;
the same statement scoped to "the streamed prefix used in this study" is
fine.

## 2. Schema scope

OFF's full record schema has 200+ fields, including dozens of nutrient
variants and many language-specific text fields. We chose a 20-column
subset that captures product identity, classification, key nutrients, and
metadata. Any field outside that subset is intentionally not analysed.

## 3. Validation thresholds

The plausibility caps (energy ≤ 900 kcal / 100 g, macros ≤ 100 g / 100 g)
are physical upper bounds, not statistical outlier detection. A
`fat_100g = 99` value is not flagged even though it's commercially rare;
only literally impossible values are flagged. This keeps the rule list
defensible without relying on category-specific baselines.

## 4. Barcode length only — not checksum

`is_valid_barcode_length` checks the EAN/UPC length (8/12/13/14 digits)
but does **not** verify the GTIN check digit. Implementing checksum
verification is straightforward but would add false positives for the
many contributor-edited or partial barcodes in OFF.

## 5. Language and translation

`product_name`, `categories`, and `ingredients_text` are stored in many
languages with no consistent column-level language tag. We do not attempt
language detection or translation. Counts of "missing product name" can
therefore include records whose name is present but in an unexpected
language.

## 6. Time semantics

`created_t` and `last_modified_t` are Unix epoch seconds. They reflect
**database edit time**, not when the product was launched commercially.
Year-over-year additions reflect contributor activity, not market behavior.

## 7. Reproducibility caveats

The OFF dump is a moving target — it changes daily. Re-running the
streaming download will fetch a different prefix as new products are added
at the head of the file (or as old ones are deleted). The committed
`data/sample/` snapshot is the only frozen artefact; running the full
pipeline against a fresh stream will produce slightly different numbers.

## 8. Out of scope

- Cross-record entity resolution (deduplicating products that differ only
  by trailing whitespace in `product_name`).
- Image quality / OCR validation.
- Nutrient inference from ingredients.
- Multi-language category alignment.
