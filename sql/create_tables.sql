-- Create a DuckDB view over the streamed OFF JSONL.
-- Path is resolved at call time; replace ':JSONL_PATH:' or pass via parameter
-- substitution at the application layer (see src/db.py:register_jsonl_view).

-- name: create_view_off_raw
CREATE OR REPLACE VIEW off_raw AS
SELECT *
FROM read_json_auto(
    ':JSONL_PATH:',
    format='newline_delimited',
    ignore_errors=true,
    sample_size=-1,
    maximum_object_size=33554432
);

-- name: materialize_parquet
COPY (
    SELECT
        code,
        product_name,
        brands,
        brands_tags,
        countries,
        countries_tags,
        categories,
        categories_tags,
        ingredients_text,
        nutriscore_grade,
        ecoscore_grade,
        additives_n,
        last_modified_t,
        created_t,
        "energy-kcal_100g",
        fat_100g,
        sugars_100g,
        salt_100g,
        proteins_100g,
        fiber_100g
    FROM off_raw
) TO ':PARQUET_PATH:' (FORMAT PARQUET);
