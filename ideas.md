1. What if the WA grid was connected to the NEM?
2. How accurate are the MMSDMPS forecasts for the next 5 mins and further?
3. Are rebidding justifications being taken advantage of?
4. To what degree is the NEM/ Australia capacity constrained beyond other markets, and what does that mean for having a dispatch engine
5. A gentailer's retail operations desire low wholesale prices, while its generation arm desires high prices. How do they coordinate bidding across their portfolio, and does that constitutes market manipulation? (Ongoing regulatory question.)
6. To what degree do Energy Asset Operators rely on heuristics or manual dispatch decisions? https://adgefficiency.com/blog/energy-py-linear/
7. How do we get from modeled competitive market price (lower bound) to realised prices in the dispatched model
8. NEMDE MILP Solve takes ~30 seconds, would the market be more efficient if this solve took less time?
9. How does the introduction of batteries change the market constraint that energy cannot be stored, and how will an increasing amount of storage capacity change the market structure?

Victoria’s Midday Power Saver offer impact
Revenue profile analysis of solar & wind
What does turning off Loy Yang look like?
Impact of PEC
Impact of HumeLink
Impact of SnowyHydro/ Snowy2.0
How do we increase the price elasticity of energy consumers (thus incentivising their demand to shift to high demand dispatch periods)?
Price cap impact


Constraints: AEMO does not just intersect supply and demand curves. Australia's grid is far more constrained than most, so AEMO's optimiser, the "NEM Dispatch Engine" (NEMDE) incorporates hundreds of constraints for system strength, transmission line capacity etc. The definition and evaluation of these is in the data.

The thing that makes electricity markets very different from any other market is that “…electrical current…must be produced, to the millisecond, at the moment of consumption, giving an exact balance between power supply and demand. Stable power grids are based on this principle” as Ziegler and his co-authors put it.



## Info Sources
1. https://www.mdavis.xyz/mms-guide/
2. https://adgefficiency.com/blog/hackers-aemo/
3. wattclarity.com.au
4. https://wattclarity.com.au/articles/2025/01/opening-the-black-box-a-beginners-guide-to-wholesale-market-modelling-part-1/
5. currentlyspeaking.substack.com
6. nemlog.substack.com
7. benbeattie.substack.com
8. itkservices3.com/posts.html

Reading sequence
Given where you are in the learning plan, the order that will compound fastest:

