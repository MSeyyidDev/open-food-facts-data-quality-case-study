"""Generate the report figures from the streamed OFF sample.

Writes at least 6 PNGs into `reports/figures/`. Each chart carries an
"Open Food Facts (ODbL)" source caption.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .db import KEY_COLUMNS, NUTRITION_100G_FIELDS, connect, register_jsonl_view

logger = logging.getLogger("generate_figures")

CAPTION = "Source: Open Food Facts (ODbL 1.0)"
FIG_DIR_DEFAULT = Path("reports/figures")


def _save(fig: plt.Figure, path: Path) -> None:
    fig.text(0.99, 0.01, CAPTION, ha="right", fontsize=8, color="#666")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", path)


def _safe_count(con, query: str) -> int:
    return int(con.execute(query).fetchone()[0])


def fig_missing_values(con, out: Path) -> None:
    available = {row[0] for row in con.execute("DESCRIBE off_raw").fetchall()}
    cols = [c for c in KEY_COLUMNS + NUTRITION_100G_FIELDS if c in available]
    total = _safe_count(con, "SELECT COUNT(*) FROM off_raw")
    pcts: list[tuple[str, float]] = []
    for col in cols:
        nulls = _safe_count(
            con,
            f"""
            SELECT COUNT(*) FROM off_raw
            WHERE "{col}" IS NULL
               OR (TYPEOF("{col}") = 'VARCHAR' AND TRIM(CAST("{col}" AS VARCHAR)) = '')
            """,
        )
        pcts.append((col, 100.0 * nulls / total if total else 0.0))
    pcts.sort(key=lambda t: t[1])

    fig, ax = plt.subplots(figsize=(10, 7))
    labels = [c for c, _ in pcts]
    values = [v for _, v in pcts]
    ax.barh(labels, values, color="#4A6FA5")
    ax.set_xlabel("Missing values (%)")
    ax.set_title("Missing values by field — OFF streamed sample")
    ax.set_xlim(0, 100)
    for i, v in enumerate(values):
        ax.text(min(v + 1, 99), i, f"{v:.1f}%", va="center", fontsize=8)
    _save(fig, out)


def fig_country_counts(con, out: Path) -> None:
    rows = con.execute(
        """
        WITH exploded AS (
            SELECT UNNEST(countries_tags) AS tag
            FROM off_raw
            WHERE countries_tags IS NOT NULL
        )
        SELECT tag, COUNT(*) AS n
        FROM exploded
        WHERE tag IS NOT NULL AND tag <> ''
        GROUP BY tag ORDER BY n DESC LIMIT 20;
        """
    ).fetchall()
    if not rows:
        logger.warning("No countries data; skipping country chart.")
        return
    labels = [r[0].replace("en:", "") for r in rows][::-1]
    values = [r[1] for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(labels, values, color="#2E8B57")
    ax.set_xlabel("Number of products")
    ax.set_title("Top 20 countries by product count")
    _save(fig, out)


def fig_top_brands(con, out: Path) -> None:
    rows = con.execute(
        """
        SELECT brands, COUNT(*) AS n
        FROM off_raw
        WHERE brands IS NOT NULL AND TRIM(CAST(brands AS VARCHAR)) <> ''
        GROUP BY brands ORDER BY n DESC LIMIT 20;
        """
    ).fetchall()
    if not rows:
        logger.warning("No brands data; skipping top brands chart.")
        return
    labels = [str(r[0])[:50] for r in rows][::-1]
    values = [r[1] for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(labels, values, color="#8C4A4A")
    ax.set_xlabel("Number of products")
    ax.set_title("Top 20 brands by product count")
    _save(fig, out)


def fig_top_categories(con, out: Path) -> None:
    rows = con.execute(
        """
        WITH exploded AS (
            SELECT UNNEST(categories_tags) AS tag
            FROM off_raw
            WHERE categories_tags IS NOT NULL
        )
        SELECT tag, COUNT(*) AS n
        FROM exploded
        WHERE tag IS NOT NULL AND tag <> ''
        GROUP BY tag ORDER BY n DESC LIMIT 20;
        """
    ).fetchall()
    if not rows:
        logger.warning("No categories data; skipping categories chart.")
        return
    labels = [r[0].replace("en:", "") for r in rows][::-1]
    values = [r[1] for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(labels, values, color="#5C5C8A")
    ax.set_xlabel("Number of products")
    ax.set_title("Top 20 categories")
    _save(fig, out)


def fig_nutrition_outliers(con, out: Path) -> None:
    fields = [
        ("fat_100g", "Fat (g/100g)"),
        ("sugars_100g", "Sugars (g/100g)"),
        ("salt_100g", "Salt (g/100g)"),
        ("proteins_100g", "Proteins (g/100g)"),
    ]
    available = {row[0] for row in con.execute("DESCRIBE off_raw").fetchall()}
    series_data: list[tuple[str, list[float]]] = []
    for field, label in fields:
        if field not in available:
            continue
        rows = con.execute(
            f"""
            SELECT TRY_CAST("{field}" AS DOUBLE)
            FROM off_raw
            WHERE "{field}" IS NOT NULL
            """
        ).fetchall()
        vals = [r[0] for r in rows if r[0] is not None]
        if vals:
            series_data.append((label, vals))
    if not series_data:
        logger.warning("No nutrition data; skipping outlier chart.")
        return

    fig, axes = plt.subplots(1, len(series_data), figsize=(4 * len(series_data), 6))
    if len(series_data) == 1:
        axes = [axes]
    for ax, (label, vals) in zip(axes, series_data):
        ax.boxplot(vals, vert=True, widths=0.6)
        ax.set_title(label)
        ax.set_ylabel("g per 100 g")
        ax.axhline(100, color="red", linestyle="--", linewidth=1, alpha=0.6)
    fig.suptitle("Nutrition value outliers (red line = 100 g cap)")
    fig.tight_layout()
    _save(fig, out)


def fig_completeness_by_country(con, out: Path) -> None:
    rows = con.execute(
        """
        WITH exploded AS (
            SELECT UNNEST(countries_tags) AS tag,
                CAST(product_name IS NOT NULL AND TRIM(CAST(product_name AS VARCHAR)) <> '' AS INT) AS has_name,
                CAST(brands IS NOT NULL AND TRIM(CAST(brands AS VARCHAR)) <> '' AS INT) AS has_brand,
                CAST(categories_tags IS NOT NULL AND LEN(categories_tags) > 0 AS INT) AS has_cat,
                CAST(ingredients_text IS NOT NULL AND TRIM(CAST(ingredients_text AS VARCHAR)) <> '' AS INT) AS has_ing
            FROM off_raw
            WHERE countries_tags IS NOT NULL
        )
        SELECT tag,
               COUNT(*) AS n,
               AVG(has_name) AS pct_name,
               AVG(has_brand) AS pct_brand,
               AVG(has_cat) AS pct_cat,
               AVG(has_ing) AS pct_ing
        FROM exploded
        WHERE tag IS NOT NULL AND tag <> ''
        GROUP BY tag
        HAVING n >= 50
        ORDER BY n DESC
        LIMIT 15;
        """
    ).fetchall()
    if not rows:
        logger.warning("No country/completeness data; skipping completeness chart.")
        return
    labels = [r[0].replace("en:", "") for r in rows]
    avg = [(r[2] + r[3] + r[4] + r[5]) / 4 * 100 for r in rows]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(labels[::-1], avg[::-1], color="#B07050")
    ax.set_xlabel("Mean key-field completeness (%)")
    ax.set_xlim(0, 100)
    ax.set_title("Data completeness score by country (top 15 by row count)")
    _save(fig, out)


def fig_nutriscore_distribution(con, out: Path) -> None:
    rows = con.execute(
        """
        SELECT COALESCE(nutriscore_grade, 'unknown') AS g, COUNT(*) AS n
        FROM off_raw
        GROUP BY g ORDER BY n DESC;
        """
    ).fetchall()
    if not rows:
        logger.warning("No nutriscore data; skipping nutriscore chart.")
        return
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    colors = {
        "a": "#1E8E3E", "b": "#73C03A", "c": "#F0C419",
        "d": "#E97E2E", "e": "#D03A3A", "unknown": "#999999",
    }
    bar_colors = [colors.get(str(l).lower(), "#999999") for l in labels]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, values, color=bar_colors)
    ax.set_ylabel("Number of products")
    ax.set_title("Nutri-Score distribution")
    _save(fig, out)


def generate_all(jsonl_path: Path, out_dir: Path = FIG_DIR_DEFAULT) -> int:
    con = connect()
    register_jsonl_view(con, jsonl_path, "off_raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_missing_values(con, out_dir / "missing_values_by_field.png")
    fig_country_counts(con, out_dir / "product_count_by_country.png")
    fig_top_brands(con, out_dir / "top_brands.png")
    fig_top_categories(con, out_dir / "top_categories.png")
    fig_nutrition_outliers(con, out_dir / "nutrition_value_outliers.png")
    fig_completeness_by_country(con, out_dir / "data_completeness_score_by_country.png")
    fig_nutriscore_distribution(con, out_dir / "nutriscore_distribution.png")
    return len(list(out_dir.glob("*.png")))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Generate report figures from OFF JSONL.")
    p.add_argument("jsonl", type=Path, help="Input JSONL.")
    p.add_argument("--out", type=Path, default=FIG_DIR_DEFAULT, help="Figure dir.")
    args = p.parse_args(argv)
    n = generate_all(args.jsonl, args.out)
    logger.info("Total figures in %s: %d", args.out, n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
