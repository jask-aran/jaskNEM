import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    from pathlib import Path
    import numpy as np
    import marimo as mo
    from pathlib import Path
    import re

    mplconfigdir = Path(__file__).resolve().parent / ".mplconfig"
    mplconfigdir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mplconfigdir))

    import matplotlib.pyplot as plt
    import pandas as pd
    import pypsa

    output_dir = Path(__file__).resolve().parent / "outputs" / "toy_model"
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

    return export_figure, mo, np, output_dir, pd, plt, pypsa


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

    n.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
    n.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
    n.add("Generator", "CCGT Gas", bus="NEM", p_nom=2000, marginal_cost=85)
    n.add("Generator", "OCGT Gas", bus="NEM", p_nom=800, marginal_cost=180)

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
def _(dispatch_order, export_figure, n, plt):
    dispatch_fig, dispatch_ax = plt.subplots(figsize=(10, 4))
    n.generators_t.p[dispatch_order].plot.area(ax=dispatch_ax, linewidth=0)
    dispatch_ax.set_title("Toy Model Dispatch by Generator")
    dispatch_ax.set_xlabel("Snapshot")
    dispatch_ax.set_ylabel("Dispatch (MW)")
    dispatch_ax.legend(title="Generator", ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax.grid(axis="y", alpha=0.2)
    export_figure(dispatch_fig)
    dispatch_ax
    return


@app.cell
def _(export_figure, n, plt):
    price_fig, price_ax = plt.subplots(figsize=(10, 3))
    n.buses_t.marginal_price["NEM"].plot(ax=price_ax, color="#d2691e", linewidth=2)
    price_ax.set_title("Toy Model Shadow Price")
    price_ax.set_xlabel("Snapshot")
    price_ax.set_ylabel("Price ($/MWh)")
    price_ax.grid(axis="y", alpha=0.2)
    export_figure(price_fig)
    price_ax
    return


@app.cell
def _(condition, dispatch_order, mo, n, output_dir, pd, status):
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

    mo.vstack(
        [
            mo.md(
                f"""
                **Solve status:** `{status}`

                **Termination condition:** `{condition}`
                """
            ),
            mo.md(
                """
                The merit-order stack remains the core logic, but demand now
                follows a stylized hourly profile with small random variation.
                This creates realistic intraday shifts in marginal unit and price.
                """
            ),
            mo.hstack([_system_summary, _generator_summary], widths="equal"),
            _results,
        ]
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
    n2.set_snapshots(pd.date_range("2024-01-01", periods=336, freq="30min").as_unit("ns"))
    n2.add("Carrier", "AC")
    n2.add("Bus", "NEM", carrier="AC")

    n2.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
    n2.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
    n2.add("Generator", "CCGT Gas", bus="NEM", p_nom=2000, marginal_cost=85)
    n2.add("Generator", "OCGT Gas", bus="NEM", p_nom=800, marginal_cost=180)

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
def _(dispatch_order2, export_figure, n2, plt):
    dispatch_fig2, dispatch_ax2 = plt.subplots(figsize=(16, 4))
    n2.generators_t.p[dispatch_order2].plot.area(ax=dispatch_ax2, linewidth=0)
    dispatch_ax2.set_title("Weekly Dispatch with Black Coal Maintenance (30-min)")
    dispatch_ax2.set_xlabel("Snapshot")
    dispatch_ax2.set_ylabel("Dispatch (MW)")
    dispatch_ax2.legend(title="Generator", ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax2.grid(axis="y", alpha=0.2)
    export_figure(dispatch_fig2)
    dispatch_ax2
    return


@app.cell
def _(export_figure, n2, plt):
    price_fig2, price_ax2 = plt.subplots(figsize=(16, 3))
    n2.buses_t.marginal_price["NEM"].plot(ax=price_ax2, color="#b22222", linewidth=2)
    price_ax2.set_title("Weekly Shadow Price with Maintenance (30-min)")
    price_ax2.set_xlabel("Snapshot")
    price_ax2.set_ylabel("Price ($/MWh)")
    price_ax2.grid(axis="y", alpha=0.2)
    export_figure(price_fig2)
    price_ax2
    return


@app.cell
def _(condition2, dispatch_order2, mo, n2, output_dir, pd, status2):
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

    mo.vstack(
        [
            mo.md(
                f"""
                **Solve status:** `{status2}`

                **Termination condition:** `{condition2}`
                """
            ),
            mo.md(
                """
                The black coal derating on day 2 pushes more daytime hours into
                the gas stack while preserving a feasible evening peak. This
                shows how maintenance shifts dispatch and prices even when the
                demand shape itself remains familiar.
                """
            ),
            mo.hstack([system_summary2, generator_summary2], widths="equal"),
            results2,
        ]
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
    n3.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"))
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
def _(dispatch_order3, export_figure, n3, plt):
    dispatch_fig3, dispatch_ax3 = plt.subplots(figsize=(16, 4))
    n3.generators_t.p[dispatch_order3].plot.area(ax=dispatch_ax3, linewidth=0)
    dispatch_ax3.set_title("Thu–Sun Dispatch — VIC Solar Penetration, Pre-BESS (10-min)")
    dispatch_ax3.set_xlabel("Snapshot")
    dispatch_ax3.set_ylabel("Dispatch (MW)")
    dispatch_ax3.legend(title="Generator", ncols=5, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax3.grid(axis="y", alpha=0.2)
    export_figure(dispatch_fig3)
    dispatch_ax3
    return


@app.cell
def _(export_figure, n3, plt):
    price_fig3, price_ax3 = plt.subplots(figsize=(16, 3))
    n3.buses_t.marginal_price["NEM"].plot(ax=price_ax3, color="#2e8b57", linewidth=1.5)
    price_ax3.set_title("Thu–Sun Shadow Price — VIC Solar Penetration, Pre-BESS (10-min)")
    price_ax3.set_xlabel("Snapshot")
    price_ax3.set_ylabel("Price ($/MWh)")
    price_ax3.grid(axis="y", alpha=0.2)
    export_figure(price_fig3)
    price_ax3
    return


@app.cell
def _(condition3, dispatch_order3, mo, n3, output_dir, pd, status3):
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

    mo.md(f"**Solve status:** `{status3}` — **Termination condition:** `{condition3}`")
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
            {"unit_name": "OCGT A", "tech": "ocgt", "p_nom_mw": 800, "marginal_cost": 185.0},
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
        n4.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"))
        n4.add("Carrier", "AC")
        n4.add("Bus", "NEM", carrier="AC")
        for _carrier in ["solar", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity"]:
            n4.add("Carrier", _carrier)

        slot_of_day = np.arange(576) % 144
        solar_pu = np.exp(-0.5 * ((slot_of_day - 72) / 15.0) ** 2)
        n4.add("Generator", "Solar", bus="NEM", carrier="solar", p_nom=6000, marginal_cost=0.0)
        n4.generators_t.p_max_pu = pd.DataFrame({"Solar": solar_pu}, index=n4.snapshots)

        demand_shape = np.concatenate(
            [
                _to_10min(weekday_h) * 1.00,
                _to_10min(weekday_h) * 0.97,
                _to_10min(weekend_h) * 0.87,
                _to_10min(weekend_h) * 0.83,
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
def _(condition4, mo, status4):
    mo.md(f"**N4 solve status:** `{status4}` — **Termination:** `{condition4}`")
    return


@app.cell
def _(dispatch_order4, export_figure, n4, plt):
    dispatch_fig4, dispatch_ax4 = plt.subplots(figsize=(16, 4))
    n4.generators_t.p[dispatch_order4].clip(lower=0.0).plot.area(ax=dispatch_ax4, linewidth=0)
    dispatch_ax4.set_title("N4 Unit Dispatch — Multi-Unit Thermal with Ramp Constraints")
    dispatch_ax4.set_xlabel("Snapshot")
    dispatch_ax4.set_ylabel("Dispatch (MW)")
    dispatch_ax4.legend(title="Generator", ncols=3, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax4.grid(axis="y", alpha=0.2)
    export_figure(dispatch_fig4, stem="n4_dispatch")
    dispatch_ax4
    return


@app.cell
def _(export_figure, n4, plt):
    price_fig4, (price_ax4_full, price_ax4_zoom) = plt.subplots(1, 2, figsize=(16, 4))

    n4.buses_t.marginal_price["NEM"].plot(ax=price_ax4_full, color="#b22222", linewidth=1.5)
    price_ax4_full.set_title("N4 Shadow Price — Full")
    price_ax4_full.set_xlabel("Snapshot")
    price_ax4_full.set_ylabel("Price ($/MWh)")
    price_ax4_full.grid(axis="y", alpha=0.2)

    n4.buses_t.marginal_price["NEM"].plot(ax=price_ax4_zoom, color="#b22222", linewidth=1.5)
    price_ax4_zoom.set_title("N4 Shadow Price — Zoom [-250, 250]")
    price_ax4_zoom.set_xlabel("Snapshot")
    price_ax4_zoom.set_ylabel("Price ($/MWh)")
    price_ax4_zoom.set_ylim(-250, 250)
    price_ax4_zoom.grid(axis="y", alpha=0.2)

    price_fig4.tight_layout()
    export_figure(price_fig4, stem="n4_price")
    price_ax4_zoom
    return


@app.cell
def _(mo):
    mo.md("""
    ### N4 Diagnostics

    - **Solar curtailment is expected** in this single-bus setup because thermal ramp-down limits can bind while demand falls; with no export path and no storage sink, some solar must be curtailed.
    - The **+15500 then negative spike** around midnight on **2024-01-06** is an intertemporal ramp shadow-price effect from adjacent-period constraints, not because solar lacks ramp speed.
    - Unit commitment (MILP) was removed: the 8-unit × 576-snapshot MILP did not converge in reasonable time, and dual-based prices from MILP are not economically meaningful anyway.
    """)
    return


@app.cell
def _(dispatch_order4, n4, output_dir, pd, thermal_units_n4):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot
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
def _(mo):
    mo.md("""
    ## N5: Multi-Unit Thermal Stack + Ramp Constraints + BESS

    Direct extension of N4 with the same 4-day, 10-minute horizon, demand, solar,
    and 8-unit thermal fleet. Adds a single aggregate BESS representing the
    VIC grid-scale fleet:

    - **600 MW / 1,200 MWh** (2-hour duration)
    - **84.6 % round-trip efficiency** (92 % store × 92 % dispatch)
    - **50 % initial SOC** (600 MWh at Thursday 00:00)
    - **Tiny storage value adder** to avoid unrealistic last-minute charging in flat zero-price windows
    - LP dispatch: optimizer charges during cheap/negative-price periods and
      discharges during scarcity peaks

    Expected effects vs N4: reduced negative midday price depth, fewer
    $15,500/MWh scarcity events, coal displacement during evening peaks.

    The small `marginal_cost_storage` term is a **modeling choice**, not a literal
    market rule. It acts as a gentle tie-breaker so the battery values being charged
    a little earlier within long flat zero-price periods, instead of waiting until
    the last possible snapshots under perfect foresight.
    """)
    return


@app.cell
def _(np, pd, pypsa, thermal_units_n4):
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
        n5.set_snapshots(pd.date_range("2024-01-04", periods=576, freq="10min").as_unit("ns"))
        n5.add("Carrier", "AC")
        n5.add("Bus", "NEM", carrier="AC")
        for _carrier in ["solar", "brown_coal", "black_coal", "ccgt", "ocgt", "scarcity", "bess"]:
            n5.add("Carrier", _carrier)

        _slot = np.arange(576) % 144
        _solar_pu = np.exp(-0.5 * ((_slot - 72) / 15.0) ** 2)
        n5.add("Generator", "Solar", bus="NEM", carrier="solar", p_nom=6000, marginal_cost=0.0)
        n5.generators_t.p_max_pu = pd.DataFrame({"Solar": _solar_pu}, index=n5.snapshots)

        _demand_shape = np.concatenate([
            _to_10min(_weekday_h) * 1.00,
            _to_10min(_weekday_h) * 0.97,
            _to_10min(_weekend_h) * 0.87,
            _to_10min(_weekend_h) * 0.83,
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
            p_nom=600.0,
            max_hours=2.0,
            efficiency_store=0.92,
            efficiency_dispatch=0.92,
            state_of_charge_initial=600.0,
            cyclic_state_of_charge=False,
            marginal_cost=0.0,
            marginal_cost_storage=-0.05,
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
def _(condition5, mo, status5):
    mo.md(f"**N5 solve status:** `{status5}` — **Termination:** `{condition5}`")
    return


@app.cell
def _(dispatch_order5, export_figure, n5, plt):
    dispatch_fig5, (dispatch_ax5, price_ax5, soc_ax5) = plt.subplots(
        3, 1, figsize=(16, 9), sharex=True
    )

    _x = n5.snapshots.to_pydatetime()
    _dispatch = n5.generators_t.p[dispatch_order5].clip(lower=0.0).copy()
    _dispatch["BESS discharge"] = n5.storage_units_t.p_dispatch["BESS"].clip(lower=0.0)
    _dispatch_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]
    _stack_handles = dispatch_ax5.stackplot(
        _x,
        *[_dispatch[column].to_numpy() for column in _dispatch.columns],
        labels=_dispatch.columns,
        colors=_dispatch_colors[: len(_dispatch.columns)],
        alpha=0.95,
    )
    _charge = n5.storage_units_t.p_store["BESS"].clip(lower=0.0)
    _charge_handle = dispatch_ax5.fill_between(
        _x,
        0.0,
        -_charge.to_numpy(),
        color="#4c78a8",
        alpha=0.30,
        label="BESS charge",
    )
    dispatch_ax5.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    dispatch_ax5.set_title(
        "Unit Dispatch (+ generation / BESS discharge, - BESS charge)", pad=12
    )
    dispatch_ax5.set_ylabel("Dispatch (MW)")
    dispatch_ax5.grid(axis="y", alpha=0.2)

    _price = n5.buses_t.marginal_price["NEM"]
    price_ax5.step(_x, _price.to_numpy(), where="post", color="#b22222", linewidth=1.8)
    price_ax5.set_title("Shadow Price")
    price_ax5.set_ylabel("Price ($/MWh)")
    price_ax5.grid(axis="y", alpha=0.2)

    _soc = n5.storage_units_t.state_of_charge["BESS"]
    soc_ax5.plot(_x, _soc.to_numpy(), color="#1f77b4", linewidth=2.2, label="SOC")
    soc_ax5.fill_between(_x, _soc.to_numpy(), 0.0, color="#1f77b4", alpha=0.08)
    soc_ax5.set_title("BESS State of Charge")
    soc_ax5.set_xlabel("Snapshot")
    soc_ax5.set_ylabel("SOC (MWh)")
    soc_ax5.set_ylim(0, 1200)
    soc_ax5.grid(axis="y", alpha=0.2)
    _zero_mask = (_price <= 0.5).astype(bool)
    _zero_starts = _zero_mask & ~_zero_mask.shift(1, fill_value=False)
    _zero_stops = _zero_mask & ~_zero_mask.shift(-1, fill_value=False)
    _zero_start_times = n5.snapshots[_zero_starts]
    _zero_stop_times = n5.snapshots[_zero_stops]
    for _start, _stop in zip(_zero_start_times, _zero_stop_times, strict=False):
        _start_dt = _start.to_pydatetime()
        _stop_dt = (_stop + n5.snapshots.freq).to_pydatetime()
        dispatch_ax5.axvspan(_start_dt, _stop_dt, color="#d62728", alpha=0.08, lw=0)
        price_ax5.axvspan(_start_dt, _stop_dt, color="#d62728", alpha=0.08, lw=0)
        soc_ax5.axvspan(_start_dt, _stop_dt, color="#d62728", alpha=0.08, lw=0)

    _mdates = plt.matplotlib.dates
    soc_ax5.xaxis.set_major_locator(_mdates.HourLocator(interval=6))
    soc_ax5.xaxis.set_major_formatter(_mdates.DateFormatter("%d\n%H"))
    soc_ax5.tick_params(axis="x", labelrotation=0)
    _legend_handles = list(_stack_handles) + [_charge_handle]
    _legend_labels = list(_dispatch.columns) + ["BESS charge"]
    dispatch_fig5.legend(
        _legend_handles,
        _legend_labels,
        title="Asset",
        ncols=4,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.1),
        frameon=True,
    )
    dispatch_fig5.suptitle("N5 Dispatch, Shadow Price, and BESS State of Charge", y=0.98)
    dispatch_fig5.subplots_adjust(top=0.90, hspace=0.22)
    export_figure(dispatch_fig5, stem="n5_dispatch_soc")
    dispatch_ax5
    return


@app.cell
def _(dispatch_order5, n4, n5, output_dir, pd, thermal_units_n4):
    _dt = 10.0 / 60.0  # hours per 10-min snapshot

    # --- results_n5.csv ---
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

    # --- unit_summary_n5.csv ---
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

    # --- displacement_n5.csv ---
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

    # --- bess_economics_n5.csv ---
    _total_charged = (_charge * _dt).sum()
    _total_discharged = (_discharge * _dt).sum()
    _rt_eff = _total_discharged / _total_charged if _total_charged > 0 else 0.0
    _price = n5.buses_t.marginal_price["NEM"]
    _arb_value = (
        (_discharge * _price * _dt).sum() - (_charge * _price * _dt).sum()
    )
    pd.DataFrame([{
        "total_charged_mwh": round(_total_charged, 1),
        "total_discharged_mwh": round(_total_discharged, 1),
        "rt_efficiency_realised": round(_rt_eff, 4),
        "arbitrage_value_aud": round(_arb_value, 0),
    }]).to_csv(output_dir / "bess_economics_n5.csv", index=False)

    # --- dispatch_outcomes_n5.csv ---
    _total_demand_mwh = (_results["demand_mw"] * _dt).sum()
    _asset_rows = []

    def _safe_div(num, den):
        return num / den if den and abs(den) > 1e-12 else float("nan")

    for _asset in dispatch_order5:
        _dispatch_mw = n5.generators_t.p[_asset].clip(lower=0.0)
        _dispatch_mwh = (_dispatch_mw * _dt).sum()
        _capacity_mw = float(n5.generators.at[_asset, "p_nom"])
        _gross_revenue = (_dispatch_mw * _price * _dt).sum()
        _marginal_cost = float(n5.generators.at[_asset, "marginal_cost"])
        _variable_cost = (_dispatch_mw * _marginal_cost * _dt).sum()
        _gross_margin = _gross_revenue - _variable_cost
        _asset_rows.append(
            {
                "asset": _asset,
                "type": n5.generators.at[_asset, "carrier"],
                "capacity_mw": _capacity_mw,
                "dispatched_mwh": _dispatch_mwh,
                "charge_mwh": float("nan"),
                "share_of_total_demand_pct": _safe_div(_dispatch_mwh, _total_demand_mwh) * 100.0,
                "active_hours": (_dispatch_mw > 0).sum() * _dt,
                "charge_hours": float("nan"),
                "average_dispatch_mw": _dispatch_mw.mean(),
                "average_loading": _safe_div(_dispatch_mw.mean(), _capacity_mw),
                "realized_sell_price_aud_per_mwh": _safe_div(_gross_revenue, _dispatch_mwh),
                "gross_revenue_aud": _gross_revenue,
                "variable_cost_aud": _variable_cost,
                "charging_cost_aud": float("nan"),
                "gross_margin_aud": _gross_margin,
                "margin_aud_per_mwh": _safe_div(_gross_margin, _dispatch_mwh),
            }
        )

    _bess_capacity_mw = float(n5.storage_units.at["BESS", "p_nom"])
    _bess_dispatched_mwh = (_discharge * _dt).sum()
    _bess_charge_mwh = (_charge * _dt).sum()
    _bess_revenue = (_discharge * _price * _dt).sum()
    _bess_charge_cost = (_charge * _price * _dt).sum()
    _bess_margin = _bess_revenue - _bess_charge_cost
    _asset_rows.append(
        {
            "asset": "BESS",
            "type": "bess",
            "capacity_mw": _bess_capacity_mw,
            "dispatched_mwh": _bess_dispatched_mwh,
            "charge_mwh": _bess_charge_mwh,
            "share_of_total_demand_pct": _safe_div(_bess_dispatched_mwh, _total_demand_mwh) * 100.0,
            "active_hours": (_discharge > 0).sum() * _dt,
            "charge_hours": (_charge > 0).sum() * _dt,
            "average_dispatch_mw": _discharge.mean(),
            "average_loading": _safe_div(_discharge.mean(), _bess_capacity_mw),
            "realized_sell_price_aud_per_mwh": _safe_div(_bess_revenue, _bess_dispatched_mwh),
            "gross_revenue_aud": _bess_revenue,
            "variable_cost_aud": 0.0,
            "charging_cost_aud": _bess_charge_cost,
            "gross_margin_aud": _bess_margin,
            "margin_aud_per_mwh": _safe_div(_bess_margin, _bess_dispatched_mwh),
        }
    )

    dispatch_outcomes_n5 = pd.DataFrame(_asset_rows).sort_values(
        "gross_margin_aud", ascending=False
    ).reset_index(drop=True)
    dispatch_outcomes_n5.to_csv(output_dir / "dispatch_outcomes_n5.csv", index=False)

    market_totals_n5 = pd.DataFrame(
        {
            "metric": [
                "Total demand (MWh)",
                "Total generator supply (MWh)",
                "Total BESS discharge (MWh)",
                "Total BESS charge (MWh)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
            ],
            "value": [
                _total_demand_mwh,
                (_results[[f"{name.lower().replace(' ', '_')}_mw" for name in dispatch_order5]] * _dt).sum().sum(),
                _bess_dispatched_mwh,
                _bess_charge_mwh,
                _price.mean(),
                _price.max(),
            ],
        }
    )
    return dispatch_outcomes_n5, market_totals_n5


@app.cell
def _(dispatch_outcomes_n5, market_totals_n5, mo):
    _display = dispatch_outcomes_n5.copy()
    _pct_cols = ["share_of_total_demand_pct", "average_loading"]
    _hour_cols = ["active_hours", "charge_hours"]
    _money_cols = [
        "realized_sell_price_aud_per_mwh",
        "gross_revenue_aud",
        "variable_cost_aud",
        "charging_cost_aud",
        "gross_margin_aud",
        "margin_aud_per_mwh",
    ]
    _energy_cols = ["capacity_mw", "dispatched_mwh", "charge_mwh", "average_dispatch_mw"]
    _display[_pct_cols] = _display[_pct_cols].round(1)
    _display[_hour_cols] = _display[_hour_cols].round(1)
    _display[_money_cols] = _display[_money_cols].round(1)
    _display[_energy_cols] = _display[_energy_cols].round(1)
    _display = _display[
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
    _totals_display = market_totals_n5.copy()
    _totals_display["value"] = _totals_display["value"].round(1)

    mo.vstack(
        [
            mo.md(
                """
                ## N5 Dispatch Outcomes

                Demand share uses **total N5 demand energy** over the full horizon.
                Realized sell price is **gross revenue / dispatched MWh**.
                For **BESS**, gross margin equals **discharge revenue minus charging cost**.
                """
            ),
            mo.hstack([_totals_display, _display], widths=[0.28, 0.72]),
        ]
    )
    return


@app.cell
def _(dispatch_outcomes_n5, export_figure, plt):
    _asset_order = dispatch_outcomes_n5["asset"].tolist()
    _y = list(range(len(_asset_order)))
    _type_colors = {
        "solar": "#f2c94c",
        "brown_coal": "#8c564b",
        "black_coal": "#4e79a7",
        "ccgt": "#e15759",
        "ocgt": "#f28e2b",
        "scarcity": "#b07aa1",
        "bess": "#59a14f",
    }
    _bar_colors = [_type_colors.get(_type, "#7f7f7f") for _type in dispatch_outcomes_n5["type"]]

    def _fmt_money(value):
        _abs = abs(value)
        if _abs >= 1_000_000:
            return f"${value / 1_000_000:.2f}m"
        if _abs >= 1_000:
            return f"${value / 1_000:.1f}k"
        return f"${value:.0f}"

    outcomes_fig, (margin_ax, share_ax, activity_ax) = plt.subplots(
        1, 3, figsize=(18, 6), sharey=True
    )

    _margin = dispatch_outcomes_n5["gross_margin_aud"]
    _margin_colors = ["#2f7d32" if value >= 0 else "#c73e1d" for value in _margin]
    margin_ax.barh(_y, _margin, color=_margin_colors, alpha=0.9)
    margin_ax.set_title("Gross Margin by Asset")
    margin_ax.set_xlabel("Gross Margin (AUD)")
    margin_ax.grid(axis="x", alpha=0.2)
    for _idx, _value in enumerate(_margin):
        _offset = max(abs(_margin).max() * 0.01, 5_000)
        _x_text = _value + _offset if _value >= 0 else _value - _offset
        margin_ax.text(
            _x_text,
            _idx,
            _fmt_money(_value),
            va="center",
            ha="left" if _value >= 0 else "right",
            fontsize=9,
        )

    _share = dispatch_outcomes_n5["share_of_total_demand_pct"]
    share_ax.barh(_y, _share, color=_bar_colors, alpha=0.9)
    share_ax.set_title("Dispatch Share of Demand")
    share_ax.set_xlabel("Share of Total Demand (%)")
    share_ax.grid(axis="x", alpha=0.2)
    for _idx, (_share_pct, _mwh) in enumerate(
        zip(_share, dispatch_outcomes_n5["dispatched_mwh"], strict=False)
    ):
        share_ax.text(
            _share_pct + 0.35,
            _idx,
            f"{_mwh:.0f} MWh",
            va="center",
            ha="left",
            fontsize=9,
        )

    _active = dispatch_outcomes_n5["active_hours"].fillna(0.0)
    _charge_hours = dispatch_outcomes_n5["charge_hours"].fillna(0.0)
    _bar_height = 0.36
    activity_ax.barh(
        [_value - _bar_height / 2 for _value in _y],
        _active,
        height=_bar_height,
        color="#4e79a7",
        label="Active hours",
        alpha=0.9,
    )
    activity_ax.barh(
        [_value + _bar_height / 2 for _value in _y],
        _charge_hours,
        height=_bar_height,
        color="#76b7b2",
        label="Charge hours",
        alpha=0.9,
    )
    activity_ax.set_title("Activity and Price Capture")
    activity_ax.set_xlabel("Hours")
    activity_ax.grid(axis="x", alpha=0.2)
    activity_ax.legend(loc="upper left")

    _price_ax = activity_ax.twiny()
    _price_ax.scatter(
        dispatch_outcomes_n5["realized_sell_price_aud_per_mwh"],
        _y,
        color="#222222",
        marker="o",
        s=36,
        label="Realized sell price",
        zorder=3,
    )
    _price_ax.set_xlabel("Realized Sell Price ($/MWh)")

    activity_ax.set_yticks(_y)
    activity_ax.set_yticklabels(_asset_order)
    activity_ax.invert_yaxis()

    outcomes_fig.suptitle("N5 Market Outcomes by Asset", y=0.98)
    outcomes_fig.subplots_adjust(top=0.86, wspace=0.28)
    export_figure(outcomes_fig, stem="n5_outcomes_dashboard")
    margin_ax
    return


if __name__ == "__main__":
    app.run()
