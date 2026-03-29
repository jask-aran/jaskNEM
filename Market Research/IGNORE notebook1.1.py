import marimo

__generated_with = "0.20.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
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
    REGION = 'VIC1'
    os.makedirs(CACHE, exist_ok=True)  # Global focus region for single-region analyses
    prices = dynamic_data_compiler('2025/01/01 00:00:00', '2026/01/01 00:00:00', 'DISPATCHPRICE', CACHE, fformat='parquet', filter_cols=['INTERVENTION'], filter_values=([0],))[['SETTLEMENTDATE', 'REGIONID', 'RRP']]
    prices['SETTLEMENTDATE'] -= pd.Timedelta('5min')
    prices_wide = prices.pivot(index='SETTLEMENTDATE', columns='REGIONID', values='RRP').sort_index()
    _thresholds = pd.read_parquet(REFERENCE).copy()
    _thresholds['EFFECTIVEDATE'] = pd.to_datetime(_thresholds['EFFECTIVEDATE'])
    _thresholds = _thresholds.sort_values(['EFFECTIVEDATE', 'VERSIONNO']).drop_duplicates(['EFFECTIVEDATE', 'VERSIONNO'], keep='last')  # 5-minute settlement prices for each NEM region.
    interval_caps = pd.merge_asof(pd.DataFrame({'SETTLEMENTDATE': prices_wide.index}).sort_values('SETTLEMENTDATE'), _thresholds[['EFFECTIVEDATE', 'VOLL']].sort_values('EFFECTIVEDATE'), left_on='SETTLEMENTDATE', right_on='EFFECTIVEDATE', direction='backward').set_index('SETTLEMENTDATE')['VOLL']
    interval_caps.name = 'VOLL'
    print()
    print(prices_wide.head())  # INTERVENTION=0 keeps only non-intervention pricing
    print(f'Shape: {prices_wide.shape}')
    print(f'Memory: {prices_wide.memory_usage(deep=True).sum() / 1000000.0:.1f} MB')
    # SETTLEMENTDATE is the *end* of the dispatch interval (e.g. 00:05 covers 00:00–00:05).
    print('\nEffective VOLL periods loaded from reference file:')
    print(_thresholds[['EFFECTIVEDATE', 'VOLL', 'MARKETPRICEFLOOR']].to_string(index=False))
    # Pivot to wide format (rows = timestamps, columns = regions).
    # This is the primary DataFrame used in all subsequent analysis.
    print('\nHow many price cap intervals were there (RRP >= effective VOLL)?')
    cap_events = prices_wide.ge(interval_caps, axis=0).sum()
    print(cap_events)
    print('\nHow many negative price intervals?')
    neg_prices = (prices_wide < 0).sum()
    # Market price thresholds are prepared outside the notebook from NEMOSIS monthly
    # snapshots, then consolidated into one effective-dated reference file.
    print(neg_prices)
    # Assign the effective VOLL to each 5-minute interval via an as-of join.
    # Use the effective VOLL for each interval rather than a hardcoded threshold.
    # Negative prices occur when supply exceeds demand and generators bid negative
    # to stay on-line (e.g. wind farms avoiding ramp costs, solar avoiding curtailment).
    # SA and QLD typically lead on negative price count due to high renewable penetration.
    print(prices_wide.describe())
    return REGION, interval_caps, mdates, np, pd, plt, prices_wide


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
    _fig, _axes = plt.subplots(5, 1, figsize=(14, 12), sharex=True)
    regions = ['NSW1', 'QLD1', 'VIC1', 'SA1', 'TAS1']
    colors = ['#2196F3', '#4CAF50', '#9C27B0', '#FF9800', '#F44336']
    for _ax, _region, _color in zip(_axes, regions, colors):
        display = prices_wide[_region].clip(upper=2000)
        cap_mask = prices_wide[_region].ge(interval_caps)
        cap_times = prices_wide.index[cap_mask]  # Cap display at $2,000 for readability — spikes exist but collapse the y-axis.
        cap_y = np.full(cap_mask.sum(), 1950.0)
        _ax.plot(display.index, display, lw=0.3, color=_color, alpha=0.8)
        if len(cap_times) > 0:
            _ax.scatter(cap_times, cap_y, marker='v', s=22, color='black', label='Cap hit' if _region == regions[0] else None, zorder=4)
        _ax.axhline(0, color='black', lw=0.5, ls='--')
        _ax.set_ylabel(f'{_region}\n$/MWh', fontsize=9)
        _ax.set_ylim(-200, 2000)
        _ax.text(0.995, 0.88, f'cap hits: {int(cap_mask.sum())}', transform=_ax.transAxes, ha='right', va='top', fontsize=8, bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))
    _axes[0].legend(loc='upper left', frameon=True, fontsize=8)
    _axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
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
    _fig, _ax = plt.subplots(figsize=(10, 6))
    for _region, _color in zip(regions, colors):
        sorted_prices = prices_wide[_region].sort_values(ascending=False).values
        _pct = np.arange(len(sorted_prices)) / len(sorted_prices) * 100
        _ax.plot(_pct, sorted_prices, label=_region, color=_color, lw=1.5)
    _ax.axhline(0, color='black', lw=0.8, ls='--')  # x-axis: % of intervals
    _ax.set_xlim(0, 100)
    _ax.set_ylim(-100, 500)
    _ax.set_xlabel('% of intervals (0% = highest price, 100% = lowest)')
    _ax.set_ylabel('Price $/MWh')
    _ax.set_title('Price Duration Curves — NEM 2025')  # zoom in on the bulk — spikes distort the top
    _ax.legend()
    _ax.grid(alpha=0.3)
    clip_counts = {r: int((prices_wide[r] > 500).sum()) for r in regions}
    clip_note = '  '.join((f'{r}: {n}' for r, n in clip_counts.items() if n > 0))
    # Show what's being clipped — the spikes are part of the story
    _ax.text(0.98, 0.02, f'Intervals > $500 clipped — {clip_note}', transform=_ax.transAxes, ha='right', va='bottom', fontsize=7, color='gray')
    return


