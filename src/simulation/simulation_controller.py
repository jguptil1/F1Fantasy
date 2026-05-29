import duckdb
import pandas as pd
import numpy as np
#simulator modeule
from src.simulation import driver_monte_carlo
#optimizer engine module
from src.optimizer.pre_race_weekend_optimizer import run_optimizer_profile
from src.optimizer.optimization_tables import optimizer_tables_controller



DATABASE_PATH = "data/database/f1_fantasy.duckdb"
RACE_ID = 77
DRIVER_PREDICTION_RUN_ID = 25 
CONSTRUCTOR_PREDICTION_RUN_ID = 26

################################Simulations#############################################

def load_current_driver_predictions(race_id_to_sim, prediction_run_id):

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        current_preds = con.execute(f"""
            SELECT
                dp.race_id,
                dp.driver_id,
                dp.constructor_id,
                dp.price,
                dp.predicted_points,
                CASE
                    WHEN dp.predicted_points < 20 THEN '00_20'
                    ELSE '20_plus'
                END AS prediction_bucket
            FROM fact_driver_predictions dp
            WHERE dp.race_id = ?
            AND dp.prediction_run_id = ?;
        """, [race_id_to_sim, prediction_run_id]).df()
        return current_preds
    
def load_driver_residual_samples():
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        residuals = con.execute("""
            SELECT
                prediction_bucket,
                residual
            FROM driver_prediction_residuals
            WHERE residual IS NOT NULL
        """).df()

    bucket_residuals = {
        bucket: group["residual"].to_numpy()
        for bucket, group in residuals.groupby("prediction_bucket")
    }

    return bucket_residuals

def run_driver_simulator():
    current_preds = load_current_driver_predictions(RACE_ID, DRIVER_PREDICTION_RUN_ID)
    print(current_preds)

    print("-------------------Loading Bucket Residuals---------------------")

    bucket_residuals = load_driver_residual_samples()
    print(bucket_residuals)

    print("-----------------Bucket Residuals-----------------------")

    for bucket, residual_values in bucket_residuals.items():
        print(bucket, len(residual_values), residual_values[:5])

    print("----------------Creating the Driver Simulations-------------------------")

    driver_simulations = driver_monte_carlo.simulate_driver_points(current_preds=current_preds, bucket_residuals=bucket_residuals, n_sims=10000)
    print(driver_simulations)

    print("----------------Driver Field Summary-------------------------")

    driver_field_summary = driver_monte_carlo.summarize_driver_simulations(driver_simulations)
    return driver_field_summary, driver_simulations


######################################Lineup###########################################
#We will run several risk and optimization profiles, ultimately returning a dataframe of each of those profiles, and their EV distributions


#helper that will verify that there are predictions for the given race_id and the prediction_run_id
def verify_race_id_pred_run_id(race_id = RACE_ID, prediction_run_id = DRIVER_PREDICTION_RUN_ID) -> bool: 
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        df = con.execute(f"""
                    SELECT *
                    FROM fact_driver_predictions
                    WHERE race_id = {race_id}
                        AND prediction_run_id = {prediction_run_id}
                    """).df()
    
    if df.empty:
        raise ValueError("There are no predictions for this race.")
    else:
        return True

#helper that sees if a prediction_run_id with a setting already exists, if so return the optimization_id
def verify_run_exists(
    settings,
    prediction_run_id,
    profile_source,
    profile_strategy,
    optimization_target
):

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:

        df = con.execute(f"""
            SELECT
                optimizer_run_id
            FROM optimizer_run
            WHERE driver_prediction_run_id = {prediction_run_id}

            AND profile_source = '{profile_source}'
            AND profile_strategy = '{profile_strategy}'
            AND optimization_target = '{optimization_target}'

            AND require_driver_from_each_constructor =
                {str(settings["require_driver_from_each_constructor"]).upper()}

            AND min_drivers_per_selected_constructor =
                {settings["min_drivers_per_selected_constructor"]}

            LIMIT 1
        """).df()

    if len(df) > 0:
        return int(df["optimizer_run_id"].iloc[0])

    return None

#helper that returns the driver_ids for a given optimization run id
def get_optimized_driver_lineup(optimization_run_id):
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        lineup_df = con.execute("""
            SELECT driver_id
            FROM optimizer_selection
            WHERE optimizer_run_id = ?
              AND asset_type = 'driver'
            ORDER BY slot_num
        """, [optimization_run_id]).df()

    return lineup_df["driver_id"].tolist()



