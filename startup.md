We're working on ToyModel.py , a Marimo Notebook based PyPSA simulation experiment series. Read Marimo Notebook , and use the deepwiki MCP to understand how best to work with PyPSA.


Start by internalising high level context and the current state of the Notebook.

**Notebook State**

[`Simulation/ToyModel.py`](/home/jask/jaskNEM/Simulation/ToyModel.py) is a marimo notebook that now operates as a staged PyPSA experiment ladder rather than a single toy dispatch example. The import/setup cell creates a shared output directory, reloads [`Simulation/pypsa_viz.py`](/home/jask/jaskNEM/Simulation/pypsa_viz.py) so helper edits are picked up in active marimo sessions, and writes PNG/CSV artifacts under [`Simulation/outputs/toy_model`](/home/jask/jaskNEM/Simulation/outputs/toy_model).

The active scenario ladder is:

1. `N1`: 24 hourly snapshots, single bus, 4 thermal units, stylized daily demand.
2. `N2`: 1 week at 30-minute resolution with black-coal maintenance derating.
3. `N3`: Thu-Sun at 10-minute resolution with solar and VIC-calibrated weekday/weekend demand.
4. `N4`: multi-unit thermal stack, ramp constraints, scarcity backstop, composite dispatch + dual price view.
5. `N5`: `N4` plus a `StorageUnit` BESS, SOC tracking, and cross-scenario thermal displacement outputs.

The current notebook presentation pattern is intentionally more uniform than before:

- one primary figure per scenario from `build_dispatch_price_figure(...)`
- one KPI/status summary block per scenario from `build_scenario_kpi_summary(...)`
- one shared market-outcomes table block per scenario via `render_market_outcomes_block(...)`
- one market-outcomes dashboard for `N3`-`N5`

The current artifact set reflects that structure:

- `results*.csv`: scenario time-series traces
- `dispatch_outcomes_*.csv` and `market_totals_*.csv`: shared economic outputs for all scenarios
- `unit_summary_*.csv` / `generator_summary*.csv` / `system_summary*.csv`: retained offline summaries where still useful
- `displacement_n5.csv` and `bess_economics_n5.csv`: specialized `N5` side analyses
- `n1_dispatch_price.png` through `n5_dispatch_soc.png`: primary scenario figures
- `n3_outcomes_dashboard.png` through `n5_outcomes_dashboard.png`: richer scenario dashboards

The notebook currently lint-checks and runs end-to-end in script mode:

- `uvx marimo check Simulation/ToyModel.py`
- `uv run Simulation/ToyModel.py`

**PyPSA Mental Model**

Use PyPSA here as a time-indexed linear dispatch model whose results are written back onto a `Network`.

- `pypsa.Network()` is the model container; components live in static tables plus time-series tables.
- `n.set_snapshots(...)` defines the operational horizon. Every time-varying input and output should align to those snapshots.
- `n.optimize(solver_name="highs")` builds and solves the linear model, then writes primal results and economically meaningful LP duals back to the network.
- `n.generators_t.p_max_pu` is the right control surface for time-dependent generator availability, which is how solar output limits and maintenance deratings are modeled in this notebook.
- `StorageUnit` behavior should be read through `storage_units_t.p_store`, `storage_units_t.p_dispatch`, and `storage_units_t.state_of_charge`.
- `ramp_limit_up` and `ramp_limit_down` are intertemporal constraints, so they can create both dispatch distortions and shadow-price spikes.
- `n.buses_t.marginal_price` is the LP shadow price of serving one more unit of demand at the bus. Treat it as economically interpretable in these LP scenarios. If unit commitment is reintroduced as MILP, do not treat the resulting duals as clean market prices.

For PyPSA questions that go beyond immediate code reading, use DeepWiki against `PyPSA/PyPSA` first. The main use cases are:

- checking how a component is meant to behave before changing the notebook model
- confirming how PyPSA interprets ramp constraints, storage dynamics, and marginal prices
- grounding modeling decisions in the current PyPSA architecture instead of memory

Typical DeepWiki questions to ask:

- “How does `Network.optimize()` write dispatch and marginal prices back to the network?”
- “How should `StorageUnit` charging, discharging, and `state_of_charge` be interpreted?”
- “How are `generators_t.p_max_pu` and ramp limits applied across snapshots?”

Use DeepWiki to understand PyPSA semantics; use the local repo to understand how this project has chosen to apply them.

**`pypsa_viz.py` Mental Model**

[`Simulation/pypsa_viz.py`](/home/jask/jaskNEM/Simulation/pypsa_viz.py) is the shared presentation and accounting layer for the notebook. It should own repeated post-processing and figure composition, not scenario design.

Its responsibilities are:

- snapshot-aware MWh accounting via `_snapshot_hours(...)`
- shared dispatch/price/SOC figure composition via `build_dispatch_price_figure(...)`
- shared market-outcomes accounting via `build_market_outcomes_tables(...)`
- shared KPI summary construction via `build_scenario_kpi_summary(...)`
- shared dashboard visualization via `build_market_outcomes_dashboard(...)`

The figure helper has two layout modes that matter operationally:

- `layout="stacked"`: standard dispatch/price/SOC stack used by `N1`, `N2`, `N3`, and `N5`
- `layout="dispatch_price_zoom"`: specialized `N4` layout with dispatch on top and full-range plus zoomed price panels below

The accounting helper is the canonical source for scenario market outputs:

- `dispatch_outcomes`: per-asset dispatched energy, activity, price capture, revenue, cost, and margin
- `market_totals`: scenario-wide demand, supply, BESS charge/discharge totals, and price KPIs

The mental boundary to keep clear is:

- [`Simulation/ToyModel.py`](/home/jask/jaskNEM/Simulation/ToyModel.py) owns scenario assumptions, network construction, narrative interpretation, and specialized side analyses
- [`Simulation/pypsa_viz.py`](/home/jask/jaskNEM/Simulation/pypsa_viz.py) owns reusable figures, reusable summary tables, and reusable accounting logic

If a new scenario needs a different demand shape, fleet, or constraint, change the notebook. If multiple scenarios need the same style of figure, KPI table, or market-outcomes calculation, extend `pypsa_viz.py`.
