import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    import sys
    import importlib
    import re
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import pypsa

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import Simulation.pypsa_viz as pypsa_viz

    pypsa_viz = importlib.reload(pypsa_viz)
    build_multiregion_summary_tables = pypsa_viz.build_multiregion_summary_tables
    build_multiscenario_comparison_dashboard = pypsa_viz.build_multiscenario_comparison_dashboard
    build_two_region_figure = pypsa_viz.build_two_region_figure
    build_dispatch_price_figure = pypsa_viz.build_dispatch_price_figure
    build_market_outcomes_dashboard = pypsa_viz.build_market_outcomes_dashboard
    build_market_outcomes_tables = pypsa_viz.build_market_outcomes_tables
    build_scenario_kpi_summary = pypsa_viz.build_scenario_kpi_summary

    mplconfigdir = Path(__file__).resolve().parent / ".mplconfig"
    mplconfigdir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mplconfigdir))

    output_dir = Path(__file__).resolve().parent / "outputs" / "toy_model_2"
    output_dir.mkdir(parents=True, exist_ok=True)
    mo.md(f"Notebook outputs are written to `{output_dir}`.")

    def export_figure(fig, stem=None):
        if stem is None:
            title = fig._suptitle.get_text() if fig._suptitle else ""
            if not title and fig.axes:
                title = fig.axes[0].get_title()
            stem = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "figure"

        output_path = output_dir / f"{stem}.png"
        fig.savefig(output_path, dpi=160, bbox_inches="tight")
        return output_path

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
        build_multiregion_summary_tables,
        build_multiscenario_comparison_dashboard,
        build_scenario_kpi_summary,
        build_two_region_figure,
        export_figure,
        mo,
        np,
        output_dir,
        pd,
        plt,
        pypsa,
        render_market_outcomes_block,
        summarize_snapshot_weightings,
    )


@app.cell
def _(mo):
    mo.md("""
    # Toy Model 2 — N5-Based Extensions

    "
        "This notebook starts from the **N5 system design** from `Simulation/ToyModel.py`
    "
        "and treats it as a reusable base network for follow-on toy-model experiments.

    "
        "The first pass keeps the workflow intentionally simple:

    "
        "- rebuild the N5-style baseline network in this notebook
    "
        "- solve and export a clean baseline case
    "
        "- create one derived scenario by **copying the N5 base template**
    "
        "- modify only a few stress inputs to establish a pattern for future extensions

    "
        "This keeps the simulation track notebook-centric and avoids any major refactor.
    """)
    return


