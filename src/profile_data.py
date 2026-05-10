"""Profile a streamed OFF JSONL file with DuckDB and Pandas.

Outputs a JSON profile to `data/processed/profile.json` containing:
- total_rows
- per-column null counts and null_pct
- distinct counts for high-cardinality identifiers
- nutrient summary stats (min/median/max/p99)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import duckdb

from .db import KEY_COLUMNS, NUTRITION_100G_FIELDS, connect, register_jsonl_view

logger = logging.getLogger("profile_data")


def profile(jsonl_path: Path) -> dict:
    con = connect()
    register_jsonl_view(con, jsonl_path, "off_raw")

    total_rows = con.execute("SELECT COUNT(*) FROM off_raw;").fetchone()[0]
    logger.info("Total rows: %d", total_rows)

    profile: dict = {
        "source": str(jsonl_path),
        "total_rows": int(total_rows),
        "columns": {},
        "nutrition_stats": {},
    }

    available = {row[0] for row in con.execute("DESCRIBE off_raw").fetchall()}

    for col in KEY_COLUMNS + NUTRITION_100G_FIELDS:
        if col not in available:
            profile["columns"][col] = {
                "present_in_schema": False,
                "null_count": total_rows,
                "null_pct": 100.0,
                "distinct_count": 0,
            }
            continue
        # Treat empty strings as null for OFF text fields.
        nulls = con.execute(
            f"""
            SELECT COUNT(*) FROM off_raw
            WHERE "{col}" IS NULL
               OR (TYPEOF("{col}") = 'VARCHAR' AND TRIM(CAST("{col}" AS VARCHAR)) = '')
            """
        ).fetchone()[0]
        # Distinct counts: only run on low-cardinality / small text columns —
        # `ingredients_text` and similar large free-text fields blow up.
        SKIP_DISTINCT = {
            "ingredients_text",
            "categories_tags",
            "brands_tags",
            "countries_tags",
        }
        if col in SKIP_DISTINCT:
            distinct = None
        else:
            try:
                distinct = con.execute(
                    f'SELECT APPROX_COUNT_DISTINCT("{col}") FROM off_raw'
                ).fetchone()[0]
            except duckdb.Error:
                distinct = None
        profile["columns"][col] = {
            "present_in_schema": True,
            "null_count": int(nulls),
            "null_pct": round(100.0 * nulls / total_rows, 2) if total_rows else 0.0,
            "distinct_count": int(distinct) if distinct is not None else None,
        }

    for col in NUTRITION_100G_FIELDS:
        if col not in available:
            continue
        try:
            row = con.execute(
                f"""
                SELECT
                    MIN(TRY_CAST("{col}" AS DOUBLE)) AS min_val,
                    MEDIAN(TRY_CAST("{col}" AS DOUBLE)) AS median_val,
                    AVG(TRY_CAST("{col}" AS DOUBLE)) AS avg_val,
                    MAX(TRY_CAST("{col}" AS DOUBLE)) AS max_val,
                    QUANTILE_CONT(TRY_CAST("{col}" AS DOUBLE), 0.99) AS p99
                FROM off_raw
                WHERE "{col}" IS NOT NULL
                """
            ).fetchone()
            profile["nutrition_stats"][col] = {
                "min": row[0],
                "median": row[1],
                "mean": row[2],
                "max": row[3],
                "p99": row[4],
            }
        except duckdb.Error as exc:
            profile["nutrition_stats"][col] = {"error": str(exc)}

    return profile


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Profile an OFF JSONL file.")
    p.add_argument("jsonl", type=Path, help="Path to OFF JSONL.")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/profile.json"),
        help="Output path for the JSON profile.",
    )
    args = p.parse_args(argv)

    if not args.jsonl.exists():
        logger.error("Input not found: %s", args.jsonl)
        return 1

    result = profile(args.jsonl)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote profile to %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
