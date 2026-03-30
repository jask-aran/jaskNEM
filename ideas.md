1. What if the WA grid was connected to the NEM?
2. How accurate are the MMSDMPS forecasts for the next 5 mins and further?
3. Are rebidding justifications being taken advantage of?
4. To what degree is the NEM/ Australia capacity constrained beyond other markets, and what does that mean for having a dispatch engine
5. A gentailer’s retail operations desire low wholesale prices, while its generation arm desires high prices. How do they coordinate bidding across their portfolio, and does that constitutes market manipulation? (Ongoing regulatory question.)
6. To what degree do Energy Asset Operators rely on heuristics or manual dispatch decisions? https://adgefficiency.com/blog/energy-py-linear/
7. How do we get from modeled competitive market price (lower bound) to realised prices in the dispatched model
8. NEMDE MILP Solve takes ~30 seconds, would the market be more efficient if this solve took less time?
9. How does the introduction of batteries change the market constraint that energy cannot be stored, and how will an increasing amount of storage capacity change the market structure?
10. Victoria’s Midday Power Saver offer impact
11. Revenue profile analysis of solar & wind
12. What does turning off Loy Yang look like?
13. Impact of PEC
14. Impact of HumeLink
15. Impact of SnowyHydro/ Snowy2.0
16. How do we increase the price elasticity of energy consumers (thus incentivising their demand to shift to high demand dispatch periods)?
17. Price cap impact
18. Analyse Dispatch interval forecast error

---

## Investigability Assessment

Ideas grouped by what data access they require.

### Investigable now — existing explored tables

These use `DISPATCHPRICE`, `DISPATCH_UNIT_SCADA`, `DISPATCHREGIONSUM`, `DISPATCHINTERCONNECTORRES`, and the registration workbook.

| # | Idea | Notes |
|---|------|-------|
| 2, 18 | Forecast accuracy / dispatch interval error | `P5MIN_REGIONSOLUTION` + `PREDISPATCHPRICE` vs `DISPATCHPRICE`. These two are the same question from different angles. |
| 11 | Solar & wind revenue profile | Capture price discount vs average RRP — directly computable from `DISPATCH_UNIT_SCADA` + `DISPATCHPRICE` + registration workbook. |
| 17 | Price cap impact | `DISPATCHPRICE` + `MARKET_PRICE_THRESHOLDS`. Already fully planned in Notebook 1.6. |
| 12 | Loy Yang shutdown | Filter existing tables by Loy Yang DUIDs, examine output history and regional price response. Near-ready; `DISPATCHLOAD.AVAILABILITY` sharpens it. |
| 10 | Midday Power Saver impact | Event-window analysis on `DISPATCHPRICE` + `DISPATCHREGIONSUM` — look for demand response in `TOTALDEMAND` during offer periods. |

### Investigable with one additional table

| # | Idea | What’s needed |
|---|------|---------------|
| 7 | Competitive vs realised price | Partial without bids. Full answer requires `BIDDAYOFFER` / `BIDPEROFFER` to compare actual offer prices against SRMC proxies. |
| 14, 15 | HumeLink / Snowy2.0 impact | Before/after on existing tables is easy. Attributing the exact binding mechanism requires `DISPATCHCONSTRAINT` + `GENCONDATA` (Notebook 1.5 tables). |
| 13 | Impact of PEC | Depends on definition. If administered pricing: extension of 1.6 via cumulative-price-threshold logic. If a generator: DUID-level filter on existing tables. |

### Requires new datasets or significant data acquisition