@app.cell
def _(REGION, np, plt, prices_wide):
    # 3D Price Duration Surface — by hour of day (REGION)
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
    _region = REGION
    _prices_hourly = prices_wide.resample('1h').mean()
    _df = _prices_hourly[[_region]].copy()
    # Prepare hourly price data
    _df['hour'] = _df.index.hour + 1
    _df = _df[_df[_region] > -500]
    _percentiles = np.linspace(0, 100, 200)  # 1–24
    _hours = list(range(1, 25))  # drop extreme outliers for surface clarity
    _Z = np.zeros((len(_hours), len(_percentiles)))
    # Build percentile-by-hour matrix
    for _i, _h in enumerate(_hours):
        _hour_prices = _df[_df['hour'] == _h][_region].dropna().values
        if len(_hour_prices) > 0:
            _Z[_i, :] = np.percentile(_hour_prices, 100 - _percentiles)
    _X, _Y = np.meshgrid(_percentiles, _hours)
    _Z_display = np.clip(_Z, -100, 400)
    _fig = plt.figure(figsize=(18, 8))  # descending like PDC
    _angles = [(25, -30), (25, 20)]
    _mappable = None
    for _idx, (_elev, _azim) in enumerate(_angles, start=1):
        _ax = _fig.add_subplot(1, 2, _idx, projection='3d')
    # Plot two camera angles in one figure
        _surf = _ax.plot_surface(_X, _Y, _Z_display, cmap='viridis', vmin=-50, vmax=300, alpha=0.9, linewidth=0, antialiased=True)
        _mappable = _surf
        _xx, _yy = np.meshgrid([0, 100], [1, 24])
        _ax.plot_surface(_xx, _yy, np.zeros_like(_xx), alpha=0.15, color='grey')
        _ax.set_xlabel('% of intervals\n(0% = highest price)', labelpad=10)
        _ax.set_ylabel('Hour of day', labelpad=10)
        _ax.set_zlabel('Price $/MWh', labelpad=10)
        _ax.set_yticks(range(1, 25, 2))  #'RdYlGn_r'
        _ax.set_yticklabels(range(1, 25, 2), fontsize=7)
        _ax.view_init(elev=_elev, azim=_azim)
    _fig.suptitle(f'{_region} — Price Duration Surface 2025', y=0.82, x=0.45)
    _fig.colorbar(_mappable, ax=_fig.axes, label='$/MWh', shrink=0.6, pad=0.03)  # zero plane
    plt.show()
    return


