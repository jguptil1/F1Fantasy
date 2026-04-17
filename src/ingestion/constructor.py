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
        df  = con.execute("SELECT * FROM raw_constructor_table").df()

    return df

#cleaning the raw file
def clean_raw_constructors(df):
    """
    Clean raw constructor data.
    Output grain: one row per constructor per year
    """

    cols_to_keep = ["year", "constructor_name"]

    df = df[[col for col in cols_to_keep if col in df.columns]]

    df = df.drop_duplicates(
        subset=["constructor_name", "year"]
    )

    df = df.sort_values(
        ["year", "constructor_name"]
    ).reset_index(drop=True)

    return df


#writing the staged table to the database
def build_stage_constructors_controller():

    raw_df = pull_raw_constructors()

    stage_df = clean_raw_constructors(raw_df)

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("constructors_staged_df_temp", stage_df)

        result = con.execute("""
            CREATE OR REPLACE TABLE staged_session_constructors_table AS
            SELECT *
            FROM constructors_staged_df_temp
            """)


    return result


###################warehousing layer################################

"""
utilimate goal is to build a dim_driver_table

the grain level for this table is one row per driver

table features: driver_id, driver_name, name_accronym, first_name, last_name

"""

def build_constructor_dim_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        #pulling whatever drivers are in staged table
        staged_constructor_pull = con.execute("""
            SELECT
                year,
                constructor_name
                                
                
            FROM staged_session_constructors_table
            GROUP BY year, constructor_name
        """).df()

        #this will only apply for the first build, all subsequent updates will take the max current id value present and will add one. 
        staged_constructor_pull = staged_constructor_pull.sort_values(["constructor_name", "year"]).reset_index(drop=True)
        staged_constructor_pull["constructor_id"] = range(1, len(staged_constructor_pull) + 1)
        staged_constructor_pull = staged_constructor_pull[["constructor_id", "year", "constructor_name"]]
        

        con.register("constructor_pull_temp", staged_constructor_pull)

        con.execute("""
            CREATE OR REPLACE TABLE dim_constructor AS
            SELECT constructor_id, year, constructor_name
            FROM constructor_pull_temp
        """)


def update_constructor_dim_table():

    '''
    Find new constructors in staged_session_constructors_table
    assign new constructor_ids, and append them to dim_constructor
    '''

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:


        current_dim_table = con.execute("""
            SELECT *
            FROM dim_constructor
            """).df()


        new_constructor_stage_pull = con.execute("""
            SELECT DISTINCT 
                s.year,
                s.constructor_name
            FROM staged_session_constructors_table as s
            LEFT JOIN dim_constructor as d
                ON s.constructor_name = d.constructor_name
                AND s.year = d.year
            WHERE d.constructor_name IS NULL
                                            
        """).df()

        
        if not new_constructor_stage_pull.empty:

            current_max = current_dim_table["constructor_id"].max()

            if pd.isna(current_max):
                current_max=0


            new_constructor_stage_pull["constructor_id"] = range(
                current_max + 1,
                current_max + 1 + len(new_constructor_stage_pull)
            )

            #appending the new records into the table
            con.register("new_constructors_df_temp", new_constructor_stage_pull)

            con.execute("""
            INSERT INTO dim_constructor
            SELECT constructor_id, year, constructor_name
            FROM new_constructors_df_temp
            """)


def read_constructors():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        constructor_table = con.execute("""
            SELECT *
            FROM dim_constructor
        """).df()

    return constructor_table



############################Pipeline Controller###############

def constructors_pipeline(update:bool, amount_to_update=15):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        #build_raw_constructors_table_controller()

        #stage
        #build_stage_constructors_controller()

        #warehouse
        build_constructor_dim_table()

    else:
        #appending and writing the raw table
        update_raw_constructor_table_controller(amount_to_update)

        #stage
        build_stage_constructors_controller()

        #update warehouse
        update_constructor_dim_table()