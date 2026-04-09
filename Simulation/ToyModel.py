import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    from pathlib import Path
    import sys
    import importlib
    import numpy as np
    import marimo as mo
    from pathlib import Path
    import re

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import Simulation.pypsa_viz as pypsa_viz

    pypsa_viz = importlib.reload(pypsa_viz)
    build_dispatch_price_figure = pypsa_viz.build_dispatch_price_figure
    build_market_outcomes_dashboard = pypsa_viz.build_market_outcomes_dashboard
    build_market_outcomes_tables = pypsa_viz.build_market_outcomes_tables
    build_scenario_kpi_summary = pypsa_viz.build_scenario_kpi_summary

    mplconfigdir = Path(__file__).resolve().parent / ".mplconfig"
    mplconfigdir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mplconfigdir))

    import matplotlib.pyplot as plt
    import pandas as pd
    import pypsa

    output_dir = Path(__file__).resolve().parent / "outputs" / "toy_model"
    output_dir.mkdir(parents=True, exist_ok=True)
    mo.md(f"Notebook outputs are written to `{output_dir}`.")

    def summarize_snapshot_weightings(network, label):
        weights = network.snapshot_weightings.astype(float)
        unique_weights = weights.nunique(dropna=False)
        expected_hours = 1.0
        if len(network.snapshots) > 1 and hasattr(network.snapshots, "to_series"):
            deltas = network.snapshots.to_series().diff().dropna()
            expected_hours = deltas.dt.total_seconds().median() / 3600.0
        return pd.DataFrame(
            {
                "scenario": [label],
                "snapshot_count": [len(network.snapshots)],
                "expected_hours_per_snapshot": [expected_hours],
                "objective_weight": [weights["objective"].iloc[0]],
                "stores_weight": [weights["stores"].iloc[0]],
                "generators_weight": [weights["generators"].iloc[0]],
                "objective_unique_values": [int(unique_weights["objective"])],
                "stores_unique_values": [int(unique_weights["stores"])],
                "generators_unique_values": [int(unique_weights["generators"])],
            }
        )

    def export_figure(fig, stem=None):
        if stem is None:
            title = fig._suptitle.get_text() if fig._suptitle else ""
            if not title and fig.axes:
                title = fig.axes[0].get_title()
            stem = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "figure"

        output_path = output_dir / f"{stem}.png"
        fig.savefig(output_path, dpi=160, bbox_inches="tight")
        return output_path

    def render_market_outcomes_block(dispatch_outcomes, market_totals, *, heading, notes_md):
        display = dispatch_outcomes.copy()
        pct_cols = ["share_of_total_demand_pct", "average_loading"]
        hour_cols = ["active_hours", "charge_hours"]
        money_cols = [
            "realized_sell_price_aud_per_mwh",
            "gross_revenue_aud",
            "variable_cost_aud",
            "charging_cost_aud",
            "gross_margin_aud",
            "margin_aud_per_mwh",
        ]
        energy_cols = ["capacity_mw", "dispatched_mwh", "charge_mwh", "average_dispatch_mw"]

        for cols in (pct_cols, hour_cols, money_cols, energy_cols):
            display[cols] = display[cols].round(1)

        display = display[
            [
                "asset",
                "type",
                "capacity_mw",
                "dispatched_mwh",
                "charge_mwh",
                "share_of_total_demand_pct",
                "active_hours",
                "charge_hours",
                "average_loading",
                "realized_sell_price_aud_per_mwh",
                "gross_revenue_aud",
                "variable_cost_aud",
                "charging_cost_aud",
                "gross_margin_aud",
                "margin_aud_per_mwh",
            ]
        ]

        totals_display = market_totals.copy()
        totals_display["value"] = totals_display["value"].round(1)

        return mo.vstack(
            [
                mo.md(f"## {heading}\n\n{notes_md}"),
                mo.hstack([totals_display, display], widths=[0.28, 0.72]),
            ]
        )

    return (
        build_dispatch_price_figure,
        build_market_outcomes_dashboard,
        build_market_outcomes_tables,
        build_scenario_kpi_summary,
        export_figure,
        mo,
        np,
        output_dir,
        pd,
        pypsa,
        render_market_outcomes_block,
        summarize_snapshot_weightings,
    )


@app.cell
def _(mo):
    mo.md("""
    # Notebook 2.1 — Toy Model

    Minimal PyPSA toy model for the Stage 2 complexity ladder.
    This notebook currently preserves the original Step 1 setup:
    one bus, four thermal generators, flat demand, and a single solve.
    """)
    return


@app.cell
def _(np, pd, pypsa):
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2024-01-01", periods=24, freq="h").as_unit("ns"))
    n.add("Carrier", "AC")
    n.add("Bus", "NEM", carrier="AC")
    for _carrier in ["brown_coal", "black_coal", "ccgt", "ocgt"]:
        n.add("Carrier", _carrier)

    n.add("Generator", "Brown Coal", bus="NEM", carrier="brown_coal", p_nom=3000, marginal_cost=25)
    n.add("Generator", "Black Coal", bus="NEM", carrier="black_coal", p_nom=5000, marginal_cost=40)
    n.add("Generator", "CCGT Gas", bus="NEM", carrier="ccgt", p_nom=2000, marginal_cost=85)
    n.add("Generator", "OCGT Gas", bus="NEM", carrier="ocgt", p_nom=800, marginal_cost=180)

    # Stylized daily demand shape with mild random noise.
    base_shape = np.array(
        [
            0.72, 0.69, 0.67, 0.66, 0.67, 0.71, 0.79, 0.88,
            0.95, 0.99, 1.01, 1.00, 0.98, 0.97, 0.98, 1.00,
            1.05, 1.12, 1.23, 1.34, 1.27, 1.10, 0.95, 0.82,
        ]
    )
    rng = np.random.default_rng(42)
    noise = rng.normal(loc=0.0, scale=0.015, size=24)
    demand_profile = (8000 * (base_shape + noise)).clip(min=6000)
    n.add("Load", "Demand", bus="NEM", p_set=pd.Series(demand_profile, index=n.snapshots))

    dispatch_order = pd.Index(
        ["Brown Coal", "Black Coal", "CCGT Gas", "OCGT Gas"],
        name="generator",
    )

    status, condition = n.optimize(solver_name="highs")
    return condition, dispatch_order, n, status