#helper that creates a generic profile object
def get_or_create_optimizer_profile(
    profile_source,
    profile_strategy,
    optimization_target,
    opt_settings
):
    try:
        print("Verifying that race and prediction exist")
        verify_race_id_pred_run_id()
    except ValueError as e:
        print(f"Error encountered: {e}")
        return None

    print(f"Verifying if {profile_strategy} run exists")

    existing_run_id = verify_run_exists(
        settings=opt_settings,
        prediction_run_id=DRIVER_PREDICTION_RUN_ID,
        profile_source=profile_source,
        profile_strategy=profile_strategy,
        optimization_target=optimization_target
    )

    if existing_run_id is not None:
        print(f"Existing optimizer run found: {existing_run_id}")
        return existing_run_id

    drivers_selected_df, constructors_selected_df, summary_dict = run_optimizer_profile(
        race_id=RACE_ID,
        driver_prediction_run_id=DRIVER_PREDICTION_RUN_ID,
        constructor_prediction_run_id=CONSTRUCTOR_PREDICTION_RUN_ID,
        optimizer_settings=opt_settings
    )

    optimizer_run_id = optimizer_tables_controller(
        drivers_selected_df,
        constructors_selected_df,
        summary_dict,
        fantasy_team_name="Guppies",
        is_production_run=False,

        profile_source=profile_source,
        profile_strategy=profile_strategy,
        optimization_target=optimization_target,

        require_drivers_from_each_constructor=opt_settings["require_driver_from_each_constructor"],
        min_drivers_per_selected_constructor=opt_settings["min_drivers_per_selected_constructor"]
    )

    return optimizer_run_id


# OPTIMIZATION Profile #1: max_predicted_points
#helper to get the most recent optimized team that contains that prediction_run and race_id
def prof_get_max_predicted_points():


    """
    This function will return the team that has the optimized max points, not considering constructor contraints.
    This fucntion returns the driver_ids from that lineup. 
    
    """

    return get_or_create_optimizer_profile(
        profile_source="optimizer",
        profile_strategy="max_projected_points",
        optimization_target="predicted_points",
        opt_settings={
            "require_driver_from_each_constructor": False,
            "min_drivers_per_selected_constructor": 0
        }
    )

# Optimization Profile #2: constructor_required

def prof_get_constructor_required():
    return get_or_create_optimizer_profile(
        profile_source="optimizer",
        profile_strategy="constructor_required",
        optimization_target="predicted_points",
        opt_settings={
            "require_driver_from_each_constructor": True,
            "min_drivers_per_selected_constructor": 1
        }
    )

# Optimization Profile #3: double_stack_constructor

def prof_double_stack_constructor():
    return get_or_create_optimizer_profile(
        profile_source="optimizer",
        profile_strategy="double_stack_constructor",
        optimization_target="predicted_points",
        opt_settings={
            "require_driver_from_each_constructor": True,
            "min_drivers_per_selected_constructor": 2
        }
    )


def get_profiles():
    """
    This stores each of the profiles that can be created
    """
    profiles = {
        "max_projected_points": prof_get_max_predicted_points,
        "constructor_required": prof_get_constructor_required,
        "double_stack_constructors": prof_double_stack_constructor,
    }
    
    return profiles


#running a single lineup summary
def run_lineup_summary(driver_simulations, driver_ids):

    lineup_sim = driver_monte_carlo.simulate_lineup(driver_simulations=driver_simulations, selected_driver_ids=driver_ids)
    lineup_summary = driver_monte_carlo.summarize_lineup(lineup_sim)
    lineup_summary_df = pd.DataFrame([lineup_summary])
    return lineup_summary_df


#this gets all of the lineups summaries
def get_lineup_profiles(driver_simulations):

    profile_summaries = []

    #dict that has each of the profiles and the value is the get method that returns the correct optimization_id
    profiles = get_profiles()

    for profile_name, profile_func in profiles.items():
        #calls the get method for that given profile
        profile_optimization_id = profile_func()
        
        if profile_optimization_id is None:
            print(f"Skipping {profile_name}: no optimizer run id returned")
            continue
        
        profile_lineup = get_optimized_driver_lineup(optimization_run_id=profile_optimization_id)
        lineup_summary = run_lineup_summary(driver_simulations, profile_lineup)

        lineup_summary["profile_name"] = profile_name
        lineup_summary["optimizer_run_id"] = profile_optimization_id


        profile_summaries.append(lineup_summary)
    
    return pd.concat(profile_summaries, ignore_index=True)



if __name__ == "__main__":

    valid = verify_race_id_pred_run_id()
    driver_field_summary, driver_simulations = run_driver_simulator()

    profile_summaries = get_lineup_profiles(driver_simulations=driver_simulations)
    print(profile_summaries)


    