@app.cell
def _(REGION, np, plt, prices_wide):
    # Seasonal PDC Surface — REGION (meteorological seasons)
    # This extends the all-year 3D surface by splitting data into DJF/MAM/JJA/SON.
    # Each panel is a full percentile duration surface by hour of day for one season.
    # Keep this as a secondary shape/intution plot; use ribbon + heatmap as primary evidence.
    _region = REGION
    _df = prices_wide.resample('1h').mean()[[_region]].copy()
    _df['hour'] = _df.index.hour + 1
    # Prepare hourly price data
    _df['month'] = _df.index.month
    _df = _df[_df[_region] > -500]  # 1–24
    season_map = {12: 'DJF', 1: 'DJF', 2: 'DJF', 3: 'MAM', 4: 'MAM', 5: 'MAM', 6: 'JJA', 7: 'JJA', 8: 'JJA', 9: 'SON', 10: 'SON', 11: 'SON'}
    _df['season'] = _df['month'].map(season_map)  # drop extreme outliers for surface clarity
    season_order = ['DJF', 'MAM', 'JJA', 'SON']
    # Meteorological seasons
    season_labels = {'DJF': 'DJF (Summer)', 'MAM': 'MAM (Autumn)', 'JJA': 'JJA (Winter)', 'SON': 'SON (Spring)'}
    _percentiles = np.linspace(0, 100, 200)
    _hours = list(range(1, 25))
    _X, _Y = np.meshgrid(_percentiles, _hours)
    surfaces = {}
    for season in season_order:
        _Z = np.zeros((len(_hours), len(_percentiles)))
        sdf = _df[_df['season'] == season]
        for _i, _h in enumerate(_hours):
            _hour_prices = sdf[sdf['hour'] == _h][_region].dropna().values
            if len(_hour_prices) > 0:
                _Z[_i, :] = np.percentile(_hour_prices, 100 - _percentiles)
        surfaces[season] = _Z
    _CLIP_LO, _CLIP_HI = (-100, 400)
    VMIN, VMAX = (-50, 300)
    _fig = plt.figure(figsize=(18, 12))
    # Build percentile-by-hour matrix for each season
    _mappable = None
    for _idx, season in enumerate(season_order, start=1):
        _ax = _fig.add_subplot(2, 2, _idx, projection='3d')
        _Z_display = np.clip(surfaces[season], _CLIP_LO, _CLIP_HI)
        _surf = _ax.plot_surface(_X, _Y, _Z_display, cmap='viridis', vmin=VMIN, vmax=VMAX, alpha=0.9, linewidth=0, antialiased=True)
        _mappable = _surf
        _xx, _yy = np.meshgrid([0, 100], [1, 24])
        _ax.plot_surface(_xx, _yy, np.zeros_like(_xx), alpha=0.15, color='grey')
        _ax.set_xlim(0, 100)
        _ax.set_ylim(1, 24)
        _ax.set_zlim(_CLIP_LO, _CLIP_HI)
        _ax.set_xlabel('% of intervals\n(0% = highest price)', labelpad=10)  # descending like PDC
        _ax.set_ylabel('Hour of day', labelpad=10)
        _ax.set_zlabel('Price $/MWh', labelpad=10)
    # Shared clipping and color scale across all 4 panels
        _ax.set_yticks(range(1, 25, 2))
        _ax.set_yticklabels(range(1, 25, 2), fontsize=7)
        _ax.view_init(elev=25, azim=-35)
    # Plot 2x2 seasonal surfaces
        _ax.set_title(season_labels[season], pad=12)
    _fig.suptitle(f'{_region} — Seasonal Price Duration Surfaces 2025\nShared scale across DJF/MAM/JJA/SON (Z clipped to [-100, 400] $/MWh)', y=0.95)
    _fig.colorbar(_mappable, ax=_fig.axes, label='$/MWh', shrink=0.65, pad=0.03)
    plt.tight_layout(rect=[0, 0.02, 1, 0.92])
    plt.show()
    p50_idx = np.argmin(np.abs(_percentiles - 50))
    left_tail_peak = {}
    midday_p50 = {}
    evening_p50 = {}
    evening_premium = {}
    for season in season_order:
        _Z = surfaces[season]
        left_tail_peak[season] = np.max(_Z[:, 0])
        midday_p50[season] = np.mean(_Z[9:15, p50_idx])  # zero plane
        evening_p50[season] = np.mean(_Z[17:21, p50_idx])
        evening_premium[season] = evening_p50[season] - midday_p50[season]
    season_spike = max(left_tail_peak, key=left_tail_peak.get)
    season_midday_low = min(midday_p50, key=midday_p50.get)
    season_ramp = max(evening_premium, key=evening_premium.get)
    print('Interpretation notes:')
    print(f'  Left-tail spike intensity highest: {season_labels[season_spike]}')
    print(f'  Deepest midday trough (P50, 10:00–15:00): {season_labels[season_midday_low]}')
    # Short interpretation block
    print(f'  Steepest evening premium (18:00–21:00 vs 10:00–15:00): {season_labels[season_ramp]}')  # 10:00–15:00  # 18:00–21:00
    return


