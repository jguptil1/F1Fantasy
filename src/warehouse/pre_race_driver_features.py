from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd




##################################Ingestion#####################################


def build_pre_race_driver_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""
                            
        CREATE OR REPLACE TABLE pre_race_driver_features AS            
        WITH base AS (
            SELECT
                fdr.year,
                fdr.race_id,
                fdr.date_start,
                fdr.date_end,
                fdr.circuit_short_name,
                fdr.is_sprint_weekend,
                fdr.country_name,
                fdr.driver_id,
                fdr.constructor_id,
                fdr.price,
                fdr.fantasy_points,
                fdr.elo_before
            FROM fact_driver_race AS fdr
        ),

        lagged AS (
            SELECT
                *,
                
                LAG(price) OVER (
                    PARTITION BY driver_id
                    ORDER BY date_start
                ) AS prev_price,

                LAG(fantasy_points) OVER (
                    PARTITION BY driver_id
                    ORDER BY date_start
                ) AS prev_points

            FROM base
        ),

        rolling AS (
            SELECT
                *,

                price - prev_price AS price_change_prev_race,
                (price - prev_price) / NULLIF(prev_price, 0) AS price_change_pct_prev_race,

                AVG(prev_points) OVER (
                    PARTITION BY driver_id
                    ORDER BY date_start
                    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                ) AS points_last_5_avg,
                      
                AVG(prev_points) OVER (
                    PARTITION BY driver_id
                    ORDER BY date_start
                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                ) AS points_last_3_avg

            FROM lagged
        ),

        feature_calc AS (
            SELECT
                *,

                points_last_5_avg / NULLIF(price, 0) AS ppm_last_5,

                CASE 
                    WHEN price_change_prev_race > 0 THEN 1 
                    ELSE 0 
                END AS price_increase,

                CASE 
                    WHEN price_change_prev_race < 0 THEN 1 
                    ELSE 0 
                END AS price_decrease

            FROM rolling
        ),

        teammate_features AS (
            SELECT
                *,

                SUM(points_last_5_avg) OVER (
                    PARTITION BY year, race_id, constructor_id
                ) - points_last_5_avg AS teammate_points_last5

            FROM feature_calc
        )

        SELECT
            year,
            race_id,
            date_start,
            date_end,
            circuit_short_name,
            CAST(is_sprint_weekend AS INTEGER) AS is_sprint_weekend,
            country_name,
            driver_id,
            constructor_id,
            price,
            fantasy_points,
            elo_before,

            price_change_prev_race,
            price_change_pct_prev_race,
            points_last_5_avg,
            ppm_last_5,
            points_last_3_avg - points_last_5_avg AS momentum,

            price_increase,
            price_decrease,

            teammate_points_last5,
            points_last_5_avg - teammate_points_last5 AS teammate_delta_last5

        FROM teammate_features
        ORDER BY race_id;
                      
    """)
        

def validate_pre_race_driver_features():
    df = read_pre_race_driver_features()

    #duplicate check

    max_dup = df.groupby(["year", "race_id", "driver_id"]).size().max()

    if max_dup > 1:
        raise ValueError("Duplicate rows found in pre_race_driver_features")

    print("fact_driver_race validated")


    critical_cols = [
    "driver_id",
    "race_id",
    "price",
    "elo_before"
    ]   

    # null check
    nulls = df[critical_cols].isnull().sum()

    if nulls.any():
        print(nulls)
        raise ValueError("Nulls found in critical columns")
    

    #row count sanity
    rows_per_race = df.groupby(["year", "race_id"]).size()

    bad_races = rows_per_race[rows_per_race < 18]

    if not bad_races.empty:
        print(bad_races)
        raise ValueError("Some races have suspiciously low driver counts")


    print("pre_race_driver_features validated")

def read_pre_race_driver_features():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT * FROM pre_race_driver_features           
            """).df()
    return result


def get_pre_race_driver_feature_columns():
    prdf = read_pre_race_driver_features()
    return prdf.columns