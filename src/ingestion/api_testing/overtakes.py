from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



"""


"""


##################################Ingestion Layer########################################


"""
The package required for overtakes is a session_key and a driver_number.

I will be adding the meeting key just as a safe measure
"""

DRIVER_NUMBER = 63
SESSION_NUMBER = 11291
MEETING_KEY = 1285

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

#helper function for updates that only need to pull the last n sessions
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
def get_raw_overtakes(session_key, driver_number, max_retries = 20, sleep_seconds=2):

    '''
    this function creates a pandas dataframe of overtake info for a given driver for a given session_key
    returns: pandas dataframe
    '''

    url = "https://api.openf1.org/v1/overtakes"
    params = {
        "session_key": session_key,
        "overtaking_driver_number": driver_number
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





def overtakes_controller():

    # I will need to pull drivers from each session (should pull this from staged_session_drivers_table

    overtakes_test = get_raw_overtakes(SESSION_NUMBER, DRIVER_NUMBER)

    print(overtakes_test)




if __name__ == "__main__":
    overtakes_controller()