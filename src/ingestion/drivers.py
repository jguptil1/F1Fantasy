from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd



##################################Ingestion Layer########################################


"""
looks like the api params are based on session keys
"""

#helper function to get all of the unique session keys
def get_session_keys():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT session_key FROM staged_race_sessions_table").df()["session_key"].tolist()

    return result



def get_session_drivers(session_key):

    '''
    collect the unique drivers for a given racing session
    '''

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
        return pd.DataFrame(response.json())
    
    raise requests.exceptions.HTTPError(
        f"429 persisted after {max_retries} retries for session_key={session_key}",
        response=response
    )
    




def build_raw_drivers_table():
    session_keys = get_session_keys()


    compiled_race_sessions_df = pd.DataFrame()
    for session in session_keys:
        session_drivers_df = get_raw_drivers(session)

        if session_drivers_df.isempty():
            continue




#helper function to read the session table

def read_meeting_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM raw_sessions_table").df()
        return result




if __name__ == "__main__":
    session_keys = get_session_keys()
    print(session_keys)