| # | Idea | Blocker |
|---|------|---------|
| 3 | Rebidding justifications | `BIDDAYOFFER` + `BIDOFFERPERIOD` with rebid reason text. Large tables, non-trivial deduplication. Substantial new acquisition before any analysis. |
| 5 | Gentailer portfolio / manipulation | Same bid table dependency as #3, plus participant attribution across retail and generation arms. Research-grade question. |
| 4 | NEM capacity constraint vs other markets | NEM side is tractable (`DISPATCHCONSTRAINT` binding frequency). Cross-market comparison (CAISO, ERCOT, GB) requires entirely external data. |
| 6 | Operator heuristics vs manual dispatch | Operational/interview data or internal logs. Not in any AEMO public dataset. |
| 8 | NEMDE solve time and market efficiency | Requires NEMDE solve-time logs (not public) and a custom MILP to test alternatives. |
| 16 | Demand price elasticity | Policy/market design question. Data can show current demand response; "how to increase it" is beyond analysis. |

### PyPSA simulation questions (Stage 2+)

These are counterfactual "what if X changes" questions — the right tool is the simulation layer, not data exploration.

| # | Idea | Stage |
|---|------|-------|
| 1 | WA connected to NEM | Multi-bus PyPSA model + WEM data (separate system). Good capstone. |
| 9 | Storage changing market structure | Directly addressed by Notebook 2.3. Data precursor is the revenue/capture-price analysis from #11. |

---

## Info Sources
1. https://www.mdavis.xyz/mms-guide/
2. https://adgefficiency.com/blog/hackers-aemo/
3. wattclarity.com.au
4. https://wattclarity.com.au/articles/2025/01/opening-the-black-box-a-beginners-guide-to-wholesale-market-modelling-part-1/
5. currentlyspeaking.substack.com
6. nemlog.substack.com
7. benbeattie.substack.com
8. itkservices3.com/posts.html

## Reading Sequence

WattClarity Beginner's Guide → Intermediate Guide → Price Setting Concepts
Endgame Economics three-part series (where PyPSA fits in the modelling hierarchy)
Open Electricity Economics chapters 4 and 5 (shadow prices and capacity mix)
Full Matthew Davis MMS guide (data gotchas as you hit them)
nempy docs and examples (when ready to model dispatch more precisely than PyPSA)

---

# Project Plan

## Stage 1 — NEM Data Exploration

Notebooks 1.1–1.5 are complete or in progress. Plans are in the individual notebook files.

**Notebook 1.6 — Price Cap and Scarcity Episodes**

This should sit between the broad orientation in 1.1 and the deeper event autopsy / constraint work in 1.3 and 1.5. The goal is narrower than a full event reconstruction: identify every interval where market prices actually hit the effective market cap, then group those intervals into a small number of scarcity episodes worth investigating further.

Core idea:
- use `DISPATCHPRICE` with `INTERVENTION = 0` to keep the cap-hit signal tied to underlying market-set prices
- use the consolidated effective-dated `MARKET_PRICE_THRESHOLDS` reference file to map the correct `VOLL` to each interval
- flag intervals where `RRP >= effective VOLL`
- optionally add rolling cumulative-price logic later to distinguish:
- isolated cap hits
- sustained scarcity episodes
- episodes likely to approach or trigger administered pricing

Outputs:
- table of cap-hit timestamps by region
- clustered event windows (for example, consecutive or near-consecutive cap intervals)
- simple charts showing cap-hit intervals on top of the 5-minute regional price series
- short written summary of which regions hit cap, when, and whether those hits were isolated spikes or part of a broader event

Possible extensions:
- add cumulative-price-threshold / administered-pricing context once the project preserves the relevant MMS field
- use this notebook as the event finder that feeds candidate windows into 1.3 and 1.5

Learning outcome:
- distinguish ordinary volatility from true scarcity pricing
- understand the difference between:
- very high prices
- market cap hits
- administered pricing
- build a reproducible event-discovery workflow before doing deep-dive autopsies

---

## Stage 2 — PyPSA Models

**The PyPSA mental model before you start:**

A `Network` object is the container for all components. `Buses` are the fundamental nodes to which generators, loads, and lines attach. `n.add("Generator", "gas", bus="Springfield", marginal_cost=70, p_nom=50)` adds a generator. `n.optimize(solver_name="highs")` builds and solves the MILP in one call.