@app.cell
def _(build_dispatch_price_figure, dispatch_order, export_figure, n):
    dispatch_price_fig = build_dispatch_price_figure(
        n,
        dispatch_order=dispatch_order,
        panels=("dispatch", "price"),
        dispatch_title="Toy Model Dispatch by Generator",
        price_title="Toy Model Shadow Price",
        price_color="#d2691e",
        legend_title="Generator",
        legend_ncols=4,
        legend_loc="upper center",
        legend_bbox=(0.5, 1.2),
        figure_legend=False,
        figsize=(12, 6.8),
    )
    export_figure(dispatch_price_fig, stem="n1_dispatch_price")
    dispatch_price_fig
    return


@app.cell
def _(dispatch_order, n, output_dir, pd):
    _results = pd.concat(
        [
            n.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n.generators_t.p[dispatch_order].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
        ],
        axis=1,
    )

    _generator_summary = (
        n.generators.loc[dispatch_order, ["p_nom", "marginal_cost"]]
        .rename(columns={"p_nom": "capacity_mw", "marginal_cost": "marginal_cost_per_mwh"})
        .assign(
            dispatched_mwh=n.generators_t.p[dispatch_order].sum(),
            average_dispatch_mw=n.generators_t.p[dispatch_order].mean(),
        )
        .reset_index(names="generator")
    )
    _generator_summary["capacity_factor"] = (
        _generator_summary["average_dispatch_mw"] / _generator_summary["capacity_mw"]
    ).round(3)

    # system_summary_n4.csv: compact scenario KPIs retained for offline review.
    _system_summary = pd.DataFrame(
        {
            "metric": [
                "Average demand (MW)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
                "Total generation (MWh)",
            ],
            "value": [
                _results["demand_mw"].mean(),
                _results["shadow_price_per_mwh"].mean(),
                _results["shadow_price_per_mwh"].max(),
                n.generators_t.p[dispatch_order].sum().sum(),
            ],
        }
    )
    _results.to_csv(output_dir / "results.csv")
    _generator_summary.to_csv(output_dir / "generator_summary.csv", index=False)
    _system_summary.to_csv(output_dir / "system_summary.csv", index=False)
    return


