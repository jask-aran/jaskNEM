@marimo.md

# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python 3.11 analytics workspace for National Electricity Market research. Top-level scripts such as `import_nem_data.py` and `build_market_price_reference.py` handle data ingestion and reference-data preparation. Research notebooks live in `Market Research/` and are the main analysis surface. Cached data and supporting reference files belong under `data/`, especially `data/nemosis_cache/` and `data/reference/`. Keep exploratory outputs out of the repo unless they are durable project artifacts.

## Build, Test, and Development Commands

Use `uv` for all environment and execution tasks:

- `uv sync` installs the locked dependencies from `pyproject.toml` and `uv.lock`.
- `uv run jupyter notebook` starts the notebook environment against the project virtualenv.
- `uv run python import_nem_data.py --core` builds the core NEM parquet cache in `data/nemosis_cache/`.
- `uv run python build_market_price_reference.py` refreshes derived market reference data.

If `.venv` does not exist yet, create it with `uv venv --python 3.11 .venv`.

## Coding Style & Naming Conventions

Follow existing Python style in the scripts and notebooks: 4-space indentation, descriptive snake_case names, and small helper functions for reusable logic. Prefer clear pandas or polars transformations over dense one-liners. Name notebooks with the established pattern `Notebook X.Y - Topic.ipynb`; keep related markdown summaries beside them when useful, for example `Market Research/Notebook 1.5.md`.

## Data & Notebook Hygiene

Do not commit large generated cache files, secrets, or ad hoc exports from `data/nemosis_cache/`. Preserve user notebook work: avoid broad metadata churn, clear obviously accidental output noise, and keep narrative markdown aligned with the analysis actually shown in the notebook.