@app.cell
def _(np, pd):
    thermal_units_base = pd.DataFrame(
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

    ramp_defaults = {
        "brown_coal": {"ramp_limit_up": 0.030, "ramp_limit_down": 0.030},
        "black_coal": {"ramp_limit_up": 0.045, "ramp_limit_down": 0.045},
        "ccgt": {"ramp_limit_up": 0.110, "ramp_limit_down": 0.110},
        "ocgt": {"ramp_limit_up": 0.250, "ramp_limit_down": 0.250},
    }

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

    bess_power_mw = 600.0
    bess_energy_mwh = 900.0
    bess_initial_soc_mwh = 450.0
    bess_cyclic_state_of_charge = True
    return (
        bess_cyclic_state_of_charge,
        bess_energy_mwh,
        bess_initial_soc_mwh,
        bess_power_mw,
        ramp_defaults,
        thermal_units_base,
        weekday_h,
        weekend_h,
    )


@app.cell
def _(
    bess_cyclic_state_of_charge,
    bess_energy_mwh,
    bess_initial_soc_mwh,
    bess_power_mw,
    np,
    pd,
    pypsa,
    ramp_defaults,
    thermal_units_base,
    weekday_h,
    weekend_h,
):
    def to_10min(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n5_base_network():
        network = pypsa.Network()
        network.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )
        network.add("Carrier", "AC")
        network.add("Bus", "NEM", carrier="AC")
        for carrier in ["solar", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            network.add("Carrier", carrier)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        solar_pu = np.exp(-0.5 * ((slot - 72) / 15.0) ** 2)
        network.add("Generator", "Solar", bus="NEM", carrier="solar", p_nom=6000, marginal_cost=0.0)
        network.generators_t.p_max_pu = pd.DataFrame({"Solar": solar_pu}, index=network.snapshots)

        demand_shape = np.concatenate(
            [
                to_10min(weekday_h) * 1.00 * peak_adder,
                to_10min(weekday_h) * 0.97 * peak_adder,
                to_10min(weekend_h) * 0.87 * peak_adder,
                to_10min(weekend_h) * 0.83 * peak_adder,
            ]
        )
        rng = np.random.default_rng(7)
        noise = rng.normal(0.0, 0.008, 576)
        demand = (8000 * (demand_shape + noise)).clip(min=0)
        network.add("Load", "Demand", bus="NEM", p_set=pd.Series(demand, index=network.snapshots))

        for row in thermal_units_base.itertuples(index=False):
            ramp = ramp_defaults[row.tech]
            network.add(
                "Generator",
                row.unit_name,
                bus="NEM",
                carrier=row.tech,
                p_nom=row.p_nom_mw,
                marginal_cost=row.marginal_cost,
                ramp_limit_up=ramp["ramp_limit_up"],
                ramp_limit_down=ramp["ramp_limit_down"],
            )

        network.add("Generator", "Scarcity", bus="NEM", carrier="scarcity", p_nom=30000, marginal_cost=15500.0)
        network.add(
            "StorageUnit",
            "BESS",
            bus="NEM",
            carrier="bess",
            p_nom=bess_power_mw,
            max_hours=bess_energy_mwh / bess_power_mw,
            efficiency_store=0.92,
            efficiency_dispatch=0.92,
            state_of_charge_initial=(
                bess_initial_soc_mwh if not bess_cyclic_state_of_charge else 0.0
            ),
            cyclic_state_of_charge=bess_cyclic_state_of_charge,
            marginal_cost=0.0,
            marginal_cost_storage=0.0,
        )

        dispatch_order = pd.Index(
            ["Solar"] + thermal_units_base["unit_name"].tolist() + ["Scarcity"],
            name="generator",
        )
        return network, dispatch_order

    def solve_network(network):
        status, condition = network.optimize(solver_name="highs")
        return status, condition

    return build_n5_base_network, solve_network


@app.cell
def _(build_n5_base_network):
    n5_template, dispatch_order_base = build_n5_base_network()
    return dispatch_order_base, n5_template


@app.cell
def _(n5_template, solve_network):
    n5_base = n5_template.copy()
    status_base, condition_base = solve_network(n5_base)
    return condition_base, n5_base, status_base


@app.cell
def _(mo):
    mo.md("""
    ## Base case: N5 baseline carried into Toy Model 2

    "
        "This is the direct N5-style system copied into a new notebook so future toy-model
    "
        "experiments can branch from a stable starting point.
    """)
    return


@app.cell
def _(
    build_dispatch_price_figure,
    dispatch_order_base,
    export_figure,
    n5_base,
):
    base_fig = build_dispatch_price_figure(
        n5_base,
        dispatch_order=dispatch_order_base,
        panels=("dispatch", "price", "soc"),
        storage_name="BESS",
        price_bus="NEM",
        near_zero_price_threshold=0.5,
        title="Toy Model 2 Base — N5 Dispatch, Price, and BESS SOC",
        dispatch_title="Base dispatch (+ generation / BESS discharge, - BESS charge)",
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
    export_figure(base_fig, stem="tm2_base_dispatch_soc")
    base_fig
    return


@app.cell
def _(
    build_market_outcomes_tables,
    dispatch_order_base,
    n5_base,
    output_dir,
    pd,
    summarize_snapshot_weightings,
    thermal_units_base,
):
    base_results = pd.concat(
        [
            n5_base.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n5_base.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n5_base.generators_t.p[dispatch_order_base].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
            n5_base.storage_units_t.p_store[["BESS"]].rename(columns={"BESS": "bess_charge_mw"}),
            n5_base.storage_units_t.p_dispatch[["BESS"]].rename(columns={"BESS": "bess_discharge_mw"}),
            n5_base.storage_units_t.state_of_charge[["BESS"]].rename(columns={"BESS": "bess_soc_mwh"}),
        ],
        axis=1,
    )
    base_results.to_csv(output_dir / "results_tm2_base.csv")

    dispatch_outcomes_base, market_totals_base = build_market_outcomes_tables(
        n5_base,
        dispatch_order=dispatch_order_base,
        thermal_units=thermal_units_base,
        storage_name="BESS",
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_base.to_csv(output_dir / "dispatch_outcomes_tm2_base.csv", index=False)
    market_totals_base.to_csv(output_dir / "market_totals_tm2_base.csv", index=False)

    snapshot_weightings_base = summarize_snapshot_weightings(n5_base, "TM2_BASE")
    snapshot_weightings_base.to_csv(output_dir / "snapshot_weightings_tm2_base.csv", index=False)
    return dispatch_outcomes_base, market_totals_base


@app.cell
def _(
    build_scenario_kpi_summary,
    condition_base,
    market_totals_base,
    n5_base,
    status_base,
):
    build_scenario_kpi_summary(
        status=status_base,
        condition=condition_base,
        demand_series=n5_base.loads_t.p["Demand"],
        market_totals=market_totals_base,
        extra_metrics=[
            ("Total BESS discharge (MWh)", market_totals_base.set_index("metric").at["Total BESS discharge (MWh)", "value"]),
            ("Total BESS charge (MWh)", market_totals_base.set_index("metric").at["Total BESS charge (MWh)", "value"]),
        ],
    )
    return


@app.cell
def _(
    dispatch_outcomes_base,
    market_totals_base,
    render_market_outcomes_block,
):
    render_market_outcomes_block(
        dispatch_outcomes_base,
        market_totals_base,
        heading="Toy Model 2 Base Outcomes",
        notes_md=(
            "This is the direct N5 baseline carried into the new notebook. "
            "It becomes the reusable launch point for follow-on toy scenarios."
        ),
    )
    return


@app.cell
def _(build_market_outcomes_dashboard, dispatch_outcomes_base, export_figure):
    base_outcomes_fig = build_market_outcomes_dashboard(
        dispatch_outcomes_base,
        title="Toy Model 2 Base — Market Outcomes by Asset",
        figsize=(20, 6.8),
    )
    export_figure(base_outcomes_fig, stem="tm2_base_outcomes_dashboard")
    base_outcomes_fig
    return


@app.cell
def _(mo):
    mo.md("""
    ## Derived case: copy the N5 base network and stress the evening ramp

    "
        "This first extension explicitly uses the N5 base template as the starting point,
    "
        "then changes only a few inputs:

    "
        "- increase demand during the late-afternoon / evening ramp
    "
        "- trim solar availability in the shoulder before sunset

    "
        "The purpose is not realism; it is to establish a clean *network lineage* pattern for
    "
        "Toy Model 2.
    """)
    return


@app.cell
def _(n5_template, pd):
    n5_ramp_stress = n5_template.copy()

    hour_mask = pd.Index(n5_ramp_stress.snapshots).hour
    evening_mask = (hour_mask >= 16) & (hour_mask <= 20)
    shoulder_mask = (hour_mask >= 15) & (hour_mask <= 17)

    stressed_demand = n5_ramp_stress.loads_t.p_set["Demand"].copy()
    stressed_demand.loc[evening_mask] *= 1.08
    n5_ramp_stress.loads_t.p_set["Demand"] = stressed_demand

    solar_cf = n5_ramp_stress.generators_t.p_max_pu["Solar"].copy()
    solar_cf.loc[shoulder_mask] *= 0.88
    n5_ramp_stress.generators_t.p_max_pu["Solar"] = solar_cf.clip(lower=0.0, upper=1.0)
    return (n5_ramp_stress,)


@app.cell
def _(n5_ramp_stress, solve_network):
    status_ramp_stress, condition_ramp_stress = solve_network(n5_ramp_stress)
    return condition_ramp_stress, status_ramp_stress


@app.cell
def _(
    build_dispatch_price_figure,
    dispatch_order_base,
    export_figure,
    n5_ramp_stress,
):
    ramp_stress_fig = build_dispatch_price_figure(
        n5_ramp_stress,
        dispatch_order=dispatch_order_base,
        panels=("dispatch", "price", "soc"),
        storage_name="BESS",
        price_bus="NEM",
        near_zero_price_threshold=0.5,
        title="Toy Model 2 Ramp Stress — Dispatch, Price, and BESS SOC",
        dispatch_title="Ramp-stress dispatch (+ generation / BESS discharge, - BESS charge)",
        price_title="Shadow Price",
        soc_title="BESS State of Charge",
        price_color="#8b0000",
        price_plot_style="step",
        legend_title="Asset",
        legend_ncols=4,
        legend_loc="lower center",
        legend_bbox=(0.5, -0.1),
        figure_legend=True,
        figsize=(18, 10.5),
        date_tick_interval_hours=6,
    )
    export_figure(ramp_stress_fig, stem="tm2_ramp_stress_dispatch_soc")
    ramp_stress_fig
    return


@app.cell
def _(
    build_market_outcomes_tables,
    dispatch_order_base,
    n5_ramp_stress,
    output_dir,
    pd,
    summarize_snapshot_weightings,
    thermal_units_base,
):
    ramp_stress_results = pd.concat(
        [
            n5_ramp_stress.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n5_ramp_stress.buses_t.marginal_price[["NEM"]].rename(columns={"NEM": "shadow_price_per_mwh"}),
            n5_ramp_stress.generators_t.p[dispatch_order_base].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
            n5_ramp_stress.storage_units_t.p_store[["BESS"]].rename(columns={"BESS": "bess_charge_mw"}),
            n5_ramp_stress.storage_units_t.p_dispatch[["BESS"]].rename(columns={"BESS": "bess_discharge_mw"}),
            n5_ramp_stress.storage_units_t.state_of_charge[["BESS"]].rename(columns={"BESS": "bess_soc_mwh"}),
        ],
        axis=1,
    )
    ramp_stress_results.to_csv(output_dir / "results_tm2_ramp_stress.csv")

    dispatch_outcomes_ramp_stress, market_totals_ramp_stress = build_market_outcomes_tables(
        n5_ramp_stress,
        dispatch_order=dispatch_order_base,
        thermal_units=thermal_units_base,
        storage_name="BESS",
        demand_name="Demand",
        price_bus="NEM",
    )
    dispatch_outcomes_ramp_stress.to_csv(output_dir / "dispatch_outcomes_tm2_ramp_stress.csv", index=False)
    market_totals_ramp_stress.to_csv(output_dir / "market_totals_tm2_ramp_stress.csv", index=False)

    snapshot_weightings_ramp_stress = summarize_snapshot_weightings(n5_ramp_stress, "TM2_RAMP_STRESS")
    snapshot_weightings_ramp_stress.to_csv(output_dir / "snapshot_weightings_tm2_ramp_stress.csv", index=False)
    return dispatch_outcomes_ramp_stress, market_totals_ramp_stress


@app.cell
def _(
    build_scenario_kpi_summary,
    condition_ramp_stress,
    market_totals_ramp_stress,
    n5_ramp_stress,
    status_ramp_stress,
):
    build_scenario_kpi_summary(
        status=status_ramp_stress,
        condition=condition_ramp_stress,
        demand_series=n5_ramp_stress.loads_t.p["Demand"],
        market_totals=market_totals_ramp_stress,
        extra_metrics=[
            ("Total BESS discharge (MWh)", market_totals_ramp_stress.set_index("metric").at["Total BESS discharge (MWh)", "value"]),
            ("Total BESS charge (MWh)", market_totals_ramp_stress.set_index("metric").at["Total BESS charge (MWh)", "value"]),
        ],
    )
    return


@app.cell
def _(
    dispatch_outcomes_ramp_stress,
    market_totals_ramp_stress,
    render_market_outcomes_block,
):
    render_market_outcomes_block(
        dispatch_outcomes_ramp_stress,
        market_totals_ramp_stress,
        heading="Toy Model 2 Ramp-Stress Outcomes",
        notes_md=(
            "This scenario is created by copying the N5-style base network and then stressing "
            "the evening ramp. It is a template for future N5-based scenario branches."
        ),
    )
    return


@app.cell
def _(
    build_market_outcomes_dashboard,
    dispatch_outcomes_ramp_stress,
    export_figure,
):
    ramp_stress_outcomes_fig = build_market_outcomes_dashboard(
        dispatch_outcomes_ramp_stress,
        title="Toy Model 2 Ramp Stress — Market Outcomes by Asset",
        figsize=(20, 6.8),
    )
    export_figure(ramp_stress_outcomes_fig, stem="tm2_ramp_stress_outcomes_dashboard")
    ramp_stress_outcomes_fig
    return


@app.cell
def _(market_totals_base, market_totals_ramp_stress, pd):
    base_lookup = market_totals_base.set_index("metric")["value"]
    ramp_lookup = market_totals_ramp_stress.set_index("metric")["value"]
    _comparison = pd.DataFrame(
        {
            "metric": base_lookup.index,
            "base": base_lookup.values,
            "ramp_stress": ramp_lookup.reindex(base_lookup.index).values,
        }
    )
    _comparison["delta"] = _comparison["ramp_stress"] - _comparison["base"]
    _comparison.round(1)
    return


@app.cell
def _(mo):
    mo.md("""
    ## N6: Multi-region toy model (VIC–SA)

    "
        "This extends the N5 design into a two-bus market. The structure stays stylized, but now adds
    "
        "the key missing market feature: **location**. VIC and SA each have their own demand and supply mix,
    "
        "connected by a limited interconnector. That allows the toy model to produce:

    "
        "- regional dispatch differences
    "
        "- interconnector flows
    "
        "- congestion-driven price separation
    "
        "- region-specific storage value

    "
        "The modeling aim is still intuition, not calibration.
    """)
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n6_multiregion():
        n6 = pypsa.Network()
        n6.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )

        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n6.add("Carrier", carrier)

        n6.add("Bus", "VIC", carrier="AC")
        n6.add("Bus", "SA", carrier="AC")
        n6.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=900)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08

        base_shape = np.concatenate(
            [
                _to_10min(weekday_h) * 1.00 * peak_adder,
                _to_10min(weekday_h) * 0.97 * peak_adder,
                _to_10min(weekend_h) * 0.87 * peak_adder,
                _to_10min(weekend_h) * 0.83 * peak_adder,
            ]
        )

        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)

        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)

        n6.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n6.snapshots))
        n6.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n6.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(
            0.42 + 0.18 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576),
            0.05,
            0.90,
        )

        n6.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n6.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=2200, marginal_cost=0.0)
        n6.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=1800, marginal_cost=0.0)
        n6.generators_t.p_max_pu = pd.DataFrame(
            {
                "VIC Solar": vic_solar_pu,
                "SA Solar": sa_solar_pu,
                "SA Wind": sa_wind_pu,
            },
            index=n6.snapshots,
        )

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]

        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue

            ramp = ramp_defaults[row.tech]
            n6.add(
                "Generator",
                unit_name,
                bus=bus,
                carrier=row.tech,
                p_nom=row.p_nom_mw,
                marginal_cost=row.marginal_cost,
                ramp_limit_up=ramp["ramp_limit_up"],
                ramp_limit_down=ramp["ramp_limit_down"],
            )

        n6.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n6.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n6.add(
            "StorageUnit",
            "SA BESS",
            bus="SA",
            carrier="bess",
            p_nom=300,
            max_hours=2.0,
            efficiency_store=0.92,
            efficiency_dispatch=0.92,
            state_of_charge_initial=0.0,
            cyclic_state_of_charge=True,
            marginal_cost=0.0,
            marginal_cost_storage=0.0,
        )

        dispatch_order_n6 = pd.Index(
            [
                "VIC Solar",
                "Brown Coal A",
                "Brown Coal B",
                "Brown Coal C",
                "Black Coal A",
                "Black Coal B",
                "CCGT A",
                "VIC Scarcity",
                "SA Solar",
                "SA Wind",
                "SA CCGT B",
                "SA OCGT A",
                "SA Scarcity",
            ],
            name="generator",
        )
        vic_dispatch_order = pd.Index(
            ["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"],
            name="generator",
        )
        sa_dispatch_order = pd.Index(
            ["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"],
            name="generator",
        )

        status, condition = n6.optimize(solver_name="highs")
        return n6, dispatch_order_n6, vic_dispatch_order, sa_dispatch_order, status, condition

    n6, dispatch_order_n6, vic_dispatch_order_n6, sa_dispatch_order_n6, status_n6, condition_n6 = build_n6_multiregion()
    return (
        condition_n6,
        n6,
        sa_dispatch_order_n6,
        status_n6,
        vic_dispatch_order_n6,
    )


