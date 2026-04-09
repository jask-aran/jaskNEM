# jaskNEM

Research and simulation workspace for Australia’s National Electricity Market (NEM).

This repo combines two complementary workflows:

1. **data-first market analysis** using AEMO / MMS-style datasets and notebooks
2. **dispatch and pricing simulation** using PyPSA to build intuition and test counterfactuals

The project is aimed at understanding how NEM prices form, what drives volatility and scarcity, how constraints and dispatch shape outcomes, and how simplified market models compare with real observed data.

---

## What this repo does

There are two main tracks.

### 1) Market research notebooks
These notebooks explore real market outcomes from NEM data, including topics like:
- regional prices
- generator dispatch
- price spikes
- interconnector flows
- constraint effects

Primary notebook directory:
- `Market Research/`

Current notebooks include:
- `Notebook 1.1 - Price Explorer.ipynb`
- `Notebook 1.2 - Generator Dispatch Explorer.ipynb`
- `Notebook 1.3 - Price Spike Autopsy.ipynb`
- `Notebook 1.4 - Interconnector Flows.ipynb`
- `Notebook 1.5 - Constraint Binding Attribution.ipynb`

Some notebooks also have companion markdown summaries beside them.

### 2) PyPSA simulation work
This track builds simplified dispatch models that explain market pricing mechanics from first principles.

Primary simulation files:
- `Simulation/ToyModel.py` — marimo notebook for staged PyPSA experiments
- `Simulation/pypsa_viz.py` — shared plotting, KPI, and market-accounting helpers

The simulation ladder currently progresses from a simple single-bus merit-order model through demand shaping, renewables, ramp limits, scarcity pricing, and storage.

---

## Project goals

The repo is building toward a workflow that can answer questions such as:
- What drives short-lived price spikes versus sustained scarcity episodes?
- How do interconnector limits and constraints affect regional prices?
- What revenue profile do solar, wind, thermal, and storage assets earn?
- How far can simplified competitive dispatch models explain observed NEM outcomes?
- What changes when storage, outages, transmission, or fuel costs shift?

The medium-term goal is not just descriptive analysis, but a credible bridge from:
- **observed market data**
- to **interpretable dispatch models**
- to **counterfactual scenarios**

---

## Repository layout

```text
.
├── Market Research/              # Jupyter notebooks for NEM data analysis
├── Simulation/                   # PyPSA + marimo simulation experiments
│   ├── ToyModel.py               # Main marimo notebook / scenario ladder
│   ├── pypsa_viz.py              # Shared visualization and accounting helpers
│   └── outputs/toy_model/        # Generated simulation figures and CSV outputs
├── data/
│   ├── nemosis_cache/            # Cached market data
│   └── reference/                # Reference tables and derived supporting data
├── import_nem_data.py            # Data ingestion / cache-building entry point
├── build_market_price_reference.py
├── ideas.md                      # Research backlog and staging notes
├── startup.md                    # Working notes for current simulation workflow
├── pyproject.toml                # Project dependencies
└── uv.lock                       # Locked dependency set
```

---

## Environment setup