@app.cell
def _(REGION, np, plt, prices_wide):
    # Price Surface
    # 3D view of hourly mean price by day-of-year (x) and hour-of-day (y).
    # This complements the duration surface by showing *when* regimes/events occur.
    # Z is clipped for readability so outlier spikes do not flatten the surface.
    _region = REGION
    _prices_hourly = prices_wide.resample('1h').mean()
    _df = _prices_hourly[[_region]].copy()
    # Prepare hourly data
    _df['hour'] = _df.index.hour + 1
    _df['day_of_year'] = _df.index.dayofyear
    _df = _df[_df[_region] > -500]  # 1–24
    _pivot = _df.pivot_table(values=_region, index='hour', columns='day_of_year', aggfunc='mean').sort_index(axis=1)
    _hours = _pivot.index.values  # drop extreme outliers for surface clarity
    days = _pivot.columns.values
    # Build day-by-hour matrix (rows = hour, cols = day)
    _X, _Y = np.meshgrid(days, _hours)
    _Z = _pivot.values
    _Z_display = np.clip(_Z, -100, 400)
    _fig = plt.figure(figsize=(18, 8))
    _angles = [(28, -62), (28, -20)]
    _mappable = None
    for _idx, (_elev, _azim) in enumerate(_angles, start=1):
        _ax = _fig.add_subplot(1, 2, _idx, projection='3d')
        _surf = _ax.plot_surface(_X, _Y, _Z_display, cmap='RdYlGn_r', vmin=-50, vmax=300, alpha=0.9, linewidth=0, antialiased=True)
        _mappable = _surf
        _xx, _yy = np.meshgrid([days.min(), days.max()], [1, 24])
        _ax.plot_surface(_xx, _yy, np.zeros_like(_xx), alpha=0.14, color='grey')
        _ax.set_xlabel('Day of year', labelpad=10)
    # Plot two viewpoints for better depth perception
        _ax.set_ylabel('Hour of day', labelpad=10)
        _ax.set_zlabel('Price $/MWh', labelpad=10)
        _ax.set_yticks(range(1, 25, 2))
        _ax.set_yticklabels(range(1, 25, 2), fontsize=7)
        _ax.view_init(elev=_elev, azim=_azim)
    _fig.suptitle(f'{_region} — Price Surface 2025 (hourly means)', y=0.82, x=0.45)
    _fig.colorbar(_mappable, ax=_fig.axes, label='$/MWh', shrink=0.6, pad=0.03)
    plt.show()  # zero plane
    return


@app.cell
def _(REGION, mdates, plt, prices_wide):
    # Daily price distribution ribbon — REGION
    # The ribbon spans P10–P90 (80% of hours each day); the line is the daily median.
    #
    # Reading the chart:
    #   - Narrow ribbon = low intra-day spread (stable generation mix that day)
    #   - Wide ribbon   = large cheap-midday / expensive-peak spread (solar duck curve days)
    #   - Ribbon dipping below $0 = negative prices occurred that day
    #   - Seasonal clusters of wide ribbons → typically summer demand peaks and spring solar surplus
    _region = REGION
    daily = prices_wide[_region].resample('1h').mean().resample('D').quantile([0.1, 0.5, 0.9]).unstack()
    daily.columns = ['p10', 'median', 'p90']
    # Filter to one region before resampling — avoids resampling 4 unused columns
    _CLIP_LO, _CLIP_HI = (-200, 800)
    daily_plot = daily.clip(_CLIP_LO, _CLIP_HI)
    _fig, _ax = plt.subplots(figsize=(14, 5))
    _ax.fill_between(daily_plot.index, daily_plot['p10'], daily_plot['p90'], alpha=0.3, color='steelblue', label='P10–P90 range')
    _ax.plot(daily_plot.index, daily_plot['median'], color='steelblue', lw=1.0, label='Daily median')
    _ax.axhline(0, color='black', lw=0.8, ls='--')
    _ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    _ax.set_ylabel('Price $/MWh')  # clip once, reuse in all three plot calls
    _ax.set_title(f'{_region} — Daily price distribution 2025\nRibbon = P10–P90 of hourly prices each day  |  Line = daily median')
    _ax.legend(loc='upper right')
    _ax.set_ylim(_CLIP_LO, _CLIP_HI)
    _ax.grid(alpha=0.2)
    plt.tight_layout()
    plt.show()
    n_neg_median = (daily['median'] < 0).sum()
    n_wide = (daily['p90'] - daily['p10'] > 200).sum()
    print(f'Days with negative median price:       {n_neg_median}')
    print(f'Days with P10–P90 spread > $200/MWh:  {n_wide}  (high intra-day volatility)')
    return