@app.cell
def _(
    build_two_region_figure,
    export_figure,
    n6,
    sa_dispatch_order_n6,
    vic_dispatch_order_n6,
):
    n6_fig = build_two_region_figure(
        n6,
        vic_dispatch_order=vic_dispatch_order_n6,
        sa_dispatch_order=sa_dispatch_order_n6,
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
    )
    export_figure(n6_fig, stem="tm2_n6_multiregion")
    n6_fig
    return


@app.cell
def _(n6, output_dir, pd, summarize_snapshot_weightings):
    results_n6 = pd.concat(
        [
            n6.loads_t.p[["VIC Demand", "SA Demand"]].rename(columns={"VIC Demand": "vic_demand_mw", "SA Demand": "sa_demand_mw"}),
            n6.buses_t.marginal_price[["VIC", "SA"]].rename(columns={"VIC": "vic_price_per_mwh", "SA": "sa_price_per_mwh"}),
            n6.lines_t.p0[["VIC-SA Interconnector"]].rename(columns={"VIC-SA Interconnector": "vic_to_sa_flow_mw"}),
            n6.storage_units_t.p_store[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_charge_mw"}),
            n6.storage_units_t.p_dispatch[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_discharge_mw"}),
            n6.storage_units_t.state_of_charge[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_soc_mwh"}),
            n6.generators_t.p.rename(columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"),
        ],
        axis=1,
    )
    results_n6.to_csv(output_dir / "results_tm2_n6_multiregion.csv")

    _weights = n6.snapshot_weightings.objective.astype(float)
    asset_rows = []
    for asset in n6.generators.index:
        bus = n6.generators.at[asset, "bus"]
        dispatch = n6.generators_t.p[asset].clip(lower=0.0)
        dispatched_mwh = (dispatch * _weights).sum()
        price = n6.buses_t.marginal_price[bus]
        gross_revenue = (dispatch * price * _weights).sum()
        variable_cost = (dispatch * float(n6.generators.at[asset, "marginal_cost"]) * _weights).sum()
        asset_rows.append(
            {
                "asset": asset,
                "bus": bus,
                "type": n6.generators.at[asset, "carrier"],
                "capacity_mw": float(n6.generators.at[asset, "p_nom"]),
                "dispatched_mwh": dispatched_mwh,
                "gross_revenue_aud": gross_revenue,
                "variable_cost_aud": variable_cost,
                "gross_margin_aud": gross_revenue - variable_cost,
            }
        )

    storage_bus = n6.storage_units.at["SA BESS", "bus"]
    storage_price = n6.buses_t.marginal_price[storage_bus]
    storage_charge = n6.storage_units_t.p_store["SA BESS"].clip(lower=0.0)
    storage_discharge = n6.storage_units_t.p_dispatch["SA BESS"].clip(lower=0.0)
    asset_rows.append(
        {
            "asset": "SA BESS",
            "bus": storage_bus,
            "type": "bess",
            "capacity_mw": float(n6.storage_units.at["SA BESS", "p_nom"]),
            "dispatched_mwh": (storage_discharge * _weights).sum(),
            "gross_revenue_aud": (storage_discharge * storage_price * _weights).sum(),
            "variable_cost_aud": (storage_charge * storage_price * _weights).sum(),
            "gross_margin_aud": ((storage_discharge - storage_charge) * storage_price * _weights).sum(),
        }
    )
    asset_summary_n6 = pd.DataFrame(asset_rows).sort_values(["bus", "gross_margin_aud"], ascending=[True, False]).reset_index(drop=True)
    asset_summary_n6.to_csv(output_dir / "asset_summary_tm2_n6_multiregion.csv", index=False)

    regional_summary_n6 = pd.DataFrame(
        [
            {
                "region": "VIC",
                "total_demand_mwh": (n6.loads_t.p["VIC Demand"] * _weights).sum(),
                "average_price_aud_per_mwh": n6.buses_t.marginal_price["VIC"].mean(),
                "peak_price_aud_per_mwh": n6.buses_t.marginal_price["VIC"].max(),
                "local_generation_mwh": (n6.generators_t.p[[g for g in n6.generators.index if n6.generators.at[g, "bus"] == "VIC"]].clip(lower=0.0).multiply(_weights, axis=0)).sum().sum(),
            },
            {
                "region": "SA",
                "total_demand_mwh": (n6.loads_t.p["SA Demand"] * _weights).sum(),
                "average_price_aud_per_mwh": n6.buses_t.marginal_price["SA"].mean(),
                "peak_price_aud_per_mwh": n6.buses_t.marginal_price["SA"].max(),
                "local_generation_mwh": (n6.generators_t.p[[g for g in n6.generators.index if n6.generators.at[g, "bus"] == "SA"]].clip(lower=0.0).multiply(_weights, axis=0)).sum().sum(),
            },
        ]
    )
    regional_summary_n6["net_import_mwh"] = [
        -(n6.lines_t.p0["VIC-SA Interconnector"] * _weights).sum(),
        (n6.lines_t.p0["VIC-SA Interconnector"] * _weights).sum(),
    ]
    regional_summary_n6.to_csv(output_dir / "regional_summary_tm2_n6_multiregion.csv", index=False)

    line_summary_n6 = pd.DataFrame(
        [
            {
                "line": "VIC-SA Interconnector",
                "average_abs_flow_mw": n6.lines_t.p0["VIC-SA Interconnector"].abs().mean(),
                "peak_abs_flow_mw": n6.lines_t.p0["VIC-SA Interconnector"].abs().max(),
                "hours_binding_estimate": (_weights * n6.lines_t.p0["VIC-SA Interconnector"].abs().ge(0.98 * float(n6.lines.at["VIC-SA Interconnector", "s_nom"]))).sum(),
            }
        ]
    )
    line_summary_n6.to_csv(output_dir / "line_summary_tm2_n6_multiregion.csv", index=False)

    snapshot_weightings_n6 = summarize_snapshot_weightings(n6, "TM2_N6_MULTIREGION")
    snapshot_weightings_n6.to_csv(output_dir / "snapshot_weightings_tm2_n6_multiregion.csv", index=False)
    return asset_summary_n6, line_summary_n6, regional_summary_n6


@app.cell
def _(regional_summary_n6):
    regional_summary_n6.round(1)
    return


@app.cell
def _(asset_summary_n6):
    asset_summary_n6.round(1)
    return


@app.cell
def _(line_summary_n6):
    line_summary_n6.round(1)
    return


@app.cell
def _(
    build_scenario_kpi_summary,
    condition_n6,
    n6,
    pd,
    regional_summary_n6,
    status_n6,
):
    market_totals_n6 = pd.DataFrame(
        {
            "metric": [
                "Total demand (MWh)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
            ],
            "value": [
                regional_summary_n6["total_demand_mwh"].sum(),
                n6.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(),
                n6.buses_t.marginal_price[["VIC", "SA"]].max().max(),
            ],
        }
    )
    build_scenario_kpi_summary(
        status=status_n6,
        condition=condition_n6,
        demand_series=n6.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1),
        market_totals=market_totals_n6,
        extra_metrics=[
            ("Average VIC price ($/MWh)", regional_summary_n6.set_index("region").at["VIC", "average_price_aud_per_mwh"]),
            ("Average SA price ($/MWh)", regional_summary_n6.set_index("region").at["SA", "average_price_aud_per_mwh"]),
            ("Peak interconnector flow (MW)", float(n6.lines_t.p0["VIC-SA Interconnector"].abs().max())),
        ],
    )
    return


@app.cell
def _(mo):
    mo.md(
        "## N7: Interconnector stress test\n\n"
        "This scenario keeps the same VIC/SA structure as N6 but tightens the interconnector.\n"
        "That makes congestion more frequent and gives a clean transmission-sensitivity comparison."
    )
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min_n7(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n7_interconnector_stress(line_capacity_mw=550.0):
        n7 = pypsa.Network()
        n7.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )

        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n7.add("Carrier", carrier)

        n7.add("Bus", "VIC", carrier="AC")
        n7.add("Bus", "SA", carrier="AC")
        n7.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=line_capacity_mw)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08

        base_shape = np.concatenate(
            [
                _to_10min_n7(weekday_h) * 1.00 * peak_adder,
                _to_10min_n7(weekday_h) * 0.97 * peak_adder,
                _to_10min_n7(weekend_h) * 0.87 * peak_adder,
                _to_10min_n7(weekend_h) * 0.83 * peak_adder,
            ]
        )

        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)
        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)

        n7.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n7.snapshots))
        n7.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n7.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(
            0.42 + 0.18 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576),
            0.05,
            0.90,
        )

        n7.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n7.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=2200, marginal_cost=0.0)
        n7.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=1800, marginal_cost=0.0)
        n7.generators_t.p_max_pu = pd.DataFrame(
            {
                "VIC Solar": vic_solar_pu,
                "SA Solar": sa_solar_pu,
                "SA Wind": sa_wind_pu,
            },
            index=n7.snapshots,
        )

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]

        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue

            ramp = ramp_defaults[row.tech]
            n7.add(
                "Generator",
                unit_name,
                bus=bus,
                carrier=row.tech,
                p_nom=row.p_nom_mw,
                marginal_cost=row.marginal_cost,
                ramp_limit_up=ramp["ramp_limit_up"],
                ramp_limit_down=ramp["ramp_limit_down"],
            )

        n7.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n7.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n7.add(
            "StorageUnit",
            "SA BESS",
            bus="SA",
            carrier="bess",
            p_nom=300,
            max_hours=2.0,
            efficiency_store=0.92,
            efficiency_dispatch=0.92,
            state_of_charge_initial=0.0,
            cyclic_state_of_charge=True,
            marginal_cost=0.0,
            marginal_cost_storage=0.0,
        )

        vic_dispatch_order_n7 = pd.Index(
            ["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"],
            name="generator",
        )
        sa_dispatch_order_n7 = pd.Index(
            ["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"],
            name="generator",
        )
        status, condition = n7.optimize(solver_name="highs")
        return n7, line_capacity_mw, sa_dispatch_order_n7, status, condition, vic_dispatch_order_n7

    n7, line_capacity_n7, sa_dispatch_order_n7, status_n7, condition_n7, vic_dispatch_order_n7 = build_n7_interconnector_stress()
    return condition_n7, line_capacity_n7, n7, sa_dispatch_order_n7, status_n7, vic_dispatch_order_n7