This project uses [`uv`](https://github.com/astral-sh/uv) and targets **Python 3.11**.

### 1. Create the environment

```bash
uv venv --python 3.11 .venv
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Activate the environment if desired

```bash
source .venv/bin/activate
```

You can also run commands without activating the environment by prefixing them with `uv run`.

---

## Core commands

### Start Jupyter

```bash
uv run jupyter notebook
```

### Build the core NEM cache

```bash
uv run python import_nem_data.py --core
```

### Refresh derived market price reference data

```bash
uv run python build_market_price_reference.py
```

### Run a Python REPL in the project environment

```bash
uv run python
```

---

## Notebook workflows

This repo uses two different notebook styles.

### Jupyter notebooks (`.ipynb`)
Used for the `Market Research/` analyses.

Project convention:
- use the local notebook files directly
- avoid unnecessary metadata churn
- keep outputs and markdown aligned with the actual analysis

### Marimo notebooks (`.py`)
Used for simulation work such as `Simulation/ToyModel.py`.

After modifying a marimo notebook, the expected checks are:

```bash
uvx marimo check Simulation/ToyModel.py
uv run Simulation/ToyModel.py
```

Running in script mode verifies that all cells execute cleanly and that expected outputs are written.

---

## Simulation track: ToyModel

`Simulation/ToyModel.py` is the current PyPSA learning and experimentation notebook.

It is structured as a staged scenario ladder rather than a single toy example. The current scenarios build up complexity through:
- single-bus dispatch
- higher-resolution demand traces
- renewable availability
- maintenance derating
- multi-unit thermal stacks
- ramp constraints
- scarcity backstop pricing
- storage behavior and state of charge

Outputs are written under:
- `Simulation/outputs/toy_model/`

Typical generated artifacts include:
- scenario result CSVs
- dispatch and market-outcomes tables
- KPI summaries
- scenario figures
- storage displacement / economics side tables

`Simulation/pypsa_viz.py` is the shared presentation layer and should hold reusable:
- figure composition
- KPI summaries
- dispatch accounting
- market-outcomes tables
- dashboard generation

Scenario assumptions and model construction should remain in `ToyModel.py`.

---

## Data track: market research notebooks

The `Market Research/` notebooks are the main exploratory analysis surface for real NEM data.

A reasonable reading order is:
1. **Notebook 1.1 - Price Explorer**
2. **Notebook 1.2 - Generator Dispatch Explorer**
3. **Notebook 1.3 - Price Spike Autopsy**
4. **Notebook 1.4 - Interconnector Flows**
5. **Notebook 1.5 - Constraint Binding Attribution**

Together they move from broad orientation toward more causal explanations of market outcomes.

Planned next step:
- **Notebook 1.6 — Price Cap and Scarcity Episodes**

That notebook is intended to systematically identify intervals where prices hit the effective market cap, cluster those into episodes, and create a reusable event-discovery workflow for deeper follow-up analysis.

---

## Current analytical roadmap

The working roadmap is roughly:

### Stage 1 — NEM data exploration
Build intuition from actual market data:
- prices
- dispatch
- flows
- constraints
- scarcity episodes
- asset-level revenue and capture-price patterns

### Stage 2 — PyPSA models
Build simplified but interpretable dispatch models that show:
- merit order pricing
- renewable suppression of prices
- ramp-driven scarcity
- storage arbitrage
- transmission congestion and price separation

### Stage 3 — Counterfactual market questions
Use calibrated models to test scenarios like:
- gas cost shocks
- major asset retirements
- storage expansion
- interconnector additions
- system configuration changes

---

## Working principles

A few conventions guide the repo:

- **Use `uv` for environment and execution tasks**
- **Keep exploratory clutter out of the repo root where possible**
- **Preserve notebook readability and narrative continuity**
- **Prefer reusable helper functions when logic starts repeating**
- **Treat PyPSA as an explanatory dispatch model first, then a counterfactual tool**

For PyPSA specifically, the core mental model is:
- a `Network` contains components and time series
- snapshots define the operational horizon
- `optimize()` solves the dispatch problem
- bus marginal prices are shadow prices of energy balance constraints

That makes the simulation work useful not just for charts, but for understanding price formation mechanically.

---

## Data hygiene

Please avoid committing:
- large generated cache files
- secrets
- scratch exports
- accidental notebook output noise

Key durable data locations are:
- `data/nemosis_cache/`
- `data/reference/`

Generated simulation outputs should live under the relevant output folder, currently:
- `Simulation/outputs/toy_model/`

---

## Recommended starting points

If you are new to the repo:

### To understand the real-data analysis
Start with:
- `Market Research/Notebook 1.1 - Price Explorer.ipynb`
- then proceed through `Notebook 1.5`

### To understand the modeling / simulation side
Start with:
- `startup.md`
- `Simulation/ToyModel.py`
- `Simulation/pypsa_viz.py`

### To understand the project backlog and next questions
Read:
- `ideas.md`

---

## Status

This is an active research workspace rather than a polished package.

What is already in place:
- a working `uv` environment
- real-data analysis notebooks
- a growing reference-data pipeline
- a structured PyPSA toy-model ladder
- shared simulation visualization and accounting helpers

What is still evolving:
- stronger extraction of reusable logic from notebooks
- more formal testing of accounting/reference logic
- clearer output discipline
- calibration of simplified models against real NEM periods
- next-stage notebooks and counterfactual scenario studies

---

## Future directions

High-value near-term directions include:
- Notebook 1.6 on price-cap and scarcity episodes
- forecast error analysis
- solar and wind revenue profile analysis
- better model-vs-reality calibration
- richer multi-region PyPSA scenarios
- gas-price-shock scenario work

---

## License / usage

No formal license is declared yet in this repository.

Until one is added, treat the repo as private working research code.
