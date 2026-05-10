"""Tests for cleaning, validation, and the SQL pipeline.

CI runs these without network access, against the committed sample at
`data/sample/openfoodfacts_sample.jsonl`.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from src import clean_data, validate_data
from src.db import (
    KEY_COLUMNS,
    NUTRITION_100G_FIELDS,
    connect,
    execute_named_blocks,
    register_jsonl_view,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = REPO_ROOT / "data" / "sample" / "openfoodfacts_sample.jsonl"
QC_SQL = REPO_ROOT / "sql" / "quality_checks.sql"
ANALYSIS_SQL = REPO_ROOT / "sql" / "analysis_queries.sql"
CREATE_SQL = REPO_ROOT / "sql" / "create_tables.sql"


# ---------- clean_data ----------

def test_normalize_whitespace_collapses_runs():
    assert clean_data.normalize_whitespace("  hello   world  ") == "hello world"


def test_normalize_whitespace_returns_none_for_empty():
    assert clean_data.normalize_whitespace("") is None
    assert clean_data.normalize_whitespace(None) is None
    assert clean_data.normalize_whitespace("   ") is None


def test_normalize_country_code_lowercases():
    assert clean_data.normalize_country_code(" FR ") == "fr"


def test_parse_barcode_strips_non_digits():
    assert clean_data.parse_barcode("3-017-62032250-5") == "3017620322505"
    assert clean_data.parse_barcode("abc") is None


def test_is_valid_barcode_length():
    assert clean_data.is_valid_barcode_length("12345678")     # EAN-8
    assert clean_data.is_valid_barcode_length("123456789012") # UPC-A
    assert clean_data.is_valid_barcode_length("1234567890123")
    assert clean_data.is_valid_barcode_length("12345678901234")
    assert not clean_data.is_valid_barcode_length("123")
    assert not clean_data.is_valid_barcode_length("")
    assert not clean_data.is_valid_barcode_length(None)


def test_normalize_product_name_strips_lang_prefix():
    assert clean_data.normalize_product_name("fr:Yaourt nature") == "Yaourt nature"
    assert clean_data.normalize_product_name(" Bread ") == "Bread"


def test_normalize_tags_dedupes_and_lowers():
    out = clean_data.normalize_tags(["en:France", "en:france", "  en:GERMANY  "])
    assert out == ["en:france", "en:germany"]


def test_clean_record_full():
    raw = {
        "code": " 0-3017-62032250-5 ",
        "product_name": "  fr:Yaourt   nature  ",
        "brands": "  Danone  ",
        "countries_tags": ["en:FRANCE", "en:france"],
    }
    cleaned = clean_data.clean_record(raw)
    assert cleaned["code"] == "03017620322505"
    assert cleaned["product_name"] == "Yaourt nature"
    assert cleaned["brands"] == "Danone"
    assert cleaned["countries_tags"] == ["en:france"]


# ---------- validate_data ----------

def test_validate_flags_implausible_fat():
    issues = validate_data.check_implausible_fat({"fat_100g": 200})
    assert len(issues) == 1
    assert issues[0].rule == "implausible_fat"


def test_validate_accepts_normal_fat():
    assert validate_data.check_implausible_fat({"fat_100g": 12.5}) == []


def test_validate_flags_implausible_energy():
    issues = validate_data.check_implausible_energy({"energy-kcal_100g": 5000})
    assert len(issues) == 1


def test_validate_flags_negative_sugar():
    issues = validate_data.check_implausible_sugars({"sugars_100g": -1})
    assert len(issues) == 1


def test_validate_flags_invalid_country_tag():
    issues = validate_data.check_country_tags({"countries_tags": ["france"]})
    assert any(i.rule == "invalid_country_tag" for i in issues)


def test_validate_invalid_barcode():
    issues = validate_data.check_barcode({"code": "123"})
    assert any(i.rule == "invalid_barcode_length" for i in issues)


def test_validate_record_aggregates_issues():
    bad = {
        "code": "x",
        "product_name": "",
        "brands": "",
        "countries": "",
        "countries_tags": [],
        "categories": "",
        "categories_tags": [],
        "fat_100g": 200,
    }
    issues = validate_data.validate_record(bad)
    rules = {i.rule for i in issues}
    assert "missing_product_name" in rules
    assert "missing_brand" in rules
    assert "missing_country" in rules
    assert "missing_categories" in rules
    assert "implausible_fat" in rules


# ---------- SQL parses cleanly ----------

def test_quality_checks_sql_loads():
    text = QC_SQL.read_text(encoding="utf-8")
    # at least 12 named blocks (we have 16+).
    assert text.count("-- name:") >= 12


def test_analysis_queries_sql_loads():
    text = ANALYSIS_SQL.read_text(encoding="utf-8")
    assert text.count("-- name:") >= 10


def test_create_tables_sql_present():
    assert CREATE_SQL.exists()
    assert "off_raw" in CREATE_SQL.read_text(encoding="utf-8")


# ---------- Smoke: full pipeline against the committed sample ----------

@pytest.fixture(scope="module")
def con():
    if not SAMPLE_PATH.exists():
        pytest.skip(f"sample not found: {SAMPLE_PATH}")
    c = connect()
    register_jsonl_view(c, SAMPLE_PATH, "off_raw")
    yield c
    c.close()


def test_sample_has_rows(con):
    n = con.execute("SELECT COUNT(*) FROM off_raw").fetchone()[0]
    assert n > 0


def test_quality_checks_run(con):
    results = execute_named_blocks(con, QC_SQL)
    assert "qc_total_rows" in results
    total = int(results["qc_total_rows"][0][0])
    assert total > 0


def test_analysis_queries_run(con):
    results = execute_named_blocks(con, ANALYSIS_SQL)
    expected = {
        "product_count_by_country",
        "top_brands",
        "top_categories",
        "nutriscore_distribution",
    }
    assert expected.issubset(results.keys())


def test_implausible_fat_detected_when_injected(tmp_path):
    """Inject a row with fat_100g=200 and verify qc_implausible_fat fires."""
    base_records = []
    if SAMPLE_PATH.exists():
        with SAMPLE_PATH.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 50:
                    break
                base_records.append(line.strip())
    # Inject a deliberately broken record
    bad = {"code": "9999999999999", "product_name": "Stunt Fat", "fat_100g": 200}
    inj_path = tmp_path / "inj.jsonl"
    with inj_path.open("w", encoding="utf-8") as f:
        for line in base_records:
            if line:
                f.write(line + "\n")
        f.write(json.dumps(bad) + "\n")

    c = connect()
    register_jsonl_view(c, inj_path, "off_raw")
    results = execute_named_blocks(c, QC_SQL)
    assert "qc_implausible_fat" in results
    flagged = int(results["qc_implausible_fat"][0][0])
    assert flagged >= 1
    c.close()


def test_key_columns_constant_present():
    assert "code" in KEY_COLUMNS
    assert "product_name" in KEY_COLUMNS
    assert "fat_100g" in NUTRITION_100G_FIELDS
