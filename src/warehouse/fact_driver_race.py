from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd





def build_fact_driver_race():
    override_rows = pd.DataFrame([
        {"race_id": 13, "driver": "daniel ricciardo", "constructor": "alphatauri"},
        {"race_id": 18, "driver": "liam lawson", "constructor": "alphatauri"},
        {"race_id": 11, "driver": "nyck de vries", "constructor": "alphatauri"},
        {"race_id": 55, "driver": "lance stroll", "constructor": "aston martin"},
    ])

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        driver_constructor_map = con.execute("""
            SELECT DISTINCT
                race_id,
                driver,
                constructor
            FROM stage_driver_placement
        """).df()

        driver_constructor_map = pd.concat(
            [driver_constructor_map, override_rows],
            ignore_index=True
        )

        driver_constructor_map = (
            driver_constructor_map
            .drop_duplicates(subset=["race_id", "driver"], keep="first")
        )

        con.register("driver_constructor_map_temp", driver_constructor_map)

        con.execute("""
            CREATE OR REPLACE TABLE fact_driver_race AS
            WITH placement_map AS (
                SELECT
                    race_id,
                    driver,
                    MIN(finish_position) AS finish_position,
                    ANY_VALUE(status) AS status
                FROM stage_driver_placement
                GROUP BY race_id, driver
            )
            SELECT
                r.race_id,
                r.year,
                r.race_name,
                r.date_start,
                r.date_end,
                r.circuit_short_name,
                r.is_sprint_weekend,
                r.country_name,
                d.driver_id,
                d.driver_name,
                c.constructor_id,
                c.constructor_name,
                p.price,
                pts.points AS fantasy_points,
                plc.finish_position AS driver_finish_position,
                plc.status,
                elo.elo_before,
                elo.elo_delta,
                elo.elo_after
            FROM stage_driver_points_table pts
            LEFT JOIN stage_driver_price_table p
                ON pts.year = p.year
                AND pts.race = p.race
                AND pts.driver = p.driver
            LEFT JOIN dim_driver d
                ON pts.driver = d.driver_name
            LEFT JOIN dim_race r
                ON pts.year = r.year
                AND pts.race = r.race_num
            LEFT JOIN driver_constructor_map_temp sd
                ON r.race_id = sd.race_id
                AND LOWER(TRIM(d.driver_name)) = LOWER(TRIM(sd.driver))
            LEFT JOIN dim_constructor c
                ON LOWER(TRIM(sd.constructor)) = LOWER(TRIM(c.constructor_name))
                AND r.year = c.year
            LEFT JOIN placement_map plc
                ON r.race_id = plc.race_id
                AND d.driver_name = plc.driver
            LEFT JOIN staged_elo_table elo
                ON r.race_id = elo.race_id
                AND d.driver_name = elo.driver
            WHERE r.race_id IS NOT NULL
            ORDER BY race_id
        """)


#helper
def get_columns():
    fdr = read_fact_driver_race()
    return fdr.columns

def validate_fact_driver_race():
    df = read_fact_driver_race()

    max_dup = df.groupby(["race_id", "driver_id"]).size().max()

    if max_dup > 1:
        raise ValueError("Duplicate rows found in fact_driver_race")

    print("fact_driver_race validated")


def read_fact_driver_race():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT * FROM fact_driver_race             
            """).df()
    return result
