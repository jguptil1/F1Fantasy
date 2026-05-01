from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd

import fastf1


#cache location
fastf1.Cache.enable_cache("data/cache/fastf1")
DATABASE_PATH = "data/database/f1_fantasy.duckdb"


#################################Ingestion Layer#################################



def get_race_sessions(year=None):
    year_filter = "" if year is None else f"AND r.year = {year}"

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        return con.execute(f"""
            SELECT
                r.race_id,
                r.year,
                s.meeting_key,
                s.session_key,
                r.race_name
            FROM staged_race_sessions_table s
            JOIN dim_race r
                ON s.meeting_key = r.meeting_key
            WHERE s.session_type = 'Race'
              {year_filter}
            ORDER BY r.year, r.race_num
        """).df()


def get_fastf1_race_results(year, race_name):
    session = fastf1.get_session(year, race_name, "R")
    session.load()

    results = session.results.copy()

    return results

def fetch_driver_placements(year=None):
    race_sessions = get_race_sessions(year=year)

    all_results = []

    for _, row in race_sessions.iterrows():
        try:
            results = get_fastf1_race_results(
                year=row["year"],
                race_name=row["race_name"]
            )

            placement_df = results[[
                "Abbreviation",
                "FullName",
                "TeamName",
                "Position",
                "ClassifiedPosition",
                "Status",
                "GridPosition"
            ]].copy()

            placement_df["race_id"] = row["race_id"]
            placement_df["meeting_key"] = row["meeting_key"]
            placement_df["session_key"] = row["session_key"]
            placement_df["year"] = row["year"]
            placement_df["race_name"] = row["race_name"]

            all_results.append(placement_df)

        except Exception as e:
            print(f"Skipping {row['year']} {row['race_name']}: {e}")

    if not all_results:
        return pd.DataFrame()

    return pd.concat(all_results, ignore_index=True)


def build_raw_driver_placements():
    df = fetch_driver_placements()

    if df.empty:
        print("No placement results found.")
        return

    write_raw_driver_placements(df)


def update_write_raw_driver_placements(df):
    if df.empty:
        print("No new placement data to write.")
        return

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("placements_temp", df)

        new_rows = con.execute("""
            SELECT t.*
            FROM placements_temp t
            LEFT JOIN raw_driver_placements r
                ON t.race_id = r.race_id
               AND t.Abbreviation = r.Abbreviation
            WHERE r.race_id IS NULL
        """).df()

        if new_rows.empty:
            print("raw_driver_placements already up to date.")
            return

        con.register("new_placements_temp", new_rows)

        con.execute("""
            INSERT INTO raw_driver_placements
            SELECT *
            FROM new_placements_temp
        """)

        print(f"Inserted {len(new_rows)} new placement rows.")


def write_raw_driver_placements(df):
    with duckdb.connect(DATABASE_PATH) as con:
        con.register("placements_temp", df)

        con.execute("""
            CREATE OR REPLACE TABLE raw_driver_placements AS
            SELECT *
            FROM placements_temp
        """)


def update_raw_driver_placements(year):
    df = fetch_driver_placements(year=year)
    update_write_raw_driver_placements(df)


#########Staging####################

def stage_driver_placements():
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        raw_table = con.execute("""
            SELECT *
            FROM raw_driver_placements
        """).df()

    raw_table = raw_table.drop_duplicates(
        subset=["race_id", "meeting_key", "session_key", "year", "race_name", "FullName"]
    )

    raw_table["driver"] = raw_table["FullName"].str.lower()
    raw_table["constructor"] = raw_table["TeamName"].str.lower()

    dnf_statuses = [
        "Retired",
        "Accident",
        "Collision damage",
        "Undertray"
    ]

    dns_statuses = ["Did not start", "Withdrew"]
    dsq_statuses = ["Disqualified"]

    raw_table["dnf"] = raw_table["Status"].isin(dnf_statuses).astype(int)
    raw_table["dns"] = raw_table["Status"].isin(dns_statuses).astype(int)
    raw_table["dsq"] = raw_table["Status"].isin(dsq_statuses).astype(int)
    raw_table["nc"] = 0

    raw_table = raw_table.dropna(subset=["finish_position", "grid_position"])

    staged_table = raw_table[
        [
            "race_id",
            "year",
            "race_name",
            "driver",
            "constructor",
            "Position",
            "ClassifiedPosition",
            "Status",
            "GridPosition",
            "dns",
            "dnf",
            "dsq",
            "nc"
        ]
    ].rename(columns={
        "Position": "finish_position",
        "ClassifiedPosition": "classified_position",
        "Status": "status",
        "GridPosition": "grid_position",
    })

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("new_placements_temp", staged_table)

        con.execute("""
            CREATE OR REPLACE TABLE stage_driver_placement AS
            SELECT *
            FROM new_placements_temp
        """)

#################################placements pipeline###################


def driver_placements_pipeline(update=False, year=None):
    if update:
        if year is None:
            raise ValueError("year must be provided when update=True")
        update_raw_driver_placements(year)
        stage_driver_placements()
    else:
        build_raw_driver_placements()
        stage_driver_placements()
