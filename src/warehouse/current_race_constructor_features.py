from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd

from pre_race_constructor_features import get_pre_race_constructor_feature_columns


def build_current_race_constructor_features(year, race_num):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute(f"""
            CREATE OR REPLACE TABLE current_race_constructor_features AS

            WITH target_race AS (
                SELECT *
                FROM dim_race
                WHERE year = {year}
                  AND race_num = {race_num}
            ),

            active_constructor_prices AS (
                SELECT
                    year,
                    race,
                    constructor,
                    price
                FROM stage_constructor_price_table
                WHERE year = {year}
                  AND race = {race_num}
            ),

            latest_history AS (
                SELECT *
                FROM pre_race_constructor_features
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY constructor_id
                    ORDER BY race_id DESC
                ) = 1
            )

            SELECT
                tr.year,
                tr.race_id,
                tr.date_start,
                tr.date_end,
                tr.circuit_short_name,
                CAST(tr.is_sprint_weekend AS INTEGER) AS is_sprint_weekend,
                tr.country_name,

                c.constructor_id,
                p.price,

                -- unknown target for upcoming race
                NULL AS fantasy_points,

                -- carry/lagged features
                h.price_change_prev_race,
                h.price_change_pct_prev_race,
                h.points_last_5_avg,
                h.points_last_3_avg,
                h.ppm_last_5,
                h.ppm_last_3,
                h.momentum,
                h.price_increase,
                h.price_decrease

            FROM target_race tr

            JOIN active_constructor_prices p
                ON tr.year = p.year
               AND tr.race_num = p.race

            JOIN dim_constructor c
                ON lower(trim(p.constructor)) = lower(trim(c.constructor_name))
               AND tr.year = c.year

            LEFT JOIN latest_history h
                ON c.constructor_id = h.constructor_id

            ORDER BY tr.race_id, c.constructor_id
        """)

def read_current_race_constructor_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT *
            FROM current_race_constructor_features
        """).df()

    return result


def get_current_week_constructor_feature_columns():
    crcf = read_current_race_constructor_features()
    return crcf.columns

def validate_current_race_constructor_features(year, race_num):

    df = read_current_race_constructor_features()

    max_dup = df.groupby(
        ["year", "race_id", "constructor_id"]
    ).size().max()

    if max_dup > 1:
        raise ValueError("Duplicate constructor rows found")

    if len(df) < 8:
        raise ValueError(f"Too few constructors found: {len(df)}")

    critical_cols = [
        "race_id",
        "year",
        "constructor_id",
        "price",
        "points_last_5_avg",
        "ppm_last_5",
        "momentum",
    ]

    null_counts = df[critical_cols].isna().sum()
    print(null_counts)

    if null_counts.sum() > 0:
        raise ValueError("Nulls found in critical model input columns")

    if df["fantasy_points"].notna().sum() > 0:
        raise ValueError("fantasy_points is populated for current week")

    if (df["price"] <= 0).any():
        raise ValueError("Invalid constructor price found")

    prcf_cols = set(get_pre_race_constructor_feature_columns())
    crcf_cols = set(get_current_week_constructor_feature_columns())

    missing_cols = prcf_cols - crcf_cols
    extra_cols = crcf_cols - prcf_cols

    if missing_cols or extra_cols:
        print("Missing columns:", missing_cols)
        print("Extra columns:", extra_cols)

        raise ValueError(
            "Column mismatch between current week and historical constructor feature tables"
        )

    print("current_race_constructor_features validated")