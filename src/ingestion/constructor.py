from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd

import fastf1


#cache location
fastf1.Cache.enable_cache("data/cache/fastf1")



"""

This table's grain is Grain Level: meeting_key, session_key, team

"""


##################################Ingestion Layer########################################

def write_raw_constructors_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("constructor_sessions_df_temp", df)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_constructor_table AS
        SELECT *
        FROM constructor_sessions_df_temp
        """)


def append_raw_constructors_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("constructor_sessions_df_temp", df)

        con.execute("""
        INSERT INTO raw_constructor_table
        SELECT *
        FROM constructor_sessions_df_temp
        """)

#API Caller
def build_raw_constructors_table_controller(years=(2023, 2024, 2025, 2026)):
    all_team_rows = []


    for year in years:
        schedule = fastf1.get_event_schedule(year)

        for _, event in schedule.iterrows():
            try:
                session = event.get_session("R")
                session.load()

                results = session.results

                if results is None or results.empty:
                    continue

                team_df = (
                    results[["TeamName"]]
                    .dropna()
                    .drop_duplicates()
                    .rename(columns={"TeamName": "constructor_name"})
                )

                team_df['year'] = year
                team_df['event_name'] = event['EventName']
                all_team_rows.append(team_df)
            
            except Exception as e:
                print(f'Skipping {year} - {event["EventName"]}: {e}')
                continue
        
    if not all_team_rows:
        return pd.DataFrame(columns=["constructor_name", "year", "event_name"])
    
    combined = pd.concat(all_team_rows, ignore_index=True)
    
    raw_constructor_source = (
        combined[["constructor_name", "year", "event_name"]]
        .drop_duplicates()
        .sort_values("constructor_name")
        .reset_index(drop=True)
    )

        
    write_raw_constructors_table(raw_constructor_source)



def update_raw_constructor_table_controller(year=2026):
    """
    will only update for the given year
    """

    all_team_rows = []

    schedule = fastf1.get_event_schedule(year)

    for _, event in schedule.iterrows():
        try:
            session = event.get_session("R")
            session.load()

            results = session.results

            if results is None or results.empty:
                continue

            team_df = (
                results[["TeamName"]]
                .dropna()
                .drop_duplicates()
                .rename(columns={"TeamName": "constructor_name"})
            )

            team_df['year'] = year
            team_df['event_name'] = event['EventName']
            all_team_rows.append(team_df)
        
        except Exception as e:
            print(f'Skipping {year} - {event["EventName"]}: {e}')
            continue
        
    if not all_team_rows:
        return pd.DataFrame(columns=["constructor_name", "year", "event_name"])
    

    combined = pd.concat(all_team_rows, ignore_index=True)
    
    raw_constructor_source = (
        combined[["constructor_name", "year", "event_name"]]
        .drop_duplicates()
        .sort_values("constructor_name")
        .reset_index(drop=True)
    )


    #need to filter the temp down to only the records that are not present in the raw table
    #these will then get appended to the raw table

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:


        con.register("temp_compiled_session_constructors_df", raw_constructor_source)

        new_raw_records = con.execute("""
            SELECT t.*
            FROM temp_compiled_session_constructors_df t
            LEFT JOIN raw_constructor_table c
                ON t.constructor_name = c.constructor_name
                AND t.year = c.year
                AND t.event_name = c.event_name
            WHERE c.constructor_name IS NULL
        """).df()

    if not new_raw_records.empty:
        append_raw_constructors_table(new_raw_records)



##########################Staging Layer#######################

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

#pull in the raw file
def pull_raw_constructors():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("SELECT * FROM raw_constructors_table").df()

#cleaning the raw file
def clean_raw_constructors(df):
    #FIXME: need to see the raw output first before building this out
    """
    1. dedup
    2. filter rows and cols
    3. data type conversions
    
    """

    #dedup
    df = df.drop_duplicates(subset=["meeting_key", "session_key", "full_name"])

    #filter cols
    cols_to_keep = ["meeting_key", "session_key", "driver_number", "full_name", "name_acronym", "team_name", "first_name", "last_name"]
    df = df[[col for col in cols_to_keep if col in df.columns]]

    return df


#writing the staged table to the database
def build_stage_drivers_controller():

    raw_df = pull_raw_constructors()

    stage_df = clean_raw_constructors(raw_df)

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("constructors_staged_df_temp", stage_df)

        result = con.execute("""
            CREATE OR REPLACE TABLE staged_session_constructors_table AS
            SELECT *
            FROM drivers_staged_df_temp
            """)


    return result

###################warehousing layer################################

"""
utilimate goal is to build a dim_driver_table

the grain level for this table is one row per driver

table features: driver_id, driver_name, name_accronym, first_name, last_name

"""

def build_driver_dim_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        #pulling whatever drivers are in staged table
        staged_driver_pull = con.execute("""
            SELECT
                full_name AS driver_name,
                MIN(name_acronym) as name_acronym
            FROM staged_session_drivers_table
            GROUP BY full_name
        """).df()

        #this will only apply for the first build, all subsequent updates will take the max current id value present and will add one. 
        staged_driver_pull = staged_driver_pull.sort_values("driver_name").reset_index(drop=True)
        staged_driver_pull["driver_id"] = range(1, len(staged_driver_pull) + 1)
        staged_driver_pull = staged_driver_pull[["driver_id", "driver_name", "name_acronym"]]
        

        con.register("driver_pull_temp", staged_driver_pull)

        con.execute("""
            CREATE OR REPLACE TABLE dim_driver AS
            SELECT driver_id, driver_name, name_acronym
            FROM driver_pull_temp
        """)


def update_driver_dim_table():

    '''
    Find new drivers in staged_session_drivers_table
    assign new driver_ids, and append them to dim_driver
    '''

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:


        current_dim_table = con.execute("""
            SELECT *
            FROM dim_driver
            """).df()


        new_driver_stage_pull = con.execute("""
            SELECT DISTINCT 
                s.full_name as driver_name,
                s.name_acronym
            FROM staged_session_drivers_table as s
            LEFT JOIN dim_driver as d
                on s.full_name = d.driver_name
            WHERE d.driver_name IS NULL
                                            
        """).df()

        
        if not new_driver_stage_pull.empty:

            current_max = current_dim_table["driver_id"].max()

            if pd.isna(current_max):
                current_max=0


            new_driver_stage_pull["driver_id"] = range(
                current_max + 1,
                current_max + 1 + len(new_driver_stage_pull)
            )

            #appending the new records into the table
            con.register("new_drivers_df_temp", new_driver_stage_pull)

            con.execute("""
            INSERT INTO dim_driver
            SELECT driver_id, driver_name, name_acronym
            FROM new_drivers_df_temp
            """)


def read_drivers():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        driver_table = con.execute("""
            SELECT *
            FROM dim_driver
        """).df()

    return driver_table



############################Pipeline Controller###############

def constructors_pipeline(update:bool, amount_to_update=15):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_constructors_table_controller()

        #stage
        #build_stage_drivers_controller()

        #warehouse
        #build_driver_dim_table()

    else:
        #appending and writing the raw table
        #update_raw_drivers_table_controller(amount_to_update)

        #stage
        #build_stage_drivers_controller()

        #update warehouse
        #update_driver_dim_table()
        return False