# NEM Data Guidance

This document is a compact working reference for finding and interpreting AEMO NEM data. It is built from:

- Matthew Davis, "So you want to query Australian electricity data?": <https://www.mdavis.xyz/mms-guide/>
- Adam Green, "A Hackers Guide to AEMO & NEM Data": <https://adgefficiency.com/blog/hackers-aemo/>
- practical experience working with `nemosis`-cached MMS tables
- the current AEMO registration workbook, especially `PU and Scheduled Loads`

The goal is simple: when a column is not in the table you expected, this should tell you where it probably is, how useful that table is, and what kind of analysis it feeds.

## First Principles

- `DISPATCH*` tables are realised outcomes.
- `P5*` and `PREDISPATCH*` tables are forecasts, not settled outcomes.
- The dispatch tables do not carry all generator metadata. Fuel type, technology, some capacity information, and messy real-world labels often live elsewhere.
- AEMO interval timestamps are usually labelled at interval end. For many analyses it is useful to derive an interval-start timestamp as well.
- Forecast data often has two time axes: when the forecast was made, and which interval it applies to.
- Table names vary slightly across sources. Treat NEMOSIS table names as the canonical names in code.
- Start with the narrowest table that answers the question. `DISPATCHLOAD` is powerful, but often heavier than necessary.

## Source Families

These are the publication layers that matter in practice:

- `CURRENT`: recent rolling data, roughly last 24 hours
- `ARCHIVE`: recent history, roughly last 13 months
- `MMSDM`: long history to end of last complete month

Practical consequence:

- older files often look like `PUBLIC_DVD_*`
- newer rolling files often look like `PUBLIC_ARCHIVE#...`
- the same logical dataset may have slightly different file/report naming across these layers

## NEMOSIS / Source-System Idiosyncrasies

- `nemosis` is a convenience layer, not a lossless mirror of the full AEMO MMS schema.
- Some MMS tables are intentionally column-trimmed by `nemosis` before they ever reach parquet.
- Standing or effective-dated tables should not be expected to behave like interval time-series tables.
- The same logical dataset can look different across `CURRENT`, `ARCHIVE`, `MMSDM`, and `nemosis` outputs.
- Before designing an analysis around a field, confirm that the column survived in your actual cached output rather than assuming the full MMS documentation schema is present.

## Table Map

### Primary Operational Tables

These are the tables you will use most often.

| Table | Granularity | Main variables | Best for | Relative size |
|---|---|---|---|---|
| `DISPATCHPRICE` | region x 5 min | `RRP`, FCAS prices, `PRICE_STATUS` | realised price analysis, price duration curves, heatmaps, spreads | small |
| `DISPATCH_UNIT_SCADA` | DUID x 5 min | `SCADAVALUE` | actual unit output, generation mix, capture price, revenue, CF work | medium |
| `DISPATCHLOAD` | DUID x 5 min | `INITIALMW`, `TOTALCLEARED`, `AVAILABILITY`, FCAS enabled MW, ramp rates | target vs actual, FCAS, availability, dispatch behaviour | very large |
| `DISPATCHREGIONSUM` | region x 5 min | `TOTALDEMAND`, `NETINTERCHANGE`, `CLEAREDSUPPLY`, `UIGF` | regional demand story, supply-demand context, net imports/exports | small-medium |
| `DISPATCHINTERCONNECTORRES` | interconnector x 5 min | `MWFLOW`, `METEREDMWFLOW`, `MWLOSSES` in common `nemosis` parquet outputs | realised interconnector flows, losses, coarse congestion diagnosis | medium |
| `P5MIN_REGIONSOLUTION` | region x forecast run x target interval | short-horizon forecast price and dispatch variables | next-hour forecast analysis, short-term prediction quality | large |
| `PREDISPATCHPRICE` | region x forecast run x target interval | longer-horizon forecast `RRP` | forecast drift, day-ahead-like planning views | very large |

Important caveat:

