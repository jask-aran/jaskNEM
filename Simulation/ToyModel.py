import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import pypsa

    return mo, pd, plt, pypsa


@app.cell
def _(mo):
    mo.md(r"""
    # Notebook 2.1 — Toy Model

    Minimal PyPSA toy model for the Stage 2 complexity ladder.
    This notebook currently preserves the original Step 1 setup:
    one bus, four thermal generators, flat demand, and a single solve.
    """)
    return


@app.cell
def _(pd):
    snapshots = pd.date_range("2024-01-01", periods=24, freq="h").as_unit("ns")
    return (snapshots,)


@app.cell
def _(pd, pypsa, snapshots):
    n = pypsa.Network()
    n.set_snapshots(snapshots)
    n.add("Carrier", "AC")
    n.add("Bus", "NEM", carrier="AC")

    n.add("Generator", "Brown Coal", bus="NEM", p_nom=3000, marginal_cost=25)
    n.add("Generator", "Black Coal", bus="NEM", p_nom=5000, marginal_cost=40)
    n.add("Generator", "CCGT Gas", bus="NEM", p_nom=2000, marginal_cost=85)
    n.add("Generator", "OCGT Gas", bus="NEM", p_nom=800, marginal_cost=180)

    n.add("Load", "Demand", bus="NEM", p_set=8000)

    dispatch_order = pd.Index(
        ["Brown Coal", "Black Coal", "CCGT Gas", "OCGT Gas"],
        name="generator",
    )
    return dispatch_order, n


@app.cell
def _(n):
    status, condition = n.optimize(solver_name="highs")
    return condition, status


@app.cell
def _(dispatch_order, n, pd):
    results = pd.concat(
        [
            n.loads_t.p[["Demand"]].rename(columns={"Demand": "demand_mw"}),
            n.buses_t.marginal_price[["NEM"]].rename(
                columns={"NEM": "shadow_price_per_mwh"}
            ),
            n.generators_t.p[dispatch_order].rename(
                columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"
            ),
        ],
        axis=1,
    )
    return (results,)


@app.cell
def _(dispatch_order, n, pd, results):
    generator_summary = (
        n.generators.loc[dispatch_order, ["p_nom", "marginal_cost"]]
        .rename(columns={"p_nom": "capacity_mw", "marginal_cost": "marginal_cost_per_mwh"})
        .assign(
            dispatched_mwh=n.generators_t.p[dispatch_order].sum(),
            average_dispatch_mw=n.generators_t.p[dispatch_order].mean(),
        )
        .reset_index(names="generator")
    )
    generator_summary["capacity_factor"] = (
        generator_summary["average_dispatch_mw"] / generator_summary["capacity_mw"]
    ).round(3)

    system_summary = pd.DataFrame(
        {
            "metric": [
                "Average demand (MW)",
                "Average shadow price ($/MWh)",
                "Peak shadow price ($/MWh)",
                "Total generation (MWh)",
            ],
            "value": [
                results["demand_mw"].mean(),
                results["shadow_price_per_mwh"].mean(),
                results["shadow_price_per_mwh"].max(),
                n.generators_t.p[dispatch_order].sum().sum(),
            ],
        }
    )
    return generator_summary, system_summary


@app.cell
def _(dispatch_order, n, plt):
    dispatch_fig, dispatch_ax = plt.subplots(figsize=(10, 4))
    n.generators_t.p[dispatch_order].plot.area(ax=dispatch_ax, linewidth=0)
    dispatch_ax.set_title("Toy Model Dispatch by Generator")
    dispatch_ax.set_xlabel("Snapshot")
    dispatch_ax.set_ylabel("Dispatch (MW)")
    dispatch_ax.legend(title="Generator", ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    dispatch_ax.grid(axis="y", alpha=0.2)
    dispatch_ax
    return


@app.cell
def _(plt, results):
    price_fig, price_ax = plt.subplots(figsize=(10, 3))
    results["shadow_price_per_mwh"].plot(ax=price_ax, color="#d2691e", linewidth=2)
    price_ax.set_title("Toy Model Shadow Price")
    price_ax.set_xlabel("Snapshot")
    price_ax.set_ylabel("Price ($/MWh)")
    price_ax.grid(axis="y", alpha=0.2)
    price_ax
    return


@app.cell
def _(condition, generator_summary, mo, results, status, system_summary):
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
                The merit-order outcome is the key result here:
                brown coal fills first, black coal sets the marginal unit,
                and gas never enters because demand never rises above 8,000 MW.
                """
            ),
            mo.hstack([system_summary, generator_summary], widths="equal"),
            results,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
