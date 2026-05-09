from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



def build_pre_race_constructor_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""

        CREATE OR REPLACE TABLE pre_race_constructor_features AS

        WITH base AS (
            SELECT
                fcr.year,
                fcr.race_id,
                fcr.date_start,
                fcr.date_end,
                fcr.circuit_short_name,
                fcr.is_sprint_weekend,
                fcr.country_name,
                fcr.constructor_id,
                fcr.constructor_name,
                fcr.price,
                fcr.fantasy_points

            FROM fact_constructor_race AS fcr
        ),

        lagged AS (
            SELECT
                *,

                LAG(price) OVER (
                    PARTITION BY constructor_name
                    ORDER BY date_start
                ) AS prev_price,

                LAG(fantasy_points) OVER (
                    PARTITION BY constructor_name
                    ORDER BY date_start
                ) AS prev_points

            FROM base
        ),

        rolling AS (
            SELECT
                *,

                price - prev_price AS price_change_prev_race,

                (price - prev_price) / NULLIF(prev_price, 0)
                    AS price_change_pct_prev_race,

                AVG(prev_points) OVER (
                    PARTITION BY constructor_name
                    ORDER BY date_start
                    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                ) AS points_last_5_avg,

                AVG(prev_points) OVER (
                    PARTITION BY constructor_name
                    ORDER BY date_start
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS points_last_3_avg

            FROM lagged
        ),

        feature_calc AS (
            SELECT
                *,

                points_last_5_avg / NULLIF(price, 0) AS ppm_last_5,

                points_last_3_avg / NULLIF(price, 0) AS ppm_last_3,

                CASE
                    WHEN price_change_prev_race > 0 THEN 1
                    ELSE 0
                END AS price_increase,

                CASE
                    WHEN price_change_prev_race < 0 THEN 1
                    ELSE 0
                END AS price_decrease

            FROM rolling
        )

        SELECT
            year,
            race_id,
            date_start,
            date_end,
            circuit_short_name,

            CAST(is_sprint_weekend AS INTEGER)
                AS is_sprint_weekend,

            country_name,

            constructor_id,

            price,
            fantasy_points,

            price_change_prev_race,
            price_change_pct_prev_race,

            points_last_5_avg,
            points_last_3_avg,

            ppm_last_5,
            ppm_last_3,

            points_last_3_avg - points_last_5_avg
                AS momentum,

            price_increase,
            price_decrease

        FROM feature_calc

        ORDER BY race_id

        """)


def read_pre_race_constructor_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
                    SELECT *
                    FROM pre_race_constructor_features
                    """).df()
    return result


def validate_pre_race_constructor_features():

    df = read_pre_race_constructor_features()

    # duplicate check
    max_dup = df.groupby(
        ["year", "race_id", "constructor_id"]
    ).size().max()

    if max_dup > 1:
        raise ValueError(
            "Duplicate rows found in pre_race_constructor_features"
        )

    critical_cols = [
        "constructor_id",
        "race_id",
        "price"
    ]

    nulls = df[critical_cols].isnull().sum()

    if nulls.any():
        print(nulls)

        raise ValueError(
            "Nulls found in critical columns"
        )

    # sanity check
    rows_per_race = df.groupby(
        ["year", "race_id"]
    ).size()

    bad_races = rows_per_race[rows_per_race < 8]

    if not bad_races.empty:
        print(bad_races)

        raise ValueError(
            "Some races have suspiciously low constructor counts"
        )

    print("pre_race_constructor_features validated")



def get_pre_race_constructor_feature_columns():
    prcf = read_pre_race_constructor_features()
    return prcf.columns