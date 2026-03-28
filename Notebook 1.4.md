# Notebook 1.4 — Interconnector Flows

## Summary

Create a new notebook, `Interconnector_Flows.ipynb`, that explains how interconnectors smooth prices when unconstrained and how regional prices separate when transfer capability becomes operationally tight. Keep the notebook in the realised-outcomes lane: use cached `DISPATCHINTERCONNECTORRES`, `DISPATCHPRICE`, and `DISPATCHREGIONSUM` only, with no exact binding-constraint attribution in the core workflow.

Use the full currently cached span, `2025-01-01` to `2026-02-28`, since the relevant tables are small enough to handle lazily in Polars (`DISPATCHINTERCONNECTORRES` is ~786k rows). The headline focus remains on `V-SA` and `T-V-MNSP1`, matching the learning plan.

## Key Changes

### Notebook structure
- Reuse the helper pattern already established in [Price_Spike_Autopsy.ipynb](/home/jask/jaskNEM/Price_Spike_Autopsy.ipynb): `cache_files(...)`, `with_interval_end(...)`, registration-style setup, and Polars lazy scans from `data/nemosis_cache`.
- Load:
  - `DISPATCHINTERCONNECTORRES` with `INTERVENTION = 0`
  - `DISPATCHPRICE` with `INTERVENTION = 0`
  - `DISPATCHREGIONSUM` with `INTERVENTION = 0`
- Parse `SETTLEMENTDATE` to `interval_end` and derive a single joined analysis frame for each target interconnector.

### Analysis frame / interfaces
- Build a notebook-local normalized dataset with these columns:
  - `interval_end`
  - `interconnector_id`
  - `mw_flow`
  - `abs_flow`
  - `observed_abs_max_mw`
  - `utilisation_proxy`
  - `region_a`, `region_b`
  - `rrp_a`, `rrp_b`
  - `price_spread`
  - `abs_price_spread`
  - `net_interchange_a`, `net_interchange_b`
- Region mapping is fixed:
  - `V-SA` -> `VIC1` vs `SA1`
  - `T-V-MNSP1` -> `TAS1` vs `VIC1`
- Define:
  - `price_spread = rrp_a - rrp_b`
  - `utilisation_proxy = abs(mw_flow) / observed_abs_max_mw`
- Use `MWFLOW` as the canonical realised flow field. Mention `METEREDMWFLOW` only as a note, not a parallel analysis path.
- Exclude `V-S-MNSP1` from the core notebook to keep 1.4 aligned with the stated scope; add one short markdown note that additional interconnector IDs exist in cache but are intentionally deferred.

### Notebook sections and outputs
- Opening markdown:
  - Explain what an interconnector does.
  - State the key limitation clearly: local `nemosis` parquet does not preserve raw `EXPORTLIMIT` / `IMPORTLIMIT`, so “utilisation” is an observed-max proxy, not true limit utilisation.
- Section 1: Flow overview
  - Summary table per interconnector: min flow, max flow, median absolute flow, observed-max proxy, share of intervals with reverse flow, share of intervals above 80% proxy utilisation.
  - One compact time-series panel using a short representative slice for intuition:
    - `V-SA`: reuse the 2026-01-26 SA event window from 1.3
    - `T-V-MNSP1`: choose the day with the largest absolute `TAS1-VIC1` spread in the sample
- Section 2: Flow duration curves
  - Signed flow duration curve for each interconnector to show dominant direction and reversals.
  - Absolute-flow duration curve using `utilisation_proxy` to show how often each link runs near its observed envelope.
- Section 3: Price separation vs flow tightness
  - For each interconnector, plot `abs_price_spread` versus `utilisation_proxy` using a hexbin or density-style scatter to avoid overplotting.
  - Add a binned line or median-by-decile overlay so the relationship is readable.
  - Include a second view with signed `price_spread` vs signed `mw_flow` to show directional asymmetry.
- Section 4: Regional context cross-check
  - Plot `NETINTERCHANGE` from `DISPATCHREGIONSUM` against interconnector flow for the same connected regions to reinforce how regional import/export conditions align with the interconnector story.
- Section 5: Findings
  - End with 5-7 concise markdown findings, written as analyst takeaways, not a memo.
  - Final note should explicitly hand off exact binding explanation to Notebook 1.5.

### Scope boundaries
- No downloader changes are required for 1.4 planning or implementation because the required cached parquet files already exist locally.
- No `DISPATCHCONSTRAINT` / `GENCONDATA` logic in the main analysis path.
- No attempt to infer true transfer limits from observed maxima beyond clearly-labeled proxy charts.

## Test Plan

- Notebook executes end-to-end against the current local cache without requiring new downloads.
- Schema checks pass for the three input tables and timestamp parsing produces no null `interval_end` values.
- Joins produce complete price pairs for both target interconnectors with no duplicate interval rows.
- Summary tables and duration curves render for both `V-SA` and `T-V-MNSP1`.
- The spotlight event logic works:
  - `V-SA` uses the fixed 2026-01-26 window from Notebook 1.3
  - `T-V-MNSP1` selects the highest absolute TAS-VIC spread day mechanically from the sample
- Final findings reference only realised flow behaviour and price separation, with no accidental claim of exact binding attribution.

## Assumptions And Defaults

- Use the full currently cached date span because table sizes are tractable.
- Use Polars lazy scanning and push projections/filters early.
- Treat `MWFLOW` as the primary flow series.
- “Utilisation” in this notebook always means observed-max proxy utilisation, never actual transfer-limit utilisation.
- Keep 1.4 as a clean market-structure notebook; exact constraint attribution remains the explicit purpose of Notebook 1.5.
