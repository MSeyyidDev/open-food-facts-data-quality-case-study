"""Stream the Open Food Facts gzipped JSONL dump and write the first N records.

We never download the full ~5+ GB compressed dump. We open a streaming HTTP GET,
wrap it in `gzip.GzipFile`, decode line-by-line, and stop at `--limit`.

Usage
-----
    python src/download_data.py --limit 50000
    python src/download_data.py --limit 5000 --out data/raw/sample_smoke.jsonl

The output JSONL contains the raw OFF records (one JSON object per line).
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

import requests

OFF_DUMP_URL = (
    "https://static.openfoodfacts.org/data/openfoodfacts-products.jsonl.gz"
)
DEFAULT_LIMIT = 50_000
DEFAULT_OUT = "data/raw/openfoodfacts_sample.jsonl"
LOG_EVERY = 5_000
CHUNK_SIZE = 1 << 16  # 64 KB

logger = logging.getLogger("download_data")


def _stream_records(url: str, timeout: int = 60) -> Iterator[dict]:
    """Yield records one-by-one from the remote gzipped JSONL dump.

    Opens an HTTP stream, lets `gzip.GzipFile` do incremental decompression,
    and `json.loads` each newline-terminated record. The connection is closed
    as soon as the consumer stops iterating.
    """
    headers = {"User-Agent": "off-data-quality-case-study/0.1 (+research)"}
    with requests.get(url, stream=True, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        # `resp.raw` is a urllib3 stream — wrap it as a binary file-like.
        resp.raw.decode_content = False  # we want the raw gzip bytes
        with gzip.GzipFile(fileobj=resp.raw) as gz:
            text = io.TextIOWrapper(gz, encoding="utf-8", errors="replace")
            for line in text:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("skipping malformed JSON line")
                    continue


def download(limit: int, out_path: Path, url: str = OFF_DUMP_URL) -> int:
    """Stream `limit` records from `url` to `out_path`. Returns number written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    started = time.time()
    logger.info("Streaming up to %d records from %s", limit, url)
    logger.info("Writing JSONL to %s", out_path)

    with out_path.open("w", encoding="utf-8") as fh:
        for record in _stream_records(url):
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            written += 1
            if written % LOG_EVERY == 0:
                elapsed = time.time() - started
                rate = written / elapsed if elapsed else 0.0
                logger.info(
                    "  %d records written (%.0f rec/s, %.1fs elapsed)",
                    written,
                    rate,
                    elapsed,
                )
            if written >= limit:
                break

    elapsed = time.time() - started
    logger.info(
        "Done. %d records written to %s in %.1fs",
        written,
        out_path,
        elapsed,
    )
    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stream the first N records of the OFF JSONL dump."
    )
    p.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of records to fetch (default: {DEFAULT_LIMIT}).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(DEFAULT_OUT),
        help=f"Output JSONL path (default: {DEFAULT_OUT}).",
    )
    p.add_argument(
        "--url",
        type=str,
        default=OFF_DUMP_URL,
        help="Override the dump URL (for testing).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)
    if args.out.exists() and not args.force:
        size = args.out.stat().st_size
        logger.info(
            "Output %s already exists (%d bytes). Use --force to overwrite.",
            args.out,
            size,
        )
        return 0
    try:
        download(args.limit, args.out, args.url)
    except requests.RequestException as exc:
        logger.error("Network error: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