- Official AEMO MMS documentation for `DISPATCHINTERCONNECTORRES` includes calculated limit fields such as `EXPORTLIMIT`, `IMPORTLIMIT`, `EXPORTCONSTRAINTID`, and `IMPORTCONSTRAINTID`.
- Common `nemosis` outputs do **not** retain those fields. Its built-in `table_columns` map trims `DISPATCHINTERCONNECTORRES` to `SETTLEMENTDATE`, `INTERCONNECTORID`, `DISPATCHINTERVAL`, `INTERVENTION`, `MWFLOW`, `METEREDMWFLOW`, and `MWLOSSES` before writing parquet.
- This is a `nemosis` design choice, not an AEMO data limitation. `nemosis` curates many MMS tables down to a smaller, easier-to-use subset of columns. The tradeoff is simpler downstream analysis and smaller files, but occasionally a later-stage analytical field you expected from the raw MMS schema is gone.
- Practical consequence: if you use `nemosis`-produced parquet files, you can plot realised flow and price separation, but you cannot read explicit transfer limits from that parquet cache.
- Practical interpretation:
- use `DISPATCHINTERCONNECTORRES` for realised flow behaviour
- use `DISPATCHCONSTRAINT` for interval-level binding evidence
- add `GENCONDATA` when you need equation context or human-readable interpretation
- only go hunting for raw `EXPORTLIMIT` / `IMPORTLIMIT` columns if you explicitly want a direct flow-versus-limit overlay

### Core Reference Tables

These mostly explain who a unit is.

| Table / file | Main variables | Best for | Notes |
|---|---|---|---|
| `DUDETAILSUMMARY` | `REGIONID`, `PARTICIPANTID`, `STATIONID`, `SCHEDULE_TYPE`, TLF, DLF | first-pass DUID metadata join | easiest way to attach region and participant |
| `DUDETAIL` | `REGISTEREDCAPACITY`, `MAXCAPACITY`, `DISPATCHTYPE`, `CONNECTIONPOINTID`, `STARTTYPE` | historical unit metadata | time-varying, so use effective dating if history matters |
| Registration workbook `PU and Scheduled Loads` | fuel, technology, station labels, region, capacities, bidirectional/storage details | fuel-type and technology analysis | best practical source for fuel/tech labels, but not perfectly historical |
| Registration workbook `Ancillary Services` | FCAS registration details by DUID | FCAS capability context | useful complement to `DISPATCHLOAD` |

### Specialist / Event Analysis Tables

Use these when the question is more specific.

| Table / source | Best for |
|---|---|
| `DISPATCHCONSTRAINT` | what bound in a dispatch interval |
| `GENCONDATA` | human-readable context for constraint equations |
| NEMDE `NemPriceSetter` XML | direct "which unit / band set price?" style analysis |
| bid tables: `BIDDAYOFFER`, `BIDOFFERPERIOD`, `BIDPEROFFER*` | rebids, offer stacks, bid-shaping, strategic behaviour |
| rooftop PV tables such as `ROOFTOP_PV_ACTUAL` and successors | correcting fuel-mix analysis for behind-the-meter solar |

## Which Table Has The Variable?

