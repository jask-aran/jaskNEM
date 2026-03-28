# Notebook 1.5 — Constraint Binding Attribution

## Summary
Create a new notebook, `Constraint_Binding_Attribution.ipynb`, that explains how to move from observed congestion symptoms to interval-level binding attribution for the `2026-01-26` SA event already used in Notebook 1.3. Keep the first version narrow and operational: use `DISPATCHCONSTRAINT` as the required new input and reuse cached `DISPATCHPRICE`, `DISPATCHREGIONSUM`, and `DISPATCHINTERCONNECTORRES` for market context.

Solve the missing context problem directly from event-period data, not from a dynamic enrichment workflow. For this notebook, constraint identification context must come from `DISPATCHCONSTRAINT` fields available in the Jan 2026 window (`CONSTRAINTID`, `GENCONID_EFFECTIVEDATE`, `GENCONID_VERSIONNO`, and interval behavior), tied back to Price Spike Autopsy timing.

The notebook should answer one question cleanly: during the SA spike window, which constraints had non-zero marginal value, when did they bind, and how does that line up with SA-VIC price separation and elevated `V-SA` flow?

## Key Changes

### Notebook structure
- Reuse the helper pattern already established in [Price_Spike_Autopsy.ipynb](/home/jask/jaskNEM/Price_Spike_Autopsy.ipynb) and [Interconnector_Flows.ipynb](/home/jask/jaskNEM/Interconnector_Flows.ipynb): local `cache_files(...)`, `with_interval_end(...)`, Polars lazy scans, and explicit `INTERVENTION = 0` filtering.
- Fix the event scope to the same 48-hour window as Notebook 1.3:
  - `2026-01-25 00:00:00` to `2026-01-27 00:00:00`
- Load:
  - `DISPATCHCONSTRAINT` as the required attribution table
  - `DISPATCHPRICE` for `SA1` and `VIC1`
  - `DISPATCHREGIONSUM` for `SA1` and `VIC1`
  - `DISPATCHINTERCONNECTORRES` for `V-SA`
- No `GENCONDATA` join logic in this notebook.
- Add one event-specific identity build step:
  - create an event-local constraint catalog keyed by `CONSTRAINTID`
  - include `GENCONID_EFFECTIVEDATE` and `GENCONID_VERSIONNO` so each active constraint has a reproducible equation-version fingerprint for the Jan 2026 case study

### Analysis frame / interfaces
- Build one notebook-local normalized event frame keyed by `interval_end` and `constraint_id` with:
  - `interval_end`
  - `constraint_id`
  - `marginal_value`
  - `violation_degree`
  - `rhs`
  - `lhs`
  - `region_a`, `region_b`
  - `rrp_a`, `rrp_b`
  - `price_spread`
  - `abs_price_spread`
  - `v_sa_mw_flow`
  - `sa_net_interchange`
  - `vic_net_interchange`
  - `gencon_effective_date`
  - `gencon_version_no`
- Add derived identity helpers for this event only:
  - `constraint_family` (prefix grouping from `CONSTRAINTID`, e.g. text before first `_` where useful)
  - `constraint_fingerprint` = (`CONSTRAINTID`, `gencon_effective_date`, `gencon_version_no`)
- Fix the region mapping to `VIC1` vs `SA1`.
- Define:
  - `price_spread = rrp_sa - rrp_vic`
  - `abs_price_spread = abs(price_spread)`
  - `binding_candidate = marginal_value != 0`
- Rank constraints within the event window by:
  - frequency of non-zero marginal value
  - peak absolute marginal value
  - cumulative absolute marginal value
- Treat `CONSTRAINTID` as the stable identifier in all tables and charts, even when descriptive metadata is available.

### Notebook sections and outputs
- Opening markdown:
  - explain the difference between realised symptoms and constraint attribution
  - state clearly that this notebook is an interval-level binding view, not a full NEMDE equation decomposition
  - state that this is a direct extension of the `2026-01-26` Price Spike Autopsy case, using only event-period data for constraint identification context
- Section 1: Event recap
  - compact reprise of SA1 price spike timing, SA-VIC spread, and `V-SA` flow during the 48-hour window
  - one two-panel context chart: prices/spread above, `V-SA` flow below
- Section 2: Constraint activity scan
  - summary table of all event-window constraints with non-zero marginal value
  - include count of active intervals, max absolute marginal value, and cumulative absolute marginal value
  - show the top 10 constraints by cumulative absolute marginal value
- Section 3: Binding timeline
  - interval-level time series of the top 3 to 5 constraints by absolute marginal value
  - overlay SA-VIC spread or SA price on a secondary axis so timing alignment is visible
  - explicitly highlight the peak SA price interval and list the active constraints at that timestamp
- Section 4: Constraint identity for this case study
  - compact catalog for dominant constraints showing:
    - `CONSTRAINTID`
    - `GENCONID_EFFECTIVEDATE`
    - `GENCONID_VERSIONNO`
    - active-interval count
    - peak absolute marginal value
    - cumulative absolute marginal value
  - short interpretation of whether one fingerprint dominates the event or whether control rotates across fingerprints