The shadow price of the power balance constraint at each bus IS the electricity price. This is the key conceptual link — understanding that the spot price is just a Lagrange multiplier is what separates someone who understands market pricing from someone who just reads numbers.

**Notebook 2.1 — Toy model complexity ladder**

A single notebook that builds the model incrementally. Each section adds one dimension of complexity, producing a visible change in the price output. The model starts with stylised inputs throughout — real data comes in 2.2.

*Step 1 — Single bus, flat demand, 24h*

One bus, four generators, flat demand profile. The first "model produces prices" moment. Dispatch stack chart + shadow price series.

```python
import pypsa, pandas as pd, numpy as np

n = pypsa.Network()
n.set_snapshots(pd.date_range("2024-01-01", periods=24, freq="h"))
n.add("Bus", "NEM")

n.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
n.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
n.add("Generator", "CCGT Gas",   bus="NEM", p_nom=2000, marginal_cost=85)
n.add("Generator", "OCGT Gas",   bus="NEM", p_nom=800,  marginal_cost=180)

n.add("Load", "Demand", bus="NEM", p_set=8000)  # flat 8 GW
n.optimize(solver_name="highs")
```

*Step 2 — Realistic demand profile*

Replace flat demand with a morning/evening peak shape. Price now varies with load — gas peakers start appearing at peaks.

```python
hours = np.arange(24)
demand = 6000 + 2000 * (np.exp(-((hours - 8) ** 2) / 8) + np.exp(-((hours - 18) ** 2) / 8))
n.loads.loc["Demand", "p_set"] = demand  # replace flat with shaped profile
n.optimize(solver_name="highs")
```

*Step 3 — Add solar with diurnal profile*

Solar capacity factor follows a bell curve peaking at midday. Price drops midday, spikes in the evening ramp. The duck curve emerges.

```python
solar_cf = np.clip(np.exp(-((hours - 12) ** 2) / 8), 0, 1)
n.add("Generator", "Solar", bus="NEM", p_nom=1500, marginal_cost=0, p_max_pu=solar_cf)
n.optimize(solver_name="highs")
```

*Step 4 — Add storage*

Add a battery (stylised Hornsdale, 150MW/1hr). The optimiser charges during the solar surplus and dispatches into the evening peak. Plot SoC alongside price — this is the core of every battery revenue model in the NEM.

```python
n.add("StorageUnit", "Hornsdale Battery",
      bus="NEM",
      p_nom=150,
      max_hours=1,
      efficiency_store=0.92,
      efficiency_dispatch=0.92,
      marginal_cost=0)
n.optimize(solver_name="highs")
# n.storage_units_t.state_of_charge to plot SoC
```

*Step 5 — Extend to one week*

Extend snapshots from 24h to 168h. Observe SoC threading across days — the battery now has to make multi-day charge/discharge decisions. This is the key distinction from a single-day model.

```python
n.set_snapshots(pd.date_range("2024-01-01", periods=168, freq="h"))
# tile demand and solar profiles across 7 days
n.loads_t.p_set["Demand"] = np.tile(demand, 7)
n.generators_t.p_max_pu["Solar"] = np.tile(solar_cf, 7)
n.optimize(solver_name="highs")
```

*Step 6 — Two-region model (VIC–SA)*

Add a second bus and a line. When SA wind is abundant it exports to VIC; when the interconnector is congested, shadow prices diverge at each bus. Reduce `s_nom` to observe price separation. This is locational marginal pricing in its purest form.

