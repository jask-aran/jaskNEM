# Notebook 1.3 — Price Spike Autopsy

Reconstruct a real high-price event from raw dispatch data and produce a coherent narrative — the kind of analysis a trading desk or regulatory team would do the morning after a spike. This is where the data fluency from 1.1 and 1.2 becomes analytical muscle.

## Chosen Event: 2026-01-26 (SA1)

Exploratory analysis of the full 2025 `DISPATCHPRICE` cache identified 19 days where SA1 exceeded $5,000/MWh. The top candidates:

| Date | >$5k intervals | Max RRP | Character |
|---|---|---|---|
| 2025-06-26 | 43 | $15,103 | Winter, all-region event (NSW/VIC/TAS also spiked) |
| 2025-06-12 | 36 | $16,983 | Winter, multi-region |
| **2026-01-26** | **36** | **$20,300 (MPC)** | **Summer, SA-only — VIC max was $437** |
| 2025-07-02 | 33 | $15,104 | Winter, prolonged elevated prices all day |

**2026-01-26 is the best autopsy target** because:
- **SA-only event**: SA1 hit market price cap while VIC1 stayed calm — textbook interconnector congestion
- **Summer evening**: negative prices during solar hours (9 intervals), then explosive spike 17:00–21:00 as solar ramps down and demand peaks
- **Clean narrative arc**: Jan 25 was calm (max $498), Jan 26 was the event, Jan 27 had aftershocks (max $14k)
- **48-hour window**: 2026-01-25 00:00 → 2026-01-27 00:00 captures build-up and resolution

## Data Requirements — New Downloads Needed

This notebook requires tables not yet in the local cache. Download before starting:

| Table | Why | Size hint |
|---|---|---|
| `DISPATCHREGIONSUM` | Regional demand, net interchange, UIGF (unconstrained intermittent generation forecast) — answers "what was demand doing?" and "was the region importing/exporting?" | small-medium (~15 months) |
| `DISPATCHINTERCONNECTORRES` | Interconnector flows for VIC1-SA1 (Heywood) — answers "what was the realised flow doing?" | medium |
| `DISPATCH_UNIT_SCADA` | Actual unit output at 5-min resolution — answers "which generators went offline or reduced?" Lighter than `DISPATCHLOAD` for this purpose | medium |

Optional but high-value if you want to go deeper:
- `DISPATCHCONSTRAINT` — which network constraints bound during the spike intervals
- `GENCONDATA` — human-readable descriptions of those constraints

Download using the project's `import_nem_data.py` script. `DISPATCHREGIONSUM` and `DISPATCH_UNIT_SCADA` are already defined as flags (`--dispatchregionsum`, `--dispatch-scada`). `DISPATCHINTERCONNECTORRES` is not yet in the script's table list — either add it or download via a one-off NEMOSIS call.

```bash
# Tables with existing flags — download full date range to match other cached data
uv run import_nem_data.py --start 2025/01/01 --end 2026/02/28 --dispatchregionsum --dispatch-scada

# DISPATCHINTERCONNECTORRES — not in import_nem_data.py yet, use NEMOSIS directly
python3 -c "
from nemosis import cache_compiler
cache_compiler('2025/01/01 00:00:00', '2026/02/28 23:55:00',
               'DISPATCHINTERCONNECTORRES', './data/nemosis_cache', fformat='parquet')
"
```

## Memory Strategy

Unlike Notebook 1.2 where you needed sampling tricks for a full year of `DISPATCHLOAD`, here you only need 48 hours of data across all tables. Everything fits comfortably in memory. The workflow is:
1. Scan the full parquet cache with `pl.scan_parquet`
2. Filter to your 48-hour window immediately (pushdown predicate)
3. Collect — the resulting DataFrames will be small (a few hundred thousand rows at most)

## Analyses — Build in Sequence

Each panel answers one of the autopsy questions.

### Panel 1: The Price Event in Context
- Plot SA1 and VIC1 RRP for the 48-hour window, with a horizontal line at the MPC ($15,100)
- Shade the spike intervals (RRP > $300) to visually delineate the event
- Annotate the peak price and its timestamp
- This panel sets the scene — what did the price signal look like?

