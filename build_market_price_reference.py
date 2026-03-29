#!/usr/bin/env python3
"""
Build a consolidated market price thresholds reference file from NEMOSIS cache.

This reads the monthly MARKET_PRICE_THRESHOLDS parquet snapshots produced by
NEMOSIS, de-duplicates them by effective date/version, and writes one canonical
reference parquet outside the cache directory.

Example:
    uv run python build_market_price_reference.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


SNAPSHOT_RE = re.compile(r"(\d{12})\.parquet$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build consolidated market price thresholds reference data."
    )
    parser.add_argument(
        "--cache",
        default="./data/nemosis_cache",
        help="Path to the NEMOSIS parquet cache directory.",
    )
    parser.add_argument(
        "--output",
        default="./data/reference/market_price_thresholds.parquet",
        help="Output parquet path for the consolidated reference file.",
    )
    return parser.parse_args()


def snapshot_from_name(path: Path) -> pd.Timestamp:
    match = SNAPSHOT_RE.search(path.name)
    if not match:
        raise ValueError(f"Could not parse snapshot timestamp from {path.name}")
    return pd.to_datetime(match.group(1), format="%Y%m%d%H%M")


def find_threshold_files(cache_dir: Path) -> list[Path]:
    files = sorted(cache_dir.glob("*MARKET_PRICE_THRESHOLDS*.parquet"))
    return [path for path in files if path.is_file()]


def load_frames(files: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_parquet(path).copy()
        frame["source_file"] = path.name
        frame["source_snapshot"] = snapshot_from_name(path)
        frames.append(frame)

    if not frames:
        raise FileNotFoundError("No MARKET_PRICE_THRESHOLDS parquet files found.")

    combined = pd.concat(frames, ignore_index=True)
    combined["EFFECTIVEDATE"] = pd.to_datetime(combined["EFFECTIVEDATE"])
    combined["VERSIONNO"] = combined["VERSIONNO"].astype("int64")
    combined["VOLL"] = combined["VOLL"].astype("int64")
    combined["MARKETPRICEFLOOR"] = combined["MARKETPRICEFLOOR"].astype("int64")
    return combined


def consolidate_thresholds(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.sort_values(["source_snapshot", "EFFECTIVEDATE", "VERSIONNO"])
        .drop_duplicates(["EFFECTIVEDATE", "VERSIONNO"], keep="last")
        .sort_values(["EFFECTIVEDATE", "VERSIONNO"])
        .reset_index(drop=True)
    )


def main() -> int:
    args = parse_args()
    cache_dir = Path(args.cache)
    output_path = Path(args.output)

    files = find_threshold_files(cache_dir)
    if not files:
        print(f"ERROR: No MARKET_PRICE_THRESHOLDS parquet files found under {cache_dir}")
        return 1

    combined = load_frames(files)
    reference = consolidate_thresholds(combined)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    reference.to_parquet(output_path, index=False)

    print(f"Read {len(files)} snapshot files")
    print(f"Combined rows: {len(combined):,}")
    print(f"Reference rows: {len(reference):,}")
    print(f"Output: {output_path}")
    print()
    print(reference.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
