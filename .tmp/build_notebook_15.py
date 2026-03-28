import json
from pathlib import Path


def md(text: str):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.strip("\n").splitlines(keepends=True),
    }


def code(text: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True),
    }


cells = [
    md(
        """
# Constraint Binding Attribution (Notebook 1.5)

This notebook is a direct extension of the **2026-01-26 SA1 Price Spike Autopsy** case study.

Goal: identify which constraints carried non-zero marginal value during the event, when they were active, and how that lined up with SA-VIC price separation and `V-SA` flow.

Scope note:
- This is an interval-level binding attribution notebook.
- It does not attempt full NEMDE equation decomposition.
- Constraint identification context here comes from event-period `DISPATCHCONSTRAINT` fields (`CONSTRAINTID`, `GENCONID_EFFECTIVEDATE`, `GENCONID_VERSIONNO`).
        """
    ),
    code(
        """
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
from IPython.display import Markdown, display

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (14, 6)
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['figure.dpi'] = 120

PROJECT_ROOT = Path.cwd()
CACHE_DIR = PROJECT_ROOT / 'data' / 'nemosis_cache'
TS_FORMAT = '%Y/%m/%d %H:%M:%S'

EVENT_START = pl.datetime(2026, 1, 25, 0, 0)
EVENT_END = pl.datetime(2026, 1, 27, 0, 0)

SA_REGION = 'SA1'
VIC_REGION = 'VIC1'
INTERCONNECTOR_ID = 'V-SA'
        """
    ),
    code(
        """
def cache_files(table_name: str) -> list[str]:
    files = sorted(CACHE_DIR.glob(f'PUBLIC_*#{table_name}#FILE01#*.parquet'))
    if not files:
        raise FileNotFoundError(f'No parquet files found for {table_name} under {CACHE_DIR}')
    return [str(path) for path in files]


def scan_selected(table_name: str, columns: list[str]) -> pl.LazyFrame:
    return pl.concat(
        [pl.scan_parquet(path).select(columns) for path in cache_files(table_name)],
        how='diagonal_relaxed',
    )


def with_interval_end(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.with_columns(
        pl.col('SETTLEMENTDATE').str.strptime(pl.Datetime, format=TS_FORMAT, strict=False).alias('interval_end')
    )


def constraint_family_expr() -> pl.Expr:
    return (
        pl.col('constraint_id')
        .str.extract(r'^([^+]+)', 1)
        .fill_null(pl.col('constraint_id'))
        .alias('constraint_family')
    )
        """
    ),
    md(
        """
## Data Preflight

Confirm required files and columns exist for this case window.
        """
    ),
    code(
        """
required = {
    'DISPATCHCONSTRAINT': [
        'SETTLEMENTDATE', 'INTERVENTION', 'CONSTRAINTID', 'RHS', 'LHS',
        'MARGINALVALUE', 'VIOLATIONDEGREE', 'GENCONID_EFFECTIVEDATE', 'GENCONID_VERSIONNO',
    ],
    'DISPATCHPRICE': ['SETTLEMENTDATE', 'INTERVENTION', 'REGIONID', 'RRP'],
    'DISPATCHREGIONSUM': ['SETTLEMENTDATE', 'INTERVENTION', 'REGIONID', 'NETINTERCHANGE'],
    'DISPATCHINTERCONNECTORRES': ['SETTLEMENTDATE', 'INTERVENTION', 'INTERCONNECTORID', 'MWFLOW'],
}

rows = []
for table, cols in required.items():
    files = cache_files(table)
    schema = scan_selected(table, cols).collect_schema().names()
    missing_cols = [c for c in cols if c not in schema]

    lf = with_interval_end(scan_selected(table, cols)).filter(
        pl.col('interval_end').is_between(EVENT_START, EVENT_END, closed='left')
    )
    if table in ('DISPATCHPRICE', 'DISPATCHREGIONSUM'):
        lf = lf.filter((pl.col('INTERVENTION') == 0) & pl.col('REGIONID').is_in([SA_REGION, VIC_REGION]))
    elif table == 'DISPATCHINTERCONNECTORRES':
        lf = lf.filter((pl.col('INTERVENTION') == 0) & (pl.col('INTERCONNECTORID') == INTERCONNECTOR_ID))
    else:
        lf = lf.filter(pl.col('INTERVENTION') == 0)

    stats = lf.select([
        pl.len().alias('rows_in_window'),
        pl.col('interval_end').min().alias('min_interval_end'),
        pl.col('interval_end').max().alias('max_interval_end'),
    ]).collect().row(0, named=True)

    rows.append({
        'table': table,
        'files_found': len(files),
        'missing_columns': ', '.join(missing_cols) if missing_cols else '',
        **stats,
    })

preflight = pl.DataFrame(rows)
display(preflight)

if preflight.filter(pl.col('rows_in_window') == 0).height > 0:
    raise ValueError('One or more required tables has zero rows in the event window.')
if preflight.filter(pl.col('missing_columns') != '').height > 0:
    raise ValueError('One or more required tables is missing required columns.')
        """
    ),
    md(
        """
## Section 1: Event Recap

Recreate the SA/VIC price and `V-SA` flow context for the exact 48-hour event window.
        """
    ),
    code(
        """
price_long = (
    with_interval_end(scan_selected('DISPATCHPRICE', ['SETTLEMENTDATE', 'INTERVENTION', 'REGIONID', 'RRP']))
    .filter(
        pl.col('interval_end').is_between(EVENT_START, EVENT_END, closed='left')
        & (pl.col('INTERVENTION') == 0)
        & pl.col('REGIONID').is_in([SA_REGION, VIC_REGION])
    )
    .select(['interval_end', 'REGIONID', 'RRP'])
    .collect()
)

price_wide = (
    price_long
    .pivot(index='interval_end', on='REGIONID', values='RRP')
    .rename({SA_REGION: 'rrp_sa', VIC_REGION: 'rrp_vic'})
    .with_columns([
        (pl.col('rrp_sa') - pl.col('rrp_vic')).alias('price_spread'),
        (pl.col('rrp_sa') - pl.col('rrp_vic')).abs().alias('abs_price_spread'),
    ])
    .sort('interval_end')
)

net_interchange = (
    with_interval_end(scan_selected('DISPATCHREGIONSUM', ['SETTLEMENTDATE', 'INTERVENTION', 'REGIONID', 'NETINTERCHANGE']))
    .filter(
        pl.col('interval_end').is_between(EVENT_START, EVENT_END, closed='left')
        & (pl.col('INTERVENTION') == 0)
        & pl.col('REGIONID').is_in([SA_REGION, VIC_REGION])
    )
    .select(['interval_end', 'REGIONID', 'NETINTERCHANGE'])
    .collect()
    .pivot(index='interval_end', on='REGIONID', values='NETINTERCHANGE')
    .rename({SA_REGION: 'sa_net_interchange', VIC_REGION: 'vic_net_interchange'})
)

v_sa_flow = (
    with_interval_end(scan_selected('DISPATCHINTERCONNECTORRES', ['SETTLEMENTDATE', 'INTERVENTION', 'INTERCONNECTORID', 'MWFLOW']))
    .filter(
        pl.col('interval_end').is_between(EVENT_START, EVENT_END, closed='left')
        & (pl.col('INTERVENTION') == 0)
        & (pl.col('INTERCONNECTORID') == INTERCONNECTOR_ID)
    )
    .select(['interval_end', pl.col('MWFLOW').alias('v_sa_mw_flow')])
    .collect()
)

market_context = (
    price_wide
    .join(v_sa_flow, on='interval_end', how='left')
    .join(net_interchange, on='interval_end', how='left')
    .sort('interval_end')
)

peak_sa = market_context.sort('rrp_sa', descending=True).row(0, named=True)

event_summary = pl.DataFrame([
    {'metric': 'SA peak price ($/MWh)', 'value': f"{peak_sa['rrp_sa']:,.0f}"},
    {'metric': 'Peak interval end', 'value': str(peak_sa['interval_end'])},
    {'metric': 'VIC price at SA peak ($/MWh)', 'value': f"{peak_sa['rrp_vic']:,.0f}"},
    {'metric': 'SA-VIC spread at SA peak ($/MWh)', 'value': f"{peak_sa['price_spread']:,.0f}"},
    {'metric': 'V-SA flow at SA peak (MW)', 'value': f"{peak_sa['v_sa_mw_flow']:,.0f}"},
])

display(event_summary)
        """
    ),
    code(
        """
ctx_pd = market_context.to_pandas()
peak_ts = pd.Timestamp(peak_sa['interval_end'])

fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True, height_ratios=[1.5, 1.0])

axes[0].plot(ctx_pd['interval_end'], ctx_pd['rrp_sa'], color='#b91c1c', linewidth=2.0, label='SA1 RRP')
axes[0].plot(ctx_pd['interval_end'], ctx_pd['rrp_vic'], color='#1d4ed8', linewidth=1.8, label='VIC1 RRP')
ax_spread = axes[0].twinx()
ax_spread.plot(ctx_pd['interval_end'], ctx_pd['price_spread'], color='#7c3aed', linewidth=1.4, alpha=0.8, label='SA-VIC spread')

axes[0].axvline(peak_ts, color='black', linestyle='--', linewidth=1)
axes[0].set_ylabel('RRP ($/MWh)')
ax_spread.set_ylabel('Spread ($/MWh)')
axes[0].set_title('Event context: SA/VIC prices and spread')
axes[0].legend(loc='upper left')
ax_spread.legend(loc='upper right')

axes[1].plot(ctx_pd['interval_end'], ctx_pd['v_sa_mw_flow'], color='#0f766e', linewidth=2.0)
axes[1].axhline(0, color='black', linewidth=0.8, alpha=0.6)
axes[1].axvline(peak_ts, color='black', linestyle='--', linewidth=1)
axes[1].set_title('V-SA interconnector flow (MW)')
axes[1].set_ylabel('MW')
axes[1].set_xlabel('Interval end')
axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b\\n%H:%M'))

fig.tight_layout()
plt.show()
        """
    ),
    md(
        """
## Section 2: Constraint Activity Scan

Build an interval-level event frame and rank constraints by active frequency and marginal-value intensity.
        """
    ),
    code(
        """
constraint_event = (
    with_interval_end(
        scan_selected(
            'DISPATCHCONSTRAINT',
            [
                'SETTLEMENTDATE', 'INTERVENTION', 'CONSTRAINTID',
                'MARGINALVALUE', 'VIOLATIONDEGREE', 'RHS', 'LHS',
                'GENCONID_EFFECTIVEDATE', 'GENCONID_VERSIONNO',
            ],
        )
    )
    .filter(
        pl.col('interval_end').is_between(EVENT_START, EVENT_END, closed='left')
        & (pl.col('INTERVENTION') == 0)
    )
    .select([
        'interval_end',
        pl.col('CONSTRAINTID').alias('constraint_id'),
        pl.col('MARGINALVALUE').alias('marginal_value'),
        pl.col('VIOLATIONDEGREE').alias('violation_degree'),
        pl.col('RHS').alias('rhs'),
        pl.col('LHS').alias('lhs'),
        pl.col('GENCONID_EFFECTIVEDATE').alias('gencon_effective_date'),
        pl.col('GENCONID_VERSIONNO').alias('gencon_version_no'),
    ])
    .collect()
    .with_columns([
        constraint_family_expr(),
        pl.col('marginal_value').abs().alias('abs_marginal_value'),
        (pl.col('marginal_value') != 0).alias('binding_candidate'),
    ])
)

event_frame = (
    constraint_event
    .join(market_context, on='interval_end', how='left')
    .with_columns([
        pl.lit(VIC_REGION).alias('region_a'),
        pl.lit(SA_REGION).alias('region_b'),
        pl.col('rrp_vic').alias('rrp_a'),
        pl.col('rrp_sa').alias('rrp_b'),
        pl.concat_str(
            [
                pl.col('constraint_id'),
                pl.lit('|'),
                pl.col('gencon_effective_date').cast(pl.String),
                pl.lit('|v'),
                pl.col('gencon_version_no').cast(pl.String),
            ]
        ).alias('constraint_fingerprint'),
    ])
)

constraint_summary = (
    event_frame
    .filter(pl.col('binding_candidate'))
    .group_by(['constraint_id', 'constraint_family', 'gencon_effective_date', 'gencon_version_no'])
    .agg([
        pl.len().alias('active_intervals'),
        pl.max('abs_marginal_value').alias('peak_abs_marginal_value'),
        pl.sum('abs_marginal_value').alias('cumulative_abs_marginal_value'),
    ])
    .sort('cumulative_abs_marginal_value', descending=True)
)

display(constraint_summary.head(10))
        """
    ),
    code(
        """
top10 = constraint_summary.head(10).to_pandas()

fig, ax = plt.subplots(figsize=(12, 5.5))
ax.barh(
    top10['constraint_id'][::-1],
    top10['cumulative_abs_marginal_value'][::-1],
    color='#1f2937',
)
ax.set_title('Top 10 constraints by cumulative absolute marginal value')
ax.set_xlabel('Cumulative |marginal value|')
ax.set_ylabel('Constraint ID')
fig.tight_layout()
plt.show()
        """
    ),
    md(
        """
## Section 3: Binding Timeline

Track dominant constraints through time and compare against price spread dynamics.
        """
    ),
    code(
        """
top_ids = constraint_summary.head(5)['constraint_id'].to_list()
peak_interval = peak_sa['interval_end']

timeline_pd = (
    event_frame
    .filter(pl.col('constraint_id').is_in(top_ids))
    .select(['interval_end', 'constraint_id', 'abs_marginal_value'])
    .to_pandas()
)

spread_pd = market_context.select(['interval_end', 'price_spread']).to_pandas()

fig, ax = plt.subplots(figsize=(15, 6.5))
for cid in top_ids:
    cdf = timeline_pd[timeline_pd['constraint_id'] == cid].sort_values('interval_end')
    ax.plot(cdf['interval_end'], cdf['abs_marginal_value'], linewidth=1.8, label=cid)

ax2 = ax.twinx()
ax2.plot(spread_pd['interval_end'], spread_pd['price_spread'], color='#111827', linewidth=1.6, alpha=0.6, label='SA-VIC spread')

ax.axvline(pd.Timestamp(peak_interval), color='black', linestyle='--', linewidth=1)
ax.set_title('Top constraint activity timeline with spread overlay')
ax.set_ylabel('|Marginal value|')
ax2.set_ylabel('SA-VIC spread ($/MWh)')
ax.set_xlabel('Interval end')
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\\n%H:%M'))

lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', ncol=2)

fig.tight_layout()
plt.show()

active_at_peak = (
    event_frame
    .filter((pl.col('interval_end') == peak_interval) & pl.col('binding_candidate'))
    .sort('abs_marginal_value', descending=True)
    .select([
        'interval_end', 'constraint_id', 'marginal_value', 'violation_degree',
        'gencon_effective_date', 'gencon_version_no',
    ])
)

display(active_at_peak)
        """
    ),
    md(
        """
## Section 4: Constraint Identity For This Case Study

Show reproducible event fingerprints (`CONSTRAINTID` + `GENCONID_EFFECTIVEDATE` + `GENCONID_VERSIONNO`) for dominant constraints.
        """
    ),
    code(
        """
identity_catalog = (
    constraint_summary
    .select([
        'constraint_id', 'constraint_family',
        'gencon_effective_date', 'gencon_version_no',
        'active_intervals', 'peak_abs_marginal_value', 'cumulative_abs_marginal_value',
    ])
    .head(15)
)

display(identity_catalog)
        """
    ),
    md(
        """
## Section 5: Constraint-To-Market Linkage

Inspect the dominant constraint against spread intensity and summarize top spike intervals with active constraints.
        """
    ),
    code(
        """
dominant = constraint_summary.row(0, named=True)
dominant_id = dominant['constraint_id']

dominant_df = (
    event_frame
    .filter(pl.col('constraint_id') == dominant_id)
    .select(['interval_end', 'abs_price_spread', 'abs_marginal_value'])
    .to_pandas()
    .sort_values('interval_end')
)

fig, ax = plt.subplots(figsize=(9, 6))
hb = ax.hexbin(
    dominant_df['abs_price_spread'],
    dominant_df['abs_marginal_value'],
    gridsize=36,
    cmap='YlOrRd',
    mincnt=1,
    bins='log',
)
ax.set_title(f'Dominant constraint linkage: {dominant_id}')
ax.set_xlabel('Absolute SA-VIC spread ($/MWh)')
ax.set_ylabel('Absolute marginal value')
fig.colorbar(hb, ax=ax, label='log10(count)')
fig.tight_layout()
plt.show()

interval_constraint_top = (
    event_frame
    .filter(pl.col('binding_candidate'))
    .sort(['interval_end', 'abs_marginal_value'], descending=[False, True])
    .group_by('interval_end')
    .agg([
        pl.col('constraint_id').head(3).alias('top_constraint_ids'),
        pl.col('marginal_value').head(3).alias('top_marginal_values'),
    ])
    .with_columns([
        pl.col('top_constraint_ids').list.join(', ').alias('top_constraint_ids'),
        pl.col('top_marginal_values').list.eval(pl.element().round(2).cast(pl.String)).list.join(', ').alias('top_marginal_values'),
    ])
)

top_spike_intervals = (
    market_context
    .sort('rrp_sa', descending=True)
    .head(12)
    .select(['interval_end', 'rrp_sa', 'rrp_vic', 'price_spread', 'v_sa_mw_flow'])
    .join(interval_constraint_top, on='interval_end', how='left')
    .sort('interval_end')
)

display(top_spike_intervals)
        """
    ),
    md(
        """
## Section 6: Findings

Concise analyst takeaways for this event.
        """
    ),
    code(
        """
peak_active_count = active_at_peak.height

binding_only = event_frame.filter(pl.col('binding_candidate'))
dominant_share = (
    binding_only
    .with_columns((pl.col('constraint_id') == dominant_id).alias('is_dominant'))
    .select(pl.mean('is_dominant').alias('dominant_share'))
    .item()
)

max_spread = market_context.select(pl.max('abs_price_spread')).item()
max_flow = market_context.select(pl.max('v_sa_mw_flow')).item()
min_flow = market_context.select(pl.min('v_sa_mw_flow')).item()

findings_md = f"""
### Analyst Takeaways

- The event window produced a reproducible set of binding candidates directly from `DISPATCHCONSTRAINT`, without requiring external metadata tables.
- The dominant constraint by cumulative absolute marginal value was **{dominant_id}**.
- At the SA price peak interval (**{peak_sa['interval_end']}**), there were **{peak_active_count}** active non-zero-marginal constraints.
- SA-VIC separation reached about **${max_spread:,.0f}/MWh** while `V-SA` flow ranged from **{min_flow:,.0f} MW** to **{max_flow:,.0f} MW** over the same case window.
- The dominant constraint accounted for about **{dominant_share * 100:.1f}%** of active constraint-interval observations in this event.
- Realised interconnector tightness (flow/spread behavior) and named binding constraints (`DISPATCHCONSTRAINT`) are complementary signals; they should not be treated as the same evidence type.
- This notebook supports interval-level attribution for the case study, but not full NEMDE equation decomposition or exact physical mechanism reconstruction.
"""

display(Markdown(findings_md))
        """
    ),
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = Path('Constraint_Binding_Attribution.ipynb')
out.write_text(json.dumps(nb, indent=2))
print(f'Wrote {out} with {len(cells)} cells')
