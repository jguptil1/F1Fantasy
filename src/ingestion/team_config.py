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

    return cwd / "data" / "raw" / "newHistPointAndPrice.xlsx"


def load_budget_sheet():
  df = pd.read_excel(load_raw_file_path(), sheet_name="WEEKLY BUDGET")
  return df


def build_budget_table(budget_sheet):
        
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("budget_sheet_temp_df", budget_sheet)

        con.execute("""
        CREATE OR REPLACE TABLE fact_budget_table AS
        SELECT *
        FROM budget_sheet_temp_df
        """)


def budget_controller():
   sheet = load_budget_sheet()
   build_budget_table(budget_sheet = sheet)