| Need | Usually use |
|---|---|
| realised regional spot price | `DISPATCHPRICE.RRP` |
| FCAS prices | `DISPATCHPRICE` |
| actual unit output | `DISPATCH_UNIT_SCADA.SCADAVALUE` |
| actual-ish unit output plus wider dispatch context | `DISPATCHLOAD.INITIALMW` |
| dispatch target | `DISPATCHLOAD.TOTALCLEARED` |
| availability | `DISPATCHLOAD.AVAILABILITY` |
| FCAS enablement | `DISPATCHLOAD` FCAS columns |
| regional demand | `DISPATCHREGIONSUM.TOTALDEMAND` |
| regional net imports / exports | `DISPATCHREGIONSUM.NETINTERCHANGE` |
| interconnector flow | `DISPATCHINTERCONNECTORRES.MWFLOW` |
| interconnector transfer limit in common `nemosis` parquet output | not available directly |
| interconnector transfer limit in the underlying AEMO MMS model | `DISPATCHINTERCONNECTORRES.EXPORTLIMIT` and `DISPATCHINTERCONNECTORRES.IMPORTLIMIT`, but only if you preserve the raw columns instead of using trimmed `nemosis` output |
| DUID to region / participant / station | `DUDETAILSUMMARY` |
| DUID to fuel / technology | registration workbook `PU and Scheduled Loads` |
| registered / max capacity | `DUDETAIL` first, workbook second |
| TLF / DLF | `DUDETAILSUMMARY` |
| constraint that bound | `DISPATCHCONSTRAINT` first, then `GENCONDATA` if you need equation context |
| direct price-setting unit / band | NEMDE `NemPriceSetter` XML |
| short-horizon price forecasts | `P5MIN_REGIONSOLUTION` |
| longer-horizon price forecasts | `PREDISPATCHPRICE` |
| rebid reasons and offer bands | bid tables |
| rooftop solar estimate | rooftop PV tables |

## Most Useful By Analysis Type

### Price and Regional Market Structure

Use first:

- `DISPATCHPRICE`
- `DISPATCHREGIONSUM`
- `DISPATCHINTERCONNECTORRES`
- if you need the reason a flow was capped in a specific event, add `DISPATCHCONSTRAINT` + `GENCONDATA`

Typical outputs:

- RRP time series
- price duration curves
- price spreads between regions
- demand versus price
- congestion and price separation
- constraint-backed explanations for why regions separated

### Generator Output and Fuel Mix

Use first:

- `DISPATCH_UNIT_SCADA`
- `DUDETAILSUMMARY`
- registration workbook
- `DUDETAIL` when capacity fields must be historically correct

Use `DISPATCHLOAD` instead when you need:

- target vs actual
- FCAS enablement
- availability
- ramp-rate context

Typical outputs:

- generation mix by region
- capacity factors
- capture prices
- revenue approximations
- marginal fuel-type heuristics

Metadata guidance:

- Use the registration workbook as the practical source of truth for fuel and technology labels.
- Use `DUDETAILSUMMARY` as the broad-coverage DUID metadata join for region, participant, and station context.
- Use `DUDETAIL` when you need effective-dated capacity fields rather than a current administrative snapshot.
- If an operational DUID exists in dispatch tables but is absent from the registration workbook, keep it in the dataset and classify fuel as unknown rather than silently dropping it.

### Event / Spike Autopsy

Use first:

- `DISPATCHPRICE`
- `DISPATCHREGIONSUM`
- `DISPATCHINTERCONNECTORRES`
- `DISPATCH_UNIT_SCADA` or `DISPATCHLOAD`
- `DISPATCHCONSTRAINT`
- optionally `GENCONDATA`
- optionally NEMDE `NemPriceSetter` XML

Recommended sequencing:

- First pass: use `DISPATCHINTERCONNECTORRES` plus regional price spreads to show that regions decoupled and flows were operationally tight.
- Use `DISPATCHREGIONSUM.NETINTERCHANGE` only as regional context. It is not a substitute for interconnector-specific flow.
- Second pass: use `DISPATCHCONSTRAINT` to identify which constraints were active and carrying marginal value in the event window.
- Third pass: add `GENCONDATA` if you need human-readable equation context or more interpretable constraint identity.
- Use NEMDE `NemPriceSetter` XML only when you need exact price-setting attribution. A view of which units were running is operational context, not proof of which unit or bid band set price.

Typical questions:

- what was demand doing?
- which units dropped or ramped?
- was the interconnector constrained?
- which constraint bound?
- which unit or bid band set price?

### Forecast Accuracy

Use first:

- `DISPATCHPRICE`
- `P5MIN_REGIONSOLUTION`
- `PREDISPATCHPRICE`

Typical outputs:

- forecast error by lead time
- next-interval forecast accuracy
- forecast revision paths
- actual versus forecast price panels

### PyPSA Input Construction

Use first:

