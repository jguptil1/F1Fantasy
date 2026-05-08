from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd

from pre_race_driver_features import get_pre_race_driver_feature_columns


def build_current_race_driver_features(year, race_num):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute(f"""
            CREATE OR REPLACE TABLE current_race_driver_features AS
            WITH target_race AS (
                SELECT *
                FROM dim_race
                WHERE year = {year}
                AND race_num = {race_num}
            ),
            active_driver_prices AS (
                SELECT
                    year,
                    race,
                    driver,
                    price
                FROM stage_driver_price_table
                WHERE year = {year}
                AND race = {race_num}
            ),
            latest_history AS (
                SELECT *
                FROM pre_race_driver_features
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY driver_id
                    ORDER BY race_id DESC
                ) = 1
            ),

            latest_elo AS (
                SELECT
                    driver_id,
                    elo_after AS elo_before
                FROM fact_driver_race
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY driver_id
                    ORDER BY race_id DESC
                ) = 1
            )

            SELECT
                tr.race_id,
                tr.date_start,
                tr.date_end,
                tr.country_name,
                tr.year,
                tr.circuit_short_name,
                d.driver_id,
                c.constructor_id,
                p.price,
                le.elo_before,

                -- carry/lagged features
                CAST(h.is_sprint_weekend AS INTEGER) AS is_sprint_weekend,
                h.price_increase,
                h.price_decrease,
                h.price_change_prev_race,
                h.price_change_pct_prev_race,
                h.points_last_5_avg,
                h.ppm_last_5,
                h.momentum,
                h.teammate_points_last5,
                h.teammate_delta_last5,

                -- upcoming race unknowns
                NULL AS fantasy_points
            FROM target_race tr
            JOIN active_driver_prices p
                ON tr.year = p.year
            AND tr.race_num = p.race
            JOIN dim_driver d
                ON p.driver = d.driver_name
            LEFT JOIN latest_history h
                ON d.driver_id = h.driver_id
            LEFT JOIN dim_constructor c
                ON h.constructor_id = c.constructor_id
            LEFT JOIN latest_elo le
                ON d.driver_id = le.driver_id;
        """).df()
    return result





#helper
def read_current_race_driver_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
                             SELECT *
                             FROM current_race_driver_features
                             """).df()
        return result

#helper

def get_current_week_driver_feature_columns():
    crdf = read_current_race_driver_features()
    return crdf.columns

def validate_current_race_driver_features(year, race_num):
    df = read_current_race_driver_features()

    # 2. One row per driver
    max_dup = df.groupby(["year", "race_id", "driver_id"]).size().max()
    if max_dup > 1:
        raise ValueError("Duplicate driver rows found")

    # 3. Expected count
    if len(df) < 18:
        raise ValueError(f"Too few drivers found: {len(df)}")

    # 4. Critical model inputs
    critical_cols = [
        "race_id",
        "year",
        "driver_id",
        "constructor_id",
        "price",
        "elo_before",
        "points_last_5_avg",
        "ppm_last_5",
        "momentum",
    ]

    null_counts = df[critical_cols].isna().sum()
    print(null_counts)

    if null_counts.sum() > 0:
        raise ValueError("Nulls found in critical model input columns")

    # 5. Leakage columns should be null/missing
    leakage_cols = [
        "fantasy_points",
        "driver_finish_position",
        "status",
        "elo_after",
        "elo_delta",
    ]

    existing_leakage_cols = [col for col in leakage_cols if col in df.columns]

    for col in existing_leakage_cols:
        if df[col].notna().sum() > 0:
            raise ValueError(f"Leakage column {col} is populated")

    # 6. Price sanity
    if (df["price"] <= 0).any():
        raise ValueError("Invalid driver price found")
    

    # 7. column validation between out of week features and current week features
    prdf_cols = set(get_pre_race_driver_feature_columns())
    crdf_cols = set(get_current_week_driver_feature_columns())

    missing_cols = prdf_cols - crdf_cols
    extra_cols = crdf_cols - prdf_cols

    if missing_cols or extra_cols:
        print("Missing columns:", missing_cols)
        print("Extra columns:", extra_cols)

        raise ValueError(
            "Column mismatch between current week and historical feature tables"
    )

    print("current_race_driver_features validated")   