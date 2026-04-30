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
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT DISTINCT session_key FROM staged_race_sessions_table").df()["session_key"].tolist()

    return result


def get_last_n_sessions(n):

    """
    returns the last n unique race_session ids
    """

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute(f"""
            SELECT session_key
            FROM (
                SELECT session_key, MAX(date_start) AS max_date_start
                FROM staged_race_sessions_table
                GROUP BY session_key
            )
            ORDER BY max_date_start DESC
            LIMIT {n}
            """).df()["session_key"].tolist()

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
        f"429 persisted after {max_retries} retries for session_key={session_key}"
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


    #this pulls all n last sessions
    session_keys = get_last_n_sessions(num)


    #this builds the temp df that needs to eventually get slimmed down based on what unique meeting_key+session_key+full_name grain exists
    temp_compiled_session_drivers_df = pd.DataFrame()
    for session in session_keys:
        session_drivers_df = get_raw_drivers(session)

        if session_drivers_df.empty:
            continue

        temp_compiled_session_drivers_df = pd.concat(
            [temp_compiled_session_drivers_df, session_drivers_df],
            ignore_index=True
        )

    
    temp_compiled_session_drivers_df = temp_compiled_session_drivers_df.drop_duplicates(subset=["meeting_key", "session_key", "full_name"])


    #need to filter the temp down to only the records that are not present in the raw table
    #these will then get appended to the raw table

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:


        con.register("temp_compiled_session_drivers_df", temp_compiled_session_drivers_df)

        new_raw_records = con.execute("""
            SELECT t.*
            FROM temp_compiled_session_drivers_df t
            LEFT JOIN raw_drivers_table r
                ON t.meeting_key = r.meeting_key
               AND t.session_key = r.session_key
               AND t.full_name = r.full_name
            WHERE r.full_name IS NULL
        """).df()

    if not new_raw_records.empty:
        append_raw_drivers_table(new_raw_records)



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

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
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

    df["full_name"] = df["full_name"].str.lower()

    df["constructor_name"] = df['team_name']
    df = df.drop(columns=["team_name"])

    return df


#writing the staged table to the database
def build_stage_drivers_controller():

    raw_df = pull_raw_drivers()

    stage_df = clean_raw_drivers(raw_df)

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("drivers_staged_df_temp", stage_df)

        result = con.execute("""
            CREATE OR REPLACE TABLE staged_session_drivers_table AS
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

def drivers_pipeline(update:bool, amount_to_update=15):

    '''
    update toggle helps with decreasing API Call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_drivers_table_controller()

        #stage
        build_stage_drivers_controller()

        #warehouse
        build_driver_dim_table()

    else:
        #appending and writing the raw table
        update_raw_drivers_table_controller(amount_to_update)

        #stage
        build_stage_drivers_controller()

        #update warehouse
        update_driver_dim_table()


 