from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



#######################Old Predictions#######################
#these were originally saved in manual excel files prior to DB being created. They will be a foundtion for the prediction tables moving forward
#these tables have been created 5/8/2026 and the methods should not be used moving forward and will not be in scope of the predictions controller

def load_data():
    old_driver_predictions = pd.read_csv("src\predictions\old_driver_predictions.csv")
    old_runs = pd.read_csv("src\predictions\old_prediction_runs.csv")

    return old_driver_predictions, old_runs

def build_old_driver_prediction_run(old_table):
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
           
        con.register("old_temp_predictions_runs", old_table)

        con.execute("""
            CREATE OR REPLACE TABLE prediction_run AS
            SELECT *
            FROM old_temp_predictions_runs
            """)
                                           

def build_old_fact_driver_predictions(old_table):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
           
        con.register("old_temp_predictions", old_table)

        con.execute("""
            CREATE OR REPLACE TABLE fact_driver_predictions AS
            SELECT *
            FROM old_temp_predictions
            """)


def build_old_predictions():
    driver_preds, old_runs = load_data()
    build_old_driver_prediction_run(old_runs)
    build_old_fact_driver_predictions(driver_preds)



def append_driver_run(df):

    insert_cols = [
        "prediction_run_id",
        "created_at",
        "model_name",
        "model_version",
        "feature_set_version",
        "target",
        "train_cutoff_race_id",
        "asset_type"
    ]

    df = df[insert_cols].copy()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_prediction_run", df)

        con.execute(f"""
            INSERT INTO prediction_run ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_prediction_run
        """)

    print(f"Appended {len(df)} row(s) to prediction_run")



def append_driver_predictions(df):

    insert_cols = [
        "prediction_run_id",
        "prediction_timestamp",
        "model_name",
        "model_version",
        "feature_set_version",
        "target_variable",
        "train_data_cutoff",
        "is_production_run",
        "year",
        "race_id",
        "driver_id",
        "constructor_id",
        "price",
        "predicted_points"
    ]

    df = df[insert_cols].copy()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_driver_predictions", df)

        con.execute(f"""
            INSERT INTO fact_driver_predictions ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_driver_predictions
        """)

    print(f"Appended {len(df)} row(s) to fact_driver_predictions")



if __name__ == "__main__":
    preds, run = load_data()
    build_old_fact_driver_predictions(preds)
    build_old_driver_prediction_run(run)