@app.cell
def _(build_two_region_figure, export_figure, n7, sa_dispatch_order_n7, vic_dispatch_order_n7):
    n7_fig = build_two_region_figure(
        n7,
        vic_dispatch_order=vic_dispatch_order_n7,
        sa_dispatch_order=sa_dispatch_order_n7,
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
    )
    export_figure(n7_fig, stem="tm2_n7_interconnector_stress")
    n7_fig
    return


@app.cell
def _(build_multiregion_summary_tables, line_capacity_n7, n7, output_dir, pd, summarize_snapshot_weightings):
    results_n7 = pd.concat(
        [
            n7.loads_t.p[["VIC Demand", "SA Demand"]].rename(columns={"VIC Demand": "vic_demand_mw", "SA Demand": "sa_demand_mw"}),
            n7.buses_t.marginal_price[["VIC", "SA"]].rename(columns={"VIC": "vic_price_per_mwh", "SA": "sa_price_per_mwh"}),
            n7.lines_t.p0[["VIC-SA Interconnector"]].rename(columns={"VIC-SA Interconnector": "vic_to_sa_flow_mw"}),
            n7.storage_units_t.p_store[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_charge_mw"}),
            n7.storage_units_t.p_dispatch[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_discharge_mw"}),
            n7.storage_units_t.state_of_charge[["SA BESS"]].rename(columns={"SA BESS": "sa_bess_soc_mwh"}),
            n7.generators_t.p.rename(columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"),
        ],
        axis=1,
    )
    results_n7.to_csv(output_dir / "results_tm2_n7_interconnector_stress.csv")

    regional_summary_n7, line_summary_n7, _storage_summary_n7 = build_multiregion_summary_tables(
        n7,
        region_load_map={"VIC": "VIC Demand", "SA": "SA Demand"},
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
        storage_bus="SA",
    )
    regional_summary_n7.to_csv(output_dir / "regional_summary_tm2_n7_interconnector_stress.csv", index=False)
    line_summary_n7.to_csv(output_dir / "line_summary_tm2_n7_interconnector_stress.csv", index=False)

    snapshot_weightings_n7 = summarize_snapshot_weightings(n7, "TM2_N7_INTERCONNECTOR_STRESS")
    snapshot_weightings_n7.to_csv(output_dir / "snapshot_weightings_tm2_n7_interconnector_stress.csv", index=False)
    return line_summary_n7, regional_summary_n7


@app.cell
def _(
    build_scenario_kpi_summary,
    condition_n7,
    line_capacity_n7,
    n7,
    pd,
    regional_summary_n7,
    status_n7,
):
    market_totals_n7 = pd.DataFrame(
        {
            "metric": [
                "Total demand (MWh)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
            ],
            "value": [
                regional_summary_n7["total_demand_mwh"].sum(),
                n7.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(),
                n7.buses_t.marginal_price[["VIC", "SA"]].max().max(),
            ],
        }
    )
    build_scenario_kpi_summary(
        status=status_n7,
        condition=condition_n7,
        demand_series=n7.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1),
        market_totals=market_totals_n7,
        extra_metrics=[
            ("Line capacity (MW)", line_capacity_n7),
            ("Average VIC price ($/MWh)", regional_summary_n7.set_index("region").at["VIC", "average_price_aud_per_mwh"]),
            ("Average SA price ($/MWh)", regional_summary_n7.set_index("region").at["SA", "average_price_aud_per_mwh"]),
            ("Peak interconnector flow (MW)", float(n7.lines_t.p0["VIC-SA Interconnector"].abs().max())),
        ],
    )
    return


@app.cell
def _(line_summary_n6, line_summary_n7, pd, regional_summary_n6, regional_summary_n7):
    n6_vic = regional_summary_n6.set_index("region").loc["VIC"]
    n6_sa = regional_summary_n6.set_index("region").loc["SA"]
    n7_vic = regional_summary_n7.set_index("region").loc["VIC"]
    n7_sa = regional_summary_n7.set_index("region").loc["SA"]

    _comparison = pd.DataFrame(
        [
            {"metric": "VIC average price ($/MWh)", "n6": n6_vic["average_price_aud_per_mwh"], "n7": n7_vic["average_price_aud_per_mwh"]},
            {"metric": "SA average price ($/MWh)", "n6": n6_sa["average_price_aud_per_mwh"], "n7": n7_sa["average_price_aud_per_mwh"]},
            {"metric": "VIC peak price ($/MWh)", "n6": n6_vic["peak_price_aud_per_mwh"], "n7": n7_vic["peak_price_aud_per_mwh"]},
            {"metric": "SA peak price ($/MWh)", "n6": n6_sa["peak_price_aud_per_mwh"], "n7": n7_sa["peak_price_aud_per_mwh"]},
            {"metric": "Average absolute interconnector flow (MW)", "n6": line_summary_n6.iloc[0]["average_abs_flow_mw"], "n7": line_summary_n7.iloc[0]["average_abs_flow_mw"]},
            {"metric": "Peak absolute interconnector flow (MW)", "n6": line_summary_n6.iloc[0]["peak_abs_flow_mw"], "n7": line_summary_n7.iloc[0]["peak_abs_flow_mw"]},
            {"metric": "Estimated binding hours", "n6": line_summary_n6.iloc[0]["hours_binding_estimate"], "n7": line_summary_n7.iloc[0]["hours_binding_estimate"]},
        ]
    )
    _comparison["delta_n7_minus_n6"] = _comparison["n7"] - _comparison["n6"]
    _comparison.round(1)
    return


@app.cell
def _(mo):
    mo.md(
        "## N8: Storage placement study\n\n"
        "This scenario asks where the battery is more valuable under congestion. The network keeps the\n"
        "N7 stressed interconnector, but moves the 300 MW / 2h BESS from SA to VIC."
    )
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min_n8(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n8_storage_placement(line_capacity_mw=550.0):
        n8 = pypsa.Network()
        n8.set_snapshots(
            pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"),
            weightings_from_timedelta=True,
        )

        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n8.add("Carrier", carrier)

        n8.add("Bus", "VIC", carrier="AC")
        n8.add("Bus", "SA", carrier="AC")
        n8.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=line_capacity_mw)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        base_shape = np.concatenate(
            [
                _to_10min_n8(weekday_h) * 1.00 * peak_adder,
                _to_10min_n8(weekday_h) * 0.97 * peak_adder,
                _to_10min_n8(weekend_h) * 0.87 * peak_adder,
                _to_10min_n8(weekend_h) * 0.83 * peak_adder,
            ]
        )

        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)
        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)

        n8.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n8.snapshots))
        n8.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n8.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(
            0.42 + 0.18 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576),
            0.05,
            0.90,
        )
        n8.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n8.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=2200, marginal_cost=0.0)
        n8.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=1800, marginal_cost=0.0)
        n8.generators_t.p_max_pu = pd.DataFrame(
            {"VIC Solar": vic_solar_pu, "SA Solar": sa_solar_pu, "SA Wind": sa_wind_pu},
            index=n8.snapshots,
        )

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]
        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue
            ramp = ramp_defaults[row.tech]
            n8.add(
                "Generator", unit_name, bus=bus, carrier=row.tech, p_nom=row.p_nom_mw,
                marginal_cost=row.marginal_cost, ramp_limit_up=ramp["ramp_limit_up"], ramp_limit_down=ramp["ramp_limit_down"],
            )

        n8.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n8.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n8.add(
            "StorageUnit", "VIC BESS", bus="VIC", carrier="bess", p_nom=300, max_hours=2.0,
            efficiency_store=0.92, efficiency_dispatch=0.92, state_of_charge_initial=0.0,
            cyclic_state_of_charge=True, marginal_cost=0.0, marginal_cost_storage=0.0,
        )

        vic_dispatch_order_n8 = pd.Index(
            ["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"],
            name="generator",
        )
        sa_dispatch_order_n8 = pd.Index(
            ["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"],
            name="generator",
        )
        status, condition = n8.optimize(solver_name="highs")
        return n8, line_capacity_mw, sa_dispatch_order_n8, status, condition, vic_dispatch_order_n8

    n8, line_capacity_n8, sa_dispatch_order_n8, status_n8, condition_n8, vic_dispatch_order_n8 = build_n8_storage_placement()
    return condition_n8, line_capacity_n8, n8, sa_dispatch_order_n8, status_n8, vic_dispatch_order_n8


