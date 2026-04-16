from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



"""

This table's grain is each driver for all of the unique race sessions in the staged race session table

"""


##################################Ingestion Layer########################################


"""
looks like the api params are based on session keys
"""

#helper function to read the session table
def read_sessions_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM raw_sessions_table").df()
        return result


#helper function to get all of the unique session keys
def get_session_keys():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT session_key FROM staged_race_sessions_table").df()["session_key"].tolist()

    return result


def get_last_n_sessions(n):
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute(f'SELECT session_key FROM staged_race_sessions_table ORDER BY date_start DESC LIMIT {n}').df()["session_key"].tolist()

    return result

#API Caller
def get_raw_drivers(session_key, max_retries = 10, sleep_seconds=2):

    '''
    this function creates a pandas dataframe of meeting info for a given year
    returns: pandas dataframe
    '''

    url = "https://api.openf1.org/v1/drivers"
    params = {
        "session_key": session_key
    }

    #throttling call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            print(f"404 not found for session_key={session_key}. Skipping.")
            return pd.DataFrame()
        
        #rate limit hit
        if response.status_code == 429:
            wait = sleep_seconds * (attempt +1)
            print(f"Rate Limited on session_key={session_key}. Sleeping {wait} seconds")
            time.sleep(wait)
            continue
            
        response.raise_for_status()
        print(f'Fetched: {session_key}')
        return pd.DataFrame(response.json())
    
    raise requests.exceptions.HTTPError(
        f"429 persisted after {max_retries} retries for session_key={session_key}",
        response=response
    )


def write_raw_drivers_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("sessions_drivers_df_temp", df)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_drivers_table AS
        SELECT *
        FROM sessions_drivers_df_temp
        """)


def append_raw_drivers_table(df):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("sessions_drivers_df_temp", df)

        con.execute("""
        INSERT INTO raw_drivers_table
        SELECT *
        FROM sessions_drivers_df_temp
        """)




def build_raw_drivers_table_controller():
    session_keys = get_session_keys()

    compiled_session_drivers_df = pd.DataFrame()
    for session in session_keys:
        session_drivers_df = get_raw_drivers(session)

        if session_drivers_df.empty:
            continue

        compiled_session_drivers_df = pd.concat(
            [compiled_session_drivers_df, session_drivers_df],
            ignore_index=True
        )

    
    write_raw_drivers_table(compiled_session_drivers_df)



def update_raw_drivers_table_controller(num):
    """
    will only update with the last 15 sessions to limit call volume and to increase speed
    """

    session_keys = get_last_n_sessions(num)

    compiled_session_drivers_df = pd.DataFrame()
    for session in session_keys:
        session_drivers_df = get_raw_drivers(session)

        if session_drivers_df.empty:
            continue

        compiled_session_drivers_df = pd.concat(
            [compiled_session_drivers_df, session_drivers_df],
            ignore_index=True
        )

    
    append_raw_drivers_table(compiled_session_drivers_df)



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
def pull_raw_drivers():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT * FROM raw_drivers_table").df()

    return result

#cleaning the raw file
def clean_raw_drivers(df):

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

    raw_df = pull_raw_drivers()

    stage_df = clean_raw_drivers(raw_df)

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    con.register("drivers_staged_df_temp", stage_df)

    result = con.execute("""
        CREATE OR REPLACE TABLE staged_session_drivers_table AS
        SELECT *
        FROM drivers_staged_df_temp
        """)

    con.close()

    return result

###################warehousing layer################################

"""
utilimate goal is to build a dim_driver_table

the grain level for this table is one row per driver

table features: driver_id, driver_name, name_accronym, first_name, last_name

"""

def build_driver_dim_table():

    #pulling the drivers_staged_table


  with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
    driver_staged = con.execute("""
        SELECT DISTINCT
            full_name as driver_name,
            name_acronym
        FROM staged_session_drivers_table
    """).df()

    return driver_staged
    

    



############################Pipeline Controller###############

def drivers_pipeline(update:bool, amount_to_update=15):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_drivers_table_controller()

        #stage
        build_stage_drivers_controller()

    else:
        #appending and writing the raw table
        update_raw_drivers_table_controller(amount_to_update)

        #stage
        build_stage_drivers_controller()

        #driver dim table
        build_driver_dim_table()


 