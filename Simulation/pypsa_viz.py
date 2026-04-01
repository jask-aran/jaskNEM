from __future__ import annotations

from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_DISPATCH_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

OUTCOME_TYPE_COLORS = {
    "solar": "#f2c94c",
    "brown_coal": "#8c564b",
    "black_coal": "#4e79a7",
    "ccgt": "#e15759",
    "ocgt": "#f28e2b",
    "scarcity": "#b07aa1",
    "bess": "#59a14f",
}


def _snapshot_hours(network) -> pd.Series:
    weights = network.snapshot_weightings.objective
    if not isinstance(weights, pd.Series):
        weights = pd.Series(weights, index=network.snapshots, dtype=float)
    else:
        weights = weights.astype(float)

    if len(network.snapshots) <= 1:
        base_hours = 1.0
    else:
        deltas = network.snapshots.to_series().diff().dropna()
        base_hours = deltas.dt.total_seconds().median() / 3600.0

    return weights * base_hours


def _shade_price_windows(axes, price_series: pd.Series, threshold: float) -> None:
    mask = (price_series <= threshold).astype(bool)
    starts = mask & ~mask.shift(1, fill_value=False)
    stops = mask & ~mask.shift(-1, fill_value=False)
    freq = price_series.index.freq
    if freq is None and len(price_series.index) > 1:
        freq = price_series.index[1] - price_series.index[0]
    if freq is None:
        return

    for start, stop in zip(price_series.index[starts], price_series.index[stops], strict=False):
        start_dt = start.to_pydatetime()
        stop_dt = (stop + freq).to_pydatetime()
        for axis in axes:
            axis.axvspan(start_dt, stop_dt, color="#d62728", alpha=0.08, lw=0)