@app.cell
def _(build_two_region_figure, export_figure, n8, sa_dispatch_order_n8, vic_dispatch_order_n8):
    n8_fig = build_two_region_figure(
        n8,
        vic_dispatch_order=vic_dispatch_order_n8,
        sa_dispatch_order=sa_dispatch_order_n8,
        line_name="VIC-SA Interconnector",
        storage_name="VIC BESS",
    )
    export_figure(n8_fig, stem="tm2_n8_storage_placement")
    n8_fig
    return


@app.cell
def _(build_multiregion_summary_tables, n8, output_dir, pd, summarize_snapshot_weightings):
    results_n8 = pd.concat(
        [
            n8.loads_t.p[["VIC Demand", "SA Demand"]].rename(columns={"VIC Demand": "vic_demand_mw", "SA Demand": "sa_demand_mw"}),
            n8.buses_t.marginal_price[["VIC", "SA"]].rename(columns={"VIC": "vic_price_per_mwh", "SA": "sa_price_per_mwh"}),
            n8.lines_t.p0[["VIC-SA Interconnector"]].rename(columns={"VIC-SA Interconnector": "vic_to_sa_flow_mw"}),
            n8.storage_units_t.p_store[["VIC BESS"]].rename(columns={"VIC BESS": "vic_bess_charge_mw"}),
            n8.storage_units_t.p_dispatch[["VIC BESS"]].rename(columns={"VIC BESS": "vic_bess_discharge_mw"}),
            n8.storage_units_t.state_of_charge[["VIC BESS"]].rename(columns={"VIC BESS": "vic_bess_soc_mwh"}),
        ],
        axis=1,
    )
    results_n8.to_csv(output_dir / "results_tm2_n8_storage_placement.csv")

    regional_summary_n8, line_summary_n8, bess_summary_n8 = build_multiregion_summary_tables(
        n8,
        region_load_map={"VIC": "VIC Demand", "SA": "SA Demand"},
        line_name="VIC-SA Interconnector",
        storage_name="VIC BESS",
        storage_bus="VIC",
    )
    regional_summary_n8.to_csv(output_dir / "regional_summary_tm2_n8_storage_placement.csv", index=False)
    line_summary_n8.to_csv(output_dir / "line_summary_tm2_n8_storage_placement.csv", index=False)
    bess_summary_n8.to_csv(output_dir / "bess_summary_tm2_n8_storage_placement.csv", index=False)

    snapshot_weightings_n8 = summarize_snapshot_weightings(n8, "TM2_N8_STORAGE_PLACEMENT")
    snapshot_weightings_n8.to_csv(output_dir / "snapshot_weightings_tm2_n8_storage_placement.csv", index=False)
    return bess_summary_n8, line_summary_n8, regional_summary_n8


