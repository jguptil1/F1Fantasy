from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd
import numpy as np
import numpy.ma as ma



def read_quali_session_key_list():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM staged_race_sessions_table WHERE session_type = 'Qualifying' AND session_name = 'Qualifying'").df()
        session_key_list = result["session_key"].tolist()
        return session_key_list





#API Caller
def get_raw_quali_session_result(session_key, max_retries = 10, sleep_seconds=2):

    '''
    this function creates a pandas dataframe of qualifying results
    returns: pandas dataframe
    '''

    url = "https://api.openf1.org/v1/session_result"
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
        return pd.DataFrame(response.json())
    
    raise requests.exceptions.HTTPError(
        f"429 persisted after {max_retries} retries for session_key={session_key}",
        response=response # type: ignore
    )


def write_raw_quali_results_table(df):


    #for whatever reason the spa, 2023 qualifying is not apart of open f1's api, so i have to manually add it every build


    manual_spa_2023_quali_rows = [
        {"position": 1, "driver_number": 1, "number_of_laps": 22, "dnf": False, "dns": False, "dsq": False, "duration": [118.515, 112.784, 106.168], "gap_to_leader": [0.000, 0.000, 0.000], "meeting_key": 1216, "session_key": 9135},
        {"position": 2, "driver_number": 16, "number_of_laps": 23, "dnf": False, "dns": False, "dsq": False, "duration": [118.300, 112.017, 106.988], "gap_to_leader": [-0.215, -0.767, 0.820], "meeting_key": 1216, "session_key": 9135},
        {"position": 3, "driver_number": 11, "number_of_laps": 22, "dnf": False, "dns": False, "dsq": False, "duration": [118.899, 112.353, 107.045], "gap_to_leader": [0.384, -0.431, 0.877], "meeting_key": 1216, "session_key": 9135},
        {"position": 4, "driver_number": 44, "number_of_laps": 24, "dnf": False, "dns": False, "dsq": False, "duration": [118.563, 112.345, 107.087], "gap_to_leader": [0.048, -0.439, 0.919], "meeting_key": 1216, "session_key": 9135},
        {"position": 5, "driver_number": 55, "number_of_laps": 23, "dnf": False, "dns": False, "dsq": False, "duration": [118.688, 111.711, 107.152], "gap_to_leader": [0.173, -1.073, 0.984], "meeting_key": 1216, "session_key": 9135},
        {"position": 6, "driver_number": 81, "number_of_laps": 23, "dnf": False, "dns": False, "dsq": False, "duration": [118.872, 111.534, 107.365], "gap_to_leader": [0.357, -1.250, 1.197], "meeting_key": 1216, "session_key": 9135},
        {"position": 7, "driver_number": 4, "number_of_laps": 21, "dnf": False, "dns": False, "dsq": False, "duration": [119.981, 112.252, 107.669], "gap_to_leader": [1.466, -0.532, 1.501], "meeting_key": 1216, "session_key": 9135},
        {"position": 8, "driver_number": 63, "number_of_laps": 24, "dnf": False, "dns": False, "dsq": False, "duration": [119.035, 112.605, 107.805], "gap_to_leader": [0.520, -0.179, 1.637], "meeting_key": 1216, "session_key": 9135},
        {"position": 9, "driver_number": 14, "number_of_laps": 22, "dnf": False, "dns": False, "dsq": False, "duration": [118.834, 112.751, 107.843], "gap_to_leader": [0.319, -0.033, 1.675], "meeting_key": 1216, "session_key": 9135},
        {"position": 10, "driver_number": 18, "number_of_laps": 22, "dnf": False, "dns": False, "dsq": False, "duration": [119.663, 112.193, 108.841], "gap_to_leader": [1.148, -0.591, 2.673], "meeting_key": 1216, "session_key": 9135},
        {"position": 11, "driver_number": 22, "number_of_laps": 15, "dnf": False, "dns": False, "dsq": False, "duration": [119.044, 113.148, None], "gap_to_leader": [0.529, 0.364, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 12, "driver_number": 10, "number_of_laps": 17, "dnf": False, "dns": False, "dsq": False, "duration": [119.511, 113.671, None], "gap_to_leader": [0.996, 0.887, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 13, "driver_number": 20, "number_of_laps": 17, "dnf": False, "dns": False, "dsq": False, "duration": [120.020, 114.160, None], "gap_to_leader": [1.505, 1.376, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 14, "driver_number": 77, "number_of_laps": 17, "dnf": False, "dns": False, "dsq": False, "duration": [119.484, 114.694, None], "gap_to_leader": [0.969, 1.910, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 15, "driver_number": 31, "number_of_laps": 13, "dnf": False, "dns": False, "dsq": False, "duration": [119.634, 116.372, None], "gap_to_leader": [1.119, 3.588, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 16, "driver_number": 23, "number_of_laps": 8, "dnf": False, "dns": False, "dsq": False, "duration": [120.314, None, None], "gap_to_leader": [1.799, None, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 17, "driver_number": 24, "number_of_laps": 9, "dnf": False, "dns": False, "dsq": False, "duration": [120.832, None, None], "gap_to_leader": [2.317, None, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 18, "driver_number": 2, "number_of_laps": 6, "dnf": False, "dns": False, "dsq": False, "duration": [121.535, None, None], "gap_to_leader": [3.020, None, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 19, "driver_number": 3, "number_of_laps": 8, "dnf": False, "dns": False, "dsq": False, "duration": [122.159, None, None], "gap_to_leader": [3.644, None, None], "meeting_key": 1216, "session_key": 9135},
        {"position": 20, "driver_number": 27, "number_of_laps": 5, "dnf": False, "dns": False, "dsq": False, "duration": [123.166, None, None], "gap_to_leader": [4.651, None, None], "meeting_key": 1216, "session_key": 9135},
    ]

    manual_df = pd.DataFrame(manual_spa_2023_quali_rows)


    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("sessions_raw_df_temp", df)

        con.execute("""
        CREATE OR REPLACE TABLE raw_quali_results_table AS
        SELECT *
        FROM sessions_raw_df_temp
        """)

        con.register("manual_spa_quali", manual_df)

        print("MANUALY ADDING QUALI SESSION 9135")

        con.execute("""
            DELETE FROM raw_quali_results_table
            WHERE session_key = 9135
        """)

        con.execute("""
            INSERT INTO raw_quali_results_table
            SELECT *
            FROM manual_spa_quali
        """)


def build_raw_quali_results():
    quali_session_keys = read_quali_session_key_list()

    compiled_quali_sessions_df = pd.DataFrame()

    for session_key in quali_session_keys:
        print(f'Getting Quali Result for: {session_key}')
        quali_session_df = get_raw_quali_session_result(session_key=session_key)

        if quali_session_df.empty:
            continue
        

        compiled_quali_sessions_df = pd.concat(
            [compiled_quali_sessions_df, quali_session_df],
            ignore_index=True
        )

    write_raw_quali_results_table(compiled_quali_sessions_df)


def read_raw_quali_results_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        result = con.execute("""
        SELECT *
        FROM raw_quali_results_table
        """).df()
        return result
    



##############################Staging###########################
#Grain should be race_id x driver_id
#desired output of this layer is the staged_qualifying_results_table




def get_quali_time(x, idx):
    if not isinstance(x, (list, tuple, np.ndarray)) or len(x) <= idx:
        return None

    value = x[idx]

    if ma.is_masked(value):
        return None

    if pd.isna(value):
        return None

    return float(value)


def build_staged_qualifying_results_table(raw_df):

    quali_stage_df = raw_df.copy()

    quali_stage_df["q1_time"] = quali_stage_df["duration"].apply(lambda x: get_quali_time(x, 0))
    quali_stage_df["q2_time"] = quali_stage_df["duration"].apply(lambda x: get_quali_time(x, 1))
    quali_stage_df["q3_time"] = quali_stage_df["duration"].apply(lambda x: get_quali_time(x, 2))

    quali_stage_df = quali_stage_df.rename(columns={
        "position": "qualifying_position",
        "number_of_laps": "qualifying_laps"
    })

    
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("quali_stage_results", quali_stage_df)

        con.execute("""
            CREATE OR REPLACE TABLE staged_qualifying_results_table AS
            
            WITH driver_map AS (
                SELECT DISTINCT
                    meeting_key,
                    driver_number,
                    full_name
                FROM staged_session_drivers_table
            )   
                        
            SELECT
                dr.year,
                dr.race_id,
                q.meeting_key,
                q.session_key,
                q.driver_number,
                ssd.full_name AS driver_name,
                dd.driver_id,
                q.qualifying_position,
                q.qualifying_laps,
                q.q1_time,
                q.q2_time,
                q.q3_time,
                q.dnf,
                q.dns,
                q.dsq
            FROM quali_stage_results q
            LEFT JOIN dim_race dr
                ON q.meeting_key = dr.meeting_key
            LEFT JOIN driver_map ssd
                ON q.meeting_key = ssd.meeting_key
            AND q.driver_number = ssd.driver_number
            LEFT JOIN dim_driver dd
                ON LOWER(TRIM(ssd.full_name)) = LOWER(TRIM(dd.driver_name))
        """)

def read_staged_qualifying_results_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""SELECT * FROM staged_qualifying_results_table""").df()

    return result

def main():
    #build_raw_quali_results()
    raw_quali_table = read_raw_quali_results_table()
    
    
    build_staged_qualifying_results_table(raw_quali_table)
    result = read_staged_qualifying_results_table()
    print(result)
    print(result.shape)
    

def quali_results_pipeline(update:bool):

    '''
    update toggle helps with decreasing API Call volume
    FIXME: currently it doesnt matter if it is built or updated as it will build regardless, add the update feature in the future to decrease call volume
    '''

    if not update:
        #building and writing the raw table
        build_raw_quali_results()

        #stage
        raw_quali_table = read_raw_quali_results_table()
        build_staged_qualifying_results_table(raw_quali_table)

    else:
        #building and writing the raw table
        build_raw_quali_results()

        #stage
        raw_quali_table = read_raw_quali_results_table()
        build_staged_qualifying_results_table(raw_quali_table)
