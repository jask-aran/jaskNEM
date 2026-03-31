import marimo

__generated_with = "0.21.1"
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
    ## Step Up: Multi-Day Run with Maintenance

        This keeps the same single-bus merit-order setup, but extends the
        horizon to three days and applies a daytime maintenance derating to
        black coal on the middle day. The point is to show a richer progression
        without introducing unit commitment or network complexity.
    """)
    return


@app.cell
def _(n2, np, pd, pypsa):
    clean2 = pypsa.Network()
    n2.set_snapshots(pd.date_range("2024-01-01", periods=72, freq="h").as_unit("ns"))
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
    _day_scalars2 = np.repeat([0.97, 0.99, 0.995], repeats=24)
    _rng2 = np.random.default_rng(7)
    _noise2 = _rng2.normal(loc=0.0, scale=0.012, size=72)
    demand_profile2 = (8000 * (np.tile(_base_shape2, 3) * _day_scalars2 + _noise2)).clip(min=6000)
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
    return condition2, dispatch_order2, status2


@app.cell
def _(dispatch_order2, export_figure, n2, plt):
    dispatch_fig2, dispatch_ax2 = plt.subplots(figsize=(12, 4))
    n2.generators_t.p[dispatch_order2].plot.area(ax=dispatch_ax2, linewidth=0)
    dispatch_ax2.set_title("Multi-Day Dispatch with Black Coal Maintenance")
    dispatch_ax2.set_xlabel("Snapshot")
    dispatch_ax2.set_ylabel("Dispatch (MW)")
    dispatch_ax2.legend(title="Generator", ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax2.grid(axis="y", alpha=0.2)
    export_figure(dispatch_fig2)
    dispatch_ax2
    return


@app.cell
def _(export_figure, n2, plt):
    price_fig2, price_ax2 = plt.subplots(figsize=(12, 3))
    n2.buses_t.marginal_price["NEM"].plot(ax=price_ax2, color="#b22222", linewidth=2)
    price_ax2.set_title("Multi-Day Shadow Price with Maintenance")
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
    ## Live-Reload Check

    If this cell does not appear without restarting `marimo run --watch`,
    the file watcher is likely not picking up notebook changes reliably.
    """)
    return


if __name__ == "__main__":
    app.run()
