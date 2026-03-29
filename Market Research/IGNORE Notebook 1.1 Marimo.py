import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""
    # Notebook 1.1 — Price Explorer

    **Learning objectives:**
    - Read full-year regional dispatch price behaviour across the NEM
    - Interpret price duration curves, intraday price shape, and negative-price timing
    - Compare SA1 against other regions using spreads, correlations, and price-shape context
    - Build intuition for why a few extreme intervals can dominate market outcomes

    **Required data prep:**
    ```bash
    uv run python import_nem_data.py --start 2025/01/01 --end 2025/12/31 --dispatchprice
    uv run python import_nem_data.py --market-price-thresholds
    uv run python build_market_price_reference.py
    ```

    **Important import note:**
    - `DISPATCHPRICE` is a normal time-series table, so the requested date window works as expected.
    - `MARKET_PRICE_THRESHOLDS` is an effective-dated standing table in `nemosis`, so `--market-price-thresholds` walks historical monthly snapshots rather than respecting a narrow `--start/--end` window.
    - That behaviour is expected for this table and is why the consolidation step exists.

    **Data notes and quirks discovered during setup:**
    - This notebook uses `DISPATCHPRICE` plus the consolidated reference file `../data/reference/market_price_thresholds.parquet`.
    - It filters `DISPATCHPRICE` to `INTERVENTION = 0` so the charts reflect underlying dispatch prices rather than intervention-distorted intervals.
    - `SETTLEMENTDATE` is shifted back by 5 minutes once at load time so the time index represents the interval start consistently across later analysis.
    - For market-cap logic, use effective-dated `VOLL` from `MARKET_PRICE_THRESHOLDS`. In practice here, `VOLL` is the usable MPC reference.
    - The old hardcoded `$15,000/MWh` threshold is wrong for 2025. The effective cap is `$17,500/MWh` until `2025-06-30 23:55`, then `$20,300/MWh` from `2025-07-01 00:00` onward.

    Notebook 1.1 is the orientation pass: broad price shape first, deeper dispatch and constraint mechanics later.
    """)
    return


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from nemosis import dynamic_data_compiler
    from mpl_toolkits.mplot3d import Axes3D
    import os

    CACHE = '../data/nemosis_cache'
    REFERENCE = '../data/reference/market_price_thresholds.parquet'
    os.makedirs(CACHE, exist_ok=True)

    prices = dynamic_data_compiler(
        '2025/01/01 00:00:00',
        '2026/01/01 00:00:00',
        'DISPATCHPRICE', # 5-minute settlement prices for each NEM region.
        CACHE,
        fformat='parquet',
        filter_cols=['INTERVENTION'],
        filter_values=([0],) # INTERVENTION=0 keeps only non-intervention pricing
    )[['SETTLEMENTDATE', 'REGIONID', 'RRP']]

    # SETTLEMENTDATE is the *end* of the dispatch interval (e.g. 00:05 covers 00:00–00:05).
    prices['SETTLEMENTDATE'] -= pd.Timedelta('5min')

    # Pivot to wide format (rows = timestamps, columns = regions).
    # This is the primary DataFrame used in all subsequent analysis.
    prices_wide = (prices
        .pivot(index='SETTLEMENTDATE', columns='REGIONID', values='RRP')
        .sort_index()
    )

    # Market price thresholds are prepared outside the notebook from NEMOSIS monthly
    # snapshots, then consolidated into one effective-dated reference file.
    thresholds = pd.read_parquet(REFERENCE).copy()
    thresholds['EFFECTIVEDATE'] = pd.to_datetime(thresholds['EFFECTIVEDATE'])
    thresholds = (thresholds
        .sort_values(['EFFECTIVEDATE', 'VERSIONNO'])
        .drop_duplicates(['EFFECTIVEDATE', 'VERSIONNO'], keep='last')
    )

    # Assign the effective VOLL to each 5-minute interval via an as-of join.
    interval_caps = pd.merge_asof(
        pd.DataFrame({'SETTLEMENTDATE': prices_wide.index}).sort_values('SETTLEMENTDATE'),
        thresholds[['EFFECTIVEDATE', 'VOLL']].sort_values('EFFECTIVEDATE'),
        left_on='SETTLEMENTDATE',
        right_on='EFFECTIVEDATE',
        direction='backward'
    ).set_index('SETTLEMENTDATE')['VOLL']
    interval_caps.name = 'VOLL'

    print()
    print(prices_wide.head())
    print(f"Shape: {prices_wide.shape}")
    print(f"Memory: {prices_wide.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    # Use the effective VOLL for each interval rather than a hardcoded threshold.
    print("\nEffective VOLL periods loaded from reference file:")
    print(thresholds[['EFFECTIVEDATE', 'VOLL', 'MARKETPRICEFLOOR']].to_string(index=False))

    print("\nHow many price cap intervals were there (RRP >= effective VOLL)?")
    cap_events = prices_wide.ge(interval_caps, axis=0).sum()
    print(cap_events)

    # Negative prices occur when supply exceeds demand and generators bid negative
    # to stay on-line (e.g. wind farms avoiding ramp costs, solar avoiding curtailment).
    # SA and QLD typically lead on negative price count due to high renewable penetration.
    print("\nHow many negative price intervals?")
    neg_prices = (prices_wide < 0).sum()
    print(neg_prices)
    print(prices_wide.describe())
    return interval_caps, mdates, np, plt, prices_wide


@app.cell
def _(interval_caps, mdates, np, plt, prices_wide):
    # Time Series Plot
    # Full-year view of 5-minute prices for each region.
    # Useful for spotting seasonal patterns, price spike clusters, and periods of
    # sustained negative prices. Prices are capped at $2,000 for display — above
    # this, the series becomes unreadable due to spike outliers.
    # Cap-hit intervals (RRP >= effective VOLL, using INTERVENTION = 0 rows only)
    # are marked with downward triangles at the top of each regional panel.
    # The dashed zero line makes negative price periods immediately visible.

    fig, axes = plt.subplots(5, 1, figsize=(14, 12), sharex=True)
    regions = ['NSW1', 'QLD1', 'VIC1', 'SA1', 'TAS1']
    colors  = ['#2196F3', '#4CAF50', '#9C27B0', '#FF9800', '#F44336']

    for ax, region, color in zip(axes, regions, colors):
        # Cap display at $2,000 for readability — spikes exist but collapse the y-axis.
        display = prices_wide[region].clip(upper=2000)
        cap_mask = prices_wide[region].ge(interval_caps)
        cap_times = prices_wide.index[cap_mask]
        cap_y = np.full(cap_mask.sum(), 1950.0)

        ax.plot(display.index, display, lw=0.3, color=color, alpha=0.8)
        if len(cap_times) > 0:
            ax.scatter(cap_times, cap_y, marker='v', s=22, color='black',
                       label='Cap hit' if region == regions[0] else None, zorder=4)
        ax.axhline(0, color='black', lw=0.5, ls='--')
        ax.set_ylabel(f'{region}\n$/MWh', fontsize=9)
        ax.set_ylim(-200, 2000)
        ax.text(0.995, 0.88, f'cap hits: {int(cap_mask.sum())}',
                transform=ax.transAxes, ha='right', va='top', fontsize=8,
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))

    axes[0].legend(loc='upper left', frameon=True, fontsize=8)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    plt.tight_layout()
    return colors, regions


@app.cell
def _(colors, np, plt, prices_wide, regions):
    # Price Duration Curve (PDC)
    # A PDC sorts all price observations from highest to lowest and plots them
    # against the fraction of time that price was exceeded. Reading the chart:
    #   - The left tail shows how severe and frequent price spikes are.
    #   - Where the curve crosses $0 shows what fraction of time prices are negative.
    #   - A steep left tail → volatile market with infrequent but large spikes (SA).
    #   - A flat, low curve → stable, low-priced market (TAS, typically hydro-dominated).
    # Y-axis is clipped at $500 to show the bulk of the distribution — spike counts
    # are annotated so the clipped data isn't hidden.

    fig, ax = plt.subplots(figsize=(10, 6))

    for region, color in zip(regions, colors):
        sorted_prices = prices_wide[region].sort_values(ascending=False).values
        pct = (np.arange(len(sorted_prices)) / len(sorted_prices)) * 100  # x-axis: % of intervals
        ax.plot(pct, sorted_prices, label=region, color=color, lw=1.5)

    ax.axhline(0, color='black', lw=0.8, ls='--')
    ax.set_xlim(0, 100)
    ax.set_ylim(-100, 500)   # zoom in on the bulk — spikes distort the top
    ax.set_xlabel('% of intervals (0% = highest price, 100% = lowest)')
    ax.set_ylabel('Price $/MWh')
    ax.set_title('Price Duration Curves — NEM 2025')
    ax.legend()
    ax.grid(alpha=0.3)

    # Show what's being clipped — the spikes are part of the story
    clip_counts = {r: int((prices_wide[r] > 500).sum()) for r in regions}
    clip_note = '  '.join(f'{r}: {n}' for r, n in clip_counts.items() if n > 0)
    ax.text(0.98, 0.02, f'Intervals > $500 clipped — {clip_note}',
            transform=ax.transAxes, ha='right', va='bottom', fontsize=7, color='gray')
    return


@app.cell
def _(np, plt, prices_wide):
    # 3D Price Duration Surface — by hour of day (SA1)
    # Two synchronized viewpoints are shown side-by-side.
    # Each horizontal slice through this surface is the PDC for a specific hour.
    # Reading the surface:
    #   - Y-axis (hour of day): look for how the shape changes between morning,
    #     midday, and evening. Solar hours (10:00–15:00) should show a deep trough
    #     in the centre of the surface (cheap/negative midday prices).
    #   - X-axis (% of intervals): leftmost edge = highest prices, rightmost = lowest.
    #   - Z-axis ($/MWh): height of the surface = price level at that percentile/hour.
    #   - The grey zero plane makes it easy to see which hour/percentile combinations
    #     produce negative prices (surface drops below the plane).
    # Z is clipped at ±400 for visual clarity — extreme spike outliers would otherwise
    # compress the rest of the surface into a flat floor.

    region = 'SA1'

    # Prepare hourly price data
    prices_hourly = prices_wide.resample('1h').mean()
    df = prices_hourly[[region]].copy()
    df['hour'] = df.index.hour + 1  # 1–24
    df = df[df[region] > -500]      # drop extreme outliers for surface clarity

    # Build percentile-by-hour matrix
    percentiles = np.linspace(0, 100, 200)
    hours = list(range(1, 25))
    Z = np.zeros((len(hours), len(percentiles)))
    for i, h in enumerate(hours):
        hour_prices = df[df['hour'] == h][region].dropna().values
        if len(hour_prices) > 0:
            Z[i, :] = np.percentile(hour_prices, 100 - percentiles)  # descending like PDC

    X, Y = np.meshgrid(percentiles, hours)
    Z_display = np.clip(Z, -100, 400)

    # Plot two camera angles in one figure
    fig = plt.figure(figsize=(18, 8))
    angles = [(25, -30), (25, 20)]
    mappable = None

    for idx, (elev, azim) in enumerate(angles, start=1):
        ax = fig.add_subplot(1, 2, idx, projection='3d')
        surf = ax.plot_surface(
            X, Y, Z_display, cmap='viridis', vmin=-50, vmax=300, #'RdYlGn_r'
            alpha=0.9, linewidth=0, antialiased=True
        )
        mappable = surf
        xx, yy = np.meshgrid([0, 100], [1, 24])  # zero plane
        ax.plot_surface(xx, yy, np.zeros_like(xx), alpha=0.15, color='grey')
        ax.set_xlabel('% of intervals\n(0% = highest price)', labelpad=10)
        ax.set_ylabel('Hour of day', labelpad=10)
        ax.set_zlabel('Price $/MWh', labelpad=10)
        ax.set_yticks(range(1, 25, 2))
        ax.set_yticklabels(range(1, 25, 2), fontsize=7)
        ax.view_init(elev=elev, azim=azim)

    fig.suptitle(f'{region} — Price Duration Surface 2025', y=0.82, x=0.45)
    fig.colorbar(mappable, ax=fig.axes, label='$/MWh', shrink=0.6, pad=0.03)
    plt.show()


    return


@app.cell
def _(np, plt, prices_wide):
    # Seasonal PDC Surface — SA1 (meteorological seasons)
    # This is a secondary shape-intuition plot. Use with the daily ribbon and month-hour
    # median heatmap as primary evidence.
    # Reference context: the prior all-year SA1 duration surface cell.
    #
    # Method:
    #   1) Resample to hourly mean prices.
    #   2) Split into DJF/MAM/JJA/SON.
    #   3) For each season-hour slice, compute full percentile PDC (descending).
    #   4) Plot a 2x2 seasonal surface panel with shared scaling.

    region = 'SA1'
    prices_hourly = prices_wide.resample('1h').mean()

    df = prices_hourly[[region]].copy()
    df = df[df[region].notna()]
    df['hour'] = df.index.hour + 1  # 1–24

    # Meteorological seasons by month
    season_map = {
        12: 'DJF', 1: 'DJF', 2: 'DJF',
        3: 'MAM', 4: 'MAM', 5: 'MAM',
        6: 'JJA', 7: 'JJA', 8: 'JJA',
        9: 'SON', 10: 'SON', 11: 'SON'
    }
    df['season'] = df.index.month.map(season_map)

    season_order = ['DJF', 'MAM', 'JJA', 'SON']
    season_title = {
        'DJF': 'DJF (Summer)',
        'MAM': 'MAM (Autumn)',
        'JJA': 'JJA (Winter)',
        'SON': 'SON (Spring)'
    }

    percentiles = np.linspace(0, 100, 200)  # x-axis as exceedance-like percentile
    hours = np.arange(1, 25)
    X, Y = np.meshgrid(percentiles, hours)

    # Build season-hour percentile matrices
    season_surfaces = {}
    for s in season_order:
        Z = np.full((len(hours), len(percentiles)), np.nan)
        for i, h in enumerate(hours):
            vals = df.loc[(df['season'] == s) & (df['hour'] == h), region].dropna().values

            # Data-integrity check: every season-hour slice must be non-empty
            assert len(vals) > 0, f'Missing data for {s}, hour {h}'

            # Descending PDC shape by percentile axis (0% = highest)
            row = np.percentile(vals, 100 - percentiles)

            # Data-integrity check: monotonic non-increasing over exceedance percentile
            assert np.all(np.diff(row) <= 1e-9), f'Non-monotonic percentile row for {s}, hour {h}'

            Z[i, :] = row

        season_surfaces[s] = Z

    # Shared display and z-limits across all panels
    CLIP_LO, CLIP_HI = -100, 400
    zlim_lo, zlim_hi = CLIP_LO, CLIP_HI
    all_vals = np.concatenate([season_surfaces[s].ravel() for s in season_order])
    vmin = max(CLIP_LO, np.nanpercentile(all_vals, 1))
    vmax = min(CLIP_HI, np.nanpercentile(all_vals, 99))

    fig = plt.figure(figsize=(18, 12))
    mappable = None

    for idx, s in enumerate(season_order, start=1):
        ax = fig.add_subplot(2, 2, idx, projection='3d')
        Z_display = np.clip(season_surfaces[s], CLIP_LO, CLIP_HI)

        surf = ax.plot_surface(
            X, Y, Z_display,
            cmap='viridis',
            vmin=vmin, vmax=vmax,
            alpha=0.92, linewidth=0, antialiased=True
        )
        mappable = surf

        # Zero plane in each panel to highlight negative-price regions
        xx, yy = np.meshgrid([0, 100], [1, 24])
        ax.plot_surface(xx, yy, np.zeros_like(xx), alpha=0.14, color='grey')

        # Visual-consistency checks: same axes in all panels
        ax.set_xlim(0, 100)
        ax.set_ylim(1, 24)
        ax.set_zlim(zlim_lo, zlim_hi)

        ax.set_xlabel('% of intervals\n(0% = highest price)', labelpad=10)
        ax.set_ylabel('Hour of day', labelpad=8)
        ax.set_zlabel('Price $/MWh', labelpad=8)
        ax.set_yticks(range(1, 25, 2))
        ax.set_yticklabels(range(1, 25, 2), fontsize=7)
        ax.set_title(season_title[s], pad=10)
        ax.view_init(elev=25, azim=-35)

    fig.suptitle(
        f'{region} — Seasonal Price Duration Surfaces (2025)\n'
        'Meteorological seasons; shared color/z scale; Z clipped to [-100, 400] $/MWh',
        y=0.96
    )
    fig.colorbar(mappable, ax=fig.axes, label='$/MWh', shrink=0.65, pad=0.03)
    plt.tight_layout(rect=[0, 0.02, 1, 0.93])
    plt.show()

    # Short interpretation block (data-driven summary)
    p50_idx = int(np.argmin(np.abs(percentiles - 50)))

    peak_by_season = {
        s: np.nanmax(season_surfaces[s][:, 0])  # left edge (0%) ~ seasonal max tail
        for s in season_order
    }
    midday_p50_by_season = {
        s: np.nanmean(season_surfaces[s][9:15, p50_idx])  # hours 10–15
        for s in season_order
    }
    evening_p50_by_season = {
        s: np.nanmean(season_surfaces[s][17:21, p50_idx])  # hours 18–21
        for s in season_order
    }
    premium_by_season = {
        s: evening_p50_by_season[s] - midday_p50_by_season[s]
        for s in season_order
    }

    season_peak = max(peak_by_season, key=peak_by_season.get)
    season_midday_low = min(midday_p50_by_season, key=midday_p50_by_season.get)
    season_evening_premium = max(premium_by_season, key=premium_by_season.get)

    print('Interpretation notes (secondary shape view):')
    print(f"  1) Left-tail spike intensity is highest in {season_title[season_peak]}")
    print(f"     (seasonal peak ~ ${peak_by_season[season_peak]:.0f}/MWh at 0% percentile edge).")
    print(f"  2) Midday trough is deepest in {season_title[season_midday_low]}")
    print(f"     (10:00–15:00 P50 ~ ${midday_p50_by_season[season_midday_low]:.1f}/MWh).")
    print(f"  3) Evening ramp premium is steepest in {season_title[season_evening_premium]}")
    print(
        f"     (18:00–21:00 P50 minus 10:00–15:00 P50 = ${premium_by_season[season_evening_premium]:.1f}/MWh)."
    )


    return


@app.cell
def _(mdates, plt, prices_wide):
    # Daily price distribution ribbon — SA1
    # The ribbon spans P10–P90 (80% of hours each day); the line is the daily median.
    #
    # Reading the chart:
    #   - Narrow ribbon = low intra-day spread (stable generation mix that day)
    #   - Wide ribbon   = large cheap-midday / expensive-peak spread (solar duck curve days)
    #   - Ribbon dipping below $0 = negative prices occurred that day
    #   - Seasonal clusters of wide ribbons → typically summer demand peaks and spring solar surplus

    region = 'SA1'

    # Filter to one region before resampling — avoids resampling 4 unused columns
    daily = (prices_wide[region]
             .resample('1h').mean()
             .resample('D').quantile([0.1, 0.5, 0.9])
             .unstack())
    daily.columns = ['p10', 'median', 'p90']

    CLIP_LO, CLIP_HI = -200, 800
    daily_plot = daily.clip(CLIP_LO, CLIP_HI)  # clip once, reuse in all three plot calls

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.fill_between(daily_plot.index, daily_plot['p10'], daily_plot['p90'],
                    alpha=0.3, color='steelblue', label='P10–P90 range')
    ax.plot(daily_plot.index, daily_plot['median'],
            color='steelblue', lw=1.0, label='Daily median')
    ax.axhline(0, color='black', lw=0.8, ls='--')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.set_ylabel('Price $/MWh')
    ax.set_title(f'{region} — Daily price distribution 2025\n'
                 f'Ribbon = P10–P90 of hourly prices each day  |  Line = daily median')
    ax.legend(loc='upper right')
    ax.set_ylim(CLIP_LO, CLIP_HI)
    ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()

    n_neg_median = (daily['median'] < 0).sum()
    n_wide = (daily['p90'] - daily['p10'] > 200).sum()
    print(f"Days with negative median price:       {n_neg_median}")
    print(f"Days with P10–P90 spread > $200/MWh:  {n_wide}  (high intra-day volatility)")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
