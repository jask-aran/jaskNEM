#!/usr/bin/env python3
"""
NEM Data Import Script

Downloads AEMO market data via NEMOSIS with explicit table selection.

Usage:
    uv run import_nem_data.py --dispatchload --dispatchprice
    uv run import_nem_data.py --start 2025/01/01 --end 2025/12/31 --dispatchload
    uv run import_nem_data.py --all
"""

import argparse
import calendar
import glob
import os
import sys
import threading
import time
from datetime import datetime, timedelta

import logging

try:
    from nemosis import cache_compiler
    from nemosis import data_fetch_methods as nemosis_data_fetch_methods
    from nemosis import defaults as nemosis_defaults
    from nemosis import processing_info_maps as nemosis_processing_info_maps
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: uv pip install nemosis pandas")
    sys.exit(1)


# ── Table definitions ────────────────────────────────────────────────────────
TABLES = {
    # Core dispatch/pricing
    'dudetailsummary':     'DUDETAILSUMMARY',
    'dispatchprice':       'DISPATCHPRICE',
    'dispatchload':        'DISPATCHLOAD',
    'dispatchregionsum':   'DISPATCHREGIONSUM',
    'dispatch-scada':      'DISPATCH_UNIT_SCADA',

    # Trading (30-min)
    'tradingprice':        'TRADINGPRICE',
    'tradingregionsum':    'TRADINGREGIONSUM',
    'tradinginterconnect': 'TRADINGINTERCONNECT',

    # Pre-dispatch forecasts
    'predispatch-price':   'PREDISPATCHPRICE',
    'predispatch-load':    'PREDISPATCHLOAD',
    'predispatch-region':  'PREDISPATCH_REGION_SOLUTION',

    # Bidding
    'biddayoffer':         'BIDDAYOFFER_D',
    'bidperoffer':         'BIDPEROFFER_D',

    # Network constraints
    'gencondata':          'GENCONDATA',
    'dispatchconstraint':  'DISPATCHCONSTRAINT',

    # Renewables
    'rooftop-pv':          'ROOFTOP_PV_ACTUAL',

    # Unit solutions
    'dispatch-unit-solution': 'DISPATCH_UNIT_SOLUTION',
}