@app.cell
def _(build_scenario_kpi_summary, bess_summary_n8, condition_n8, n8, pd, regional_summary_n8, status_n8):
    market_totals_n8 = pd.DataFrame({
        "metric": ["Total demand (MWh)", "Average shadow price ($/MWh)", "Peak shadow price ($/MWh)"],
        "value": [regional_summary_n8["total_demand_mwh"].sum(), n8.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(), n8.buses_t.marginal_price[["VIC", "SA"]].max().max()],
    })
    build_scenario_kpi_summary(
        status=status_n8,
        condition=condition_n8,
        demand_series=n8.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1),
        market_totals=market_totals_n8,
        extra_metrics=[
            ("Average VIC price ($/MWh)", regional_summary_n8.set_index("region").at["VIC", "average_price_aud_per_mwh"]),
            ("Average SA price ($/MWh)", regional_summary_n8.set_index("region").at["SA", "average_price_aud_per_mwh"]),
            ("VIC BESS discharge (MWh)", bess_summary_n8.iloc[0]["total_discharge_mwh"]),
        ],
    )
    return


@app.cell
def _(mo):
    mo.md(
        "## N9: Renewable expansion stress\n\n"
        "This scenario keeps the stressed N7 line, but expands SA renewables. The aim is to show how\n"
        "a more renewable-heavy SA changes exports, binding, and regional prices under limited transmission."
    )
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min_n9(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n9_renewable_expansion(line_capacity_mw=550.0):
        n9 = pypsa.Network()
        n9.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"), weightings_from_timedelta=True)
        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n9.add("Carrier", carrier)
        n9.add("Bus", "VIC", carrier="AC")
        n9.add("Bus", "SA", carrier="AC")
        n9.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=line_capacity_mw)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        base_shape = np.concatenate([
            _to_10min_n9(weekday_h) * 1.00 * peak_adder,
            _to_10min_n9(weekday_h) * 0.97 * peak_adder,
            _to_10min_n9(weekend_h) * 0.87 * peak_adder,
            _to_10min_n9(weekend_h) * 0.83 * peak_adder,
        ])
        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)
        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)
        n9.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n9.snapshots))
        n9.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n9.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(0.45 + 0.22 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576), 0.08, 0.95)
        n9.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n9.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n9.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=2600, marginal_cost=0.0)
        n9.generators_t.p_max_pu = pd.DataFrame({"VIC Solar": vic_solar_pu, "SA Solar": sa_solar_pu, "SA Wind": sa_wind_pu}, index=n9.snapshots)

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]
        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue
            ramp = ramp_defaults[row.tech]
            n9.add("Generator", unit_name, bus=bus, carrier=row.tech, p_nom=row.p_nom_mw, marginal_cost=row.marginal_cost, ramp_limit_up=ramp["ramp_limit_up"], ramp_limit_down=ramp["ramp_limit_down"])

        n9.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n9.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n9.add("StorageUnit", "SA BESS", bus="SA", carrier="bess", p_nom=300, max_hours=2.0, efficiency_store=0.92, efficiency_dispatch=0.92, state_of_charge_initial=0.0, cyclic_state_of_charge=True, marginal_cost=0.0, marginal_cost_storage=0.0)

        vic_dispatch_order_n9 = pd.Index(["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"], name="generator")
        sa_dispatch_order_n9 = pd.Index(["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"], name="generator")
        status, condition = n9.optimize(solver_name="highs")
        return n9, line_capacity_mw, sa_dispatch_order_n9, status, condition, vic_dispatch_order_n9

    n9, line_capacity_n9, sa_dispatch_order_n9, status_n9, condition_n9, vic_dispatch_order_n9 = build_n9_renewable_expansion()
    return condition_n9, line_capacity_n9, n9, sa_dispatch_order_n9, status_n9, vic_dispatch_order_n9


@app.cell
def _(build_two_region_figure, export_figure, n9, sa_dispatch_order_n9, vic_dispatch_order_n9):
    n9_fig = build_two_region_figure(
        n9,
        vic_dispatch_order=vic_dispatch_order_n9,
        sa_dispatch_order=sa_dispatch_order_n9,
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
    )
    export_figure(n9_fig, stem="tm2_n9_renewable_expansion")
    n9_fig
    return


@app.cell
def _(line_capacity_n9, n9, output_dir, pd, summarize_snapshot_weightings):
    _weights_n9 = n9.snapshot_weightings.objective.astype(float)
    regional_summary_n9 = pd.DataFrame([
        {"region": "VIC", "total_demand_mwh": (n9.loads_t.p["VIC Demand"] * _weights_n9).sum(), "average_price_aud_per_mwh": n9.buses_t.marginal_price["VIC"].mean(), "peak_price_aud_per_mwh": n9.buses_t.marginal_price["VIC"].max()},
        {"region": "SA", "total_demand_mwh": (n9.loads_t.p["SA Demand"] * _weights_n9).sum(), "average_price_aud_per_mwh": n9.buses_t.marginal_price["SA"].mean(), "peak_price_aud_per_mwh": n9.buses_t.marginal_price["SA"].max()},
    ])
    regional_summary_n9["net_import_mwh"] = [-(n9.lines_t.p0["VIC-SA Interconnector"] * _weights_n9).sum(), (n9.lines_t.p0["VIC-SA Interconnector"] * _weights_n9).sum()]
    regional_summary_n9.to_csv(output_dir / "regional_summary_tm2_n9_renewable_expansion.csv", index=False)

    line_summary_n9 = pd.DataFrame([
        {"line": "VIC-SA Interconnector", "line_capacity_mw": line_capacity_n9, "average_abs_flow_mw": n9.lines_t.p0["VIC-SA Interconnector"].abs().mean(), "peak_abs_flow_mw": n9.lines_t.p0["VIC-SA Interconnector"].abs().max(), "hours_binding_estimate": (_weights_n9 * n9.lines_t.p0["VIC-SA Interconnector"].abs().ge(0.98 * line_capacity_n9)).sum()}
    ])
    line_summary_n9.to_csv(output_dir / "line_summary_tm2_n9_renewable_expansion.csv", index=False)

    renewable_summary_n9 = pd.DataFrame([
        {
            "sa_solar_mwh": (n9.generators_t.p["SA Solar"].clip(lower=0.0) * _weights_n9).sum(),
            "sa_wind_mwh": (n9.generators_t.p["SA Wind"].clip(lower=0.0) * _weights_n9).sum(),
            "sa_bess_discharge_mwh": (n9.storage_units_t.p_dispatch["SA BESS"] * _weights_n9).sum(),
        }
    ])
    renewable_summary_n9.to_csv(output_dir / "renewable_summary_tm2_n9_renewable_expansion.csv", index=False)

    results_n9 = pd.concat([
        n9.loads_t.p[["VIC Demand", "SA Demand"]].rename(columns={"VIC Demand": "vic_demand_mw", "SA Demand": "sa_demand_mw"}),
        n9.buses_t.marginal_price[["VIC", "SA"]].rename(columns={"VIC": "vic_price_per_mwh", "SA": "sa_price_per_mwh"}),
        n9.lines_t.p0[["VIC-SA Interconnector"]].rename(columns={"VIC-SA Interconnector": "vic_to_sa_flow_mw"}),
    ], axis=1)
    results_n9.to_csv(output_dir / "results_tm2_n9_renewable_expansion.csv")

    snapshot_weightings_n9 = summarize_snapshot_weightings(n9, "TM2_N9_RENEWABLE_EXPANSION")
    snapshot_weightings_n9.to_csv(output_dir / "snapshot_weightings_tm2_n9_renewable_expansion.csv", index=False)
    return line_summary_n9, regional_summary_n9, renewable_summary_n9


@app.cell
def _(build_scenario_kpi_summary, condition_n9, n9, pd, regional_summary_n9, renewable_summary_n9, status_n9):
    market_totals_n9 = pd.DataFrame({
        "metric": ["Total demand (MWh)", "Average shadow price ($/MWh)", "Peak shadow price ($/MWh)"],
        "value": [regional_summary_n9["total_demand_mwh"].sum(), n9.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(), n9.buses_t.marginal_price[["VIC", "SA"]].max().max()],
    })
    build_scenario_kpi_summary(
        status=status_n9,
        condition=condition_n9,
        demand_series=n9.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1),
        market_totals=market_totals_n9,
        extra_metrics=[
            ("Average VIC price ($/MWh)", regional_summary_n9.set_index("region").at["VIC", "average_price_aud_per_mwh"]),
            ("Average SA price ($/MWh)", regional_summary_n9.set_index("region").at["SA", "average_price_aud_per_mwh"]),
            ("SA solar dispatched (MWh)", renewable_summary_n9.iloc[0]["sa_solar_mwh"]),
            ("SA wind dispatched (MWh)", renewable_summary_n9.iloc[0]["sa_wind_mwh"]),
        ],
    )
    return


