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


def get_raw_race_sessions(meeting_ids):

    #throttling happens here 
    pass


if __name__ == "__main__":
    #build_raw_race_meetings_controller()
    get_meeting_ids()
    # show_driver_table()
    #race_sessions_database_controller()
    #print(read_meetings_table())
