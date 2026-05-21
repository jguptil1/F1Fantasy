from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



def read_quali_session_key_list():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM staged_race_sessions_table WHERE session_type = 'Qualifying'").df()
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

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("sessions_raw_df_temp", df)

        con.execute("""
        CREATE OR REPLACE TABLE raw_quali_results_table AS
        SELECT *
        FROM sessions_raw_df_temp
        """)


def build_raw_quali_results():
    quali_session_keys = read_quali_session_key_list()

    compiled_quali_sessions_df = pd.DataFrame()

    for session_key in quali_session_keys:
        print(f'Getting Quali Result for: {session_key}')
        quali_session_df = get_raw_quali_session_result(session_key=session_key)

        if quali_session_df.empty:
            continue
        

        compiled_race_sessions_df = pd.concat(
            [compiled_quali_sessions_df, quali_session_df],
            ignore_index=True
        )

        write_raw_quali_results_table(compiled_race_sessions_df)


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


#cols to keep: meeting_key, session_key, driver_number, qualifying_position, qualifying_laps, q1_time, q2_time, q3_time, dnf, dns, dsq

def build_staged_qualifying_results_table(raw_df):

    stage_df = raw_df.copy()

    stage_df["q1_time"] = stage_df["duration"].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None)
    stage_df["q2_time"] = stage_df["duration"].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else None)
    stage_df["q3_time"] = stage_df["duration"].apply(lambda x: x[2] if isinstance(x, list) and len(x) > 2 else None)

    stage_df = stage_df.rename(columns={
        "position": "qualifying_position",
        "number_of_laps": "qualifying_laps"
    })

    #need to bring in the dim_driver

    #will get race_id via the dim_race (join on meeting_key)

    #will get the driver_name (full_name) via the staged_session_drivers_table (join on meeting_key and driver_number)



def main():
    build_raw_quali_results()
    raw_quali_table = read_raw_quali_results_table()
    print(raw_quali_table.head())




if __name__ == "__main__":
    main()
