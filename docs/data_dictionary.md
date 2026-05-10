# Data Dictionary — Open Food Facts subset

## License & attribution

The Open Food Facts data dump is licensed under the **Open Database License
(ODbL) 1.0**. Required attribution (verbatim from
[openfoodfacts.org/data](https://world.openfoodfacts.org/data)):

> "© Open Food Facts contributors — https://world.openfoodfacts.org —
> licensed under ODbL 1.0."

Implications of ODbL for downstream users:

- You may use, share, modify, and adapt the data, including for commercial use.
- You must **attribute** the source.
- If you publicly distribute a derivative database, you must do so under
  ODbL **(share-alike)**.
- "Public Domain" snippets (individual records) can be used without
  share-alike, but the dataset as a whole carries the share-alike duty.

This repository's source code is MIT-licensed; the OFF data is **not**
relicensed by being processed here. Anyone redistributing a derivative of
the OFF data must continue to respect ODbL.

## Source URL

- Page: <https://world.openfoodfacts.org/data>
- Direct dump: <https://static.openfoodfacts.org/data/openfoodfacts-products.jsonl.gz>

The dump is a single gzipped file of newline-delimited JSON records
(JSONL). Compressed it is well over 5 GB; uncompressed it is much larger.

## Sampling note

We never download the full dump. `src/download_data.py` opens an HTTP stream,
decodes gzip incrementally, and stops after `--limit` records. The full OFF
schema includes 200+ fields; this dictionary only covers the subset used in
this case study.

## Columns we use

| Column | Type | Notes |
|---|---|---|
| `code` | text | Product barcode. Should be 8 / 12 / 13 / 14 digits (EAN-8, UPC-A, EAN-13, ITF-14). |
| `product_name` | text | Free-text product name in the contributor's language. |
| `brands` | text | Comma-separated brand list. |
| `brands_tags` | text[] | Normalized brand slugs. |
| `countries` | text | Free-text comma-separated list of countries where the product is sold. |
| `countries_tags` | text[] | Normalized list, e.g. `en:france`, `en:germany`. |
| `categories` | text | Free-text comma-separated category list. |
| `categories_tags` | text[] | Normalized category slugs (`en:dairies`, etc). |
| `ingredients_text` | text | Ingredients as printed on the package. |
| `nutriscore_grade` | text | Letter grade `a`..`e` or NULL. |
| `ecoscore_grade` | text | Letter grade `a`..`e` or NULL. |
| `additives_n` | int | Count of additives detected from the ingredients text. |
| `last_modified_t` | bigint (unix) | Unix epoch — last edit time. |
| `created_t` | bigint (unix) | Unix epoch — first creation time. |
| `energy-kcal_100g` | double | Energy in kcal per 100 g. |
| `fat_100g` | double | Fat g per 100 g. |
| `sugars_100g` | double | Sugars g per 100 g. |
| `salt_100g` | double | Salt g per 100 g. |
| `proteins_100g` | double | Proteins g per 100 g. |
| `fiber_100g` | double | Fiber g per 100 g. |

## Plausibility caps used in validation

| Field | Lower | Upper | Reason |
|---|---|---|---|
| `energy-kcal_100g` | 0 | 900 | Pure fat is ~900 kcal / 100 g. |
| `fat_100g` | 0 | 100 | g per 100 g cannot exceed 100 g. |
| `sugars_100g` | 0 | 100 | Same. |
| `salt_100g` | 0 | 100 | Same. |
| `proteins_100g` | 0 | 100 | Same. |
| `fiber_100g` | 0 | 100 | Same. |