- `DISPATCHREGIONSUM` for demand
- `DISPATCH_UNIT_SCADA` for wind / solar profiles
- registration workbook for fuel and technology classes
- `DUDETAIL` and `DUDETAILSUMMARY` for region, schedule type, and capacities
- `DISPATCHPRICE` for model-vs-actual comparison

## Major Gotchas

### Timestamps

- `SETTLEMENTDATE` usually marks interval end.
- `LASTCHANGED` is a point-in-time event timestamp.
- For forecasts, keep both "forecast made at" and "forecast applies to" timestamps.

Useful pattern:

```python
lf = lf.with_columns(
    pl.col("SETTLEMENTDATE").alias("interval_end"),
    (pl.col("SETTLEMENTDATE") - pl.duration(minutes=5)).alias("interval_start"),
)
```

### `DISPATCHLOAD` vs `DISPATCH_UNIT_SCADA`

- If you just need actual MW, prefer `DISPATCH_UNIT_SCADA`.
- If you need targets, availability, FCAS, or ramp fields, use `DISPATCHLOAD`.
- `DISPATCHLOAD` is far larger and easier to make memory mistakes with.

### Forecast Tables Have Two-Dimensional Time

- `P5MIN_REGIONSOLUTION` has both forecast-run time and target interval time.
- `PREDISPATCHPRICE` also stores the history of forecasts for the same target interval.
- Do not collapse to one datetime until you are sure whether you care about lead time or realised interval.

### Registration Workbook Is Operationally Important

- Fuel and technology labels are often easiest to get from the workbook, not MMS reference tables.
- It is not perfectly versioned historically.
- `DUDETAILSUMMARY` is often the easiest broad-coverage join for region and DUID identity.
- For historical capacity correctness, fall back to `DUDETAIL`.
- If a DUID is operationally present but absent from the workbook, keep it and mark its fuel / technology as unknown rather than dropping it.

### Effective-Dated Tables Behave Differently

- Not every useful table is a simple interval time series.
- Standing or effective-dated tables should be interpreted by validity period, not by assuming one row per dispatch interval.
- In `nemosis`, tables such as `MARKET_PRICE_THRESHOLDS` may need a historical snapshot walk rather than a narrow interval-style query.
- For market-cap logic, use the effective-dated values that apply at the interval being analysed rather than hardcoding one threshold for the whole sample.

### Rooftop Solar Matters

- If you build fuel mix from dispatchable units alone, solar shares can be badly understated.
- Rooftop solar is estimated, not directly measured.
- It is often 30-minute data and needs careful upsampling before mixing with 5-minute dispatch data.

### Bidding Data Is A Different Scale Of Problem

- Bid tables are huge.
- Deduplication is non-trivial.
- For many current project tasks, you do not need them yet.

## Practical Access Pattern

This is a compact workflow for reusable NEM analysis:

1. Start from the variable you actually need.
2. Choose the narrowest operational table that contains it.
3. Parse timestamps and interval flags explicitly instead of assuming loader defaults are analysis-ready.
4. Filter `INTERVENTION == 0` early unless intervention intervals are part of the question.
5. Normalize interval-end timestamps to interval-start only if that matches the analysis frame you want.
6. Narrow the operational table before joining metadata.
7. Join `DUDETAILSUMMARY` for broad DUID identity and region context.
8. Join the registration workbook only when fuel / technology labels are required.
9. Join `DUDETAIL` when historically correct capacity matters.
10. Treat unknown metadata explicitly rather than dropping unmatched operational rows.

### Good Uses Of This Pattern

- regional fuel-stack plots
- top-generator output rankings
- rough capacity-factor screening
- seasonal comparison with bounded memory
- first-pass identification of low-output coal units or unusual regional mix shifts

### Important Caveats From This Pattern

- `DISPATCHLOAD.INITIALMW` is acceptable for dispatch-context analysis, but if the question is strictly actual output then `DISPATCH_UNIT_SCADA.SCADAVALUE` is the better default.
- Fuel simplification is a modelling choice; keep the raw descriptor available for auditability.
- Registration-workbook capacity is pragmatic, but for historically correct capacity you may need effective-dated `DUDETAIL`.
- Negative dispatch values from charging batteries or pumped hydro need explicit treatment before stacked-area plots or energy-share charts.