@app.cell
def _(mo):
    mo.md(
        "## N10: VIC thermal outage stress\n\n"
        "This scenario keeps the N7 stressed transmission setting and removes one major VIC coal unit.\n"
        "The aim is to show how an outage shifts regional prices, flows, and local scarcity."
    )
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min_n10(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n10_outage(line_capacity_mw=550.0):
        n10 = pypsa.Network()
        n10.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"), weightings_from_timedelta=True)
        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n10.add("Carrier", carrier)
        n10.add("Bus", "VIC", carrier="AC")
        n10.add("Bus", "SA", carrier="AC")
        n10.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=line_capacity_mw)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        base_shape = np.concatenate([
            _to_10min_n10(weekday_h) * 1.00 * peak_adder,
            _to_10min_n10(weekday_h) * 0.97 * peak_adder,
            _to_10min_n10(weekend_h) * 0.87 * peak_adder,
            _to_10min_n10(weekend_h) * 0.83 * peak_adder,
        ])
        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)
        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)
        n10.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n10.snapshots))
        n10.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n10.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(0.42 + 0.18 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576), 0.05, 0.90)
        n10.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n10.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=2200, marginal_cost=0.0)
        n10.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=1800, marginal_cost=0.0)
        n10.generators_t.p_max_pu = pd.DataFrame({"VIC Solar": vic_solar_pu, "SA Solar": sa_solar_pu, "SA Wind": sa_wind_pu}, index=n10.snapshots)

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]
        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue
            ramp = ramp_defaults[row.tech]
            p_nom = 0.0 if row.unit_name == "Brown Coal A" else row.p_nom_mw
            n10.add("Generator", unit_name, bus=bus, carrier=row.tech, p_nom=p_nom, marginal_cost=row.marginal_cost, ramp_limit_up=ramp["ramp_limit_up"], ramp_limit_down=ramp["ramp_limit_down"])

        n10.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n10.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n10.add("StorageUnit", "SA BESS", bus="SA", carrier="bess", p_nom=300, max_hours=2.0, efficiency_store=0.92, efficiency_dispatch=0.92, state_of_charge_initial=0.0, cyclic_state_of_charge=True, marginal_cost=0.0, marginal_cost_storage=0.0)

        vic_dispatch_order_n10 = pd.Index(["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"], name="generator")
        sa_dispatch_order_n10 = pd.Index(["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"], name="generator")
        status, condition = n10.optimize(solver_name="highs")
        return n10, sa_dispatch_order_n10, status, condition, vic_dispatch_order_n10

    n10, sa_dispatch_order_n10, status_n10, condition_n10, vic_dispatch_order_n10 = build_n10_outage()
    return condition_n10, n10, sa_dispatch_order_n10, status_n10, vic_dispatch_order_n10


@app.cell
def _(build_two_region_figure, export_figure, n10, sa_dispatch_order_n10, vic_dispatch_order_n10):
    n10_fig = build_two_region_figure(n10, vic_dispatch_order=vic_dispatch_order_n10, sa_dispatch_order=sa_dispatch_order_n10, line_name="VIC-SA Interconnector", storage_name="SA BESS")
    export_figure(n10_fig, stem="tm2_n10_vic_outage")
    n10_fig
    return


@app.cell
def _(build_multiregion_summary_tables, n10, output_dir, pd, summarize_snapshot_weightings):
    regional_summary_n10, line_summary_n10, _storage_summary_n10 = build_multiregion_summary_tables(
        n10,
        region_load_map={"VIC": "VIC Demand", "SA": "SA Demand"},
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
        storage_bus="SA",
    )
    regional_summary_n10.to_csv(output_dir / "regional_summary_tm2_n10_vic_outage.csv", index=False)
    line_summary_n10.to_csv(output_dir / "line_summary_tm2_n10_vic_outage.csv", index=False)
    snapshot_weightings_n10 = summarize_snapshot_weightings(n10, "TM2_N10_VIC_OUTAGE")
    snapshot_weightings_n10.to_csv(output_dir / "snapshot_weightings_tm2_n10_vic_outage.csv", index=False)
    return line_summary_n10, regional_summary_n10


@app.cell
def _(build_scenario_kpi_summary, condition_n10, n10, pd, regional_summary_n10, status_n10):
    market_totals_n10 = pd.DataFrame({"metric": ["Total demand (MWh)", "Average shadow price ($/MWh)", "Peak shadow price ($/MWh)"], "value": [regional_summary_n10["total_demand_mwh"].sum(), n10.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(), n10.buses_t.marginal_price[["VIC", "SA"]].max().max()]})
    build_scenario_kpi_summary(status=status_n10, condition=condition_n10, demand_series=n10.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1), market_totals=market_totals_n10, extra_metrics=[("Average VIC price ($/MWh)", regional_summary_n10.set_index("region").at["VIC", "average_price_aud_per_mwh"]), ("Average SA price ($/MWh)", regional_summary_n10.set_index("region").at["SA", "average_price_aud_per_mwh"]), ("Peak VIC price ($/MWh)", regional_summary_n10.set_index("region").at["VIC", "peak_price_aud_per_mwh"])])
    return


@app.cell
def _(mo):
    mo.md(
        "## N11: Storage duration study\n\n"
        "This scenario keeps the N7 stressed transmission setting and the SA battery location, but extends\n"
        "the battery from 2 hours to 4 hours. The point is to compare power-limited vs duration-rich storage."
    )
    return


