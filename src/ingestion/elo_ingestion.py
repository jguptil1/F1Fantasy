from urllib.request import urlopen
from pathlib import Path
import duckdb
import requests
import time
import pandas as pd
import matplotlib.pyplot as plt
import os

import elo


"""

elo module requires a placement table and an overrides table for post race disqualifications due to api errors

"""


##############################ingestion############################

#brining in the 
def read_placement_table():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
        SELECT *
        FROM stage_driver_placement
                    """).df()
    return result


def create_overrides_table():

    overrides_df = pd.DataFrame({
        "year": [2023, 2023, 2026],
        "race_id": [19, 19, 1],
        "driver": ["HAM", "LEC", "STR"],
        "dsq_override": [True, True, None],
        "position_override": [None, None, None],
        "dns_override": [None, None, None],
        "dnf_override": [None, None, None],
        "nc_override": [None, None, True],
    })
        
    return overrides_df

def run_elo(placement_table, overrides_df):
    elo_table = elo.run_driver_elo_pipeline(
        placement_df=placement_table,
        overrides_df=overrides_df,
        year_col="year",
        race_col="race_id",
        driver_col="driver",
        position_col="finish_position",
        dns_col="dns",
        dnf_col="dnf",
        dsq_col="dsq",
        nc_col="nc",
        init_elo=1500,
        k_factor=8,
        season_shrink=0.75,
        inactivity_shrink=0.75,
        return_matchups=False
    )
    return elo_table

def print_graphic(elo_table):
    print("Building ELO plot...")

    required_cols = {"year", "race_id", "driver", "elo_before"}
    missing_cols = required_cols - set(elo_table.columns)

    if missing_cols:
        raise ValueError(f"Missing columns in elo_table: {missing_cols}")

    elo_plot = elo_table.copy()

    elo_plot = elo_plot.dropna(subset=["year", "race_id", "driver", "elo_before"])

    if elo_plot.empty:
        raise ValueError("elo_table has no rows after dropping missing values.")

    elo_plot["year"] = elo_plot["year"].astype(int)
    elo_plot["race_id"] = elo_plot["race_id"].astype(int)
    elo_plot["driver"] = elo_plot["driver"].astype(str).str.upper().str.strip()
    elo_plot["elo_before"] = pd.to_numeric(elo_plot["elo_before"], errors="coerce")

    elo_plot = elo_plot.dropna(subset=["elo_before"])

    elo_plot = elo_plot.sort_values(["year", "race_id", "driver"]).copy()

    race_order = (
        elo_plot[["year", "race_id"]]
        .drop_duplicates()
        .sort_values(["year", "race_id"])
        .reset_index(drop=True)
    )

    race_order["race_index"] = range(1, len(race_order) + 1)

    elo_plot = elo_plot.merge(
        race_order,
        on=["year", "race_id"],
        how="left"
    )

    fig, ax = plt.subplots(figsize=(18, 9))

    for driver, sub in elo_plot.groupby("driver"):
        sub = sub.sort_values("race_index")

        if sub.empty:
            continue

        ax.plot(
            sub["race_index"],
            sub["elo_before"],
            linewidth=1.8,
            alpha=0.85
        )

        last_row = sub.iloc[-1]

        ax.text(
            last_row["race_index"] + 0.3,
            last_row["elo_before"],
            driver,
            fontsize=9,
            va="center"
        )

    season_starts = race_order.groupby("year", as_index=False)["race_index"].min()

    for _, row in season_starts.iterrows():
        ax.axvline(row["race_index"], linestyle="--", alpha=0.35)
        ax.text(
            row["race_index"],
            ax.get_ylim()[1],
            str(row["year"]),
            fontsize=10,
            va="top",
            ha="left"
        )

    ax.set_xlabel("Race Index")
    ax.set_ylabel("Pre-Race ELO")
    ax.set_title("Driver ELO Trends")
    ax.grid(True, alpha=0.3)

    ax.set_xlim(
        elo_plot["race_index"].min(),
        elo_plot["race_index"].max() + 4
    )

    output_path = Path(r"C:\Users\jackg\code\F1Fantasy\data\outputs\elo_trends.png")

    try:
        print("About to create output folder")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print("About to tight_layout")
        fig.tight_layout()

        print("About to save")
        fig.savefig(output_path, dpi=200, bbox_inches="tight")

        print("About to close")
        plt.close(fig)

        print(f"Saved plot to: {output_path}")
        print(f"Exists: {output_path.exists()}")

    except Exception as e:
        print("SAVE BLOCK FAILED:", repr(e))
        raise



def elo_pipeline():
    placement_table = read_placement_table()
    overrides_table = create_overrides_table()

    elo_table = run_elo(placement_table=placement_table, overrides_df=overrides_table)

    return elo_table



if __name__ == "__main__":
   elo_table = elo_pipeline()
   print(elo_table)
   print(os.getcwd())
   print_graphic(elo_table)










