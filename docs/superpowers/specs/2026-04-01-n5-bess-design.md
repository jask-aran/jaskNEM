# N5 BESS Integration — Design Spec

**Date:** 2026-04-01  
**File:** `Simulation/ToyModel.py`  
**Builds on:** N4 (multi-unit thermal stack + ramp constraints, LP)

---

## Context

N4 introduced 8 differentiated thermal units, class-based ramp limits, and a Scarcity generator.
Two artefacts remain:

- **Negative price spikes (~−$15k/MWh):** ramp-down limits on coal prevent backing off fast
  enough during solar ramp-up; the single-bus LP has no dump path for surplus energy.
- **High price spikes ($15,500/MWh):** evening peak occasionally exhausts all thermal capacity.

N5 adds a single aggregate BESS. It absorbs midday solar surplus and discharges into the
evening peak, dampening both artefacts while remaining a pure LP (no binary decisions).
The analytical goal is twofold: observe how BESS reshapes the price series, and study the
LP's optimal charge/discharge schedule (SOC trajectories, generator displacement, arbitrage P&L).

---

## BESS Parameters

| Parameter | Value | Notes |
|---|---|---|
| Component type | `StorageUnit` | Native PyPSA LP storage |
| `p_nom` | 600 MW | Stylised VIC grid-scale fleet |
| `max_hours` | 2 | → 1,200 MWh energy capacity |
| `efficiency_store` | 0.92 | |
| `efficiency_dispatch` | 0.92 | → ~84.6% round-trip |
| `state_of_charge_initial` | 0.5 | 50% = 600 MWh at t=0 |
| `cyclic_state_of_charge` | False | LP free to end at any SOC |
| `marginal_cost` | 0 | Dispatch driven purely by shadow prices |
| `standing_loss` | 0 | Negligible over 4-day window |

---

## Notebook Structure

N5 appends the following cells after the existing N4 block in `Simulation/ToyModel.py`:

### Cell 1 — Intro markdown
Describes N5: same 4-day Thu–Sun window and VIC-calibrated demand/solar as N4; adds a
600 MW / 1,200 MWh BESS; LP optimises charge/discharge freely across all 576 snapshots.

### Cell 2 — Build cell
`build_n5()` standalone function:
- Replicates N4's network setup verbatim (same demand, solar, 8 thermal units, ramp limits, Scarcity)
- Appends `n5.add("StorageUnit", "BESS", ...)` with the parameters above
- Calls `n5.optimize(solver_name="highs")`
- Returns `n5, dispatch_order5, status5, condition5`

`dispatch_order5` = `["Solar", <8 thermal units>, "Scarcity"]` (BESS is a `StorageUnit`,
not a `Generator`, so it does not appear in this index).

### Cell 3 — Status cell
Single `mo.md` line: solve status + termination condition.

### Cell 4 — Dispatch + SOC chart
Two vertically stacked subplots sharing the x-axis:
- **Top:** stacked area dispatch chart (same style as N4)
- **Bottom:** line chart of `n5.storage_units_t.state_of_charge["BESS"]` in MWh (0–1,200 MWh y-axis)

Saved as `n5_dispatch_soc.png`.

### Cell 5 — Price comparison chart
1×2 subplots:
- **Left:** N4 vs N5 shadow price overlay (full range)
- **Right:** same overlay, zoom [−250, 250] $/MWh

Saved as `n5_price_compare.png`.

### Cell 6 — Summary + CSV export
Computes and writes four CSV files (no dataframe display in cell output):

| File | Contents |
|---|---|
| `results_n5.csv` | Per-snapshot: demand_mw, shadow_price_per_mwh, dispatch per generator (MW), bess_charge_mw (`p_store`), bess_discharge_mw (`p_dispatch`), bess_soc_mwh (`state_of_charge`) |
| `unit_summary_n5.csv` | Per thermal unit: capacity_mw, marginal_cost, dispatched_mwh, average_loading, on_hours |
| `displacement_n5.csv` | Per unit: dispatched_mwh_n4, dispatched_mwh_n5, delta_mwh, pct_change |
| `bess_economics_n5.csv` | Single row: total_charged_mwh, total_discharged_mwh, rt_efficiency_realised, arbitrage_value_aud |

**`arbitrage_value_aud`** = Σ(discharge_t × price_t × dt) − Σ(charge_t × price_t × dt),
using N5 shadow prices and dt = 10/60 h.

**`displacement_n5.csv`** requires `n4` to be in scope. Since `build_n4()` already runs
in the prior cell and returns `n4`, the N5 summary cell takes `n4` as a dependency.

---

## Structural Approach

**A — Standalone `build_n5()`** (selected).  
Self-contained function following the exact pattern of every prior step.
N4 and N5 solve independently; comparison is pure post-processing.
Approximately 20 lines of shared setup are duplicated — intentional: each step
in the complexity ladder should be readable in isolation.

---

## Verification

1. `uvx marimo check Simulation/ToyModel.py` — must pass with no errors
2. `uv run Simulation/ToyModel.py` — all solves must reach `optimal`; check that N5 solve
   time is under 5 seconds
3. Inspect `n5_dispatch_soc.png`: BESS should charge during solar midday periods and
   discharge during Thu/Fri evening peaks
4. Inspect `n5_price_compare.png`: N5 prices should show reduced negative depth and
   reduced $15,500 spike frequency vs N4
5. Inspect `bess_economics_n5.csv`: `rt_efficiency_realised` should be ≈ 0.846;
   `arbitrage_value_aud` should be positive (BESS buys cheap, sells dear)