@app.cell
def _(REGION, plt, prices_wide):
    # Price Carpet — REGION
    # A carpet plot maps the full year on the x-axis and hours of the day on the y-axis.
    # Each cell is coloured by the mean price in that hour on that calendar day.
    # This is a dense, information-rich view that makes several patterns visible at once:
    #   - Vertical bands of colour → multi-day price events (heatwaves, generator outages).
    #   - Horizontal colour gradients → intra-day price shape (cheap midday, expensive morning/evening).
    #   - Seasonal colour shift → summer/winter demand differences.
    #   - Green patches in midday rows (hours 10–15) → solar surplus driving prices negative.
    # Colour scale is clipped at $300 — spike outliers would wash out the gradient otherwise.
    _region = REGION
    # Median Price Heatmap — by hour of day and month
    # Shows the typical intra-day price shape for each month of the year.
    # Using median (not mean) to reduce the influence of spike events.
    # Reading the chart:
    #   - Dark red cells = expensive hours (morning/evening demand peaks).
    #   - Green/yellow cells = cheap or negative hours (midday solar, overnight low demand).
    #   - Compare months: summer months should show higher afternoon prices in SA/NSW
    #     (air conditioning load) while spring/autumn show deeper midday troughs (solar surplus).
    # Plotted for SA1, VIC1, and NSW1 to contrast renewable-heavy and gas-peaking markets.
    _prices_hourly = prices_wide.resample('1h').mean()
    _df = _prices_hourly[[_region]].copy()
    _df['hour'] = _df.index.hour + 1
    _df['day_of_year'] = _df.index.dayofyear
    # --- Plot 1: price carpet (day-of-year x hour) ---
    _pivot = _df.pivot_table(values=_region, index='hour', columns='day_of_year', aggfunc='mean')
    _fig, _ax = plt.subplots(figsize=(16, 6))  # 1–24
    _im = _ax.imshow(_pivot, aspect='auto', cmap='RdYlGn_r', vmin=-50, vmax=300, interpolation='nearest')
    month_starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    # Pivot: rows = hour of day, columns = calendar day
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    _ax.set_xticks([d - 1 for d in month_starts])
    _ax.set_xticklabels(month_labels)  # y-axis: 1–24
    _ax.set_yticks(range(24))  # x-axis: 1–365
    _ax.set_yticklabels(range(1, 25), fontsize=8)
    _ax.set_ylabel('Hour of day')
    _ax.set_title(f'{_region} — Price Carpet 2025 ($/MWh)')
    plt.colorbar(_im, label='$/MWh', shrink=0.8)
    plt.tight_layout()
    plt.show()
    _df = _prices_hourly[[_region]].copy()
    _df['hour'] = _df.index.hour + 1
    _df['month'] = _df.index.month  # clip — don't let spikes dominate colour scale
    _pivot = _df.pivot_table(values=_region, index='hour', columns='month', aggfunc='median')
    _fig, _ax = plt.subplots(figsize=(12, 6))
    _im = _ax.imshow(_pivot, aspect='auto', cmap='RdYlGn_r', vmin=0, vmax=200)
    # X-axis: label by month
    _ax.set_xlabel('Month')
    _ax.set_ylabel('Hour of day')
    _ax.set_yticks(range(24))
    _ax.set_yticklabels(range(1, 25), fontsize=8)  # -1 because imshow is 0-indexed
    _ax.set_title(f'{_region} — Median price by hour and month 2025')
    _ax.set_xticks(range(12))
    _ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    plt.colorbar(_im, label='$/MWh')
    plt.tight_layout()
    # --- Plot 2: median heatmap (month x hour) ---
    # Hour bucket 1–24 (not 0–23)
    plt.show()  # shifts 0-23 → 1-24  # 1–24, 24 rows
    return


