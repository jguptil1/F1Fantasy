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
                r.race_name,
                c.constructor_id,
                p.price,
                pts.points AS fantasy_points
            FROM stage_constructor_points_table pts
            LEFT JOIN stage_constructor_price_table p
                ON pts.year = p.year
               AND pts.race = p.race
               AND pts.constructor = p.constructor
            LEFT JOIN dim_race r
                ON pts.year = r.year
               AND pts.race = r.race_num
            LEFT JOIN dim_constructor c
                ON LOWER(TRIM(pts.constructor)) = LOWER(TRIM(c.constructor_name))
               AND pts.year = c.year
            WHERE r.race_id IS NOT NULL
        """)

def validate_fact_constructor_race():
    df = read_fact_constructor_race()

    max_dup = df.groupby(["race_id", "constructor_id"]).size().max()

    if max_dup > 1:
        raise ValueError("Duplicate rows found in fact_constructor_race")

    print("fact_constructor_race validated")


def read_fact_constructor_race():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT * FROM fact_constructor_race             
            """).df()
    return result