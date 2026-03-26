# NEM Data Import Script

Downloader/cache-builder for AEMO MMSDM data using `nemosis`.

This script is now cache-only:
- it uses `nemosis.cache_compiler()` to build parquet cache files
- it does not load the final dataset into memory for analysis
- analysis notebooks can still use `dynamic_data_compiler(...)` later when reading from cache

## Quick Start

```bash
# Core tables for the most recent complete month
uv run python import_nem_data.py --core

# Full-year dispatch price cache build
uv run python import_nem_data.py --start 2025/01/01 --end 2025/12/31 --dispatchprice

# Multiple tables for a year
uv run python import_nem_data.py --core --start 2025/01/01 --end 2025/12/31
```

## What The Script Does

For each selected table, the script:
- counts how many parquet cache files already exist for the requested range
- calls `nemosis.cache_compiler(...)`
- streams native `nemosis` INFO output during download/build
- shows a one-line elapsed-time spinner between INFO messages
- reports how many parquet files were added

Cache location:

```text
./data/nemosis_cache
```

## Example Output

### Fully cached range

```text
Importing 1 table for 2025/01/01 to 2026/01/31

--- DISPATCHPRICE ---
    14 parquet files already cached
    INFO: Caching data for table DISPATCHPRICE
    0 files added, 0.0s

Done: 1/1 tables, 0.0s total
```

### Partially cached range

```text
Importing 1 table for 2024/01/01 to 2026/01/31

--- DISPATCHPRICE ---
    16 parquet files already cached
    INFO: Caching data for table DISPATCHPRICE
    INFO: Downloading data for table DISPATCHPRICE, year 2023, month 12
    INFO: Creating parquet file for DISPATCHPRICE, 2023, 12
    ...
    10 files added, 16.3s

Done: 1/1 tables, 16.3s total
```

Notes:
- `N parquet files already cached` is a pre-run count based on the actual `nemosis` search range for that table.
- `N files added` is the number of new parquet files created by this run.
- Repetitive `Cache for ... already compiled ...` messages from `nemosis` are suppressed because the pre-run cached count already covers that information.

## Supported Tables

### Core Dispatch/Pricing (`--core`)
| Flag | Table | Description |
|------|-------|-------------|
| `--dudetailsummary` | `DUDETAILSUMMARY` | Generator registration / capacity |
| `--dispatchprice` | `DISPATCHPRICE` | 5-minute regional spot prices |
| `--dispatchload` | `DISPATCHLOAD` | 5-minute generator dispatch |
| `--dispatchregionsum` | `DISPATCHREGIONSUM` | 5-minute regional demand and flows |

### Bidding (`--bids`)
| Flag | Table | Description |
|------|-------|-------------|
| `--biddayoffer` | `BIDDAYOFFER_D` | Daily bid availability |
| `--bidperoffer` | `BIDPEROFFER_D` | Bid price/quantity bands |

### Trading (`--trading`)
| Flag | Table | Description |
|------|-------|-------------|
| `--tradingprice` | `TRADINGPRICE` | 30-minute trading prices |
| `--tradingregionsum` | `TRADINGREGIONSUM` | 30-minute regional demand and losses |
| `--tradinginterconnect` | `TRADINGINTERCONNECT` | 30-minute interconnector flows |

### Forecasts (`--forecasts`)
| Flag | Table | Description |
|------|-------|-------------|
| `--predispatch-price` | `PREDISPATCHPRICE` | Price forecasts |
| `--predispatch-load` | `PREDISPATCHLOAD` | Unit dispatch forecasts |
| `--predispatch-region` | `PREDISPATCH_REGION_SOLUTION` | Regional forecasts |

### Other Supported Tables
| Flag | Table | Description |
|------|-------|-------------|
| `--gencondata` | `GENCONDATA` | Constraint coefficients |
| `--dispatchconstraint` | `DISPATCHCONSTRAINT` | Constraint shadow prices |
| `--rooftop-pv` | `ROOFTOP_PV_ACTUAL` | Distributed solar actuals |
| `--dispatch-scada` | `DISPATCH_UNIT_SCADA` | Unit SCADA telemetry |
| `--dispatch-unit-solution` | `DISPATCH_UNIT_SOLUTION` | Unit dispatch solution details |

## CLI Usage

```bash
uv run python import_nem_data.py [table flags] [date options]
```

Examples:

```bash
# One table
uv run python import_nem_data.py --dispatchprice

# Core group for a year
uv run python import_nem_data.py --core --start 2025/01/01 --end 2025/12/31

# Mixed custom selection
uv run python import_nem_data.py --dispatchprice --dispatchload --biddayoffer
```

Date behavior:
- If `--start` and `--end` are omitted, the script uses the most recent complete month.
- If dates are supplied without times, the script expands them to:
  - start: `00:00:00`
  - end: `23:55:00`

## Important Behavior Notes

### Cache-only by default

The script no longer uses `dynamic_data_compiler()` internally, so it does not build a combined in-memory DataFrame during import. This is important for large tables such as `DISPATCHLOAD`.

### Raw cache contents

The script does not apply `filter_cols` / `filter_values` during download because `cache_compiler()` does not support that interface.

That means cached parquet files contain the raw rows from the source table, including intervention rows where relevant.

If you want filtered data for analysis, apply filters when loading from cache later, for example in notebooks using `dynamic_data_compiler(..., filter_cols=..., filter_values=...)`.

### Resumable behavior

If a run is interrupted, re-running the same command will reuse already-built parquet files and only build the missing ones.

## Relationship To The Notebooks

Recommended workflow:
1. Use `import_nem_data.py` to populate `./data/nemosis_cache`.
2. Use notebooks to load only the tables and date ranges you need for analysis.
3. Apply filters such as `INTERVENTION=0` in analysis code, not in the downloader.

This keeps the downloader lightweight while preserving the existing notebook experience.