- Section 5: Constraint-to-market linkage
  - scatter or binned plot of `abs_price_spread` versus absolute marginal value for the dominant constraint
  - compact table for the top spike intervals showing:
    - `interval_end`
    - SA price
    - VIC price
    - spread
    - `V-SA` flow
    - top active constraint IDs
    - their marginal values
  - short markdown interpretation of whether the same constraint dominates throughout the run or whether the binding driver changes across intervals
- Section 6: Findings
  - end with 5 to 7 concise analyst takeaways
  - one takeaway must explicitly separate:
    - “the interconnector looked tight” from realised flow/spread data
    - “this named constraint carried non-zero marginal value” from the constraint table
  - final note should state what can and cannot be concluded from event-period `DISPATCHCONSTRAINT` identity fields alone

### Scope boundaries
- No importer or downloader code changes are part of Notebook 1.5.
- No full constraint-equation parsing or coefficient-level decomposition in v1.
- No attempt to infer transfer limits from `DISPATCHINTERCONNECTORRES`.
- No multi-event framework in v1; this notebook is intentionally built around the single `2026-01-26` SA case.
- No dynamic/generalized metadata pipeline in v1.
- No dependency on `GENCONDATA` in v1.

## Test Plan
- Notebook executes end-to-end with local cache when `DISPATCHCONSTRAINT` is present, with no `GENCONDATA` dependency.
- Schema checks pass for all required tables and timestamp parsing produces no null `interval_end` values.
- Event-window joins produce unique `interval_end` plus `constraint_id` rows with complete SA/VIC price context.
- The top-constraint summary table populates with at least one non-zero-marginal-value constraint during the spike run.
- The peak SA price interval shows a reproducible list of active constraint IDs and marginal values.
- Event-local constraint catalog populates `GENCONID_EFFECTIVEDATE` and `GENCONID_VERSIONNO` for dominant constraints.
- Final findings do not overclaim exact physical mechanism beyond what interval-level `DISPATCHCONSTRAINT` supports.

## Data Preflight And Fallback Commands
- Run this preflight check before building the notebook to confirm required cache coverage and schema for the `2026-01-25` to `2026-01-27` case window:

```bash
uv run python - <<'PY'
import polars as pl
from glob import glob

required = {
    "DISPATCHCONSTRAINT": (
        "data/nemosis_cache/PUBLIC_ARCHIVE#DISPATCHCONSTRAINT#FILE01#*.parquet",
        ["SETTLEMENTDATE","INTERVENTION","CONSTRAINTID","RHS","LHS","MARGINALVALUE","VIOLATIONDEGREE","GENCONID_EFFECTIVEDATE","GENCONID_VERSIONNO"],
    ),
    "DISPATCHPRICE": (
        "data/nemosis_cache/PUBLIC_ARCHIVE#DISPATCHPRICE#FILE01#*.parquet",
        ["SETTLEMENTDATE","INTERVENTION","REGIONID","RRP"],
    ),
    "DISPATCHREGIONSUM": (
        "data/nemosis_cache/PUBLIC_ARCHIVE#DISPATCHREGIONSUM#FILE01#*.parquet",
        ["SETTLEMENTDATE","INTERVENTION","REGIONID","NETINTERCHANGE"],
    ),
    "DISPATCHINTERCONNECTORRES": (
        "data/nemosis_cache/PUBLIC_ARCHIVE#DISPATCHINTERCONNECTORRES#FILE01#*.parquet",
        ["SETTLEMENTDATE","INTERVENTION","INTERCONNECTORID","MWFLOW"],
    ),
}

for name, (pattern, cols) in required.items():
    files = sorted(glob(pattern))
    print(name, "files:", len(files))
    if not files:
        print("  MISSING FILES")
        continue
    schema = pl.scan_parquet(files).collect_schema().names()
    miss = [c for c in cols if c not in schema]
    print("  missing cols:", miss)
PY
```

- If any required table files are missing, backfill only the required table for the same cache range:

```bash
uv run import_nem_data.py --start 2025/01/01 --end 2026/02/28 --dispatchconstraint
uv run import_nem_data.py --start 2025/01/01 --end 2026/02/28 --dispatchprice
uv run import_nem_data.py --start 2025/01/01 --end 2026/02/28 --dispatchregionsum
uv run python - <<'PY'
from nemosis import cache_compiler
cache_compiler(
    "2025/01/01 00:00:00",
    "2026/02/28 23:55:00",
    "DISPATCHINTERCONNECTORRES",
    "./data/nemosis_cache",
    fformat="parquet",
)
PY
```

## Assumptions And Defaults
- Default event window is the same 48-hour `2026-01-25` to `2026-01-27` window used in Notebook 1.3.
- `DISPATCHCONSTRAINT` is required for v1.
- Constraint-identification context is recovered from event-period `DISPATCHCONSTRAINT` identity fields, not external metadata tables.
- Polars lazy scanning remains the default data access pattern.
- `CONSTRAINTID` plus (`GENCONID_EFFECTIVEDATE`, `GENCONID_VERSIONNO`) is the primary reproducible identifier set for this case study.
- Interval-by-interval attribution here means ranking non-zero marginal-value constraints over time for the Jan 26 event, not building a general reusable reconstruction framework.