WattClarity Beginner's Guide → Intermediate Guide → Price Setting Concepts (understand how prices actually get set before building 1.3)
Endgame Economics three-part series (understand where your PyPSA model fits in the modelling hierarchy)
Open Electricity Economics chapters 4 and 5 (theoretical grounding for shadow prices and capacity mix)
Full Matthew Davis MMS guide (fill in data gotchas as you hit them in 1.2)
nempy docs and examples (when you're ready to model dispatch more precisely than PyPSA allows)


# Project Plan
## Stage 1 — NEM Data Exploration

**Notebook 1.1 — Price explorer**

Pull 12 months of `DISPATCHPRICE` for all five NEM regions (QLD, NSW, VIC, SA, TAS) using NEMOSIS. Build:
- A time-series plot of 5-minute RRP for each region overlaid
- A **price duration curve** — sort prices descending, plot against % of intervals. 
- A heatmap of average price by hour-of-day and day-of-week for each region

What you'll see: the characteristic "duck curve" shape in SA, the tight correlation between NSW and QLD, how TAS decouples when the Basslink interconnector is constrained. This is domain knowledge you can't get from reading.

**Notebook 1.2 — Generator dispatch explorer**

**Data challenge**: `DISPATCHLOAD` is 90-120x larger than `DISPATCHPRICE` (~50M rows vs. 500K rows for a full year). Loading everything into memory exhausts typical laptop RAM, especially in WSL.

**Memory-efficient strategy**:
1. **Use Polars** for lazy evaluation and efficient memory usage
2. **Read parquet files directly** from NEMOSIS cache (bypass `dynamic_data_compiler`)
3. **Strategic sampling**:
   - **One week** for merit order stacks and marginal generator analysis (~1M rows)
   - **12 weeks** (one per month) for capacity factor and regional mix (~12M rows)
   - **Result**: 75% fewer rows, 80% less memory than brute-force full-year load

**Analyses**:
- **Merit order stack** — for a representative week, plot generator dispatch by fuel type across 24 hours. Coal at the bottom, gas in the middle, peakers at the top. Compare VIC (coal-heavy) vs. SA (wind/gas).
- **Marginal generator identification** — use SRMC proxy to identify which fuel type was price-setting in each interval. VIC: gas peakers during peaks, coal during off-peak. SA: gas dominates (no coal baseload).
- **Capacity factor analysis** — from 12 weekly samples (one per month), calculate annual CF estimates. Coal: 70-90%, Wind: 30-35%, Solar: 20-25%, Gas peakers: <5%. Identify low-CF coal units (potential outages).
- **Regional generation mix** — VIC: coal-dominated, SA: wind-dominated, TAS: hydro-dominated. This is the structural difference that drives price dynamics.

**Learning outcome**: You learn not just the analytics, but also **how to work with large energy datasets** — sampling strategies, memory management, and when to brute-force vs. when to be smart. This is production-ready data work.

**Notebook 1.3 — Price spike autopsy** (detailed plan: [Notebook 1.3.md](Notebook 1.3.md))

Reconstruct a real SA high-price event from multiple dispatch tables and write a trader-briefing narrative. Requires downloading `DISPATCHREGIONSUM`, `DISPATCHINTERCONNECTORRES`, and `DISPATCH_UNIT_SCADA` (event month only). Five analysis panels: price context, demand/supply, interconnector congestion, generator response, and price-setter identification. Outputs a 3-paragraph written autopsy explaining what happened, why, and what it means for a portfolio. Builds the multi-table joining and event-narrative skills needed for 1.4 and Stage 3.

**Notebook 1.4 — Interconnector flows**

Pull `DISPATCHREGIONSUM` and focus on interconnector flows (VIC-SA `V-SA`, TAS-VIC `T-V-MNSP1`). Build:
- Flow duration curves for each interconnector
- Price differentials between connected regions vs. interconnector utilisation — you'll visually see the relationship between flow limits and price separation

**Notebook 1.5 — Constraint and Dynamic Binding Attribution**

This sits **after** 1.3 and 1.4 on purpose. We originally expected to read interconnector transfer limits straight from `DISPATCHINTERCONNECTORRES`, but the local `nemosis` parquet schema trims that table down to realised flows and losses. That is enough for a case-study narrative in 1.3, but not enough to prove the exact binding mechanism.

So the later notebook should do the next layer properly:
- download `DISPATCHCONSTRAINT` and `GENCONDATA`
- identify which constraints had non-zero marginal value during a chosen event window
- connect those binding constraints to the observed regional price separation and interconnector flow behaviour
- write a short note on the difference between:
- observed congestion symptoms in `DISPATCHINTERCONNECTORRES` and `DISPATCHPRICE`
- exact binding attribution from the constraint tables

Learning outcome:
- understand how to move from "this looks constrained" to "this specific network constraint bound and changed the dispatch outcome"
- learn when a simple event notebook is enough and when you need to step into NEMDE constraint logic

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

## Stage 2 — First PyPSA Models (Weeks 5–10)

**The PyPSA mental model before you start:**

A `Network` object is the container for all components. `Buses` are the fundamental nodes to which generators, loads, and lines attach. `n.add("Generator", "gas", bus="Springfield", marginal_cost=70, p_nom=50)` adds a generator. `n.optimize(solver_name="highs")` builds and solves the MILP in one call.

The shadow price of the power balance constraint at each bus IS the electricity price. This is the key conceptual link — understanding that the spot price is just a Lagrange multiplier is what separates someone who understands market pricing from someone who just reads numbers.

**Notebook 2.1 — Toy single-bus dispatch (Day 1 of PyPSA)**

Build the simplest possible model: one bus, four generators, one load, 24-hour horizon.

```python
import pypsa, pandas as pd

n = pypsa.Network()
n.set_snapshots(pd.date_range("2024-01-01", periods=24, freq="h"))
n.add("Bus", "NEM")

# Generator fleet (stylised NEM)
n.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
n.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
n.add("Generator", "CCGT Gas",   bus="NEM", p_nom=2000, marginal_cost=85)
n.add("Generator", "OCGT Gas",   bus="NEM", p_nom=800,  marginal_cost=180)
n.add("Generator", "Wind",       bus="NEM", p_nom=2000, marginal_cost=0,
      p_max_pu=wind_profile)  # time-varying capacity factor

n.add("Load", "Demand", bus="NEM", p_set=demand_profile)
n.optimize(solver_name="highs")
```

Outputs to build:
- Dispatch stack chart by hour — stacked area showing each technology's contribution
- The model's shadow price series (this is your "simulated spot price")
- Total system cost

This is your first "model produces prices" moment. It's simple but the structure is identical to what PLEXOS does at industrial scale.

**Notebook 2.2 — Add transmission: two-region model**

Add a second bus and a line. This is where it gets interesting.

```python
n.add("Bus", "VIC")
n.add("Bus", "SA")
n.add("Line", "VIC-SA interconnector", 
      bus0="VIC", bus1="SA", 
      s_nom=650,   # MW transfer limit
      x=0.1)
```

Now run the same dispatch optimisation. When SA has cheap wind, it exports to VIC. When SA wind is low and VIC generation is tight, SA imports and prices diverge. The model will produce **different shadow prices at each bus** when the line is congested — this is locational marginal pricing in its purest form.

Exercise: reduce `s_nom` to 200MW and observe how SA prices spike relative to VIC. You've just modelled interconnector congestion.

**Notebook 2.3 — Add storage**

```python
n.add("StorageUnit", "Hornsdale Battery",
      bus="SA",
      p_nom=150,        # MW charge/discharge
      max_hours=1,      # MWh/MW = 1hr duration
      efficiency_store=0.92,
      efficiency_dispatch=0.92,
      marginal_cost=0)
```

Now the optimiser decides when to charge (when prices are low) and discharge (when prices are high). Plot the battery's state of charge alongside the SA price. You'll see it charging during wind surplus and dispatching into evening peaks. This is the core of every battery revenue model in the NEM.

**Notebook 2.4 — Feed in real AEMO data**

This is the bridge between toy models and real analysis. Use your Stage 1 data pipelines to:
1. Pull actual AEMO demand profiles for VIC and SA for a specific week
2. Build wind capacity factor time-series from `DISPATCH_UNIT_SCADA` for major SA wind farms
3. Use the AEMO Registration list to parameterise real generators (capacity, fuel type → marginal cost approximation)
4. Run your two-region model on real inputs for that week
5. Compare your model's shadow prices to actual AEMO spot prices for the same period

The gap between your model and reality is your calibration exercise. SA prices spike to thousands of $/MWh in real data; your model probably won't do that unless you add peakers and model scarcity correctly. Understanding *why* they diverge is the learning.

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