@app.cell
def _(mdates, np, plt, prices_wide):
    # SA–VIC Price Spread
    # The spread (SA price minus VIC price) is a proxy for the interconnector margin.
    # When SA is more expensive than VIC (positive spread), it suggests:
    #   - The Heywood interconnector is importing at capacity (SA is short of supply), or
    #   - SA has a local price event (generator trip, high gas prices).
    # When VIC is more expensive (negative spread):
    #   - SA is exporting, or
    #   - SA has excess renewable generation pushing prices down.
    #
    # Interconnectors have a small unavoidable loss component, so a spread of ~$0–$10
    # can exist even with an unconstrained interconnector. Spreads persistently above
    # ~$50–$100 are a more reliable proxy for binding interconnector constraints.
    spread = prices_wide['SA1'] - prices_wide['VIC1']
    spread_hourly = spread.resample('1h').mean()
    spread_display = spread_hourly.clip(-200, 500)
    _fig, _axes = plt.subplots(3, 1, figsize=(12, 11))
    _axes[0].fill_between(spread_display.index, spread_display, 0, where=spread_display > 0, alpha=0.5, color='red', label='SA > VIC')
    _axes[0].fill_between(spread_display.index, spread_display, 0, where=spread_display < 0, alpha=0.5, color='blue', label='VIC > SA')
    _axes[0].axhline(0, color='black', lw=0.8, ls='--')
    # --- Top: spread time series (hourly) ---
    _axes[0].set_title('SA–VIC Price Spread 2025 (hourly means, clipped ±$200/$500)')
    _axes[0].set_ylabel('Spread $/MWh')
    _axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    _axes[0].legend(loc='upper right')
    XMIN, XMAX = (-300, 600)
    _thresholds = [50, 100, 200, 500]
    threshold_colors = ['#FFC107', '#FF9800', '#F44336', '#9C27B0']
    _axes[1].hist(spread_hourly.clip(XMIN, XMAX), bins=180, color='steelblue', edgecolor='none')
    _axes[1].axvline(0, color='black', lw=1.5, ls='--', label='$0 (parity)')
    for t, c in zip(_thresholds, threshold_colors):
    # --- Shared x-range for panels 2 and 3 so x=0 aligns visually ---
        _axes[1].axvline(t, color=c, lw=1.2, ls='--', label=f'${t}')
    _axes[1].set_xlim(XMIN, XMAX)
    # --- Middle: distribution (hourly) with log y-scale ---
    _axes[1].set_xlabel('SA - VIC spread $/MWh')
    _axes[1].set_title('Distribution of SA–VIC spread 2025 (hourly)')
    _axes[1].set_ylabel('Count (hourly intervals)')
    _axes[1].legend(loc='upper right', fontsize=8)
    threshold_range = np.arange(XMIN, XMAX + 1, 5)
    threshold_arr = threshold_range[:, None]
    pct_above = (spread_hourly.values > threshold_arr).mean(axis=1) * 100
    t_idx = {t: _i for _i, t in enumerate(threshold_range)}
    _axes[2].plot(threshold_range, pct_above, color='red', lw=1.5, label='% time SA > VIC by >$X')
    _axes[2].axvline(0, color='black', lw=0.8, ls='--')
    for t, c in zip(_thresholds, threshold_colors):
        _pct = pct_above[t_idx[t]]
        _axes[2].axvline(t, color=c, lw=1, ls=':')
    # --- Bottom: exceedance curve with finer threshold grid (hourly) ---
        _axes[2].annotate(f'{_pct:.1f}%', xy=(t, _pct), xytext=(t + 10, _pct + 1.2), fontsize=7, color=c)
    _axes[2].set_xlim(XMIN, XMAX)
    _axes[2].set_xlabel('Spread threshold $/MWh')
    _axes[2].set_ylabel('% of hourly intervals')
    _axes[2].set_title('% of time SA–VIC spread exceeds threshold\n(proxy for binding interconnector constraint — $50+ is a practical signal)')
    _axes[2].legend(loc='upper right')
    _axes[2].grid(alpha=0.3)
    plt.tight_layout()
    plt.show()
    print('SA–VIC spread summary (hourly intervals)\n')
    print(f'  Mean spread:    {spread_hourly.mean():>8.1f} $/MWh')
    print(f'  Median spread:  {spread_hourly.median():>8.1f} $/MWh')
    print(f'  Std dev:        {spread_hourly.std():>8.1f} $/MWh')
    print()
    pos_t = np.array([0, 10, 50, 100, 200, 500])
    pos_mask = spread_hourly.values > pos_t[:, None]
    pos_n, pos_pct = (pos_mask.sum(axis=1), pos_mask.mean(axis=1) * 100)
    print('  Interconnector constraint proxy (SA > VIC by threshold):')
    for t, n, _pct in zip(pos_t, pos_n, pos_pct):
        print(f'    > ${t:>4}: {_pct:5.1f}% of intervals  ({n:>5} intervals, {n:>5} hrs)')
    neg_t = np.array([10, 50, 100, 200])
    neg_mask = spread_hourly.values < -neg_t[:, None]
    neg_n, neg_pct = (neg_mask.sum(axis=1), neg_mask.mean(axis=1) * 100)
    # --- Summary table (hourly intervals) ---
    print()
    print('  VIC > SA (negative spread, SA exporting or oversupplied):')
    for t, n, _pct in zip(neg_t, neg_n, neg_pct):
        print(f'    > ${t:>4}: {_pct:5.1f}% of intervals  ({n:>5} intervals, {n:>5} hrs)')
    return


