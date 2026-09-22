# Project guide

## Purpose and structure

Python analytics pipeline for predicting Formula 1 Fantasy points, optimizing lineups under budget/transfer constraints, and comparing lineup risk with Monte Carlo simulations. DuckDB at `data/database/f1_fantasy.duckdb` is the shared store.

- `src/ingestion/`: OpenF1/FastF1 ingestion, Excel fantasy points/prices, budget/team configuration, qualifying and Elo; builds raw, staged and dimension tables.
- `src/warehouse/`: driver/constructor race facts, historical pre-race features and upcoming-race features; includes table validation functions.
- `src/models/`: scikit-learn/LightGBM training, evaluation, prediction persistence and model artifacts.
- `src/optimizer/`: PuLP lineup solver, input loading and optimizer run/selection persistence.
- `src/simulation/`: historical driver residuals, sampled driver outcomes, lineup profiles and simulation persistence.
- `src/reporting/`: joins database results and exports Parquet to `data/reporting/`.
- `src/admin/`: database validation, inspection, backups and chart utilities.
- `data/raw/`: Excel inputs (`newHistPointAndPrice.xlsx`, `driver_config.xlsx`); `data/database/`: working database and backups; `model_metadata/`: saved joblib pipelines and JSON metadata.
- `notebooks (deprecated)/`, `data/deprecated/`: historical work. `src/predictions/` contains `old_*.csv` snapshots; active prediction code is in `src/models/`.

## Data flow and entry points

1. `ingestion_controller.run_pipeline(plan)` selects builds/updates: APIs and Excel → raw/staged tables → dimensions and fantasy inputs. Its checked-in `main()` enables only Elo, not the full ingestion pipeline.
2. `warehouse_controller.build_warehouse(year, race_num)` builds/validates facts, historical features and current-race features.
3. `models_controller.main()` runs `driverModel.run_driver_model()` and `constructorModel.run_constructor_model()`: historical features → training/evaluation → current-race predictions → `prediction_run`, prediction facts, performance records and model artifacts. `predictions_controller.py` contains run lookup helpers, not a pipeline CLI.
4. `pre_race_weekend_optimizer.run_optimizer_profile()` loads predictions, budget and prior lineup, then calls `teamOptimizer.optimize_team()`. `optimization_tables.py` saves results. `optimization_controller.py` is stale: it calls the absent `pre_race_weekend_optimizer_controller()`.
5. `driver_prediction_residuals.py` joins predictions to actuals; `simulation_controller.py` samples residuals, compares optimizer/benchmark profiles and saves simulation results. Lineup simulations currently aggregate driver outcomes.
6. `rpt_view_controller.main()` exports reporting Parquet files.

## Environment and commands

Run from the repository root: many database/output paths are relative to the working directory. `.python-version` specifies Python 3.14; `pyproject.toml` and `uv.lock` require Python >=3.14. Set up with `uv sync --locked`. A separate `environment.yml` defines Conda `f1_dev` on Python 3.10 (`conda env create -f environment.yml`); these configurations are not equivalent.

The following are entry-point commands, not a single unattended pipeline. Review hard-coded race/year, prediction run IDs, team name, ingestion plan and production flags first. Build/train/simulation commands write data; reporting overwrites exports.

```powershell
uv run python src/ingestion/ingestion_controller.py
uv run python src/warehouse/warehouse_controller.py
uv run python src/models/models_controller.py
uv run python -m src.optimizer.pre_race_weekend_optimizer
uv run python -m src.simulation.driver_prediction_residuals
uv run python -m src.simulation.simulation_controller
uv run python -m src.reporting.rpt_view_controller
```

Ingestion, warehouse and model controllers use sibling imports and are run as scripts; the optimizer/simulation/reporting commands above use package imports. The optimizer explicitly uses `pulp.COIN_CMD` with `C:\Users\jackg\miniconda3\envs\f1_dev\Library\bin\cbc.exe`; uv installation alone does not provision that executable.

Validation: `uv run python src/admin/validation.py` opens the existing database read-only and checks table presence, required columns, nulls, unique grains and qualifying features. Warehouse controllers also invoke their own validators. No automated test suite or test-runner configuration is present; testing notebooks/API experiments are not a unit-test suite. Do not run data-building controllers as smoke tests.

## Conventions and boundaries

- Transformations use pandas plus DuckDB SQL, with `raw_*`, `stage_*`/`staged_*`, `dim_*`, `fact_*` and feature tables. Many builders use `CREATE OR REPLACE TABLE`; updates and rebuilds have different effects.
- Preserve table grains: race facts/features use `(race_id, driver_id)` or `(race_id, constructor_id)`; predictions additionally use `prediction_run_id`. `dim_constructor` is keyed by `(year, constructor_id)`. Consult `src/admin/validation.py` for schema expectations.
- Preserve historical feature windows ending before the current row, chronological race holdouts, preprocessing pipelines and training-cutoff metadata. Keep historical/current feature schemas aligned. Current-race builders select the latest available history; do not assume they provide an as-of historical backtest.
- Preserve run IDs and links between predictions, optimizer selections and simulations. Production flags are metadata, not dry-run switches; non-production runs also persist results.
- Avoid incidental edits/regeneration of raw spreadsheets, databases/backups, model artifacts, reporting exports and old snapshots. Back up the database before intentional destructive rebuilds (`src/admin/backup_database.py` provides the helper).
- Keep new implementation in active `src/` modules; do not revive deprecated notebooks/data or refactor mixed import styles as unrelated cleanup. The ingestion controller explicitly warns against rebuilding drivers; prefer its update path for new drivers.
