import duckdb
import pandas as pd
import numpy as np
#simulator modeule
import driver_monte_carlo
#optimizer engine module
from src.optimizer.pre_race_weekend_optimizer import pre_race_weekend_optimizer_controller
from src.optimizer.optimization_tables import optimizer_tables_controller


DATABASE_PATH = "data/database/f1_fantasy.duckdb"
RACE_ID = 77
PREDICTION_RUN_ID = 11

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
    current_preds = load_current_driver_predictions(RACE_ID, PREDICTION_RUN_ID)
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
#Lineup will run several risk and optimization profiles 
#Profiles

# Optimization #1: max_predicted_points



#helper that will verify that there are predictions for the given race_id and the prediction_run_id
def verify_race_id_pred_run_id(race_id = RACE_ID, prediction_run_id = PREDICTION_RUN_ID) -> bool: 
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



#helper to get the most recent optimized team that contains that prediction_run and race_id
def get_max_predicted_points():

    try:
        verify_race_id_pred_run_id()
    except ValueError as e:
        print(f"Error encountered: {e}")
        return None

    profile_source = "optimizer"
    profile_strategy = "max_projected_points"
    optimization_target = "predicted_points"

    opt_settings = {
        "require_driver_from_each_constructor": False,
        "min_drivers_per_selected_constructor": 0
    }

    existing_run_id = verify_run_exists(
        settings=opt_settings,
        prediction_run_id=PREDICTION_RUN_ID,
        profile_source=profile_source,
        profile_strategy=profile_strategy,
        optimization_target=optimization_target
    )

    if existing_run_id is not None:
        print(f"Existing optimizer run found: {existing_run_id}")
        return existing_run_id

    drivers_selected_df, constructors_selected_df, summary_dict = (
        pre_race_weekend_optimizer_controller()
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

# Optimization #2: constructor_required
# Optimization #3: 1_con_driver_required


def get_linup_profiles():

    optimized_team = get_max_predicted_points()



#running a single lineup
def run_lineup(driver_simulations, driver_ids):

    lineup_sim = driver_monte_carlo.simulate_lineup(driver_simulations=driver_simulations, selected_driver_ids=driver_ids)
    lineup_summary = driver_monte_carlo.summarize_lineup(lineup_sim)
    lineup_summary_df = pd.DataFrame([lineup_summary])
    return lineup_summary_df



if __name__ == "__main__":

    valid = verify_race_id_pred_run_id()
    driver_field_summary, driver_simulations = run_driver_simulator()




    #FIXME: need to figure out how i am going to be getting driver_ids
    #lineup_summary_df = run_lineup(driver_simulations=driver_simulations, driver_ids=driver_ids)
    