@app.cell
def _(plt, prices_wide):
    # Regional price correlation
    # How tightly coupled are the five NEM regions?
    # Values near 1 = regions move together (interconnected, similar fuel mix)
    # Values near 0 = regions decouple (Basslink constrained for TAS, or SA islanding)
    corr = prices_wide.resample('1h').mean().corr()
    _fig, _ax = plt.subplots(figsize=(6, 5))
    _im = _ax.imshow(corr, cmap='RdYlGn', vmin=0, vmax=1)
    _ax.set_xticks(range(5))
    _ax.set_xticklabels(corr.columns, rotation=45)
    _ax.set_yticks(range(5))
    _ax.set_yticklabels(corr.index)
    for _i in range(5):
        for j in range(5):
    # Annotate each cell with the correlation value
            _ax.text(j, _i, f'{corr.iloc[_i, j]:.2f}', ha='center', va='center', fontsize=9, color='black' if corr.iloc[_i, j] > 0.5 else 'white')
    plt.colorbar(_im, label='Pearson correlation')
    _ax.set_title('Regional price correlation 2025\n(hourly means)')
    plt.tight_layout()
    plt.show()
    print(corr.to_string())
    return


@app.cell
def _(pd, plt, regions, seasons):
    missing = [r for r in regions if r not in hourly.columns]
    if missing:
        raise ValueError(f'Missing required region columns: {missing}')

    hourly = hourly[regions]

    def _corr(df: pd.DataFrame, method: str) -> pd.DataFrame:
        return df.corr(method=method).reindex(index=regions, columns=regions)

    def _plot_heatmap(ax, matrix: pd.DataFrame, title: str, vmin: float=-1, vmax: float=1):
        im = ax.imshow(matrix.values, cmap='RdYlGn', vmin=vmin, vmax=vmax)
        ax.set_xticks(range(len(regions)))
        ax.set_xticklabels(regions, rotation=45, ha='right')
        ax.set_yticks(range(len(regions)))
        ax.set_yticklabels(regions)
        ax.set_title(title, fontsize=10)
        for i in range(len(regions)):
            for j in range(len(regions)):
                value = matrix.iloc[i, j]
                color = 'black' if abs(value) < 0.6 else 'white'
                ax.text(j, i, f'{value:.2f}', ha='center', va='center', fontsize=8, color=color)
        return im

    def _print_matrix(name: str, matrix: pd.DataFrame, n_obs: int):
        symmetric = matrix.equals(matrix.T)
        diagonal_ok = (matrix.values.diagonal() == 1).all()
        print(f'\n{name} (n_obs={n_obs})')
        print(matrix.to_string(float_format=lambda x: f'{x:7.3f}'))
        print(f'  integrity: symmetric={symmetric}, diagonal_all_ones={diagonal_ok}')

    def _render_pair(section_name: str, df: pd.DataFrame):
        pearson = _corr(df, method='pearson')
        spearman = _corr(df, method='spearman')
        n_obs = len(df)

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        im = _plot_heatmap(axes[0], pearson, f'{section_name} — Pearson')
        _plot_heatmap(axes[1], spearman, f'{section_name} — Spearman')
        fig.colorbar(im, ax=axes, shrink=0.85, label='Correlation')
        fig.tight_layout()
        plt.show()

        _print_matrix(f'{section_name} — Pearson', pearson, n_obs=n_obs)
        _print_matrix(f'{section_name} — Spearman', spearman, n_obs=n_obs)

    print('\n=== Correlation Matrix Pack (Hourly) ===')

    # 1) Baseline matrices
    print('\n[1] Baseline (all intervals)')
    _render_pair('Baseline', hourly)

    # 2) Seasonal matrices
    print('\n[2] Seasonal (DJF, MAM, JJA, SON)')
    season_map = {12: 'DJF', 1: 'DJF', 2: 'DJF', 3: 'MAM', 4: 'MAM', 5: 'MAM', 6: 'JJA', 7: 'JJA', 8: 'JJA', 9: 'SON', 10: 'SON', 11: 'SON'}
    seasons['season'] = seasons.index.month.map(season_map)
    for season in ['DJF', 'MAM', 'JJA', 'SON']:
        df_season = seasons[seasons['season'] == season][regions]
        _render_pair(f'Season {season}', df_season)

    # 3) Time-of-day regime matrices
    print('\n[3] Time-of-day regimes')
    time_windows = {
        'Solar window 10:00-15:00': [10, 11, 12, 13, 14, 15],
        'Evening ramp 18:00-21:00': [18, 19, 20, 21],
        'Overnight 00:00-05:00': [0, 1, 2, 3, 4, 5],
    }
    for label, hours in time_windows.items():
        df_window = hourly[hourly.index.hour.isin(hours)]
        _render_pair(label, df_window)

    # 4) Stress-state matrices
    print('\n[4] Stress states')
    negative_mask = (hourly < 0).any(axis=1)
    _render_pair('Negative-price intervals (any region < 0)', hourly[negative_mask])

    p95_by_region = hourly.quantile(0.95)
    upper_tail_mask = hourly.ge(p95_by_region, axis=1).any(axis=1)
    _render_pair('Upper-tail intervals (any region >= regional P95)', hourly[upper_tail_mask])

    # 5) Interconnector-stress proxy matrix
    print('\n[5] Interconnector-stress proxy')
    spread = (hourly['SA1'] - hourly['VIC1']).abs()
    spread_p95 = spread.quantile(0.95)
    spread_mask = spread >= spread_p95
    print(f'  SA1-VIC1 |spread| P95 threshold: {spread_p95:.2f} $/MWh')
    _render_pair('Interconnector stress (|SA1 - VIC1| >= P95)', hourly[spread_mask])
    return (hourly,)


