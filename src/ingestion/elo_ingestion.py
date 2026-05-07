from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


import os

import elo


"""

elo module requires a placement table and an overrides table for post race disqualifications due to api errors

"""


##############################ingestion############################

#brining in the 
def read_placement_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
        SELECT *
        FROM stage_driver_placement
                    """).df()
    return result


def create_overrides_table():

    overrides_df = pd.DataFrame({
        "year": [2023, 2023, 2026],
        "race_id": [19, 19, 1],
        "driver": ["HAM", "LEC", "STR"],
        "dsq_override": [True, True, None],
        "position_override": [None, None, None],
        "dns_override": [None, None, None],
        "dnf_override": [None, None, None],
        "nc_override": [None, None, True],
    })
        
    return overrides_df

def run_elo(placement_table, overrides_df):
    elo_table = elo.run_driver_elo_pipeline(
        placement_df=placement_table,
        overrides_df=overrides_df,
        year_col="year",
        race_col="race_id",
        driver_col="driver",
        position_col="finish_position",
        dns_col="dns",
        dnf_col="dnf",
        dsq_col="dsq",
        nc_col="nc",
        init_elo=1500,
        k_factor=8,
        season_shrink=0.75,
        inactivity_shrink=0.75,
        return_matchups=False
    )
    return elo_table

#######################################Raw########################################


def build_raw_elo_table(elo_table):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("raw_elo_table_temp", elo_table)

        con.execute("""
        CREATE OR REPLACE TABLE raw_elo_table AS
        SELECT *
        FROM raw_elo_table_temp
        """)





###################################Stage###################################

#rename columns
#standardize data types
#filter unwanted rows/columns
    #testing and canceled events
#deduplicate
#reshape wide to long
#standardize names/codes
#add simple derived fields needed for joins
#align grains
#prepare keys for warehouse layer


#helper functions

def pull_raw_elo_table():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:


        result = con.execute("""
        SELECT *
        FROM raw_elo_table
        """).df()

    return result

#cleaning the raw file
def clean_raw_elo(df):

    """
    1. dedup
    2. filter rows and cols
    3. data type conversions
    
    """

    #dedup
    df = df.drop_duplicates(subset=["race_id", "year", "race_name", "driver"])



    return df


DATABASE_PATH = "data/database/f1_fantasy.duckdb"


def get_fact_driver_race_for_elo_expand():
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        return con.execute("""
            SELECT
                f.race_id,
                f.year,
                f.race_name,
                f.driver_id,
                d.driver_name AS driver
            FROM fact_driver_race f
            JOIN dim_driver d
                ON f.driver_id = d.driver_id
            WHERE f.race_id IS NOT NULL
            ORDER BY f.year, f.race_id
        """).df()


def expand_elo_to_fact_driver_race(elo_df, fact_df):
    fact_base = fact_df[
        ["race_id", "year", "race_name", "driver_id", "driver"]
    ].copy()

    elo_small = elo_df[
        ["race_id", "driver", "elo_before", "elo_delta", "elo_after"]
    ].copy()

    merged = fact_base.merge(
        elo_small,
        on=["race_id", "driver"],
        how="left"
    )

    merged = merged.sort_values(
        ["driver_id", "year", "race_id"]
    ).reset_index(drop=True)

    merged["carried_elo"] = (
        merged.groupby("driver_id")["elo_after"].ffill()
    )

    merged["elo_before"] = (
        merged["elo_before"]
        .fillna(merged["carried_elo"])
        .fillna(1500)
    )

    merged["elo_delta"] = merged["elo_delta"].fillna(0)
    merged["elo_after"] = merged["elo_after"].fillna(merged["elo_before"])

    merged = merged.drop(columns=["carried_elo"])

    return merged


def build_staged_elo_table():
    raw_elo = pull_raw_elo_table()
    raw_elo = clean_raw_elo(raw_elo)

    fact_df = get_fact_driver_race_for_elo_expand()

    staged_elo = expand_elo_to_fact_driver_race(
        elo_df=raw_elo,
        fact_df=fact_df
    )

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("staged_elo_temp", staged_elo)

        con.execute("""
            CREATE OR REPLACE TABLE staged_elo_table AS
            SELECT *
            FROM staged_elo_temp
        """)

############################Pipeline Controller###############

def elo_pipeline(update:bool):

    '''
    for this one, given that it doesnt use API's directly we can always build
    '''

    if not update:
        placement_table = read_placement_table()
        overrides_table = create_overrides_table()

        elo_table = run_elo(placement_table=placement_table, overrides_df=overrides_table)

        build_raw_elo_table(elo_table)
        build_stage_elo_controller()

    else:
        placement_table = read_placement_table()
        overrides_table = create_overrides_table()

        elo_table = run_elo(placement_table=placement_table, overrides_df=overrides_table)

        build_raw_elo_table(elo_table)
        build_stage_elo_controller()











