# Repository Guidelines

## Marimo Notebooks

When working with **or answering questions about** Marimo `.py` notebooks, invoke the `marimo-notebook` skill first. (Obtained via Skills.sh)

After modifying a marimo notebook, always:
1. Run `uvx marimo check <notebook.py>` to lint for common mistakes.
2. Run `uv run <notebook.py>` in script mode to execute all cells and verify outputs. Read any saved PNGs or CSVs from the notebook's output directory to inspect results.

## Working with Jupyter Notebooks (.ipynb files)

When the user asks to read, edit, execute, or work with `.ipynb` files, use the notebook-cli skill, which provides the `nb` command-line tool.

Use `nb` in local file mode only. Do not use the built-in Read/Write tools for `.ipynb` files. Do not run `nb connect`, do not attempt to connect `nb` to a Jupyter server or kernel, and do not rely on remote/live collaboration features for notebook edits or execution. Prefer direct local notebook file operations with `nb`.

(Obtained via https://github.com/jupyter-ai-contrib/nb-cli)


## Working with PyPSA
Use the DeepWiki MCP to query the PyPSA github repo to understand implemenation. https://deepwiki.com/PyPSA/PyPSA


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
