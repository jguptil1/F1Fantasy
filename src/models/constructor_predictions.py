from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


#initial build (use once)

def build_fact_constructor_predictions():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.execute("""
            CREATE TABLE IF NOT EXISTS fact_constructor_predictions (

                prediction_run_id BIGINT,
                prediction_timestamp TIMESTAMP,

                model_name VARCHAR,
                model_version VARCHAR,
                feature_set_version VARCHAR,

                target_variable VARCHAR,

                train_data_cutoff BIGINT,

                is_production_run BOOLEAN,

                year INTEGER,
                race_id BIGINT,
                constructor_id BIGINT,

                price DOUBLE,
                predicted_points DOUBLE
            )
        """)

    print("fact_constructor_predictions ready")

#hleper function during testing
def clear_constructor_prediction_tables():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.execute("""
            DELETE FROM fact_constructor_predictions
        """)

        con.execute("""
            DELETE FROM prediction_run
            WHERE asset_type = 'constructor'
        """)

    print("Constructor prediction tables cleared")



######################new prediction runs######################



def append_constructor_run(df):

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


def append_constructor_predictions(df):

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
        "constructor_id",
        "price",
        "predicted_points"
    ]

    df = df[insert_cols].copy()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_constructor_predictions", df)

        con.execute(f"""
            INSERT INTO fact_constructor_predictions ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_constructor_predictions
        """)

    print(f"Appended {len(df)} row(s) to fact_constructor_predictions")
