import pandas as pd
import numpy as np
import duckdb

import teamOptimizer

#helper SQL views
def pull_driver_predictions():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT
                p.*,
                d.driver_name
            FROM fact_driver_predictions AS p
            LEFT JOIN dim_driver AS d
                ON p.driver_id = d.driver_id
                """).df()
    return result
def pull_constructor_predictions():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT
                p.*,
                c.constructor_name
            FROM fact_constructor_predictions AS p
            LEFT JOIN dim_constructor AS c
                ON p.constructor_id = c.constructor_id
                """).df()
    return result
def pull_budgets():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM fact_budget_table
                """).df()
    return result
def pull_driver_dim():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM dim_driver
                """).df()
    return result    
def pull_constructor_dim():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM dim_constructor
                """).df()
    return result
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
def pull_team_config():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM fact_team_config
                """).df()
    return result    



def get_last_race_lineup(race, fantasy_team_name = "Guppies"):
    team_config = pull_team_config()


    team_config = team_config[(team_config['race'] == race) & (team_config['fantasy_team_name'] == fantasy_team_name)]

    last_race_lineup  = {'drivers': None,
                         'constructors': None} #empty init
    
    if team_config.empty:
        raise ValueError("Last race lineup is empty")
    
    if len(team_config) > 1:
        raise ValueError("Multiple team config rows found for this race/team")
    

    row = team_config.iloc[0]

    driver_cols = [
        "driver_1_id",
        "driver_2_id",
        "driver_3_id",
        "driver_4_id",
        "driver_5_id",
    ]

    constructor_cols = [
        "constructor_1_id",
        "constructor_2_id",
    ]

    row = team_config.iloc[0]

    last_race_lineup = {
        "drivers": {int(row[col]) for col in driver_cols},
        "constructors": {int(row[col]) for col in constructor_cols},
    }

    return last_race_lineup



#narrowing down the querys for each pull before passing into the optimizer
def filter_driver_query(df , race_id=None, prediction_run_id=None, is_production_run=None):
    filtered_df = df.copy()

    if race_id is not None:
        filtered_df = filtered_df[
            filtered_df["race_id"] == race_id
        ]

    if prediction_run_id is not None:
        filtered_df = filtered_df[
            filtered_df["prediction_run_id"] == prediction_run_id
        ]

    if is_production_run is not None:
        filtered_df = filtered_df[
            filtered_df["is_production_run"] == is_production_run
        ]

    return filtered_df

def filter_constructor_query(df, race_id=None, prediction_run_id=None, is_production_run=None):
    filtered_df = df.copy()

    if race_id is not None:
        filtered_df = filtered_df[
            filtered_df["race_id"] == race_id
        ]

    if prediction_run_id is not None:
        filtered_df = filtered_df[
            filtered_df["prediction_run_id"] == prediction_run_id
        ]

    if is_production_run is not None:
        filtered_df = filtered_df[
            filtered_df["is_production_run"] == is_production_run
        ]

    return filtered_df

def filter_budget_query(df, race):
    budget_value = df.loc[
        df["race"] == race,
        "budget"
    ].iloc[0]

    return budget_value


#optimizer function call
def run_optimizer(budget, drivers, cons, last_week_lineup):
    
    drivers_selected_df, constructors_selected_df, summary_dict = teamOptimizer.optimize_team(
        budget=budget,
        drivers=drivers,
        cons=cons,
        last_week_lineup=last_week_lineup,
        free_transfers_avail=3,
        points_col="predicted_points",
        n_drivers=5,
        n_constructors=2,
        max_drivers_per_team=None,
        use_drs=True,
        drs_multiplier=2.0,
        solver_msg=False,
        require_driver_from_each_constructor=False,
        min_drivers_per_selected_constructor=1
    )

    return drivers_selected_df, constructors_selected_df, summary_dict


def pre_race_weekend_optimizer_controller():
    driver_predictions_df = pull_driver_predictions()
    constructor_predictions_df = pull_constructor_predictions()
    budgets = pull_budgets()


    #helper pulls to merge to eventual output as ID's are only present in prediction tables
    drivers = pull_driver_dim()
    constructors = pull_constructor_dim()

    driver_predictions_df = filter_driver_query(driver_predictions_df, race_id = 77, prediction_run_id=25)
    constructor_predictions_df = filter_constructor_query(constructor_predictions_df, race_id = 77, prediction_run_id=26)
    budget = filter_budget_query(budgets, race=7)

    last_race_lineup = get_last_race_lineup(race = 6)
    


    drivers_selected_df, constructors_selected_df, summary_dict = run_optimizer(budget = budget, drivers=driver_predictions_df, cons = constructor_predictions_df, last_week_lineup=last_race_lineup)
    print("--------------------------------------------------------DRIVERS---------------------------------------------------------------")
    print(drivers_selected_df[['driver_id', "driver_name", 'price', "predicted_points"]])


    print("-----------------------------------------------------Constructors------------------------------------------------------------")
    print(constructors_selected_df)


    print("---------------------------------------------------------Summary------------------------------------------------------------")
    print(summary_dict)

    return drivers_selected_df, constructors_selected_df, summary_dict