class SpinnerConsole:
    """Coordinate a one-line spinner with streaming log output."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.lock = threading.Lock()
        self.spinner_visible = False
        self.max_width = 0

    def _write(self, text):
        self.stream.write(text)
        self.stream.flush()

    def render(self, text):
        with self.lock:
            self.max_width = max(self.max_width, len(text))
            padded = text.ljust(self.max_width)
            self._write(f"\r{padded}")
            self.spinner_visible = True

    def clear(self):
        with self.lock:
            if self.spinner_visible or self.max_width:
                self._write("\r" + (" " * self.max_width) + "\r")
            self.spinner_visible = False

    def log(self, message):
        with self.lock:
            if self.spinner_visible or self.max_width:
                self._write("\r" + (" " * self.max_width) + "\r")
            self._write(f"{message}\n")
            self.spinner_visible = False


class NemosisLogHandler(logging.Handler):
    """Send NEMOSIS log records through the spinner-safe console."""

    def __init__(self, console):
        super().__init__()
        self.console = console

    def emit(self, record):
        try:
            message = record.getMessage()
            if "date range already compiled" in message:
                return
            self.console.log(self.format(record))
        except Exception:
            self.handleError(record)


def configure_nemosis_logging(console):
    """Route NEMOSIS INFO logs through a spinner-aware handler."""
    logger = logging.getLogger("nemosis")
    handler = NemosisLogHandler(console)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("    %(levelname)s: %(message)s"))

    original = {
        'level': logger.level,
        'handlers': list(logger.handlers),
        'propagate': logger.propagate,
    }

    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, original


def restore_nemosis_logging(logger, original):
    """Restore NEMOSIS logging state after a table download."""
    logger.handlers = original['handlers']
    logger.setLevel(original['level'])
    logger.propagate = original['propagate']


def get_most_recent_complete_month():
    """Calculate the most recent complete month."""
    now = datetime.now()
    if now.day == 1:
        last_month = (now - timedelta(days=2)).replace(day=1)
    else:
        last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)

    start = last_month.replace(hour=0, minute=0, second=0)
    _, last_day = calendar.monthrange(last_month.year, last_month.month)
    end = last_month.replace(day=last_day, hour=23, minute=55, second=0)
    return start, end


def normalize_start(value):
    """Normalize a CLI start date to a full timestamp string."""
    return f"{value} 00:00:00" if ' ' not in value else value


def normalize_end(value):
    """Normalize a CLI end date to a full timestamp string."""
    return f"{value} 23:55:00" if ' ' not in value else value


def cache_files_for_table(table_name, start_date, end_date, cache_dir, fformat='parquet'):
    """Return existing non-CSV cache files matching the requested table/date range."""
    (
        _,
        end_date,
        _,
        _,
        start_search,
    ) = nemosis_data_fetch_methods._set_up_dynamic_compilers(
        table_name, start_date, end_date, None
    )

    end_dt = datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
    start_search_dt = datetime.strptime(start_search, '%Y/%m/%d %H:%M:%S')
    table_type = nemosis_defaults.table_types[table_name]
    date_gen = nemosis_processing_info_maps.date_gen[table_type](start_search_dt, end_dt)

    matches = set()
    for year, month, day, index in date_gen:
        chunk = 0
        while True:
            chunk += 1
            filename_stub, full_filename, _ = nemosis_data_fetch_methods._create_filename(
                table_name, table_type, cache_dir, fformat, day, month, year, chunk, index
            )
            chunk_matches = glob.glob(full_filename)
            matches.update(chunk_matches)
            if not chunk_matches or '#' not in filename_stub:
                break

    return matches


def download_table(table_name, start_date, end_date, cache_dir):
    """Download a single NEMOSIS table. Returns True on success."""
    print(f"\n--- {table_name} ---", flush=True)
    t0 = time.time()
    result = {}
    console = SpinnerConsole()
    before_files = cache_files_for_table(table_name, start_date, end_date, cache_dir)
    cached_count = len(before_files)
    print(f"    {cached_count:,} parquet files already cached")
    logger, original_logging = configure_nemosis_logging(console)

    def run():
        try:
            cache_compiler(
                start_date, end_date, table_name, cache_dir,
                fformat='parquet',
            )
        except Exception as e:
            result['error'] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    blink = True
    while thread.is_alive():
        elapsed = f"{time.time() - t0:.0f}s"
        char = '⠿' if blink else ' '
        console.render(f"    {char} {elapsed} ")
        blink = not blink
        thread.join(timeout=0.3)

    console.clear()
    restore_nemosis_logging(logger, original_logging)

    if 'error' in result:
        print(f"    FAILED: {result['error']}")
        return False

    after_files = cache_files_for_table(table_name, start_date, end_date, cache_dir)
    files_added = len(after_files - before_files)
    print(f"    {files_added:,} files added, {time.time() - t0:.1f}s")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Download NEM market data via NEMOSIS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run import_nem_data.py --dispatchload --dispatchprice
  uv run import_nem_data.py --core --start 2025/01/01 --end 2025/12/31
  uv run import_nem_data.py --all

Groups:
  --all          All tables
  --core         Price, load, registration, regional summary
  --bids         Bidding data (day offer + price bands)
  --trading      30-min trading interval data
  --forecasts    Pre-dispatch forecasts
        """
    )

    parser.add_argument(
        '--start',
        help='Start YYYY/MM/DD; if used alone, end defaults to the latest complete month',
    )
    parser.add_argument(
        '--end',
        help='End YYYY/MM/DD; requires --start, otherwise the request is rejected',
    )
    parser.add_argument('--cache', default='./data/nemosis_cache')

    # Groups
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--core', action='store_true')
    parser.add_argument('--bids', action='store_true')
    parser.add_argument('--trading', action='store_true')
    parser.add_argument('--forecasts', action='store_true')

    # Individual tables
    for key in TABLES:
        parser.add_argument(f'--{key}', action='store_true')

    args = parser.parse_args()
    os.makedirs(args.cache, exist_ok=True)

    # Date range
    if args.start and args.end:
        start_date = normalize_start(args.start)
        end_date = normalize_end(args.end)
        period = f"{args.start} to {args.end}"
    elif args.start:
        _, default_end = get_most_recent_complete_month()
        start_date = normalize_start(args.start)
        end_date = default_end.strftime('%Y/%m/%d %H:%M:%S')
        period = f"{start_date} to {end_date}"
    elif args.end:
        print("ERROR: --end requires --start")
        sys.exit(1)
    else:
        s, e = get_most_recent_complete_month()
        start_date = s.strftime('%Y/%m/%d %H:%M:%S')
        end_date = e.strftime('%Y/%m/%d %H:%M:%S')
        period = s.strftime('%Y-%m')

    start_dt = datetime.strptime(start_date, '%Y/%m/%d %H:%M:%S')
    end_dt = datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
    if start_dt > end_dt:
        print(
            "ERROR: Start date must not be after end date. "
            f"Resolved end date is {end_date}."
        )
        sys.exit(1)

    # Build table list
    selected = []
    if args.all:
        selected = list(TABLES.keys())
    else:
        if args.core:
            selected.extend(['dudetailsummary', 'dispatchprice', 'dispatchload', 'dispatchregionsum'])
        if args.bids:
            selected.extend(['biddayoffer', 'bidperoffer'])
        if args.trading:
            selected.extend(['tradingprice', 'tradingregionsum', 'tradinginterconnect'])
        if args.forecasts:
            selected.extend(['predispatch-price', 'predispatch-load'])

        for key in TABLES:
            if getattr(args, key.replace('-', '_'), False):
                selected.append(key)

    selected = list(dict.fromkeys(selected))  # dedup

    if not selected:
        print("ERROR: No tables selected. Use --help")
        sys.exit(1)

    # Download
    n = len(selected)
    print(f"Importing {n} table{'s' if n != 1 else ''} for {period}")

    t_total = time.time()
    ok_count = 0
    try:
        for key in selected:
            if download_table(TABLES[key], start_date, end_date, args.cache):
                ok_count += 1
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)

    elapsed = time.time() - t_total
    print(f"\nDone: {ok_count}/{n} tables, {elapsed:.1f}s total")


if __name__ == '__main__':
    main()
