import pandas as pd
import numpy as np
import duckdb

from src.optimizer import teamOptimizer

DATABASE_PATH = "data/database/f1_fantasy.duckdb"

DEFAULT_OPTIMIZER_SETTINGS = {
    "free_transfers_avail": 2,
    "points_col": "predicted_points",
    "n_drivers": 5,
    "n_constructors": 2,
    "max_drivers_per_team": None,
    "use_drs": True,
    "drs_multiplier": 2.0,
    "solver_msg": False,
    "require_driver_from_each_constructor": False,
    "min_drivers_per_selected_constructor": 0,
}


#helper SQL views
def pull_race_dim():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM dim_race
                """).df()
    return result

def pull_constructor_mapping(year = 2026):
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:

        df = con.execute(f"""
            SELECT DISTINCT
                constructor_id,
                constructor_name
            FROM fact_constructor_race
            WHERE year = {year}
            ORDER BY constructor_name
            """).df()

    return df

def pull_driver_mapping(year = 2026):
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:

        df = con.execute(f"""
            SELECT DISTINCT
                driver_id,
                driver_name
            FROM fact_driver_race
            WHERE year = {year}
            ORDER BY driver_name
            """).df()

    return df 

def get_last_race_lineup(race_id, fantasy_team_name="Guppies"):

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:

        team_config = con.execute("""
            SELECT *
            FROM fact_team_config
            WHERE race_id = ?
              AND fantasy_team_name = ?
        """, [race_id, fantasy_team_name]).df()

    if team_config.empty:
        raise ValueError("Last race lineup is empty")

    if len(team_config) > 1:
        raise ValueError("Multiple team config rows found")

    row = team_config.iloc[0]

    return {
        "drivers": {
            int(row["driver_1_id"]),
            int(row["driver_2_id"]),
            int(row["driver_3_id"]),
            int(row["driver_4_id"]),
            int(row["driver_5_id"]),
        },
        "constructors": {
            int(row["constructor_1_id"]),
            int(row["constructor_2_id"]),
        },
    }


#loading up all of the inputs for the optimizer
def load_optimizer_inputs(
    race_id,
    driver_prediction_run_id,
    constructor_prediction_run_id,
    fantasy_team_name="Guppies",
):
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        drivers = con.execute("""
            SELECT
                p.*,
                d.driver_name
            FROM fact_driver_predictions p
            LEFT JOIN dim_driver d
                ON p.driver_id = d.driver_id
            WHERE p.race_id = ?
              AND p.prediction_run_id = ?
        """, [race_id, driver_prediction_run_id]).df()

        constructors = con.execute("""
            SELECT
                p.*,
                c.constructor_name
            FROM fact_constructor_predictions p
            LEFT JOIN dim_constructor c
                ON p.constructor_id = c.constructor_id
            WHERE p.race_id = ?
              AND p.prediction_run_id = ?
        """, [race_id, constructor_prediction_run_id]).df()

        budget = con.execute("""
            SELECT budget
            FROM fact_budget_table
            WHERE race_id = ?
        """, [race_id]).fetchone()[0] # type: ignore


    last_week_lineup = get_last_race_lineup(
        race_id=race_id-1,
        fantasy_team_name=fantasy_team_name
    )

    if drivers.empty:
        raise ValueError("No driver predictions found")

    if constructors.empty:
        raise ValueError("No constructor predictions found")



    return budget, drivers, constructors, last_week_lineup


#main run for the optimizer
def run_optimizer_profile(
    race_id,
    driver_prediction_run_id,
    constructor_prediction_run_id,
    fantasy_team_name="Guppies",
    optimizer_settings=None,
):
    settings = DEFAULT_OPTIMIZER_SETTINGS.copy()

    if optimizer_settings:
        settings.update(optimizer_settings)

    budget, drivers, constructors, last_week_lineup = load_optimizer_inputs(
        race_id=race_id,
        driver_prediction_run_id=driver_prediction_run_id,
        constructor_prediction_run_id=constructor_prediction_run_id,
        fantasy_team_name=fantasy_team_name,
    )

    drivers_selected_df, constructors_selected_df, summary_dict = (
        teamOptimizer.optimize_team(
            budget=budget,
            drivers=drivers,
            cons=constructors,
            last_week_lineup=last_week_lineup,
            **settings,
        )
    )

    return drivers_selected_df, constructors_selected_df, summary_dict


if __name__ == "__main__":
    drivers_selected_df, constructors_selected_df, summary_dict = run_optimizer_profile(
        race_id=77,
        driver_prediction_run_id=25,
        constructor_prediction_run_id=26,
    )

    print(drivers_selected_df[["driver_id", "driver_name", "price", "predicted_points"]])
    print(constructors_selected_df)
    print(summary_dict)