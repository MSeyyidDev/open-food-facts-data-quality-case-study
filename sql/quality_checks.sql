-- Open Food Facts — Data quality checks
-- Each query is preceded by `-- name: <id>` so it can be loaded by
-- src.db.execute_named_blocks(). Each query returns a single row whose LAST
-- column is the count of offending rows (the report layer reads col[-1]).

-- name: qc_total_rows
SELECT COUNT(*) AS total_rows FROM off_raw;

-- name: qc_missing_product_name
SELECT COUNT(*) AS n
FROM off_raw
WHERE product_name IS NULL
   OR TRIM(CAST(product_name AS VARCHAR)) = '';

-- name: qc_missing_brand
SELECT COUNT(*) AS n
FROM off_raw
WHERE brands IS NULL
   OR TRIM(CAST(brands AS VARCHAR)) = '';

-- name: qc_missing_country
SELECT COUNT(*) AS n
FROM off_raw
WHERE (countries IS NULL OR TRIM(CAST(countries AS VARCHAR)) = '')
  AND (countries_tags IS NULL OR LEN(countries_tags) = 0);

-- name: qc_missing_categories
SELECT COUNT(*) AS n
FROM off_raw
WHERE (categories IS NULL OR TRIM(CAST(categories AS VARCHAR)) = '')
  AND (categories_tags IS NULL OR LEN(categories_tags) = 0);

-- name: qc_missing_nutrition_block
SELECT COUNT(*) AS n
FROM off_raw
WHERE "energy-kcal_100g" IS NULL
  AND fat_100g IS NULL
  AND sugars_100g IS NULL
  AND salt_100g IS NULL
  AND proteins_100g IS NULL
  AND fiber_100g IS NULL;

-- name: qc_invalid_barcode_length
SELECT COUNT(*) AS n
FROM off_raw
WHERE code IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(CAST(code AS VARCHAR), '\D', '', 'g')) NOT IN (8, 12, 13, 14);

-- name: qc_implausible_energy
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST("energy-kcal_100g" AS DOUBLE) > 900;

-- name: qc_implausible_fat
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST(fat_100g AS DOUBLE) > 100;

-- name: qc_implausible_sugars
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST(sugars_100g AS DOUBLE) > 100;

-- name: qc_implausible_salt
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST(salt_100g AS DOUBLE) > 100;

-- name: qc_implausible_proteins
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST(proteins_100g AS DOUBLE) > 100;

-- name: qc_negative_nutrition_values
SELECT COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST("energy-kcal_100g" AS DOUBLE) < 0
   OR TRY_CAST(fat_100g AS DOUBLE) < 0
   OR TRY_CAST(sugars_100g AS DOUBLE) < 0
   OR TRY_CAST(salt_100g AS DOUBLE) < 0
   OR TRY_CAST(proteins_100g AS DOUBLE) < 0
   OR TRY_CAST(fiber_100g AS DOUBLE) < 0;

-- name: qc_duplicate_barcodes
WITH normalized AS (
    SELECT REGEXP_REPLACE(CAST(code AS VARCHAR), '\D', '', 'g') AS code_n
    FROM off_raw
    WHERE code IS NOT NULL
)
SELECT COUNT(*) AS n
FROM (
    SELECT code_n
    FROM normalized
    WHERE code_n <> ''
    GROUP BY code_n
    HAVING COUNT(*) > 1
);

-- name: qc_invalid_country_tag
WITH exploded AS (
    SELECT UNNEST(countries_tags) AS tag
    FROM off_raw
    WHERE countries_tags IS NOT NULL
)
SELECT COUNT(*) AS n
FROM exploded
WHERE tag IS NOT NULL
  AND tag <> ''
  AND tag NOT LIKE 'en:%';

-- name: qc_unparseable_dates
SELECT COUNT(*) AS n
FROM off_raw
WHERE (last_modified_t IS NOT NULL AND TRY_CAST(last_modified_t AS BIGINT) IS NULL)
   OR (created_t       IS NOT NULL AND TRY_CAST(created_t       AS BIGINT) IS NULL);
