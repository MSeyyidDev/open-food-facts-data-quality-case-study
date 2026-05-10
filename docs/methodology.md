# Methodology

## Pipeline

```
+------------------+    +------------------+    +-------------------+
| download_data.py | -> |  data/raw/*.jsonl| -> |  profile_data.py  |
| (stream + gzip)  |    |    (gitignored)  |    |  (DuckDB profile) |
+------------------+    +------------------+    +-------------------+
                                                          |
                                                          v
                +-----------------------+    +-------------------+
                | generate_figures.py   | -> | reports/figures/  |
                +-----------------------+    +-------------------+
                                                          |
                                                          v
                                           +---------------------------+
                                           | generate_report.py        |
                                           | + sql/quality_checks.sql  |
                                           +---------------------------+
                                                          |
                                                          v
                                          reports/data_quality_report.md
```

## Streaming download — how the gzip handling works

```
HTTP GET stream=True   ───►  response.raw  (raw gzip bytes, urllib3 stream)
                              │
                              ▼
                       gzip.GzipFile      (incremental inflate)
                              │
                              ▼
                  io.TextIOWrapper        (utf-8 decode, line-iteration)
                              │
                              ▼
                       json.loads(line)   (per-record JSON)
                              │
                              ▼
                       JSONL writer       (out file)
```

We never buffer the entire dump. Memory pressure is bounded by the gzip
window plus a single decoded line. As soon as `--limit` records have been
written, the iterator stops, the HTTP socket is closed, and the function
returns.

## DuckDB usage

DuckDB reads JSONL directly via `read_json_auto()` with
`format='newline_delimited'`. We register a view (`off_raw`) over the
streamed JSONL, which lets every quality check and analysis query run
without an explicit Pandas DataFrame round-trip. For larger samples,
`materialize_parquet()` writes a Parquet copy of the curated columns.

## Quality checks

Each check in `sql/quality_checks.sql` is a named SQL block (`-- name:
qc_*`). The Python helper `src.db.execute_named_blocks` parses the file,
runs each block, and returns row results. Results are surfaced both in
`reports/data_quality_report.md` and as the canonical answer for the
`pytest` suite.

## Validation rules — Python mirror

The same rules are also implemented in Python (`src/validate_data.py`)
so that synthetic records can be unit-tested without spinning up DuckDB.
The Python rule names match the SQL block names where applicable.

## Reproducibility

- Pinned dependencies (`requirements.txt`).
- The sample committed under `data/sample/` is the deterministic basis for
  CI tests. CI does not perform any network IO.
- The full streaming pipeline is exercised locally; the report numbers in
  the README reflect a real run captured at build time.
