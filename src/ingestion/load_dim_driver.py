import duckdb
import pandas as pd

from urllib.request import urlopen
import json

def load_dim_driver():
    con = duckdb.connect("data/database/f1_fantasy.duckdb")

    con.execute("""
    CREATE OR REPLACE TABLE dim_driver AS
    SELECT *
    FROM read_csv_auto('data/raw/manual/dim_driver.csv')
    """)



    con.close()


def show_driver_table():

    con = duckdb.connect("data/database/f1_fantasy.duckdb")
    con.execute("SHOW TABLES").fetchall()



def get_driver_names(): 

    #get all relavent meeting ids for 2023 and beyond
        #for each meeting_id, get all race sessions for each meeting
        #within each race_session get the participating drivers numbers
        #store the drivers
    #dedup after going through each year


    years = [2023, 2024, 2025, 2026]
    meeting_keys = []
    
    for year in years:

    #getting the meeting_keys for each year
        response = urlopen(f'https://api.openf1.org/v1/meetings?year={year}')
        data = json.loads(response.read().decode('utf-8'))
        
        meeting_df = pd.DataFrame(data)
        meeting_df = meeting_df[
        ~meeting_df["meeting_official_name"].str.contains(
            "test|testing|called off",
            case=False,
            na=False
        )
    ]
        meeting_keys.append(meeting_df["meeting_key"].drop_duplicates().tolist())
    

    
    race_session_keys = []
    for meeting_key in meeting_keys:
        response = urlopen(f'https://api.openf1.org/v1/sessions?meeting_key={meeting_key}')
        data = json.loads(response.read().decode('utf-8'))

        sessions = pd.DataFrame(data)
        race_session_row = sessions[sessions["session_type"] == "Race"].reset_index(drop=True)
        race_session_keys.append(int(race_session_row["session_key"].iloc[0]))
    
    print(race_session_keys)


if __name__ == "__main__":
    # load_dim_driver()
    # show_driver_table()
    get_driver_names()