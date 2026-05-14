import pandas as pd
import numpy as np
import duckdb

import teamOptimizer

#helper data pull functions
def pull_driver_predictions():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM fact_driver_predictions
                """).df()
    return result
def pull_constructor_predictions():
    with duckdb.connect("data/database/f1_fantasy.duckdb", read_only=True) as con:
        result = con.execute("""
            SELECT *
            FROM fact_constructor_predictions
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


def get_last_race_lineup():
    last_race_lineup  = {} #empty init


    # return object should look like this: 
    # last_week_lineup = {
    # "drivers": {"RUS", "BEA", "HAD", "HUL", "LAW"}, 
    # "constructors": {"MER", "RB"}
    #}   



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
def run_optimizer(budget, drivers, cons):
    
    drivers_selected_df, constructors_selected_df, summary_dict = teamOptimizer.optimize_team(
        budget=budget,
        drivers=drivers,
        cons=cons,
        last_week_lineup=None,
        free_transfers_avail=2,
        points_col="predicted_points",
        n_drivers=5,
        n_constructors=2,
        max_drivers_per_team=None,
        use_drs=False,
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

    driver_predictions_df = filter_driver_query(driver_predictions_df, race_id = 77, prediction_run_id=5)
    constructor_predictions_df = filter_driver_query(constructor_predictions_df, race_id = 77, prediction_run_id=6)
    budget = filter_budget_query(budgets, race=7)


    drivers_selected_df, constructors_selected_df, summary_dict = run_optimizer(budget = budget, drivers=driver_predictions_df, cons = constructor_predictions_df)
    print("--------------------------------------------------------DRIVERS---------------------------------------------------------------")
    print(drivers_selected_df)


    print("-----------------------------------------------------Constructors------------------------------------------------------------")
    print(constructors_selected_df)


    print("---------------------------------------------------------Summary------------------------------------------------------------")
    print(summary_dict)



if __name__ == "__main__":
    pre_race_weekend_optimizer_controller()
