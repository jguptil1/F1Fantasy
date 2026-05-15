from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


#######################Old Predictions#######################
#these were originally saved in manual excel files prior to DB being created. They will be a foundtion for the prediction tables moving forward
#these tables have been created 5/8/2026 and the methods should not be used moving forward and will not be in scope of the predictions controller

def load_old_model_performance_table():
    old_model_results = pd.read_csv("src\predictions\old_model_performance.csv")
    print("loaded old model performance table")
    return old_model_results

def load_old_model_mean_results_table():
    old_model_results = pd.read_csv("src\predictions\old_niave_baselines.csv")
    print("loaded old model mean results")
    return old_model_results



def build_old_fact_model_results(old_table):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
           
        con.register("old_temp_performance", old_table)

        con.execute("""
            CREATE OR REPLACE TABLE fact_model_results AS
            SELECT *
            FROM old_temp_performance
            """)
        
        print("built old fact model results")


def build_old_niave_baselines(old_table):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
           
        con.register("old_temp_baselines", old_table)

        con.execute("""
            CREATE OR REPLACE TABLE fact_niave_baselines AS
            SELECT *
            FROM old_temp_baselines
            """)
        
        print("built old niave baseline table")


def read_niave_baseline():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
           

        result = con.execute("""
                SELECT *
                FROM fact_niave_baselines
                """).df()
        
    return result

def append_niave_baseline(id, baseline_mae, baseline_rmse):

    new_row = pd.DataFrame([{
        "prediction_run_id": id,
        "test_mae": baseline_mae,
        "test_rmse": baseline_rmse
    }])


    insert_cols = [
        "prediction_run_id",
        "test_mae",
        "test_rmse"
    ]

    df = new_row[insert_cols].copy()



    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_niave_performance", df)

        con.execute(f"""
            INSERT INTO fact_niave_baselines ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_niave_performance
        """)

    print(f"Appended {len(df)} row(s) to fact_niave_baselines")

        
def append_model_performance(df, prediction_run_id):

    df.columns = df.columns.str.lower()
    
    df["prediction_run_id"] = prediction_run_id

    naive_baseline_df = read_niave_baseline()

    
    #the rest require knowing niave baseline for the given prediction_run_id
    baseline_row = naive_baseline_df[ # type: ignore
        naive_baseline_df["prediction_run_id"] == prediction_run_id # type: ignore
    ]
    if baseline_row.empty:
        raise ValueError(f"No naive baseline found for prediction_run_id={prediction_run_id}")


    naive_baseline_rmse = baseline_row["test_rmse"].iloc[0]
    naive_baseline_mae = baseline_row["test_mae"].iloc[0]


    df["expected_improvement"] = (naive_baseline_mae - df["cv_mae"]) / naive_baseline_mae
    df["realized_improvement"] = (naive_baseline_mae - df["test_mae"]) / naive_baseline_mae

    df["overfit_underfit"] = df["test_mae"] - df["train_mae"]
    df["rmse_overfit_underfit_gap"] = df["test_rmse"] - df["train_rmse"]

    df["generalization"] = df["test_mae"] - df["cv_mae"]

    df = df.rename(columns={"model": "model_type"})

    insert_cols = [
        "prediction_run_id",
        "model_type",
        "cv_mae",
        "cv_mae_std",
        "train_mae",
        "train_rmse",
        "test_mae",
        "test_rmse",
        "expected_improvement",
        "realized_improvement",
        "overfit_underfit",
        "rmse_overfit_underfit_gap",
        "generalization"
    ]

    df = df[insert_cols].copy()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_model_performance", df)

        con.execute(f"""
            INSERT INTO fact_model_results ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_model_performance
        """)

    print(f"Appended {len(df)} row(s) to fact_model_results")