def build_dispatch_price_figure(
    network,
    *,
    dispatch_order=None,
    panels: tuple[str, ...] = ("dispatch", "price"),
    storage_name: str | None = None,
    price_bus: str = "NEM",
    near_zero_price_threshold: float | None = None,
    title: str | None = None,
    dispatch_title: str | None = None,
    price_title: str | None = None,
    soc_title: str | None = None,
    dispatch_colors: Iterable[str] | None = None,
    price_color: str = "#b22222",
    price_plot_style: str = "line",
    price_ylim: tuple[float, float] | None = None,
    legend_title: str = "Asset",
    legend_ncols: int = 4,
    legend_loc: str = "upper center",
    legend_bbox: tuple[float, float] | None = None,
    figure_legend: bool = False,
    figsize: tuple[float, float] | None = None,
    date_tick_interval_hours: int | None = None,
    date_format: str = "%d\n%H",
):
    panel_list = list(panels)
    axes_count = len(panel_list)
    if axes_count == 0:
        raise ValueError("panels must include at least one of dispatch, price, soc")

    if "soc" in panel_list:
        if storage_name is None or storage_name not in network.storage_units.index:
            raise ValueError("storage_name must reference an existing StorageUnit when soc panel is requested")

    if "price" in panel_list and price_bus not in network.buses_t.marginal_price.columns:
        raise ValueError(f"price_bus={price_bus!r} not found in network.buses_t.marginal_price")

    if "dispatch" in panel_list and dispatch_order is None:
        raise ValueError("dispatch_order is required when a dispatch panel is requested")

    fig, axes = plt.subplots(
        axes_count,
        1,
        figsize=figsize or (16, 3 + 2.6 * axes_count),
        sharex=True,
    )
    axes = np.atleast_1d(axes)
    axis_by_panel = dict(zip(panel_list, axes, strict=False))
    x = network.snapshots.to_pydatetime()
    price_series = network.buses_t.marginal_price[price_bus] if "price" in panel_list else None

    if "dispatch" in axis_by_panel:
        dispatch_ax = axis_by_panel["dispatch"]
        dispatch = network.generators_t.p[dispatch_order].clip(lower=0.0).copy()
        legend_handles = None
        legend_labels = None

        if storage_name is not None and storage_name in network.storage_units.index:
            dispatch["BESS discharge"] = network.storage_units_t.p_dispatch[storage_name].clip(lower=0.0)

        stack_handles = dispatch_ax.stackplot(
            x,
            *[dispatch[column].to_numpy() for column in dispatch.columns],
            labels=dispatch.columns,
            colors=list(dispatch_colors or DEFAULT_DISPATCH_COLORS)[: len(dispatch.columns)],
            alpha=0.95,
        )
        legend_handles = list(stack_handles)
        legend_labels = list(dispatch.columns)

        if storage_name is not None and storage_name in network.storage_units.index:
            charge = network.storage_units_t.p_store[storage_name].clip(lower=0.0)
            charge_handle = dispatch_ax.fill_between(
                x,
                0.0,
                -charge.to_numpy(),
                color="#4c78a8",
                alpha=0.30,
                label="BESS charge",
            )
            legend_handles.append(charge_handle)
            legend_labels.append("BESS charge")

        dispatch_ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
        dispatch_ax.set_title(dispatch_title or "Dispatch")
        dispatch_ax.set_ylabel("Dispatch (MW)")
        dispatch_ax.grid(axis="y", alpha=0.2)

        if figure_legend:
            fig.legend(
                legend_handles,
                legend_labels,
                title=legend_title,
                ncols=legend_ncols,
                loc=legend_loc,
                bbox_to_anchor=legend_bbox,
                frameon=True,
            )
        else:
            dispatch_ax.legend(
                title=legend_title,
                ncols=legend_ncols,
                loc=legend_loc,
                bbox_to_anchor=legend_bbox,
            )

    if "price" in axis_by_panel:
        price_ax = axis_by_panel["price"]
        if price_plot_style == "step":
            price_ax.step(x, price_series.to_numpy(), where="post", color=price_color, linewidth=1.8)
        else:
            price_ax.plot(x, price_series.to_numpy(), color=price_color, linewidth=1.5)
        price_ax.set_title(price_title or "Shadow Price")
        price_ax.set_ylabel("Price ($/MWh)")
        if price_ylim is not None:
            price_ax.set_ylim(*price_ylim)
        price_ax.grid(axis="y", alpha=0.2)

    if "soc" in axis_by_panel:
        soc_ax = axis_by_panel["soc"]
        soc = network.storage_units_t.state_of_charge[storage_name]
        soc_ax.plot(x, soc.to_numpy(), color="#1f77b4", linewidth=2.2)
        soc_ax.fill_between(x, soc.to_numpy(), 0.0, color="#1f77b4", alpha=0.08)
        soc_ax.set_title(soc_title or "State of Charge")
        soc_ax.set_ylabel("SOC (MWh)")
        soc_ax.set_xlabel("Snapshot")
        soc_ax.set_ylim(0, max(float(network.storage_units.at[storage_name, "p_nom"]) * float(network.storage_units.at[storage_name, "max_hours"]), 1.0))
        soc_ax.grid(axis="y", alpha=0.2)

    if near_zero_price_threshold is not None and price_series is not None:
        _shade_price_windows(axes, price_series, near_zero_price_threshold)

    bottom_ax = axes[-1]
    bottom_ax.set_xlabel("Snapshot")
    if date_tick_interval_hours is not None:
        bottom_ax.xaxis.set_major_locator(mdates.HourLocator(interval=date_tick_interval_hours))
    bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    bottom_ax.tick_params(axis="x", labelrotation=0)

    if title is not None:
        fig.suptitle(title, y=0.98)
        fig.subplots_adjust(top=0.90, hspace=0.22)
    else:
        fig.tight_layout()

    return fig


