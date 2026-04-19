from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd


"""
This module solely deals with the ingestion, staging and warehouse of the data withing the newhistPointPrice excel file

the data can be easily updated in that weekly or on a race by race basis and can flow into the pipeline as needed
"""


###########################################Ingestion##################################

#helper
def load_working_directory():
    return Path.cwd()

#helper
def load_raw_file_path():

    cwd = load_working_directory()

    return cwd / "data" / "raw" / "rawHistPointAndPrice.xlsx"


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
            cleaned_cols.append(int(float(str(c).strip())))
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

    driver_price_long  = convert_to_long(driver_price_dfs,  var_name="race", value_name="price",  type = "driver")
    convert_to_long()




def raw_fantasy_table_controller():
    dfs, years, sheet_types, asset_types = load_sheets()





'''

sheet_names =["2023DriverPrice", "2023ConstructorPrice", "2023DriverPoints","2023ConstructorPoints","2023DriverRoster", 
              "2024DriverPrice", "2024ConstructorPrice", "2024DriverPoints", "2024ConstructorPoints", "2024DriverRoster",
              "2025DriverPrice", "2025ConstructorPrice","2025DriverPoints", "2025ConstructorPoints",  "2025DriverRoster",
               "2026DriverRoster", "2026DriverPrice", "2026DriverPoints", "2026ConstructorPrice", "2026ConstructorPoints"]


dfs = {sheet: pd.read_excel(file_path, sheet_name=sheet) for sheet in sheet_names}


# access one
print(dfs["2023DriverPoints"].head())


'''









def main():

    dfs = load_sheets()
    print(dfs)


if __name__ == "__main__":
    main()

