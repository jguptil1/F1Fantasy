import duckdb
import pandas as pd
import numpy as np
import driver_monte_carlo
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


def run_lineup(driver_simulations, driver_ids):

    lineup_sim = driver_monte_carlo.simulate_lineup(driver_simulations=driver_simulations, selected_driver_ids=driver_ids)
    lineup_summary = driver_monte_carlo.summarize_lineup(lineup_sim)
    lineup_summary_df = pd.DataFrame([lineup_summary])
    return lineup_summary_df



if __name__ == "__main__":
    driver_field_summary, driver_simulations = run_driver_simulator()




    #FIXME: need to figure out how i am going to be getting driver_ids
    lineup_summary_df = run_lineup(driver_simulations=driver_simulations, driver_ids=driver_ids)
    