### Panel 2: Demand and Supply Context
- From `DISPATCHREGIONSUM`: plot SA1 `TOTALDEMAND` alongside `CLEAREDSUPPLY` and `UIGF`
- The gap between UIGF (what renewables could have produced) and actual cleared supply tells you about curtailment
- Overlay temperature if available (BOM data, optional) — heatwave events are often demand-driven
- Key question: was this a demand-pull spike (demand surged) or a supply-push spike (supply withdrew)?

### Panel 3: Interconnector — Was SA Islanded?
- From `DISPATCHINTERCONNECTORRES`: plot flow on VIC1-SA1 (Heywood interconnector)
- Plot the VIC1-SA1 price differential below it — you should see the spread widen when SA and VIC decouple
- Important caveat: the local `nemosis` parquet cache does not retain `EXPORTLIMIT` and `IMPORTLIMIT`, even though the underlying AEMO MMS schema has them
- Therefore the notebook's chosen base-case analysis is flow plus price separation, not a literal flow-vs-limit chart
- If you later want the exact binding mechanism for this event, inspect `DISPATCHCONSTRAINT` + `GENCONDATA` for the spike intervals and narrate the relevant network constraint manually
- This still demonstrates locational marginal pricing in action without turning the case study into a reusable constraint-attribution pipeline

### Panel 4: Generator Response — Who Dropped, Who Ramped?
- From `DISPATCH_UNIT_SCADA` joined with the registration workbook: plot output by fuel type as a stacked area for SA1
- Identify specific DUIDs that reduced output during the spike window — a large coal or gas unit tripping is the classic trigger
- Separately plot the top 5 SA generators by MW change (largest drops) in a waterfall or bar chart
- This answers: which unit(s) going offline or reducing output caused the supply shortfall?

### Panel 5 (Stretch): Who Set the Price?
- If you downloaded `DISPATCHCONSTRAINT` + `GENCONDATA`: identify which constraints bound during the spike intervals
- If you have NEMDE `NemPriceSetter` XML (advanced, optional): identify the exact DUID and bid band that was marginal
- Without these, use a heuristic from Notebook 1.2: the highest-SRMC fuel type that was dispatching in each interval is approximately the price-setter. During a spike, this will typically be an OCGT peaker or a load shedding band.

## The Write-Up — 3 Paragraphs, Trader-Briefing Style

After building the panels, write a markdown cell with three paragraphs:

1. **What happened**: Date, time, peak price, duration. "SA1 spot prices exceeded $X,000/MWh for Y consecutive intervals on [date], peaking at $Z at [time]."

2. **Why it happened**: The causal chain. "Demand was [rising/elevated] due to [reason]. [Generator X] reduced output by [Y] MW at [time], removing [Z]% of SA's available capacity. Heywood imports were [elevated / operationally tight], and SA-VIC price separation widened sharply, showing that additional imports were not available when SA needed them most. If you downloaded `DISPATCHCONSTRAINT` + `GENCONDATA`, add the relevant binding constraint here. With limited local supply and constrained imports, the marginal generator was [OCGT unit / bid band], setting prices at $[X]/MWh."

3. **What it means**: Implications for a trader or portfolio manager. "This event illustrates [interconnector congestion / peaker scarcity / renewable intermittency]. A [battery / demand response / additional interconnector capacity] positioned in SA would have [captured $X in arbitrage / reduced the duration by Y intervals]. The price signal resolved when [demand fell / generator returned / interconnector constraint relaxed] at [time]."

This is the analytical format you'll reuse in Stage 3 when writing the gas price shock memo.

## Learning Outcomes
- Joining multiple dispatch tables to build a multi-dimensional event narrative (price + demand + interconnector + generation)
- Understanding the causal chain from physical event (generator trip, demand surge, binding network constraint / interconnector limit) to price outcome
- Seeing locational marginal pricing in practice — why SA and VIC prices diverge when the interconnector binds
- Producing analyst-grade written output from data, not just charts
- Working with `DISPATCHREGIONSUM` and `DISPATCHINTERCONNECTORRES` first, then using `DISPATCHCONSTRAINT` + `GENCONDATA` as a focused follow-up when you need exact binding attribution
