import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from nemosis import dynamic_data_compiler
    from mpl_toolkits.mplot3d import Axes3D
    import os


    os.makedirs('../data/nemosis_cache', exist_ok=True)
    CACHE = '../data/nemosis_cache'


    # DISPATCHPRICE: 5-minute settlement prices for each NEM region.
    # INTERVENTION=0 filters out intervention pricing — during network interventions
    # AEMO sets prices via constraint equations, which distort the market signal.
    # Keeping only INTERVENTION=0 gives you the "true" dispatch prices.
    prices = dynamic_data_compiler(
        '2025/01/01 00:00:00',
        '2026/01/01 00:00:00',
        'DISPATCHPRICE', CACHE,
        fformat='parquet',
        filter_cols=['INTERVENTION'],
        filter_values=([0],)
    )

    prices = prices[['SETTLEMENTDATE', 'REGIONID', 'RRP', 'PRICE_STATUS']].copy()

    # SETTLEMENTDATE is the *end* of the dispatch interval (e.g. 00:05 covers 00:00–00:05).
    # Subtract 5 minutes here — once, on the raw data — so that both derived DataFrames
    # share a consistent interval-start index without needing separate post-pivot shifts.
    prices['SETTLEMENTDATE'] = prices['SETTLEMENTDATE'] - pd.Timedelta('5min')

    print(prices.head(20))

    # Pivot to wide format (rows = timestamps, columns = regions).
    # This is the primary DataFrame used in all subsequent analysis.
    prices_wide = (prices
        .pivot(index='SETTLEMENTDATE', columns='REGIONID', values='RRP')
        .sort_index()
    )

    # Same shape/index as prices_wide — used to mask administered pricing periods.
    # PRICE_STATUS is 'FIRM' under normal conditions, 'ADMINISTERED' when AEMO
    # sets prices outside the normal market mechanism (e.g. during price cap events).
    price_status_wide = (prices
        .pivot(index='SETTLEMENTDATE', columns='REGIONID', values='PRICE_STATUS')
        .sort_index()
    )

    print()
    print(prices_wide.head())
    print(f"Shape: {prices_wide.shape}")
    print(f"Memory: {prices_wide.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    # Expect all FIRM for 2025 — if ADMINISTERED shows up here, those periods
    # will be highlighted in the administered pricing overlay cell below.
    print("\nPRICE_STATUS value counts (all regions):")
    print(price_status_wide.apply(pd.Series.value_counts).fillna(0).astype(int))

    # Market price cap (MPC) is ~$15,100/MWh. Hitting the cap indicates a
    # severe supply shortage. A handful of cap events per year is normal for SA.
    print("\nHow many price cap intervals were there?")
    cap_events = (prices_wide >= 15000).sum()
    print(cap_events)

    # Negative prices occur when supply exceeds demand and generators bid negative
    # to stay on-line (e.g. wind farms avoiding ramp costs, solar avoiding curtailment).
    # SA and QLD typically lead on negative price count due to high renewable penetration.
    print("\nHow many negative price intervals?")
    neg_prices = (prices_wide < 0).sum()
    print(neg_prices)

    print(prices_wide.describe())
    return


if __name__ == "__main__":
    app.run()