def build_market_outcomes_tables(
    network,
    *,
    dispatch_order,
    thermal_units=None,
    storage_name: str | None = None,
    demand_name: str = "Demand",
    price_bus: str = "NEM",
):
    weights = _snapshot_hours(network)
    price = network.buses_t.marginal_price[price_bus]
    demand = network.loads_t.p[demand_name]
    total_demand_mwh = (demand * weights).sum()

    def safe_div(num, den):
        return num / den if den and abs(den) > 1e-12 else float("nan")

    asset_rows = []
    for asset in dispatch_order:
        dispatch_mw = network.generators_t.p[asset].clip(lower=0.0)
        dispatched_mwh = (dispatch_mw * weights).sum()
        capacity_mw = float(network.generators.at[asset, "p_nom"])
        gross_revenue = (dispatch_mw * price * weights).sum()
        marginal_cost = float(network.generators.at[asset, "marginal_cost"])
        variable_cost = (dispatch_mw * marginal_cost * weights).sum()
        gross_margin = gross_revenue - variable_cost
        asset_rows.append(
            {
                "asset": asset,
                "type": network.generators.at[asset, "carrier"],
                "capacity_mw": capacity_mw,
                "dispatched_mwh": dispatched_mwh,
                "charge_mwh": float("nan"),
                "share_of_total_demand_pct": safe_div(dispatched_mwh, total_demand_mwh) * 100.0,
                "active_hours": (dispatch_mw > 0).mul(weights, axis=0).sum(),
                "charge_hours": float("nan"),
                "average_dispatch_mw": dispatch_mw.mean(),
                "average_loading": safe_div(dispatch_mw.mean(), capacity_mw),
                "realized_sell_price_aud_per_mwh": safe_div(gross_revenue, dispatched_mwh),
                "gross_revenue_aud": gross_revenue,
                "variable_cost_aud": variable_cost,
                "charging_cost_aud": float("nan"),
                "gross_margin_aud": gross_margin,
                "margin_aud_per_mwh": safe_div(gross_margin, dispatched_mwh),
            }
        )

    if storage_name is not None and storage_name in network.storage_units.index:
        charge = network.storage_units_t.p_store[storage_name].clip(lower=0.0)
        discharge = network.storage_units_t.p_dispatch[storage_name].clip(lower=0.0)
        dispatched_mwh = (discharge * weights).sum()
        charge_mwh = (charge * weights).sum()
        gross_revenue = (discharge * price * weights).sum()
        charging_cost = (charge * price * weights).sum()
        gross_margin = gross_revenue - charging_cost
        capacity_mw = float(network.storage_units.at[storage_name, "p_nom"])
        asset_rows.append(
            {
                "asset": storage_name,
                "type": "bess",
                "capacity_mw": capacity_mw,
                "dispatched_mwh": dispatched_mwh,
                "charge_mwh": charge_mwh,
                "share_of_total_demand_pct": safe_div(dispatched_mwh, total_demand_mwh) * 100.0,
                "active_hours": (discharge > 0).mul(weights, axis=0).sum(),
                "charge_hours": (charge > 0).mul(weights, axis=0).sum(),
                "average_dispatch_mw": discharge.mean(),
                "average_loading": safe_div(discharge.mean(), capacity_mw),
                "realized_sell_price_aud_per_mwh": safe_div(gross_revenue, dispatched_mwh),
                "gross_revenue_aud": gross_revenue,
                "variable_cost_aud": 0.0,
                "charging_cost_aud": charging_cost,
                "gross_margin_aud": gross_margin,
                "margin_aud_per_mwh": safe_div(gross_margin, dispatched_mwh),
            }
        )

    dispatch_outcomes = pd.DataFrame(asset_rows).sort_values(
        "gross_margin_aud", ascending=False
    ).reset_index(drop=True)

    generator_cols = [f"{name.lower().replace(' ', '_')}_mw" for name in dispatch_order]
    results = pd.concat(
        [
            demand.rename("demand_mw"),
            price.rename("shadow_price_per_mwh"),
            network.generators_t.p[dispatch_order].rename(columns=lambda name: f"{name.lower().replace(' ', '_')}_mw"),
        ],
        axis=1,
    )

    market_totals = pd.DataFrame(
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
                total_demand_mwh,
                (results[generator_cols].multiply(weights, axis=0)).sum().sum(),
                dispatch_outcomes.loc[dispatch_outcomes["type"] == "bess", "dispatched_mwh"].sum(),
                dispatch_outcomes.loc[dispatch_outcomes["type"] == "bess", "charge_mwh"].sum(),
                price.mean(),
                price.max(),
            ],
        }
    )
    return dispatch_outcomes, market_totals

