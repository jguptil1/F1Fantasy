
from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



##################################Ingestion Layer########################################



#helper functions
def get_raw_meetings(year, max_retries = 10, sleep_seconds=2):

    '''
    this function creates a pandas dataframe of meeting info for a given year
    returns: pandas dataframe
    '''

    url = "https://api.openf1.org/v1/meetings"
    params = {
        "year": year
    }

    #throttling call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            raise requests.exceptions.HTTPError(
                f"404 not found for year:{year}"
            )
        
        #rate limit hit
        if response.status_code == 429:
            wait = sleep_seconds * (attempt +1)
            print(f"Rate Limited on year={year}. Sleeping {wait} seconds")
            time.sleep(wait)
            continue
            
        response.raise_for_status()
        return pd.DataFrame(response.json())
    
    raise requests.exceptions.HTTPError(
        f"429 persisted after {max_retries} retries for year={year}",
        response=response
    )

#QA
def read_raw_meetings_table():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT * FROM raw_meetings_table").df()

    return result

#QA
def get_unique_years_in_raw_meetings_table():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT year FROM raw_meetings_table").fetchall()
    years = [row[0] for row in result]
    return years


#helper function to read meeting_key table
def get_unique_meeting_ids_raw_table():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT meeting_key FROM raw_meetings_table")
    return result

#LOAD
def write_raw_meetings_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        
        con.register("raw_meetings_df_temp", df)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_meetings_table AS
        SELECT *
        FROM raw_meetings_df_temp
        """)


#LOAD
def append_raw_meetings_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("raw_meetings_df_temp", df)

        result = con.execute("""
        INSERT INTO raw_meetings_table
        SELECT *
        FROM raw_meetings_df_temp
        """)

#RAW CONTROLLER
def build_raw_race_meetings_controller(years = [2023, 2024, 2025, 2026]):

    '''
    this function controls getting the various meeting ids and writing to the database
    - this is a one time use to build the meetings and to push it to the database
    - for simple update/append of the meetings ids, another function should be used instead to increase efficiency
    '''

    compiled_race_sessions_df = pd.DataFrame()

    for year in years:
        year_df = get_raw_meetings(year)
        compiled_race_sessions_df = pd.concat(
            [compiled_race_sessions_df, year_df],
            ignore_index=True
        )

    
    write_raw_meetings_table(compiled_race_sessions_df)

def update_raw_race_meetings_controller(year = 2026): 
    compiled_race_sessions_df = pd.DataFrame()

    print(f'Compiling race meetings for year: {year}')   
    year_df = get_raw_meetings(year)

    compiled_race_sessions_df = pd.concat(
        [compiled_race_sessions_df, year_df],
        ignore_index=True
    )

    
    append_raw_meetings_table(compiled_race_sessions_df)

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
def pull_raw_meetings():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT * FROM raw_meetings_table").df()

    return result

#cleaning the raw file
def clean_raw_meetings(df):

    """
    1. dedup
    2. filter rows and cols
    3. data type conversions
    
    """

    #dedup
    df = df.drop_duplicates(subset=["meeting_key"])

    #filter rows
    
    ##taking out testing meetings or meetings that got canceled
    df = df[
        ~df["meeting_official_name"].str.contains(
            "called off|test",
            case=False,
            na=False
        )
    ]

    #filter cols
    cols_to_keep = ["meeting_key", "meeting_name", "country_name", "circuit_short_name", "circuit_type", "date_start", "date_end", "year"]
    df = df[[col for col in cols_to_keep if col in df.columns]]


    #data type conversions
    df["date_start"] = pd.to_datetime(df["date_start"], utc=True, errors="coerce")
    df["date_end"] = pd.to_datetime(df["date_start"], utc=True, errors="coerce")  

    return df


#writing the staged table to the database
def build_stage_meetings_controller():

    raw_df = pull_raw_meetings()

    stage_df = clean_raw_meetings(raw_df)

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    con.register("meetings_staged_df_temp", stage_df)

    result = con.execute("""
        CREATE OR REPLACE TABLE staged_race_meetings_table AS
        SELECT *
        FROM meetings_staged_df_temp
        """)

    con.close()

    return result




############################Pipeline Controller###############

def meetings_pipeline(update:bool):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_race_meetings_controller(years = [2023,2024,2025,2026])

        #stage
        build_stage_meetings_controller()

    else:
        #building and writing the raw table
        update_raw_race_meetings_controller(year = 2026)

        #stage
        build_stage_meetings_controller()
 

    