@app.cell
def _(plt, prices_wide):
    # Negative price frequency by hour of day
    # Negative prices occur when there is excess generation that cannot be curtailed
    # (e.g. must-run wind/solar during low-demand periods). Generators bid negative
    # to avoid being dispatched off and losing production tax credits or RPO compliance.
    # High negative price frequency in midday hours → solar-driven curtailment pressure.
    # SA and VIC should show a pronounced midday trough; QLD may differ due to solar mix.
    neg_by_hour = (prices_wide < 0).groupby(prices_wide.index.hour).mean() * 100
    _fig, _ax = plt.subplots(figsize=(12, 4))
    neg_by_hour[['SA1', 'VIC1', 'NSW1', 'QLD1']].plot(kind='bar', ax=_ax, color=['#FF9800', '#9C27B0', '#2196F3', '#4CAF50'], width=0.8)
    _ax.set_xlabel('Hour of day (0 = midnight)')
    _ax.set_ylabel('% of 5-min intervals with negative price')
    _ax.set_title('Negative price frequency by hour of day — 2025')
    _ax.legend(title='Region')
    _ax.grid(axis='y', alpha=0.3)
    _ax.set_xticklabels(range(24), rotation=0)
    plt.tight_layout()
    plt.show()
    print('\nPeak negative price hour by region:')
    for _region in ['SA1', 'VIC1', 'NSW1', 'QLD1']:
        peak_hour = neg_by_hour[_region].idxmax()
        peak_pct = neg_by_hour[_region].max()
        print(f'  {_region}: hour {peak_hour:02d}:00 — {peak_pct:.1f}% of intervals')
    return


if __name__ == "__main__":
    app.run()