```python
n.add("Bus", "SA")
n.add("Line", "VIC-SA", bus0="NEM", bus1="SA", s_nom=650, x=0.1)

wind_cf = np.random.uniform(0.1, 0.8, 168)  # stylised intermittent wind
n.add("Generator", "SA Wind", bus="SA", p_nom=2000, marginal_cost=0, p_max_pu=wind_cf)
n.add("Generator", "SA Gas",  bus="SA", p_nom=800,  marginal_cost=120)
n.add("Load", "SA Demand",    bus="SA", p_set=np.tile(demand * 0.4, 1))  # SA ~40% of VIC

n.optimize(solver_name="highs")
# n.buses_t.marginal_price to compare shadow prices at each bus
```

*Step 7 — Three-region model (VIC–SA–NSW)*

Add NSW. Prices now interact across three nodes — a constraint on one line shifts dispatch and prices everywhere else. Observe how NSW acts as a sink for both VIC and SA exports.

```python
n.add("Bus", "NSW")
n.add("Line", "VIC-NSW", bus0="NEM", bus1="NSW", s_nom=1400, x=0.1)

n.add("Generator", "NSW Black Coal", bus="NSW", p_nom=6000, marginal_cost=42)
n.add("Generator", "NSW OCGT",       bus="NSW", p_nom=1000, marginal_cost=190)
n.add("Load", "NSW Demand", bus="NSW", p_set=np.tile(demand * 1.3, 1))  # NSW largest region

n.optimize(solver_name="highs")
```

*Step 8 — Scarcity pricing / VOLL*

Add a VOLL-priced scarcity generator to represent the market price cap. The model can now produce spike events when physical supply is exhausted. Compare price duration curves with and without it.

```python
VOLL = 15_500  # $/MWh — current NEM market price cap
n.add("Generator", "Scarcity", bus="NEM", p_nom=99999, marginal_cost=VOLL)
# With supply tightened (reduce coal p_nom to force scarcity):
n.generators.loc["Brown Coal", "p_nom"] = 1000
n.optimize(solver_name="highs")
# plot price duration curve: n.buses_t.marginal_price.sort_values(..., ascending=False)
```

**Notebook 2.2 — Real AEMO data**

The bridge from toy models to real analysis. Use a simplified two-region model (VIC–SA) fed with real inputs for a specific week:

1. Pull actual demand profiles from `DISPATCHREGIONSUM`
2. Build SA wind capacity factor time-series from `DISPATCH_UNIT_SCADA`
3. Parameterise generators from the AEMO registration workbook (capacity, fuel type → marginal cost proxy)
4. Run the model and compare shadow prices to actual AEMO spot prices for the same period

The gap between model and reality is the calibration exercise. SA prices spike to thousands of $/MWh in real data; the toy model won't replicate that without scarcity pricing and network constraints. Understanding *why* they diverge is the learning.

---

## Stage 3 — The Gas Price Shock Model (Weeks 11–14)

This is the portfolio piece. The question: **"What happens to NEM spot prices if east-coast gas prices increase 50%?"**

This is commercially real — the 2022 NEM suspension was triggered partly by gas price dynamics feeding into generator offer prices. You're building a credible analytical answer to a question that analysts at AGL, Origin, and AEMO's market strategy team actually work on.

**Structure:**

1. **Baseline scenario** — calibrated two-or-three region model (VIC, SA, NSW), parameterised with current (~2024) gas prices, run for a representative week in summer and winter

2. **Shock scenario** — increase OCGT and CCGT marginal costs by 50%, re-run identical periods

3. **Outputs:**
 - Delta in average spot price by region
 - Delta in gas generator dispatch (substitution toward coal and renewables)
 - Impact on battery revenues (higher peak prices = more valuable arbitrage)
 - Price duration curve comparison: baseline vs. shock

4. **The memo** — 2 pages: what happened, why, what it means for a retailer or a battery investor. Your Eightcap strategy deck format applied directly.

The reason this works as a portfolio piece is that it demonstrates you understand the *transmission mechanism* from a fuel input cost to an electricity spot price — that's the core analytical question in energy markets, and it requires knowing merit order, marginal cost formation, and dispatch dynamics simultaneously.

---
