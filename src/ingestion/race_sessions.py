from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



##################################Ingestion Layer########################################


#helper function to get all of the unique meeting ids
def get_meeting_ids():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT meeting_key FROM staged_race_meetings_table").df()["meeting_key"].tolist()

    return result


#helper function to read the session table

def read_meeting_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM raw_sessions_table").df()
        return result



#API Caller
def get_raw_race_session(year, max_retries = 10, sleep_seconds=2):

    '''
    this function creates a pandas dataframe of meeting info for a given year
    returns: pandas dataframe
    '''

    url = "https://api.openf1.org/v1/sessions"
    params = {
        "year": year
    }

    #throttling call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            print(f"404 not found for meeting_id={year}. Skipping.")
            return pd.DataFrame()
        
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
        response=response # type: ignore
    )


#HUGE WRITE
def write_raw_sessions_table(df):

    con = duckdb.connect("data/database/f1_fantasy.duckdb")

    con.register("sessions_raw_df_temp", df)

    result = con.execute("""
    CREATE OR REPLACE TABLE raw_sessions_table AS
    SELECT *
    FROM sessions_raw_df_temp
    """)

    con.close()

    return result


#APPEND
def append_raw_sessions_table(df):

    con = duckdb.connect("data/database/f1_fantasy.duckdb")

    con.register("sessions_raw_df_temp", df)

    result = con.execute("""
    INSERT INTO raw_sessions_table
    SELECT *
    FROM sessions_raw_df_temp
    """)

    con.close()

    return result



#database writer
def build_raw_race_sessions_controller(years = [2023, 2024, 2025, 2026]):
    
    compiled_race_sessions_df = pd.DataFrame()

    for year in years:
        print(f'Compiling year: {year}')
        race_session_df = get_raw_race_session(year)

        if race_session_df.empty:
                continue

        compiled_race_sessions_df = pd.concat(
            [compiled_race_sessions_df, race_session_df],
            ignore_index=True
        )


    write_raw_sessions_table(compiled_race_sessions_df)

def update_raw_race_sessions_controller(year = 2026):
    compiled_race_sessions_df = pd.DataFrame()

    print(f'Compiling race sessions for year: {year}')
    race_session_df = get_raw_race_session(year)
        

    compiled_race_sessions_df = pd.concat(
        [compiled_race_sessions_df, race_session_df],
        ignore_index=True
    )


    append_raw_sessions_table(compiled_race_sessions_df)



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
def pull_raw_sessions():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT * FROM raw_sessions_table").df()

    return result

#cleaning the raw file
def clean_raw_sessions(df):

    """
    1. dedup
    2. filter rows and cols
    3. data type conversions
    
    """

    #dedup
    df = df.drop_duplicates(subset=["session_key"])


    #filter cols
    cols_to_keep = ["session_key", "session_type", "session_name", "date_start", "date_end", "meeting_key", "location", "year"]
    df = df[[col for col in cols_to_keep if col in df.columns]]


    #data type conversions
    df["date_start"] = pd.to_datetime(df["date_start"], utc=True, errors="coerce")
    df["date_end"] = pd.to_datetime(df["date_end"], utc=True, errors="coerce") 

    return df


#writing the staged table to the database
def build_stage_sessions_controller():

    raw_df = pull_raw_sessions()

    stage_df = clean_raw_sessions(raw_df)

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    con.register("sessions_staged_df_temp", stage_df)

    result = con.execute("""
        CREATE OR REPLACE TABLE staged_race_sessions_table AS
        SELECT *
        FROM sessions_staged_df_temp
        """)

    con.close()

    return result


############################Pipeline Controller###############

def sessions_pipeline(update:bool):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_race_sessions_controller(years = [2023,2024,2025,2026])

        #stage
        build_stage_sessions_controller()

    else:
        #building and writing the raw table
        update_raw_race_sessions_controller(year = 2026)

        #stage
        build_stage_sessions_controller()
 



