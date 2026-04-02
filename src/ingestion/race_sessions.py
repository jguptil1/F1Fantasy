
from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


#helper functions
def get_meetings_info(year, max_retries = 10, sleep_seconds=2):

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


def write_meetings_table(df):

    con = duckdb.connect("data/database/f1_fantasy.duckdb")

    con.register("meetings_df_temp", df)

    result = con.execute("""
    CREATE OR REPLACE TABLE meetings AS
    SELECT *
    FROM meetings_df_temp
    """)

    con.close()

    return result



def race_sessions_database_controller(years = [2023, 2024, 2025, 2026]):

    '''
    this function controls getting the various meeting ids and writing to the database
    - this is a one time use to build the meetings and to push it to the database
    - for simple update/append of the meetings ids, another function should be used instead to increase efficiency
    '''

    compiled_race_sessions_df = pd.DataFrame()

    for year in years:
        year_df = get_meetings_info(year)
        compiled_race_sessions_df = pd.concat(
            [compiled_race_sessions_df, year_df],
            ignore_index=True
        )

    
    write_meetings_table(compiled_race_sessions_df)



def read_meetings_table():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT * FROM meetings").df()

    return result


#### Helpful get functions for other modules


def get_unique_years_in_meetings_table():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT year FROM meetings").fetchall()
    years = [row[0] for row in result]
    return years


def get_unique_meeting_ids():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    result = con.execute("SELECT DISTINCT meeting_key FROM meetings")
    return result



if __name__ == "__main__":
    # load_dim_driver()
    # show_driver_table()
    #race_sessions_database_controller()
    #print(read_meetings_table())




    years = get_unique_years_in_meetings_table()
    print(years)

    