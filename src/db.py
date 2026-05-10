"""DuckDB helpers for the OFF case study.

We use DuckDB's `read_json_auto` to read the streamed JSONL directly with no
intermediate Parquet conversion required. For larger samples, callers can
materialize the JSONL into a Parquet file via `materialize_parquet`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import duckdb


# Subset of OFF columns we actually use in this case study. The full schema has
# 200+ columns — see `docs/assumptions_and_limitations.md`.
KEY_COLUMNS: tuple[str, ...] = (
    "code",
    "product_name",
    "brands",
    "brands_tags",
    "countries",
    "countries_tags",
    "categories",
    "categories_tags",
    "ingredients_text",
    "nutriscore_grade",
    "ecoscore_grade",
    "additives_n",
    "last_modified_t",
    "created_t",
)

# Nutriment-100g fields are scattered across the OFF schema; we treat them
# as the union of the conventional subset.
NUTRITION_100G_FIELDS: tuple[str, ...] = (
    "energy-kcal_100g",
    "fat_100g",
    "sugars_100g",
    "salt_100g",
    "proteins_100g",
    "fiber_100g",
)


def connect(database: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection. In-memory by default."""
    return duckdb.connect(str(database))


def register_jsonl_view(
    con: duckdb.DuckDBPyConnection,
    jsonl_path: str | Path,
    view_name: str = "off_raw",
) -> None:
    """Materialize the JSONL into a temp table containing only the columns
    we use, then register `view_name` over that table.

    OFF nutrients live inside a nested `nutriments` object in the raw dump
    but are flattened to top-level in our slim sample. The COALESCE here
    handles both shapes. We materialize once so subsequent SELECTs don't
    re-read the (very large) JSONL each time.
    """
    jsonl_path = Path(jsonl_path).as_posix()
    # Inspect available top-level columns once.
    desc_rows = con.execute(
        f"""
        DESCRIBE SELECT * FROM read_json_auto(
            '{jsonl_path}',
            format='newline_delimited',
            ignore_errors=true,
            sample_size=200,
            maximum_object_size=33554432
        );
        """
    ).fetchall()
    available = {row[0] for row in desc_rows}
    has_nutriments = "nutriments" in available

    def col(name: str, alias: str | None = None) -> str:
        a = f' AS "{alias or name}"'
        if name in available:
            return f'"{name}"{a}'
        return f"NULL{a}"

    def nutrient_col(name: str) -> str:
        top = f'"{name}"' if name in available else "NULL"
        if has_nutriments:
            nested = f"TRY_CAST(nutriments->>'{name}' AS DOUBLE)"
            return f'COALESCE(TRY_CAST({top} AS DOUBLE), {nested}) AS "{name}"'
        return f'TRY_CAST({top} AS DOUBLE) AS "{name}"'

    select_clauses = [
        col("code"),
        col("product_name"),
        col("brands"),
        col("brands_tags"),
        col("countries"),
        col("countries_tags"),
        col("categories"),
        col("categories_tags"),
        col("ingredients_text"),
        col("nutriscore_grade"),
        col("ecoscore_grade"),
        col("additives_n"),
        col("last_modified_t"),
        col("created_t"),
        nutrient_col("energy-kcal_100g"),
        nutrient_col("fat_100g"),
        nutrient_col("sugars_100g"),
        nutrient_col("salt_100g"),
        nutrient_col("proteins_100g"),
        nutrient_col("fiber_100g"),
    ]
    select_sql = ",\n            ".join(select_clauses)
    table_name = f"_{view_name}_t"
    con.execute(f"DROP TABLE IF EXISTS {table_name};")
    con.execute(
        f"""
        CREATE TEMP TABLE {table_name} AS
        SELECT
            {select_sql}
        FROM read_json_auto(
            '{jsonl_path}',
            format='newline_delimited',
            ignore_errors=true,
            sample_size=200,
            maximum_object_size=33554432
        );
        """
    )
    con.execute(
        f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM {table_name};"
    )


def materialize_parquet(
    con: duckdb.DuckDBPyConnection,
    jsonl_path: str | Path,
    parquet_path: str | Path,
    columns: Iterable[str] | None = None,
) -> int:
    """Write a Parquet copy of the JSONL with only the columns we care about.

    Returns the row count written. If `columns` is None, write the keys plus
    the standard nutrition-100g block.
    """
    jsonl_path = Path(jsonl_path).as_posix()
    parquet_path = Path(parquet_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(columns) if columns else list(KEY_COLUMNS) + list(NUTRITION_100G_FIELDS)
    quoted = ", ".join(f'"{c}"' for c in cols)
    con.execute(
        f"""
        COPY (
            SELECT {quoted}
            FROM read_json_auto(
                '{jsonl_path}',
                format='newline_delimited',
                ignore_errors=true,
                sample_size=-1,
                maximum_object_size=33554432
            )
        ) TO '{parquet_path.as_posix()}' (FORMAT PARQUET);
        """
    )
    count = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_path.as_posix()}');"
    ).fetchone()[0]
    return int(count)


def execute_named_blocks(
    con: duckdb.DuckDBPyConnection, sql_path: str | Path
) -> dict[str, list[tuple]]:
    """Execute a `.sql` file split by `-- name: <block_name>` markers.

    Returns a dict mapping block name to a list of result rows.
    """
    text = Path(sql_path).read_text(encoding="utf-8")
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current is not None:
                blocks[current] = buf
            current = stripped.split(":", 1)[1].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        blocks[current] = buf

    results: dict[str, list[tuple]] = {}
    for name, sql_lines in blocks.items():
        sql = "\n".join(sql_lines).strip()
        if not sql:
            continue
        try:
            results[name] = con.execute(sql).fetchall()
        except duckdb.Error as exc:
            results[name] = [("ERROR", str(exc))]
    return results