@app.cell
def _(build_market_outcomes_tables, dispatch_order, n, output_dir):
    dispatch_outcomes_n1, market_totals_n1 = build_market_outcomes_tables(
        n,
        dispatch_order=dispatch_order,
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_n1.to_csv(output_dir / "dispatch_outcomes_n1.csv", index=False)
    market_totals_n1.to_csv(output_dir / "market_totals_n1.csv", index=False)
    return dispatch_outcomes_n1, market_totals_n1


@app.cell
def _(build_scenario_kpi_summary, condition, market_totals_n1, n, status):
    build_scenario_kpi_summary(
        status=status,
        condition=condition,
        demand_series=n.loads_t.p["Demand"],
        market_totals=market_totals_n1,
        extra_metrics=[
            ("Total generator supply (MWh)", market_totals_n1.set_index("metric").at["Total generator supply (MWh)", "value"]),
        ],
    )
    return


@app.cell
def _(dispatch_outcomes_n1, market_totals_n1, render_market_outcomes_block):
    render_market_outcomes_block(
        dispatch_outcomes_n1,
        market_totals_n1,
        heading="N1 Dispatch Outcomes",
        notes_md=(
            "Demand share uses **total N1 demand energy** over the full horizon. "
            "Gross margin is **revenue minus variable cost** for generator dispatch."
        ),
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step Up: Weekly Run with Maintenance

    This keeps the same single-bus merit-order setup, but extends the
    horizon to one week at 30-minute resolution and applies a daytime
    maintenance derating to black coal on day 2. The higher resolution
    smooths the dispatch and price series without materially increasing
    solve time.
    """)
    return


@app.cell
def _(np, pd, pypsa):
    n2 = pypsa.Network()
    n2.set_snapshots(
        pd.date_range("2024-01-01", periods=336, freq="30min").as_unit("ns"),
        weightings_from_timedelta=True,
    )
    n2.add("Carrier", "AC")
    n2.add("Bus", "NEM", carrier="AC")
    for _carrier in ["brown_coal", "black_coal", "ccgt", "ocgt"]:
        n2.add("Carrier", _carrier)

    n2.add("Generator", "Brown Coal", bus="NEM", carrier="brown_coal", p_nom=3000, marginal_cost=25)
    n2.add("Generator", "Black Coal", bus="NEM", carrier="black_coal", p_nom=5000, marginal_cost=40)
    n2.add("Generator", "CCGT Gas", bus="NEM", carrier="ccgt", p_nom=2000, marginal_cost=85)
    n2.add("Generator", "OCGT Gas", bus="NEM", carrier="ocgt", p_nom=800, marginal_cost=180)

    _base_shape2 = np.array(
        [
            0.72, 0.69, 0.67, 0.66, 0.67, 0.71, 0.79, 0.88,
            0.95, 0.99, 1.01, 1.00, 0.98, 0.97, 0.98, 1.00,
            1.05, 1.12, 1.23, 1.34, 1.27, 1.10, 0.95, 0.82,
        ]
    )
    # Interpolate hourly shape to 30-min resolution (48 slots/day, 7 days = 336)
    _base_shape2_30min = np.repeat(_base_shape2, 2)
    _day_scalars2 = np.repeat([0.97, 0.98, 0.985, 0.99, 0.992, 0.995, 0.997], repeats=48)
    _rng2 = np.random.default_rng(7)
    _noise2 = _rng2.normal(loc=0.0, scale=0.012, size=336)
    demand_profile2 = (8000 * (np.tile(_base_shape2_30min, 7) * _day_scalars2 + _noise2)).clip(min=6000)
    n2.add("Load", "Demand", bus="NEM", p_set=pd.Series(demand_profile2, index=n2.snapshots))

    _black_coal_availability2 = pd.Series(1.0, index=n2.snapshots)
    _maintenance_window2 = (n2.snapshots >= pd.Timestamp("2024-01-02 09:00:00")) & (
        n2.snapshots < pd.Timestamp("2024-01-02 16:00:00")
    )
    _black_coal_availability2.loc[_maintenance_window2] = 0.5
    n2.generators_t.p_max_pu = pd.DataFrame(
        {"Black Coal": _black_coal_availability2}, index=n2.snapshots
    )

    dispatch_order2 = pd.Index(
        ["Brown Coal", "Black Coal", "CCGT Gas", "OCGT Gas"],
        name="generator",
    )

    status2, condition2 = n2.optimize(solver_name="highs")
    return condition2, dispatch_order2, n2, status2


@app.cell
def _(build_dispatch_price_figure, dispatch_order2, export_figure, n2):
    dispatch_price_fig2 = build_dispatch_price_figure(
        n2,
        dispatch_order=dispatch_order2,
        panels=("dispatch", "price"),
        dispatch_title="Weekly Dispatch with Black Coal Maintenance (30-min)",
        price_title="Weekly Shadow Price with Maintenance (30-min)",
        price_color="#b22222",
        legend_title="Generator",
        legend_ncols=4,
        legend_loc="upper center",
        legend_bbox=(0.5, 1.2),
        figure_legend=False,
        figsize=(16, 7.0),
        date_tick_interval_hours=12,
    )
    export_figure(dispatch_price_fig2, stem="n2_dispatch_price")
    dispatch_price_fig2
    return


@app.cell
def _(dispatch_order2, n2, output_dir, pd):
    results2 = pd.concat(
        [
            n2.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n2.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n2.generators_t.p[dispatch_order2].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
        ],
        axis=1,
    )

    generator_summary2 = (
        n2.generators.loc[dispatch_order2, ["p_nom", "marginal_cost"]]
        .rename(columns={"p_nom": "capacity_mw", "marginal_cost": "marginal_cost_per_mwh"})
        .assign(
            dispatched_mwh=n2.generators_t.p[dispatch_order2].sum(),
            average_dispatch_mw=n2.generators_t.p[dispatch_order2].mean(),
        )
        .reset_index(names="generator")
    )
    generator_summary2["capacity_factor"] = (
        generator_summary2["average_dispatch_mw"] / generator_summary2["capacity_mw"]
    ).round(3)

    system_summary2 = pd.DataFrame(
        {
            "metric": [
                "Average demand (MW)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
                "Hours at OCGT price",
            ],
            "value": [
                results2["demand_mw"].mean(),
                results2["shadow_price_per_mwh"].mean(),
                results2["shadow_price_per_mwh"].max(),
                (results2["shadow_price_per_mwh"] == 180).sum(),
            ],
        }
    )

    results2.to_csv(output_dir / "results_multiday.csv")
    generator_summary2.to_csv(output_dir / "generator_summary_multiday.csv", index=False)
    system_summary2.to_csv(output_dir / "system_summary_multiday.csv", index=False)
    return


@app.cell
def _(build_market_outcomes_tables, dispatch_order2, n2, output_dir):
    dispatch_outcomes_n2, market_totals_n2 = build_market_outcomes_tables(
        n2,
        dispatch_order=dispatch_order2,
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_n2.to_csv(output_dir / "dispatch_outcomes_n2.csv", index=False)
    market_totals_n2.to_csv(output_dir / "market_totals_n2.csv", index=False)
    return dispatch_outcomes_n2, market_totals_n2


@app.cell
def _(build_scenario_kpi_summary, condition2, market_totals_n2, n2, status2):
    build_scenario_kpi_summary(
        status=status2,
        condition=condition2,
        demand_series=n2.loads_t.p["Demand"],
        market_totals=market_totals_n2,
        extra_metrics=[
            ("Hours at OCGT price", (n2.buses_t.marginal_price["NEM"] == 180).sum()),
        ],
    )
    return


@app.cell
def _(dispatch_outcomes_n2, market_totals_n2, render_market_outcomes_block):
    render_market_outcomes_block(
        dispatch_outcomes_n2,
        market_totals_n2,
        heading="N2 Dispatch Outcomes",
        notes_md=(
            "Demand share uses **total N2 demand energy** over the full horizon. "
            "Gross margin is **revenue minus variable cost** for generator dispatch."
        ),
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step Up: Thu–Sun with Solar, VIC-Calibrated Demand (Pre-BESS Era)

    Four-day window (Thursday–Sunday) at 10-minute resolution using
    separate VIC-calibrated weekday and weekend demand shapes. Solar is
    6 000 MW with a Gaussian diurnal profile (σ = 2.5 h).

    This approximates Victoria circa 2018–2020: significant solar
    penetration, no grid-scale storage. Expected pricing regimes:

    - **Thu/Fri midday** — $25 (brown coal marginal, solar suppresses black coal)
    - **Sat/Sun midday** — $0 (solar exceeds weekend demand, curtailment)
    - **Thu evening** — $180 (OCGT forced by high weekday peak)
    - **Fri evening** — $85 (CCGT marginal, slightly lower demand)
    - **Sat/Sun evening** — $40 (black coal, modest weekend peak)
    """)
    return


@app.cell
def _(np, pd, pypsa):
    n3 = pypsa.Network()
    n3.set_snapshots(
        pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
        weightings_from_timedelta=True,
    )
    n3.add("Carrier", "AC")
    n3.add("Bus", "NEM", carrier="AC")

    n3.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
    n3.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
    n3.add("Generator", "CCGT Gas",   bus="NEM", p_nom=2000, marginal_cost=85)
    n3.add("Generator", "OCGT Gas",   bus="NEM", p_nom=800,  marginal_cost=180)
    n3.add("Generator", "Solar",      bus="NEM", p_nom=6000, marginal_cost=0)

    # Gaussian solar: σ = 2.5 h = 15 × 10-min slots, noon = slot 72
    _slot_of_day = np.arange(576) % 144
    _solar_pu3 = np.exp(-0.5 * ((_slot_of_day - 72) / 15.0) ** 2)
    n3.generators_t.p_max_pu = pd.DataFrame({"Solar": _solar_pu3}, index=n3.snapshots)

    # VIC-calibrated half-hourly shapes (48 values), linearly interpolated to 10-min
    # Each 10-min slot maps to 1/3 of a half-hour interval
    def _to_10min(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    _weekday_h = np.array([
        # 00:00–02:30 — overnight minimum (~4 000 MW)
        0.53, 0.52, 0.51, 0.50, 0.50, 0.50,
        # 03:00–05:30 — pre-dawn, slow rise
        0.50, 0.51, 0.52, 0.54, 0.57, 0.62,
        # 06:00–08:30 — morning ramp to peak (~7 400 MW)
        0.69, 0.76, 0.83, 0.89, 0.92, 0.93,
        # 09:00–10:30 — post-morning sag
        0.91, 0.88, 0.86, 0.85,
        # 11:00–14:30 — flat midday low (solar holds price at $25)
        0.84, 0.84, 0.84, 0.84, 0.85, 0.86, 0.87, 0.88,
        # 15:00–17:30 — afternoon build into evening
        0.90, 0.93, 0.96, 1.00, 1.05, 1.13,
        # 18:00–20:30 — broad evening peak plateau (OCGT zone above 1.25)
        1.22, 1.28, 1.33, 1.32, 1.28, 1.18,
        # 21:00–23:30 — post-peak decline
        1.04, 0.91, 0.80, 0.71, 0.64, 0.58,
    ])
    _weekend_h = np.array([
        # 00:00–02:30 — overnight minimum (~3 900 MW with Sat scalar)
        0.52, 0.51, 0.50, 0.49, 0.49, 0.49,
        # 03:00–05:30 — pre-dawn
        0.50, 0.50, 0.51, 0.52, 0.53, 0.55,
        # 06:00–08:30 — slow morning rise (sleeping in, no sharp peak)
        0.58, 0.61, 0.65, 0.69, 0.73, 0.77,
        # 09:00–10:30 — gentle rise toward midday
        0.80, 0.82, 0.83, 0.83,
        # 11:00–14:30 — flat midday plateau (solar curtailment zone)
        0.83, 0.83, 0.83, 0.83, 0.84, 0.85, 0.87, 0.90,
        # 15:00–17:30 — afternoon build (later than weekday)
        0.93, 0.97, 1.00, 1.03, 1.05, 1.06,
        # 18:00–20:30 — modest evening plateau (~7 400 MW, black coal marginal)
        1.06, 1.06, 1.05, 1.02, 0.97, 0.91,
        # 21:00–23:30 — post-peak decline
        0.83, 0.74, 0.66, 0.60, 0.55, 0.52,
    ])

    # Thu ×1.00, Fri ×0.97, Sat ×0.87, Sun ×0.83
    _demand_shape = np.concatenate([
        _to_10min(_weekday_h) * 1.00,
        _to_10min(_weekday_h) * 0.97,
        _to_10min(_weekend_h) * 0.87,
        _to_10min(_weekend_h) * 0.83,
    ])
    _rng3 = np.random.default_rng(7)
    _noise3 = _rng3.normal(0.0, 0.008, 576)
    _demand3 = (8000 * (_demand_shape + _noise3)).clip(min=0)
    n3.add("Load", "Demand", bus="NEM", p_set=pd.Series(_demand3, index=n3.snapshots))

    dispatch_order3 = pd.Index(
        ["Solar", "Brown Coal", "Black Coal", "CCGT Gas", "OCGT Gas"],
        name="generator",
    )

    status3, condition3 = n3.optimize(solver_name="highs")
    return condition3, dispatch_order3, n3, status3


@app.cell
def _(build_dispatch_price_figure, dispatch_order3, export_figure, n3):
    dispatch_price_fig3 = build_dispatch_price_figure(
        n3,
        dispatch_order=dispatch_order3,
        panels=("dispatch", "price"),
        dispatch_title="Thu–Sun Dispatch — VIC Solar Penetration, Pre-BESS (10-min)",
        price_title="Thu–Sun Shadow Price — VIC Solar Penetration, Pre-BESS (10-min)",
        price_bus="NEM",
        price_color="#2e8b57",
        price_plot_style="line",
        legend_title="Generator",
        legend_ncols=5,
        legend_loc="upper center",
        legend_bbox=(0.5, 1.2),
        figure_legend=False,
        figsize=(18, 7.4),
        date_tick_interval_hours=6,
    )
    export_figure(dispatch_price_fig3, stem="n3_dispatch_price")
    dispatch_price_fig3
    return


@app.cell
def _(dispatch_order3, n3, output_dir, pd):
    _results3 = pd.concat(
        [
            n3.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n3.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n3.generators_t.p[dispatch_order3].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
        ],
        axis=1,
    )
    _results3.to_csv(output_dir / "results_solar.csv")
    return


@app.cell
def _(build_market_outcomes_tables, dispatch_order3, n3, output_dir):
    dispatch_outcomes_n3, market_totals_n3 = build_market_outcomes_tables(
        n3,
        dispatch_order=dispatch_order3,
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_n3.to_csv(output_dir / "dispatch_outcomes_n3.csv", index=False)
    market_totals_n3.to_csv(output_dir / "market_totals_n3.csv", index=False)
    return dispatch_outcomes_n3, market_totals_n3


@app.cell
def _(build_scenario_kpi_summary, condition3, market_totals_n3, n3, status3):
    build_scenario_kpi_summary(
        status=status3,
        condition=condition3,
        demand_series=n3.loads_t.p["Demand"],
        market_totals=market_totals_n3,
        extra_metrics=[
            ("Near-zero price hours", (n3.buses_t.marginal_price["NEM"] <= 0.5).sum() * (10.0 / 60.0)),
        ],
    )
    return


@app.cell
def _(dispatch_outcomes_n3, market_totals_n3, render_market_outcomes_block):
    render_market_outcomes_block(
        dispatch_outcomes_n3,
        market_totals_n3,
        heading="N3 Dispatch Outcomes",
        notes_md=(
            "Solar reshapes both **energy share** and **price capture** across the Thu–Sun horizon. "
            "Weekend midday curtailment and weekday evening gas-setting intervals are reflected in asset margins."
        ),
    )
    return


@app.cell
def _(build_market_outcomes_dashboard, dispatch_outcomes_n3, export_figure):
    outcomes_fig3 = build_market_outcomes_dashboard(
        dispatch_outcomes_n3,
        title="N3 Market Outcomes by Asset",
        figsize=(20, 6.6),
    )
    export_figure(outcomes_fig3, stem="n3_outcomes_dashboard")
    outcomes_fig3
    return


@app.cell
def _(mo):
    mo.md("""
    ## N4: Multi-Unit Thermal Stack + Ramp Constraints + Optional Unit Commitment

    Direct extension of `n3` with the same 4-day, 10-minute horizon, demand, and solar:
    - thermal fleet split into 8 separate units with differentiated costs
    - class-based thermal ramp-rate limits
    - optional unit commitment for coal and gas (`uc_on=True`)
    """)
    return


@app.cell
def _(np, pd, pypsa):
    thermal_units_n4 = pd.DataFrame(
        [
            {"unit_name": "Brown Coal A", "tech": "brown_coal", "p_nom_mw": 1400, "marginal_cost": 23.0},
            {"unit_name": "Brown Coal B", "tech": "brown_coal", "p_nom_mw": 1000, "marginal_cost": 26.0},
            {"unit_name": "Brown Coal C", "tech": "brown_coal", "p_nom_mw": 600, "marginal_cost": 29.0},
            {"unit_name": "Black Coal A", "tech": "black_coal", "p_nom_mw": 2800, "marginal_cost": 38.0},
            {"unit_name": "Black Coal B", "tech": "black_coal", "p_nom_mw": 2200, "marginal_cost": 44.0},
            {"unit_name": "CCGT A", "tech": "ccgt", "p_nom_mw": 1200, "marginal_cost": 82.0},
            {"unit_name": "CCGT B", "tech": "ccgt", "p_nom_mw": 800, "marginal_cost": 90.0},
            {"unit_name": "OCGT A", "tech": "ocgt", "p_nom_mw": 800, "marginal_cost": 260.0},
        ]
    )

    ramp_defaults_n4 = {
        "brown_coal": {"ramp_limit_up": 0.030, "ramp_limit_down": 0.030},
        "black_coal": {"ramp_limit_up": 0.045, "ramp_limit_down": 0.045},
        "ccgt": {"ramp_limit_up": 0.110, "ramp_limit_down": 0.110},
        "ocgt": {"ramp_limit_up": 0.250, "ramp_limit_down": 0.250},
    }

    def _to_10min(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    weekday_h = np.array(
        [
            0.53, 0.52, 0.51, 0.50, 0.50, 0.50,
            0.50, 0.51, 0.52, 0.54, 0.57, 0.62,
            0.69, 0.76, 0.83, 0.89, 0.92, 0.93,
            0.91, 0.88, 0.86, 0.85,
            0.84, 0.84, 0.84, 0.84, 0.85, 0.86, 0.87, 0.88,
            0.90, 0.93, 0.96, 1.00, 1.05, 1.13,
            1.22, 1.28, 1.33, 1.32, 1.28, 1.18,
            1.04, 0.91, 0.80, 0.71, 0.64, 0.58,
        ]
    )
    weekend_h = np.array(
        [
            0.52, 0.51, 0.50, 0.49, 0.49, 0.49,
            0.50, 0.50, 0.51, 0.52, 0.53, 0.55,
            0.58, 0.61, 0.65, 0.69, 0.73, 0.77,
            0.80, 0.82, 0.83, 0.83,
            0.83, 0.83, 0.83, 0.83, 0.84, 0.85, 0.87, 0.90,
            0.93, 0.97, 1.00, 1.03, 1.05, 1.06,
            1.06, 1.06, 1.05, 1.02, 0.97, 0.91,
            0.83, 0.74, 0.66, 0.60, 0.55, 0.52,
        ]
    )

    def build_n4():
        n4 = pypsa.Network()
        n4.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )
        n4.add("Carrier", "AC")
        n4.add("Bus", "NEM", carrier="AC")
        for _carrier in ["solar", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity"]:
            n4.add("Carrier", _carrier)

        slot_of_day = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        solar_pu = np.exp(-0.5 * ((slot_of_day - 72) / 15.0) ** 2)
        n4.add("Generator", "Solar", bus="NEM", carrier="solar", p_nom=6000, marginal_cost=0.0)
        n4.generators_t.p_max_pu = pd.DataFrame({"Solar": solar_pu}, index=n4.snapshots)

        demand_shape = np.concatenate(
            [
                _to_10min(weekday_h) * 1.00 * peak_adder,
                _to_10min(weekday_h) * 0.97 * peak_adder,
                _to_10min(weekend_h) * 0.87 * peak_adder,
                _to_10min(weekend_h) * 0.83 * peak_adder,
            ]
        )
        rng = np.random.default_rng(7)
        noise = rng.normal(0.0, 0.008, 576)
        demand = (8000 * (demand_shape + noise)).clip(min=0)
        n4.add("Load", "Demand", bus="NEM", p_set=pd.Series(demand, index=n4.snapshots))

        for row in thermal_units_n4.itertuples(index=False):
            ramp_cfg = ramp_defaults_n4[row.tech]
            n4.add(
                "Generator",
                row.unit_name,
                bus="NEM",
                carrier=row.tech,
                p_nom=row.p_nom_mw,
                marginal_cost=row.marginal_cost,
                ramp_limit_up=ramp_cfg["ramp_limit_up"],
                ramp_limit_down=ramp_cfg["ramp_limit_down"],
            )

        n4.add(
            "Generator",
            "Scarcity",
            bus="NEM",
            carrier="scarcity",
            p_nom=30000,
            marginal_cost=15500.0,
        )

        dispatch_order = pd.Index(
            ["Solar"] + thermal_units_n4["unit_name"].tolist() + ["Scarcity"],
            name="generator",
        )

        status, condition = n4.optimize(solver_name="highs")
        return n4, dispatch_order, status, condition

    n4, dispatch_order4, status4, condition4 = build_n4()
    return condition4, dispatch_order4, n4, status4, thermal_units_n4


@app.cell
def _(build_dispatch_price_figure, dispatch_order4, export_figure, n4):
    dispatch_price_fig4 = build_dispatch_price_figure(
        n4,
        dispatch_order=dispatch_order4,
        panels=("dispatch", "price"),
        layout="dispatch_price_zoom",
        dispatch_title="N4 Unit Dispatch — Multi-Unit Thermal with Ramp Constraints",
        price_title_full="N4 Shadow Price — Full",
        price_title_zoom="N4 Shadow Price — Zoom [-250, 250]",
        price_color="#b22222",
        price_ylim_zoom=(-250, 250),
        legend_title="Generator",
        legend_ncols=3,
        legend_loc="upper center",
        legend_bbox=(0.5, 1.18),
        figure_legend=False,
        figsize=(18, 8.6),
        date_tick_interval_hours=6,
    )
    export_figure(dispatch_price_fig4, stem="n4_dispatch_price_composite")
    dispatch_price_fig4
    return


@app.cell
def _(dispatch_order4, n4, output_dir, pd, thermal_units_n4):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot
    # results_n4.csv: time-series demand, price, and dispatch trace for the N4 scenario.
    _results = pd.concat(
        [
            n4.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n4.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n4.generators_t.p[dispatch_order4].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
        ],
        axis=1,
    )
    _results.to_csv(output_dir / "results_n4.csv")

    # unit_summary_n4.csv: unit-level thermal operating summary across the full N4 horizon.
    _thermal_units_idx = thermal_units_n4.set_index("unit_name")
    _unit_summary = _thermal_units_idx[["tech", "p_nom_mw", "marginal_cost"]].rename(
        columns={"p_nom_mw": "capacity_mw", "marginal_cost": "marginal_cost_per_mwh"}
    )
    _unit_summary["dispatched_mwh"] = (n4.generators_t.p[_thermal_units_idx.index] * _dt).sum()
    _unit_summary["average_dispatch_mw"] = n4.generators_t.p[_thermal_units_idx.index].mean()
    _unit_summary["average_loading"] = (
        _unit_summary["average_dispatch_mw"] / _unit_summary["capacity_mw"]
    ).round(3)
    _unit_summary["on_hours"] = (n4.generators_t.p[_thermal_units_idx.index] > 0).sum() * _dt
    _unit_summary = _unit_summary.reset_index(names="unit")
    _unit_summary.to_csv(output_dir / "unit_summary_n4.csv", index=False)

    _system_summary = pd.DataFrame(
        {
            "metric": [
                "Average demand (MW)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
                "Thermal on-hours (sum)",
            ],
            "value": [
                _results["demand_mw"].mean(),
                _results["shadow_price_per_mwh"].mean(),
                _results["shadow_price_per_mwh"].max(),
                _unit_summary["on_hours"].sum(),
            ],
        }
    )
    _system_summary.to_csv(output_dir / "system_summary_n4.csv", index=False)
    return


@app.cell
def _(build_market_outcomes_tables, dispatch_order4, n4, output_dir):
    # dispatch_outcomes_n4.csv and market_totals_n4.csv: shared market outcomes for notebook tables and exports.
    dispatch_outcomes_n4, market_totals_n4 = build_market_outcomes_tables(
        n4,
        dispatch_order=dispatch_order4,
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_n4.to_csv(output_dir / "dispatch_outcomes_n4.csv", index=False)
    market_totals_n4.to_csv(output_dir / "market_totals_n4.csv", index=False)
    return dispatch_outcomes_n4, market_totals_n4


@app.cell
def _(n4, output_dir, summarize_snapshot_weightings):
    weighting_summary_n4 = summarize_snapshot_weightings(n4, "N4")
    weighting_summary_n4.to_csv(output_dir / "snapshot_weightings_n4.csv", index=False)
    weighting_summary_n4
    return


@app.cell
def _(
    build_scenario_kpi_summary,
    condition4,
    market_totals_n4,
    n4,
    status4,
    thermal_units_n4,
):
    thermal_on_hours = (
        (n4.generators_t.p[thermal_units_n4["unit_name"]] > 0).sum().sum() * (10.0 / 60.0)
    )
    build_scenario_kpi_summary(
        status=status4,
        condition=condition4,
        demand_series=n4.loads_t.p["Demand"],
        market_totals=market_totals_n4,
        extra_metrics=[("Thermal on-hours (sum)", thermal_on_hours)],
    )
    return


@app.cell
def _(dispatch_outcomes_n4, market_totals_n4, render_market_outcomes_block):
    render_market_outcomes_block(
        dispatch_outcomes_n4,
        market_totals_n4,
        heading="N4 Dispatch Outcomes",
        notes_md=(
            "Thermal unit splitting and ramp constraints create **price volatility** and **margin separation** "
            "within the thermal stack. Scarcity remains a modeled backstop rather than a regularly dispatched asset."
        ),
    )
    return


@app.cell
def _(build_market_outcomes_dashboard, dispatch_outcomes_n4, export_figure):
    outcomes_fig4 = build_market_outcomes_dashboard(
        dispatch_outcomes_n4,
        title="N4 Market Outcomes by Asset",
        figsize=(20, 6.8),
    )
    export_figure(outcomes_fig4, stem="n4_outcomes_dashboard")
    outcomes_fig4
    return


@app.cell
def _(mo):
    mo.md("""
    ## N5: Multi-Unit Thermal Stack + Ramp Constraints + BESS

    Direct extension of N4 with the same 4-day, 10-minute horizon, demand, solar,
    and 8-unit thermal fleet. Adds a single aggregate BESS representing the
    VIC grid-scale fleet and explicitly uses elapsed-hour snapshot weighting so
    PyPSA solves the 10-minute horizon on a physically correct sub-hourly basis:

    - **600 MW / 900 MWh** (1.5-hour duration)
    - **84.6 % round-trip efficiency** (92 % store × 92 % dispatch)
    - **50 % initial SOC** (450 MWh at Thursday 00:00)
    - **Higher peaker marginal cost** so the evening peak more often clears on expensive gas
    - LP dispatch: optimizer charges during cheap/near-zero-price periods and
      discharges into afternoon and evening gas-priced peaks

    Expected effects vs N4: retained near-zero midday solar pricing, stronger
    gas-priced evening peaks, more visible BESS arbitrage, and larger high-cost
    thermal displacement.

    The BESS has no additional storage-value adder in this calibration. Charging
    and discharging decisions are driven purely by observed arbitrage value under
    perfect foresight.
    """)
    return


@app.cell
def _():
    n5_bess_power_mw = 600.0
    n5_bess_energy_mwh = 900.0
    n5_bess_initial_soc_mwh = 450.0
    n5_bess_cyclic_state_of_charge = True
    return (
        n5_bess_cyclic_state_of_charge,
        n5_bess_energy_mwh,
        n5_bess_initial_soc_mwh,
        n5_bess_power_mw,
    )


@app.cell
def _(
    n5_bess_cyclic_state_of_charge,
    n5_bess_energy_mwh,
    n5_bess_initial_soc_mwh,
    n5_bess_power_mw,
    np,
    pd,
    pypsa,
    thermal_units_n4,
):
    _ramp_defaults = {
        "brown_coal": {"ramp_limit_up": 0.030, "ramp_limit_down": 0.030},
        "black_coal": {"ramp_limit_up": 0.045, "ramp_limit_down": 0.045},
        "ccgt":       {"ramp_limit_up": 0.110, "ramp_limit_down": 0.110},
        "ocgt":       {"ramp_limit_up": 0.250, "ramp_limit_down": 0.250},
    }
    _weekday_h = np.array([
        0.53, 0.52, 0.51, 0.50, 0.50, 0.50,
        0.50, 0.51, 0.52, 0.54, 0.57, 0.62,
        0.69, 0.76, 0.83, 0.89, 0.92, 0.93,
        0.91, 0.88, 0.86, 0.85,
        0.84, 0.84, 0.84, 0.84, 0.85, 0.86, 0.87, 0.88,
        0.90, 0.93, 0.96, 1.00, 1.05, 1.13,
        1.22, 1.28, 1.33, 1.32, 1.28, 1.18,
        1.04, 0.91, 0.80, 0.71, 0.64, 0.58,
    ])
    _weekend_h = np.array([
        0.52, 0.51, 0.50, 0.49, 0.49, 0.49,
        0.50, 0.50, 0.51, 0.52, 0.53, 0.55,
        0.58, 0.61, 0.65, 0.69, 0.73, 0.77,
        0.80, 0.82, 0.83, 0.83,
        0.83, 0.83, 0.83, 0.83, 0.84, 0.85, 0.87, 0.90,
        0.93, 0.97, 1.00, 1.03, 1.05, 1.06,
        1.06, 1.06, 1.05, 1.02, 0.97, 0.91,
        0.83, 0.74, 0.66, 0.60, 0.55, 0.52,
    ])

    def _to_10min(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n5():
        n5 = pypsa.Network()
        n5.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )
        n5.add("Carrier", "AC")
        n5.add("Bus", "NEM", carrier="AC")
        for _carrier in ["solar", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n5.add("Carrier", _carrier)

        _slot = np.arange(576) % 144
        _peak_adder = np.ones(144)
        _peak_adder[96:126] = 1.05
        _peak_adder[102:120] = 1.08
        _solar_pu = np.exp(-0.5 * ((_slot - 72) / 15.0) ** 2)
        n5.add("Generator", "Solar", bus="NEM", carrier="solar", p_nom=6000, marginal_cost=0.0)
        n5.generators_t.p_max_pu = pd.DataFrame({"Solar": _solar_pu}, index=n5.snapshots)

        _demand_shape = np.concatenate([
            _to_10min(_weekday_h) * 1.00 * _peak_adder,
            _to_10min(_weekday_h) * 0.97 * _peak_adder,
            _to_10min(_weekend_h) * 0.87 * _peak_adder,
            _to_10min(_weekend_h) * 0.83 * _peak_adder,
        ])
        _rng = np.random.default_rng(7)  # same seed as N4 for controlled comparison
        _noise = _rng.normal(0.0, 0.008, 576)
        _demand = (8000 * (_demand_shape + _noise)).clip(min=0)
        n5.add("Load", "Demand", bus="NEM", p_set=pd.Series(_demand, index=n5.snapshots))

        for _row in thermal_units_n4.itertuples(index=False):
            _ramp = _ramp_defaults[_row.tech]
            n5.add(
                "Generator", _row.unit_name,
                bus="NEM", carrier=_row.tech,
                p_nom=_row.p_nom_mw,
                marginal_cost=_row.marginal_cost,
                ramp_limit_up=_ramp["ramp_limit_up"],
                ramp_limit_down=_ramp["ramp_limit_down"],
            )

        n5.add("Generator", "Scarcity", bus="NEM", carrier="scarcity",
               p_nom=30000, marginal_cost=15500.0)

        n5.add(
            "StorageUnit", "BESS",
            bus="NEM",
            carrier="bess",
            p_nom=n5_bess_power_mw,
            max_hours=n5_bess_energy_mwh / n5_bess_power_mw,
            efficiency_store=0.92,
            efficiency_dispatch=0.92,
            state_of_charge_initial=(
                n5_bess_initial_soc_mwh if not n5_bess_cyclic_state_of_charge else 0.0
            ),
            cyclic_state_of_charge=n5_bess_cyclic_state_of_charge,
            marginal_cost=0.0,
            marginal_cost_storage=0.0,
        )

        _dispatch_order = pd.Index(
            ["Solar"] + thermal_units_n4["unit_name"].tolist() + ["Scarcity"],
            name="generator",
        )
        _status, _condition = n5.optimize(solver_name="highs")
        return n5, _dispatch_order, _status, _condition

    n5, dispatch_order5, status5, condition5 = build_n5()
    return condition5, dispatch_order5, n5, status5


@app.cell
def _(build_dispatch_price_figure, dispatch_order5, export_figure, n5):
    dispatch_fig5 = build_dispatch_price_figure(
        n5,
        dispatch_order=dispatch_order5,
        panels=("dispatch", "price", "soc"),
        storage_name="BESS",
        price_bus="NEM",
        near_zero_price_threshold=0.5,
        title="N5 Dispatch, Shadow Price, and BESS State of Charge",
        dispatch_title="Unit Dispatch (+ generation / BESS discharge, - BESS charge)",
        price_title="Shadow Price",
        soc_title="BESS State of Charge",
        price_color="#b22222",
        price_plot_style="step",
        legend_title="Asset",
        legend_ncols=4,
        legend_loc="lower center",
        legend_bbox=(0.5, -0.1),
        figure_legend=True,
        figsize=(18, 10.5),
        date_tick_interval_hours=6,
    )
    export_figure(dispatch_fig5, stem="n5_dispatch_soc")
    dispatch_fig5
    return


@app.cell
def _(
    build_market_outcomes_tables,
    dispatch_order5,
    n5,
    output_dir,
    pd,
    thermal_units_n4,
):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot

    # results_n5.csv: time-series demand, price, dispatch, charge, discharge, and SOC trace.
    _charge = n5.storage_units_t.p_store["BESS"]
    _discharge = n5.storage_units_t.p_dispatch["BESS"]
    _soc = n5.storage_units_t.state_of_charge["BESS"]
    _results = pd.concat(
        [
            n5.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n5.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n5.generators_t.p[dispatch_order5].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
            _charge.rename("bess_charge_mw"),
            _discharge.rename("bess_discharge_mw"),
            _soc.rename("bess_soc_mwh"),
        ],
        axis=1,
    )
    _results.to_csv(output_dir / "results_n5.csv")

    # dispatch_outcomes_n5.csv and market_totals_n5.csv: shared market outcomes for notebook tables and exports.
    dispatch_outcomes_n5, market_totals_n5 = build_market_outcomes_tables(
        n5,
        dispatch_order=dispatch_order5,
        thermal_units=thermal_units_n4,
        storage_name="BESS",
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_n5.to_csv(output_dir / "dispatch_outcomes_n5.csv", index=False)
    market_totals_n5.to_csv(output_dir / "market_totals_n5.csv", index=False)
    return dispatch_outcomes_n5, market_totals_n5


@app.cell
def _(n5, output_dir, summarize_snapshot_weightings):
    weighting_summary_n5 = summarize_snapshot_weightings(n5, "N5")
    weighting_summary_n5.to_csv(output_dir / "snapshot_weightings_n5.csv", index=False)
    weighting_summary_n5
    return


@app.cell
def _(n4, n5, output_dir, pd, thermal_units_n4):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot

    # unit_summary_n5.csv: unit-level thermal operating summary across the full N5 horizon.
    _thermal_idx = thermal_units_n4.set_index("unit_name")
    _unit_summary = _thermal_idx[["tech", "p_nom_mw", "marginal_cost"]].rename(
        columns={"p_nom_mw": "capacity_mw", "marginal_cost": "marginal_cost_per_mwh"}
    )
    _unit_summary["dispatched_mwh"] = (n5.generators_t.p[_thermal_idx.index] * _dt).sum()
    _unit_summary["average_dispatch_mw"] = n5.generators_t.p[_thermal_idx.index].mean()
    _unit_summary["average_loading"] = (
        _unit_summary["average_dispatch_mw"] / _unit_summary["capacity_mw"]
    ).round(3)
    _unit_summary["on_hours"] = (
        (n5.generators_t.p[_thermal_idx.index] > 0).sum() * _dt
    )
    _unit_summary = _unit_summary.reset_index(names="unit")
    _unit_summary.to_csv(output_dir / "unit_summary_n5.csv", index=False)

    # displacement_n5.csv: N4-versus-N5 thermal output change by unit after adding the BESS.
    _dispatched_n4 = (n4.generators_t.p[_thermal_idx.index] * _dt).sum()
    _dispatched_n5 = (n5.generators_t.p[_thermal_idx.index] * _dt).sum()
    _displacement = (
        pd.DataFrame({"dispatched_mwh_n4": _dispatched_n4, "dispatched_mwh_n5": _dispatched_n5})
        .rename_axis("unit")
        .reset_index()
    )
    _displacement["delta_mwh"] = (
        _displacement["dispatched_mwh_n5"] - _displacement["dispatched_mwh_n4"]
    )
    _displacement["pct_change"] = (
        _displacement["delta_mwh"] / _displacement["dispatched_mwh_n4"] * 100
    ).round(1)
    _displacement.to_csv(output_dir / "displacement_n5.csv", index=False)

    _displacement_by_tech = (
        _displacement.merge(_thermal_idx[["tech"]], left_on="unit", right_index=True)
        .groupby("tech", as_index=False)[["dispatched_mwh_n4", "dispatched_mwh_n5", "delta_mwh"]]
        .sum()
    )
    _displacement_by_tech["pct_change"] = (
        _displacement_by_tech["delta_mwh"] / _displacement_by_tech["dispatched_mwh_n4"] * 100
    ).round(1)
    _displacement_by_tech.to_csv(output_dir / "displacement_by_tech_n5.csv", index=False)
    return


@app.cell
def _(n5, output_dir, pd):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot

    # bess_economics_n5.csv: aggregate BESS charge, discharge, realised efficiency, and arbitrage value.
    _charge = n5.storage_units_t.p_store["BESS"]
    _discharge = n5.storage_units_t.p_dispatch["BESS"]
    _total_charged = (_charge * _dt).sum()
    _total_discharged = (_discharge * _dt).sum()
    _rt_eff = _total_discharged / _total_charged if _total_charged > 0 else 0.0
    _price = n5.buses_t.marginal_price["NEM"]
    _arb_value = (
        (_discharge * _price * _dt).sum() - (_charge * _price * _dt).sum()
    )
    _energy_capacity = (
        float(n5.storage_units.at["BESS", "p_nom"]) * float(n5.storage_units.at["BESS", "max_hours"])
    )
    _full_cycles = _total_discharged / _energy_capacity if _energy_capacity > 0 else 0.0
    _near_full_hours = (_dt * (_soc := n5.storage_units_t.state_of_charge["BESS"]).ge(0.95 * _energy_capacity).sum())
    _high_discharge_hours = (_dt * _discharge.ge(0.75 * float(n5.storage_units.at["BESS", "p_nom"])).sum())
    _high_price_threshold = max(120.0, float(_price.quantile(0.95)))
    _discharge_high_price_mwh = (_discharge[_price >= _high_price_threshold] * _dt).sum()
    _high_price_discharge_share = (
        _discharge_high_price_mwh / _total_discharged if _total_discharged > 0 else 0.0
    )
    pd.DataFrame([{
        "total_charged_mwh": round(_total_charged, 1),
        "total_discharged_mwh": round(_total_discharged, 1),
        "rt_efficiency_realised": round(_rt_eff, 4),
        "arbitrage_value_aud": round(_arb_value, 0),
        "full_equivalent_cycles": round(_full_cycles, 3),
        "hours_near_full_soc": round(_near_full_hours, 2),
        "hours_high_discharge": round(_high_discharge_hours, 2),
        "high_price_threshold_aud_per_mwh": round(_high_price_threshold, 2),
        "discharge_mwh_above_high_price_threshold": round(_discharge_high_price_mwh, 1),
        "share_of_discharge_above_high_price_threshold": round(_high_price_discharge_share, 4),
    }]).to_csv(output_dir / "bess_economics_n5.csv", index=False)
    return


@app.cell
def _(
    build_scenario_kpi_summary,
    condition5,
    market_totals_n5,
    n5,
    output_dir,
    pd,
    status5,
):
    _bess_economics = pd.read_csv(output_dir / "bess_economics_n5.csv").iloc[0]
    build_scenario_kpi_summary(
        status=status5,
        condition=condition5,
        demand_series=n5.loads_t.p["Demand"],
        market_totals=market_totals_n5,
        extra_metrics=[
            ("Total BESS discharge (MWh)", market_totals_n5.set_index("metric").at["Total BESS discharge (MWh)", "value"]),
            ("Total BESS charge (MWh)", market_totals_n5.set_index("metric").at["Total BESS charge (MWh)", "value"]),
            ("BESS full-equivalent cycles", _bess_economics["full_equivalent_cycles"]),
            ("High-price discharge share", _bess_economics["share_of_discharge_above_high_price_threshold"] * 100),
        ],
    )
    return


@app.cell
def _(dispatch_outcomes_n5, market_totals_n5, render_market_outcomes_block):
    render_market_outcomes_block(
        dispatch_outcomes_n5,
        market_totals_n5,
        heading="N5 Dispatch Outcomes",
        notes_md=(
            "Demand share uses **total N5 demand energy** over the full horizon. "
            "Realized sell price is **gross revenue / dispatched MWh**. "
            "For **BESS**, gross margin equals **discharge revenue minus charging cost**. "
            "The exported `bess_economics_n5.csv` now also reports full-equivalent cycles, "
            "time spent near full SOC, and the share of discharge captured in high-price windows."
        ),
    )
    return


@app.cell
def _(build_market_outcomes_dashboard, dispatch_outcomes_n5, export_figure):
    outcomes_fig = build_market_outcomes_dashboard(
        dispatch_outcomes_n5,
        title="N5 Market Outcomes by Asset",
        figsize=(20, 6.8),
    )
    export_figure(outcomes_fig, stem="n5_outcomes_dashboard")
    outcomes_fig
    return


if __name__ == "__main__":
    app.run()