def build_market_outcomes_dashboard(
    dispatch_outcomes_df: pd.DataFrame,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (18, 6),
):
    asset_order = dispatch_outcomes_df["asset"].tolist()
    y = list(range(len(asset_order)))
    bar_colors = [OUTCOME_TYPE_COLORS.get(asset_type, "#7f7f7f") for asset_type in dispatch_outcomes_df["type"]]

    def fmt_money(value: float) -> str:
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"${value / 1_000_000:.2f}m"
        if abs_value >= 1_000:
            return f"${value / 1_000:.1f}k"
        return f"${value:.0f}"

    fig, (margin_ax, share_ax, activity_ax) = plt.subplots(1, 3, figsize=figsize, sharey=True)

    margin = dispatch_outcomes_df["gross_margin_aud"]
    margin_colors = ["#2f7d32" if value >= 0 else "#c73e1d" for value in margin]
    margin_ax.barh(y, margin, color=margin_colors, alpha=0.9)
    margin_ax.set_title("Gross Margin by Asset")
    margin_ax.set_xlabel("Gross Margin (AUD)")
    margin_ax.grid(axis="x", alpha=0.2)
    for idx, value in enumerate(margin):
        offset = max(abs(margin).max() * 0.01, 5_000)
        x_text = value + offset if value >= 0 else value - offset
        margin_ax.text(
            x_text,
            idx,
            fmt_money(value),
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=9,
        )

    share = dispatch_outcomes_df["share_of_total_demand_pct"]
    share_ax.barh(y, share, color=bar_colors, alpha=0.9)
    share_ax.set_title("Dispatch Share of Demand")
    share_ax.set_xlabel("Share of Total Demand (%)")
    share_ax.grid(axis="x", alpha=0.2)
    for idx, (share_pct, mwh) in enumerate(zip(share, dispatch_outcomes_df["dispatched_mwh"], strict=False)):
        share_ax.text(
            share_pct + 0.35,
            idx,
            f"{mwh:.0f} MWh",
            va="center",
            ha="left",
            fontsize=9,
        )

    active = dispatch_outcomes_df["active_hours"].fillna(0.0)
    charge_hours = dispatch_outcomes_df["charge_hours"].fillna(0.0)
    bar_height = 0.36
    activity_ax.barh(
        [value - bar_height / 2 for value in y],
        active,
        height=bar_height,
        color="#4e79a7",
        label="Active hours",
        alpha=0.9,
    )
    activity_ax.barh(
        [value + bar_height / 2 for value in y],
        charge_hours,
        height=bar_height,
        color="#76b7b2",
        label="Charge hours",
        alpha=0.9,
    )
    activity_ax.set_title("Activity and Price Capture")
    activity_ax.set_xlabel("Hours")
    activity_ax.grid(axis="x", alpha=0.2)
    activity_ax.legend(loc="upper left")

    price_ax = activity_ax.twiny()
    price_ax.scatter(
        dispatch_outcomes_df["realized_sell_price_aud_per_mwh"],
        y,
        color="#222222",
        marker="o",
        s=36,
        zorder=3,
    )
    price_ax.set_xlabel("Realized Sell Price ($/MWh)")

    activity_ax.set_yticks(y)
    activity_ax.set_yticklabels(asset_order)
    activity_ax.invert_yaxis()

    fig.suptitle(title or "Market Outcomes by Asset", y=0.98)
    fig.subplots_adjust(top=0.86, wspace=0.28)
    return fig