@app.cell
def _(np, pd, pypsa, ramp_defaults, thermal_units_base, weekday_h, weekend_h):
    def _to_10min_n11(half_hourly):
        x = np.linspace(0, 48, 144, endpoint=False)
        return np.interp(x, np.arange(49), np.append(half_hourly, half_hourly[0]))

    def build_n11_duration(line_capacity_mw=550.0):
        n11 = pypsa.Network()
        n11.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"), weightings_from_timedelta=True)
        for carrier in ["AC", "solar", "wind", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n11.add("Carrier", carrier)
        n11.add("Bus", "VIC", carrier="AC")
        n11.add("Bus", "SA", carrier="AC")
        n11.add("Line", "VIC-SA Interconnector", bus0="VIC", bus1="SA", r=0.01, x=0.15, s_nom=line_capacity_mw)

        slot = np.arange(576) % 144
        peak_adder = np.ones(144)
        peak_adder[96:126] = 1.05
        peak_adder[102:120] = 1.08
        base_shape = np.concatenate([
            _to_10min_n11(weekday_h) * 1.00 * peak_adder,
            _to_10min_n11(weekday_h) * 0.97 * peak_adder,
            _to_10min_n11(weekend_h) * 0.87 * peak_adder,
            _to_10min_n11(weekend_h) * 0.83 * peak_adder,
        ])
        rng = np.random.default_rng(17)
        vic_noise = rng.normal(0.0, 0.007, 576)
        sa_noise = rng.normal(0.0, 0.010, 576)
        vic_demand = (6000 * (base_shape + vic_noise)).clip(min=0)
        sa_shape = np.roll(base_shape, 6) * 0.96
        sa_shape += 0.03 * np.sin(2 * np.pi * np.arange(576) / 144)
        sa_demand = (1900 * (sa_shape + sa_noise)).clip(min=0)
        n11.add("Load", "VIC Demand", bus="VIC", p_set=pd.Series(vic_demand, index=n11.snapshots))
        n11.add("Load", "SA Demand", bus="SA", p_set=pd.Series(sa_demand, index=n11.snapshots))

        vic_solar_pu = np.exp(-0.5 * ((slot - 72) / 15.5) ** 2)
        sa_solar_pu = np.exp(-0.5 * ((slot - 74) / 14.0) ** 2)
        sa_wind_pu = np.clip(0.42 + 0.18 * np.sin(2 * np.pi * np.arange(576) / 144 + 0.8) + rng.normal(0.0, 0.06, 576), 0.05, 0.90)
        n11.add("Generator", "VIC Solar", bus="VIC", carrier="solar", p_nom=3200, marginal_cost=0.0)
        n11.add("Generator", "SA Solar", bus="SA", carrier="solar", p_nom=2200, marginal_cost=0.0)
        n11.add("Generator", "SA Wind", bus="SA", carrier="wind", p_nom=1800, marginal_cost=0.0)
        n11.generators_t.p_max_pu = pd.DataFrame({"VIC Solar": vic_solar_pu, "SA Solar": sa_solar_pu, "SA Wind": sa_wind_pu}, index=n11.snapshots)

        vic_units = ["Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A"]
        sa_units = ["CCGT B", "OCGT A"]
        for row in thermal_units_base.itertuples(index=False):
            if row.unit_name in vic_units:
                bus = "VIC"
                unit_name = row.unit_name
            elif row.unit_name in sa_units:
                bus = "SA"
                unit_name = f"SA {row.unit_name}"
            else:
                continue
            ramp = ramp_defaults[row.tech]
            n11.add("Generator", unit_name, bus=bus, carrier=row.tech, p_nom=row.p_nom_mw, marginal_cost=row.marginal_cost, ramp_limit_up=ramp["ramp_limit_up"], ramp_limit_down=ramp["ramp_limit_down"])

        n11.add("Generator", "VIC Scarcity", bus="VIC", carrier="scarcity", p_nom=15000, marginal_cost=15500.0)
        n11.add("Generator", "SA Scarcity", bus="SA", carrier="scarcity", p_nom=8000, marginal_cost=15500.0)
        n11.add("StorageUnit", "SA BESS", bus="SA", carrier="bess", p_nom=300, max_hours=4.0, efficiency_store=0.92, efficiency_dispatch=0.92, state_of_charge_initial=0.0, cyclic_state_of_charge=True, marginal_cost=0.0, marginal_cost_storage=0.0)

        vic_dispatch_order_n11 = pd.Index(["VIC Solar", "Brown Coal A", "Brown Coal B", "Brown Coal C", "Black Coal A", "Black Coal B", "CCGT A", "VIC Scarcity"], name="generator")
        sa_dispatch_order_n11 = pd.Index(["SA Solar", "SA Wind", "SA CCGT B", "SA OCGT A", "SA Scarcity"], name="generator")
        status, condition = n11.optimize(solver_name="highs")
        return n11, sa_dispatch_order_n11, status, condition, vic_dispatch_order_n11

    n11, sa_dispatch_order_n11, status_n11, condition_n11, vic_dispatch_order_n11 = build_n11_duration()
    return condition_n11, n11, sa_dispatch_order_n11, status_n11, vic_dispatch_order_n11


@app.cell
def _(build_two_region_figure, export_figure, n11, sa_dispatch_order_n11, vic_dispatch_order_n11):
    n11_fig = build_two_region_figure(n11, vic_dispatch_order=vic_dispatch_order_n11, sa_dispatch_order=sa_dispatch_order_n11, line_name="VIC-SA Interconnector", storage_name="SA BESS")
    export_figure(n11_fig, stem="tm2_n11_duration_study")
    n11_fig
    return


@app.cell
def _(build_multiregion_summary_tables, n11, output_dir, pd, summarize_snapshot_weightings):
    regional_summary_n11, _line_summary_n11, bess_summary_n11 = build_multiregion_summary_tables(
        n11,
        region_load_map={"VIC": "VIC Demand", "SA": "SA Demand"},
        line_name="VIC-SA Interconnector",
        storage_name="SA BESS",
        storage_bus="SA",
    )
    regional_summary_n11.to_csv(output_dir / "regional_summary_tm2_n11_duration_study.csv", index=False)
    bess_summary_n11.to_csv(output_dir / "bess_summary_tm2_n11_duration_study.csv", index=False)
    snapshot_weightings_n11 = summarize_snapshot_weightings(n11, "TM2_N11_DURATION_STUDY")
    snapshot_weightings_n11.to_csv(output_dir / "snapshot_weightings_tm2_n11_duration_study.csv", index=False)
    return bess_summary_n11, regional_summary_n11


@app.cell
def _(build_scenario_kpi_summary, bess_summary_n11, condition_n11, n11, pd, regional_summary_n11, status_n11):
    market_totals_n11 = pd.DataFrame({"metric": ["Total demand (MWh)", "Average shadow price ($/MWh)", "Peak shadow price ($/MWh)"], "value": [regional_summary_n11["total_demand_mwh"].sum(), n11.buses_t.marginal_price[["VIC", "SA"]].mean(axis=1).mean(), n11.buses_t.marginal_price[["VIC", "SA"]].max().max()]})
    build_scenario_kpi_summary(status=status_n11, condition=condition_n11, demand_series=n11.loads_t.p[["VIC Demand", "SA Demand"]].sum(axis=1), market_totals=market_totals_n11, extra_metrics=[("Average VIC price ($/MWh)", regional_summary_n11.set_index("region").at["VIC", "average_price_aud_per_mwh"]), ("Average SA price ($/MWh)", regional_summary_n11.set_index("region").at["SA", "average_price_aud_per_mwh"]), ("SA BESS discharge (MWh)", bess_summary_n11.iloc[0]["total_discharge_mwh"]), ("SA BESS average sell price ($/MWh)", bess_summary_n11.iloc[0]["average_sell_price_aud_per_mwh"])])
    return


@app.cell
def _(
    bess_summary_n11,
    bess_summary_n8,
    build_multiscenario_comparison_dashboard,
    export_figure,
    line_summary_n10,
    line_summary_n6,
    line_summary_n7,
    line_summary_n8,
    line_summary_n9,
    n10,
    n11,
    n6,
    n7,
    n8,
    n9,
    output_dir,
    pd,
    regional_summary_n10,
    regional_summary_n11,
    regional_summary_n6,
    regional_summary_n7,
    regional_summary_n8,
    regional_summary_n9,
    renewable_summary_n9,
):
    def _row(name, regional_df, *, line_df=None, network=None, storage_discharge_mwh=None):
        regional = regional_df.set_index("region")
        binding_hours = float("nan")
        if line_df is not None:
            binding_hours = float(line_df.iloc[0]["hours_binding_estimate"])
        elif network is not None:
            _weights = network.snapshot_weightings.objective.astype(float)
            line = network.lines_t.p0["VIC-SA Interconnector"].abs()
            cap = float(network.lines.at["VIC-SA Interconnector", "s_nom"])
            binding_hours = float((_weights * line.ge(0.98 * cap)).sum())

        return {
            "scenario": name,
            "avg_price_vic": regional.at["VIC", "average_price_aud_per_mwh"],
            "avg_price_sa": regional.at["SA", "average_price_aud_per_mwh"],
            "peak_price_system": max(
                regional.at["VIC", "peak_price_aud_per_mwh"],
                regional.at["SA", "peak_price_aud_per_mwh"],
            ),
            "binding_hours": binding_hours,
            "storage_discharge_mwh": storage_discharge_mwh if storage_discharge_mwh is not None else 0.0,
        }

    scenario_comparison = pd.DataFrame(
        [
            _row("N6", regional_summary_n6, line_df=line_summary_n6, network=n6, storage_discharge_mwh=(n6.storage_units_t.p_dispatch["SA BESS"] * n6.snapshot_weightings.objective.astype(float)).sum()),
            _row("N7", regional_summary_n7, line_df=line_summary_n7, network=n7, storage_discharge_mwh=(n7.storage_units_t.p_dispatch["SA BESS"] * n7.snapshot_weightings.objective.astype(float)).sum()),
            _row("N8", regional_summary_n8, line_df=line_summary_n8, network=n8, storage_discharge_mwh=bess_summary_n8.iloc[0]["total_discharge_mwh"]),
            _row("N9", regional_summary_n9, line_df=line_summary_n9, network=n9, storage_discharge_mwh=renewable_summary_n9.iloc[0]["sa_bess_discharge_mwh"]),
            _row("N10", regional_summary_n10, line_df=line_summary_n10, storage_discharge_mwh=(n10.storage_units_t.p_dispatch["SA BESS"] * n10.snapshot_weightings.objective.astype(float)).sum()),
            _row("N11", regional_summary_n11, network=n11, storage_discharge_mwh=bess_summary_n11.iloc[0]["total_discharge_mwh"]),
        ]
    )
    scenario_comparison.to_csv(output_dir / "scenario_comparison_tm2_multiregion.csv", index=False)

    comparison_fig = build_multiscenario_comparison_dashboard(
        scenario_comparison,
        title="Toy Model 2 Multi-region Scenario Comparison",
        figsize=(18, 10),
    )
    export_figure(comparison_fig, stem="tm2_multiregion_comparison_dashboard")
    comparison_fig
    return (scenario_comparison,)


if __name__ == "__main__":
    app.run()
