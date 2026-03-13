from urllib.request import urlopen
from pathlib import Path
import requests
import time
import pandas as pd


#data import/ file paths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = PROJECT_ROOT / "data" / "clean" / "race_session_meeting_info.csv"


print("Resolved file path:", file_path)
print("Exists:", file_path.exists())

race_sessions = pd.read_csv(file_path)


def get_meeting_keys():
    meeting_keys = []

    for key in race_sessions["meeting_key"].unique():
        meeting_keys.append(int(key))
    return meeting_keys

def get_session_info(year, max_retries = 10, sleep_seconds=2):
    url = "https://api.openf1.org/v1/sessions"
    params = {
        "year": year
    }

    #throttling call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            raise requests.exceptions.HTTPError(
                f"404 not found for session_key:{session_key}"
            )
        
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

def get_race_session_result(session_key, max_retries=10, sleep_seconds=2):

    url = "https://api.openf1.org/v1/session_result"
    params = {
        "session_key": session_key
    }

    #throttling call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            raise requests.exceptions.HTTPError(
                f"404 not found for session_key:{session_key}"
            )
        
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

def get_driver_info(session_key, max_retries=10, sleep_seconds=2):
    
    #package
    url = "https://api.openf1.org/v1/drivers"
    params = {
        
        "session_key": session_key
    }
    
    #throttligg call
    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=30)


        #not a valid session_key
        if response.status_code == 404:
            raise requests.exceptions.HTTPError(
                f"404 not found for session_key:{session_key}"
            )
        
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

def get_placement_df(years: list=[2023, 2024, 2025,2026]):
    years = years
    all_results = []
    exception_session_keys = []

    for year in years:

        # need to get the session key for the race

        session_info_df = get_session_info(year)
        session_info_df = session_info_df[session_info_df["session_name"] == "Race"]
        session_info_df = session_info_df[["session_key", "date_start"]]

        #getting each race session key for the given year
        race_session_keys = []

        for session_key in session_info_df["session_key"].unique():
            race_session_keys.append(int(session_key))



        for session_key in race_session_keys:
            try:
                #session_key = race_session_keys[0:5] #session key will eventually be an iterable
                curr_race_result = get_race_session_result(session_key)

                #need to add to this data set the driver acronym
                curr_session_driver_info = get_driver_info(session_key)
                curr_session_driver_info = curr_session_driver_info[["driver_number", "name_acronym", "meeting_key", "session_key"]]
                
                #merge the driver info to the curr race result
                curr_race_result = curr_race_result.merge(curr_session_driver_info, how="left", on=["driver_number", "meeting_key", "session_key"]).rename(columns={"name_acronym": "driver"})
                curr_race_result = curr_race_result.merge(session_info_df, how="left", on="session_key")
                #cut down to only needed columns
                curr_race_result = curr_race_result[["date_start", "driver", "driver_number", "position", "points", "gap_to_leader", "meeting_key", "session_key"]]

                all_results.append(curr_race_result)

                print(f"ADDED session_key {session_key}")
            
            except Exception as e:
                print(f"SKIPPING session_key {session_key}: {e}")
                exception_session_keys.append(session_key)
                continue

    placements = pd.concat(all_results, ignore_index=True)
    return placements


