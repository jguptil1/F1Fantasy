from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


"""
Ingesting the data from the excel file that contains the team config data for each of the weeks

"""


###########################################Ingestion##################################

#helper
def load_working_directory():
    return Path.cwd()

#helper
def load_raw_file_path():

    cwd = load_working_directory()

    return cwd / "data" / "raw" / "driver_config.xlsx"


def load_team_config_sheet():
  df = pd.read_excel(load_raw_file_path(), sheet_name="DRIVER CONFIG")
  return df


def build_team_config_table(budget_sheet):
        
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("team_sheet_df_temp", budget_sheet)

        con.execute("""
        CREATE OR REPLACE TABLE fact_team_config AS
        SELECT *
        FROM team_sheet_df_temp
        """)


def team_config_controller():
   sheet = load_team_config_sheet()
   build_team_config_table(budget_sheet = sheet)
