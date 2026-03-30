import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import pypsa

    return mo, pd, pypsa


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
def _(condition, mo, results, status):
    mo.vstack(
        [
            mo.md(
                f"""
                **Solve status:** `{status}`

                **Termination condition:** `{condition}`
                """
            ),
            results,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
