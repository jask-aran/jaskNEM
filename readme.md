# jaskNEM

Analytics project on NEM data using PyPSA and related Python tooling.

## Status

The repo is set up with a `uv`-managed Python 3.11 virtual environment at `.venv`.
Project dependencies are declared in `pyproject.toml` and resolved in `uv.lock`.

## Environment setup

This repo uses `uv` with a project-local virtual environment in `.venv`.

1. Create the environment with Python 3.11:

```bash
uv venv --python 3.11 .venv
```

2. Install and lock dependencies from `pyproject.toml`:

```bash
uv sync
```

3. Activate the environment when you want an interactive shell:

```bash
source .venv/bin/activate
```

4. Start Jupyter:

```bash
jupyter notebook
```

You can also run tools without activating the environment:

```bash
uv run jupyter notebook
uv run python
```
