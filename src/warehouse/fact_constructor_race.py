from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


def build_fact_constructor_race():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""
        
        CREATE OR REPLACE TABLE fact_constructor_race AS
        
        SELECT
            r.race_id,
            r.year,
            r.race_name,
            r.date_start,
            r.date_end,
            r.circuit_short_name,
            r.is_sprint_weekend,
            r.country_name,
            c.constructor_id,
            c.constructor_name,
            p.price,
            pts.points AS fantasy_points

        FROM stage_constructor_points_table pts

        LEFT JOIN stage_constructor_price_table p
            ON pts.year = p.year
           AND pts.race = p.race
           AND lower(trim(pts.constructor)) = lower(trim(p.constructor))

        LEFT JOIN dim_race r
            ON pts.year = r.year
           AND pts.race = r.race_num

        LEFT JOIN dim_constructor c
            ON lower(trim(pts.constructor)) = lower(trim(c.constructor_name))
           AND pts.year = c.year

        WHERE r.race_id IS NOT NULL

        ORDER BY r.race_id, c.constructor_id
        
        """)

def validate_fact_constructor_race():
    df = read_fact_constructor_race()

    max_dup = df.groupby(["race_id", "constructor_id"]).size().max()

    if max_dup > 1:
        raise ValueError("Duplicate rows found in fact_constructor_race")

    critical_cols = [
        "race_id",
        "year",
        "constructor_id",
        "constructor_name",
        "price",
        "fantasy_points"
    ]

    null_counts = df[critical_cols].isna().sum()
    print(null_counts)

    if null_counts.sum() > 0:
        raise ValueError("Nulls found in critical columns")

    print("fact_constructor_race validated")


def read_fact_constructor_race():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT *
            FROM fact_constructor_race
        """).df()

    return result


def get_columns():
    fcr = read_fact_constructor_race()
    return fcr.columns