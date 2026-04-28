from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


"""
This module solely deals with the ingestion, staging and warehouse of the data withing the newhistPointPrice excel file

the data can be easily updated in that week or on a race by race basis and can flow into the rest of the pipeline as needed

unlike the other pipeline modules these functions deal with mutliple tables due to the ingestion, not just a single one

"""


###########################################Ingestion##################################

#helper
def load_working_directory():
    return Path.cwd()

#helper
def load_raw_file_path():

    cwd = load_working_directory()

    return cwd / "data" / "raw" / "newHistPointAndPrice.xlsx"


#helper (pulled from old histDataClean.ipynb)
def standardize_headers(df: pd.DataFrame, first_col_name: str) -> pd.DataFrame:
    df = df.copy()

    # Dropping unnamed cols
    unnamed_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    for c in unnamed_cols:
        if df[c].isna().all():
            df = df.drop(columns=c)

    # renaming first col to first_col_name
    df = df.rename(columns={df.columns[0]: first_col_name})

    # Clean race headers
    cleaned_cols = [first_col_name]
    for c in df.columns[1:]:
        try:
            cleaned_cols.append(int(float(str(c).strip()))) # type: ignore
        except ValueError:
            cleaned_cols.append(str(c).strip())

    df.columns = cleaned_cols
    return df

#helper (pulled from old histDataClean.ipynb)
def convert_to_long(sheets: dict, var_name: str, value_name: str, type: str):
    longs = []

    for sheet_name, df in sheets.items():
        df_clean = standardize_headers(df, first_col_name=type)

        temp = (
            df_clean
            .melt(id_vars=type, var_name=var_name, value_name=value_name)
            .assign(source_sheet=sheet_name)
        )
        longs.append(temp)

    return pd.concat(longs, ignore_index=True)


def load_sheets(years = [2023, 2024, 2025, 2026], sheet_types ={"Price", "Points"}, asset_types=["Driver", "Constructor"]):

    #creating string value that will be used to load in the correct df
    sheets = []
    for year in years:
        for sheet_type in sheet_types:
            for asset_type in asset_types:
                string_val = f'{year}{asset_type}{sheet_type}'
                sheets.append(string_val)

    dfs = {sheet: pd.read_excel(load_raw_file_path(), sheet_name=sheet) for sheet in sheets}

    return dfs, years, sheet_types, asset_types


def clean_and_transform_raw_dfs(dfs:dict):

    driver_price_sheets = ["2023DriverPrice", "2024DriverPrice", "2025DriverPrice", "2026DriverPrice"]
    driver_points_sheets = ["2023DriverPoints", "2024DriverPoints", "2025DriverPoints", "2026DriverPoints"]

    con_price_sheets = ["2023ConstructorPrice", "2024ConstructorPrice", "2025ConstructorPrice", "2026ConstructorPrice"]
    con_points_sheets = ["2023ConstructorPoints", "2024ConstructorPoints", "2025ConstructorPoints", "2026ConstructorPoints"]


    driver_price_dfs  = {k: dfs[k] for k in driver_price_sheets}
    driver_points_dfs = {k: dfs[k] for k in driver_points_sheets}

    con_price_dfs = {k: dfs[k] for k in con_price_sheets}
    con_points_dfs = {k: dfs[k] for k in con_points_sheets}


    driver_price_long  = convert_to_long(driver_price_dfs,  var_name="race", value_name="price",  type = "driver")
    driver_price_long["driver"] = driver_price_long['driver'].str.lower()
    driver_points_long  = convert_to_long(driver_points_dfs,  var_name="race", value_name="points",  type = "driver")
    driver_points_long["driver"] = driver_price_long['driver'].str.lower()
    
    con_price_long = convert_to_long(con_price_dfs, var_name="race", value_name="price", type= "constructor")
    con_price_long["constructor"] = con_price_long['constructor'].str.lower()
    con_points_long = convert_to_long(con_points_dfs, var_name="race", value_name="points", type= "constructor")
    con_points_long["constructor"] = con_points_long['constructor'].str.lower()

    
    return driver_price_long, driver_points_long, con_price_long, con_points_long


def build_raw_fantasy_table(driver_price, driver_points, constructor_price, contructor_points):

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        con.register("driver_price_df_temp", driver_price)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_driver_price_table AS
        SELECT *
        FROM driver_price_df_temp
        """)

        con.register("driver_points_df_temp", driver_points)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_driver_points_table AS
        SELECT *
        FROM driver_points_df_temp
        """)

        con.register("constructor_price_df_temp", constructor_price)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_constructor_price_table AS
        SELECT *
        FROM constructor_price_df_temp
        """)

        con.register("constructor_points_df_temp", contructor_points)

        result = con.execute("""
        CREATE OR REPLACE TABLE raw_constructor_points_table AS
        SELECT *
        FROM constructor_points_df_temp
        """)


def raw_fantasy_tables_controller():
    dfs, years, sheet_types, asset_types = load_sheets()
    driver_price, driver_points, constructor_price, constructor_points = clean_and_transform_raw_dfs(dfs)
    build_raw_fantasy_table(driver_price, driver_points, constructor_price, constructor_points)



def build_stage_fantasy_tables():

    raw_tables = [
        "raw_constructor_price_table",
        "raw_constructor_points_table",
        "raw_driver_price_table",
        "raw_driver_points_table",
    ]

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        for table_name in raw_tables:

            result = con.execute(f"""
                SELECT *
                FROM {table_name}
            """).df()

            result = result.dropna()

            result["year"] = result["source_sheet"].str[:4].astype(int)
            result = result.drop(columns=["source_sheet"])

            stage_table_name = "stage" + table_name[3:]

            con.register("built_df", result)

            con.execute(f"""
                CREATE OR REPLACE TABLE {stage_table_name} AS
                SELECT *
                FROM built_df
            """)


    #clean the raw table to include no rows where driver, race, points/price, source sheet is not na
        #need to pull the year and have as a seperate column

    #push the raw tables to the stage



#########################Fantasy Tables Pipeline##############################

def fantasy_tables_pipeline():
    
    raw_fantasy_tables_controller()
    build_stage_fantasy_tables()