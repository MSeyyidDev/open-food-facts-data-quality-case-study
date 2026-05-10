-- Open Food Facts — Analytical queries
-- Each query is preceded by `-- name: <id>` so it can be loaded by
-- src.db.execute_named_blocks().

-- name: product_count_by_country
WITH exploded AS (
    SELECT UNNEST(countries_tags) AS tag
    FROM off_raw
    WHERE countries_tags IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS country, COUNT(*) AS product_count
FROM exploded
WHERE tag IS NOT NULL AND tag <> ''
GROUP BY country
ORDER BY product_count DESC
LIMIT 30;

-- name: top_brands
SELECT brands, COUNT(*) AS n
FROM off_raw
WHERE brands IS NOT NULL AND TRIM(CAST(brands AS VARCHAR)) <> ''
GROUP BY brands
ORDER BY n DESC
LIMIT 50;

-- name: top_categories
WITH exploded AS (
    SELECT UNNEST(categories_tags) AS tag
    FROM off_raw
    WHERE categories_tags IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS category, COUNT(*) AS n
FROM exploded
WHERE tag IS NOT NULL AND tag <> ''
GROUP BY category
ORDER BY n DESC
LIMIT 50;

-- name: nutriscore_distribution
SELECT COALESCE(LOWER(nutriscore_grade), 'unknown') AS grade, COUNT(*) AS n
FROM off_raw
GROUP BY grade
ORDER BY n DESC;

-- name: ecoscore_distribution
SELECT COALESCE(LOWER(ecoscore_grade), 'unknown') AS grade, COUNT(*) AS n
FROM off_raw
GROUP BY grade
ORDER BY n DESC;

-- name: avg_sugar_by_category
WITH exploded AS (
    SELECT UNNEST(categories_tags) AS tag, TRY_CAST(sugars_100g AS DOUBLE) AS s
    FROM off_raw
    WHERE categories_tags IS NOT NULL AND sugars_100g IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS category,
       COUNT(*) AS n,
       ROUND(AVG(s), 2) AS avg_sugar_g_per_100g
FROM exploded
WHERE tag IS NOT NULL AND s BETWEEN 0 AND 100
GROUP BY category
HAVING n >= 5
ORDER BY n DESC
LIMIT 20;

-- name: avg_fat_by_category
WITH exploded AS (
    SELECT UNNEST(categories_tags) AS tag, TRY_CAST(fat_100g AS DOUBLE) AS f
    FROM off_raw
    WHERE categories_tags IS NOT NULL AND fat_100g IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS category,
       COUNT(*) AS n,
       ROUND(AVG(f), 2) AS avg_fat_g_per_100g
FROM exploded
WHERE tag IS NOT NULL AND f BETWEEN 0 AND 100
GROUP BY category
HAVING n >= 5
ORDER BY n DESC
LIMIT 20;

-- name: avg_salt_by_country
WITH exploded AS (
    SELECT UNNEST(countries_tags) AS tag, TRY_CAST(salt_100g AS DOUBLE) AS s
    FROM off_raw
    WHERE countries_tags IS NOT NULL AND salt_100g IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS country,
       COUNT(*) AS n,
       ROUND(AVG(s), 3) AS avg_salt_g_per_100g
FROM exploded
WHERE tag IS NOT NULL AND s BETWEEN 0 AND 100
GROUP BY country
HAVING n >= 10
ORDER BY n DESC
LIMIT 20;

-- name: additives_distribution
SELECT TRY_CAST(additives_n AS INTEGER) AS additives_count, COUNT(*) AS n
FROM off_raw
WHERE additives_n IS NOT NULL
GROUP BY additives_count
ORDER BY additives_count;

-- name: data_completeness_score_by_country
WITH exploded AS (
    SELECT UNNEST(countries_tags) AS tag,
        CAST(product_name IS NOT NULL AND TRIM(CAST(product_name AS VARCHAR)) <> '' AS INT) AS has_name,
        CAST(brands IS NOT NULL AND TRIM(CAST(brands AS VARCHAR)) <> '' AS INT) AS has_brand,
        CAST(categories_tags IS NOT NULL AND LEN(categories_tags) > 0 AS INT) AS has_cat,
        CAST(ingredients_text IS NOT NULL AND TRIM(CAST(ingredients_text AS VARCHAR)) <> '' AS INT) AS has_ing
    FROM off_raw
    WHERE countries_tags IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS country,
       COUNT(*) AS n,
       ROUND(100.0 * AVG((has_name + has_brand + has_cat + has_ing) / 4.0), 2) AS completeness_pct
FROM exploded
WHERE tag IS NOT NULL AND tag <> ''
GROUP BY country
HAVING n >= 50
ORDER BY completeness_pct DESC
LIMIT 20;

-- name: data_completeness_score_by_category
WITH exploded AS (
    SELECT UNNEST(categories_tags) AS tag,
        CAST(product_name IS NOT NULL AND TRIM(CAST(product_name AS VARCHAR)) <> '' AS INT) AS has_name,
        CAST(brands IS NOT NULL AND TRIM(CAST(brands AS VARCHAR)) <> '' AS INT) AS has_brand,
        CAST(ingredients_text IS NOT NULL AND TRIM(CAST(ingredients_text AS VARCHAR)) <> '' AS INT) AS has_ing,
        CAST(fat_100g IS NOT NULL AS INT) AS has_nut
    FROM off_raw
    WHERE categories_tags IS NOT NULL
)
SELECT REPLACE(tag, 'en:', '') AS category,
       COUNT(*) AS n,
       ROUND(100.0 * AVG((has_name + has_brand + has_ing + has_nut) / 4.0), 2) AS completeness_pct
FROM exploded
WHERE tag IS NOT NULL AND tag <> ''
GROUP BY category
HAVING n >= 20
ORDER BY completeness_pct DESC
LIMIT 20;

-- name: products_added_per_year
SELECT
    EXTRACT('year' FROM TO_TIMESTAMP(TRY_CAST(created_t AS BIGINT))) AS year,
    COUNT(*) AS n
FROM off_raw
WHERE TRY_CAST(created_t AS BIGINT) IS NOT NULL
GROUP BY year
ORDER BY year;