## Common Query Examples

These examples are adapted from the MMS guide's "Common Queries" section and translated into compact working patterns. They are intended as templates, not copy-paste production code.

### 1. Average Regional Price

Use `DISPATCHPRICE` only.

```python
import polars as pl

def parse_dt(lf: pl.LazyFrame, cols: list[str]) -> pl.LazyFrame:
    for c in cols:
        lf = lf.with_columns(
            pl.col(c).str.strptime(pl.Datetime, "%Y/%m/%d %H:%M:%S")
        )
    return lf

avg_price = (
    pl.scan_parquet("path/to/cache/*DISPATCHPRICE*.parquet")
    .pipe(parse_dt, ["SETTLEMENTDATE"])
    .filter(pl.col("INTERVENTION") == 0)
    .group_by("REGIONID")
    .agg(pl.mean("RRP").alias("avg_rrp"))
    .sort("REGIONID")
    .collect()
)
```

Why this example matters:

- it is the cleanest template for realised price work
- it enforces the habit of checking `INTERVENTION`
- it keeps the time parse explicit

### 2. Revenue Skewness By Region

This follows the MMS guide's point that outliers are central, not noise. Use `DISPATCH_UNIT_SCADA` instead of `DISPATCHLOAD` unless you specifically need the extra fields.

```python
import polars as pl
import pandas as pd

def parse_dt(lf: pl.LazyFrame, cols: list[str]) -> pl.LazyFrame:
    for c in cols:
        lf = lf.with_columns(
            pl.col(c).str.strptime(pl.Datetime, "%Y/%m/%d %H:%M:%S")
        )
    return lf

reg = pd.read_excel(
    "path/to/NEM Registration and Exemption List.xlsx",
    sheet_name="PU and Scheduled Loads",
)

duid_meta = pl.from_pandas(reg).lazy().select(["DUID", "Region"])

price = (
    pl.scan_parquet("path/to/cache/*DISPATCHPRICE*.parquet")
    .pipe(parse_dt, ["SETTLEMENTDATE"])
    .filter(pl.col("INTERVENTION") == 0)
    .select(["SETTLEMENTDATE", "REGIONID", "RRP"])
)

scada = (
    pl.scan_parquet("path/to/cache/*DISPATCH_UNIT_SCADA*.parquet")
    .pipe(parse_dt, ["SETTLEMENTDATE"])
    .select(["SETTLEMENTDATE", "DUID", "SCADAVALUE"])
)

revenue_by_interval = (
    scada
    .join(duid_meta, on="DUID", how="left")
    .join(price, left_on=["SETTLEMENTDATE", "Region"], right_on=["SETTLEMENTDATE", "REGIONID"], how="left")
    .with_columns(
        # 5-minute MWh approximation using piecewise-linear power between intervals
        (pl.col("SCADAVALUE") / 12.0).alias("mwh_5min"),
        ((pl.col("SCADAVALUE") / 12.0) * pl.col("RRP")).alias("energy_revenue"),
    )
    .group_by(["Region", "SETTLEMENTDATE"])
    .agg(pl.sum("energy_revenue").alias("regional_revenue"))
)

result = (
    revenue_by_interval
    .sort(["Region", "regional_revenue"], descending=[False, True])
    .with_columns(
        pl.cum_sum("regional_revenue").over("Region").alias("cum_revenue"),
        pl.len().over("Region").alias("n_intervals"),
        pl.sum("regional_revenue").over("Region").alias("total_revenue"),
    )
    .filter(pl.col("cum_revenue") >= 0.5 * pl.col("total_revenue"))
    .group_by("Region")
    .agg((pl.min(1 + pl.int_range(pl.len())) / pl.first("n_intervals")).alias("frac_time_for_half_revenue"))
    .collect()
)
```

Why this example matters:

- it is a good template for joining output to price and metadata
- it captures the guide's warning that price tails dominate revenue
- it shows why `DISPATCH_UNIT_SCADA` is often the right default for generator-energy analysis

### 3. Short-Horizon vs Longer-Horizon Price Forecasts

This is the core pattern for forecast-accuracy work.

```python
import polars as pl

def parse_dt(lf: pl.LazyFrame, cols: list[str]) -> pl.LazyFrame:
    for c in cols:
        lf = lf.with_columns(
            pl.col(c).str.strptime(pl.Datetime, "%Y/%m/%d %H:%M:%S")
        )
    return lf

actual = (
    pl.scan_parquet("path/to/cache/*DISPATCHPRICE*.parquet")
    .pipe(parse_dt, ["SETTLEMENTDATE"])
    .filter(pl.col("INTERVENTION") == 0)
    .select([
        pl.col("SETTLEMENTDATE").alias("target_interval_end"),
        "REGIONID",
        pl.col("RRP").alias("actual_rrp"),
    ])
)

p5 = (
    pl.scan_parquet("path/to/cache/*P5MIN_REGIONSOLUTION*.parquet")
    .pipe(parse_dt, ["INTERVAL_DATETIME", "RUN_DATETIME", "LASTCHANGED"])
    .filter(pl.col("RUN_DATETIME") < pl.col("INTERVAL_DATETIME"))
    .select([
        pl.col("INTERVAL_DATETIME").alias("target_interval_end"),
        pl.col("RUN_DATETIME").alias("forecast_run_end"),
        "REGIONID",
        pl.col("RRP").alias("forecast_rrp"),
    ])
)

predispatch = (
    pl.scan_parquet("path/to/cache/*PREDISPATCHPRICE*.parquet")
    .pipe(parse_dt, ["DATETIME", "LASTCHANGED"])
    .filter(pl.col("INTERVENTION") == 0)
    .filter(pl.col("LASTCHANGED") < pl.col("DATETIME") - pl.duration(hours=1))
    .with_columns(
        pl.col("LASTCHANGED").dt.ceil("5m").alias("forecast_run_end")
    )
    .select([
        pl.col("DATETIME").alias("target_interval_end"),
        "forecast_run_end",
        "REGIONID",
        pl.col("RRP").alias("forecast_rrp"),
    ])
)

forecast_errors = (
    pl.concat([p5, predispatch])
    .join(actual, on=["target_interval_end", "REGIONID"], how="left")
    .with_columns(
        (pl.col("target_interval_end") - pl.col("forecast_run_end")).alias("lead_time"),
        (pl.col("forecast_rrp") - pl.col("actual_rrp")).alias("error"),
        (pl.col("forecast_rrp") - pl.col("actual_rrp")).abs().alias("abs_error"),
    )
)
```

Why this example matters:

- it enforces the two-dimensional-time distinction
- it follows the MMS guide's recommended split: use `P5MIN_REGIONSOLUTION` for medium-term short-horizon forecasts, `PREDISPATCHPRICE` for forecasts made further ahead
- it avoids collapsing all forecast history into one noisy table too early

### 4. Rooftop Solar Caution Pattern

This is included because it is one of the easiest ways to get the NEM fuel mix wrong.

```python
# High-level workflow rather than full code:
#
# 1. Build large-scale generation from DISPATCH_UNIT_SCADA + registration workbook.
# 2. Load rooftop PV estimates.
# 3. Deduplicate rooftop rows by choosing best estimate type.
# 4. Upsample 30-minute rooftop power to 5-minute intervals.
# 5. Append rooftop solar to large-scale solar before computing shares.
```

What to remember:

- rooftop PV is estimated rather than directly measured
- table structure and preferred source can change over time
- if you skip rooftop PV, solar shares can be materially understated

## References

- Matthew Davis, "So you want to query Australian electricity data?": <https://www.mdavis.xyz/mms-guide/>
- Adam Green, "A Hackers Guide to AEMO & NEM Data": <https://adgefficiency.com/blog/hackers-aemo/>
