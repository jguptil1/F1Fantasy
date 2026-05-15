#imports
import pandas as pd
import numpy as np

from pathlib import Path
import pulp
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpBinary, GLPK_CMD, value

# pulp: underlying optimization engine
# LpProblem: optimzation problem object
# LpMaximize: we are wanting to maximize projected points, will use this in the LpProblem object
# LpVariable: creates decision variables like picking a driver
# lpSum: builds linear sums for objectives and constraints
# lpBinary: variables can be 0 or 1
# PULP_CBC_CMD: solves the model and reads solution variables


def optimize_team(
    budget: float,
    drivers,
    cons,
    last_week_lineup: dict | None = None, 
    free_transfers_avail: int = 2,
    points_col: str = "predicted_points",
    n_drivers: int = 5,
    n_constructors: int = 2,
    max_drivers_per_team: int | None = None,
    use_drs: bool = False,
    drs_multiplier: float = 2.0,
    solver_msg: bool = False,
    require_driver_from_each_constructor: bool = False,
    min_drivers_per_selected_constructor: int = 1,
):
    """
    Optimize an F1 Fantasy lineup using a specified points column and prices.

    Parameters
    ----------
    budget : float
        Max total budget allowed.
    drivers : pd.DataFrame
        Must include: driver, constructor, price, <points_col>
    cons : pd.DataFrame
        Must include: constructor, price, <points_col>
    transfer_aware : bool
        If the engine will take into account transfers and transfer penelties
    last_week_lineup: dict
        this stores the drivers and constructors used in the prior week
        - (EXAMPLE) last_week_roster = {
            "drivers": {"VER", "LEC", "HUL", "COL", "LAW"},
            "constructors": {"FER", "RB"}
            }
    free_transfers_avail: int
        how many transfers are free before the penalty is incurred
}
    points_col : str, default "predicted_points"
        Column to optimize on. Examples:
        - "predicted_points" for pre-race optimization
        - "points" for post-race optimal lineup analysis
    

    Returns
    -------
    (drivers_selected_df, constructors_selected_df, summary_dict)
    """

    # making a copy so that the originals are unaffected by this function
    drivers = drivers.copy()
    cons = cons.copy()

    # Basic validation for debugging
    needed_driver_cols = {"driver_id", "constructor_id", "price", points_col}
    needed_cons_cols = {"constructor_id", "price", points_col}

    if not needed_driver_cols.issubset(drivers.columns):
        raise ValueError(
            f"drivers missing columns: {needed_driver_cols - set(drivers.columns)}"
        )
    if not needed_cons_cols.issubset(cons.columns):
        raise ValueError(
            f"constructors missing columns: {needed_cons_cols - set(cons.columns)}"
        )

    # Normalize team keys
    drivers["team_key"] = drivers["constructor_id"].astype(str).str.strip().str.upper()
    cons["team_key"] = cons["constructor_id"].astype(str).str.strip().str.upper()

    # Coerce to numeric types where needed
    drivers["price"] = pd.to_numeric(drivers["price"], errors="coerce")
    drivers[points_col] = pd.to_numeric(drivers[points_col], errors="coerce")
    cons["price"] = pd.to_numeric(cons["price"], errors="coerce")
    cons[points_col] = pd.to_numeric(cons[points_col], errors="coerce")

    # Drop rows with missing essentials
    drivers = drivers.dropna(subset=["driver_id", "constructor_id", "price", points_col]).reset_index(drop=True)
    cons = cons.dropna(subset=["constructor_id", "price", points_col]).reset_index(drop=True)

    # Indices
    d_idx = drivers.index.tolist()
    c_idx = cons.index.tolist()

    # Problem
    prob = LpProblem("F1FantasyOptimizer", LpMaximize) #instantiating the object with a name and type

    #########DECISION VARS###########

    # Mandatory Decision vars
    x_d = LpVariable.dicts("pick_driver", d_idx, cat=LpBinary) #creates a binary variable for each driver row index
    x_c = LpVariable.dicts("pick_constructor", c_idx, cat=LpBinary) #creates a binary variable for each con row index

    # Optional DRS vars (if param is true)
    if use_drs:
        z_drs = LpVariable.dicts("drs_driver", d_idx, cat=LpBinary) #creates a binary variable for each driver row index

        for i in d_idx:
            prob += z_drs[i] <= x_d[i]

        prob += lpSum(z_drs[i] for i in d_idx) == 1
    else:
        z_drs = None


    #Optional Transfer Decision vars
    if last_week_lineup is not None:
        t_d = LpVariable.dicts("trans_driver", d_idx, cat=LpBinary)
        t_c = LpVariable.dicts("trans_constr", c_idx, cat=LpBinary)
    else: 
        t_d = None
        t_c = None

    # Objective
    obj = (
        #sum of mutiplying each driver's points by the switch
        lpSum(drivers.loc[i, points_col] * x_d[i] for i in d_idx)
        #sum of mutiplying each constructor's points by the switch
        + lpSum(cons.loc[j, points_col] * x_c[j] for j in c_idx)
    )

    if use_drs:
        obj += (drs_multiplier - 1.0) * lpSum(drivers.loc[i, points_col] * z_drs[i] for i in d_idx) # type: ignore

    

    ###########Constraints#############
    prob += lpSum(x_d[i] for i in d_idx) == n_drivers #the amount of drivers turned on needs to equal to n_drivers (5)
    prob += lpSum(x_c[j] for j in c_idx) == n_constructors #the amount of constructors turned on needs to equal to n_constructors (2)


    #the sum of the drivers' and constructors' costs that are picked needs to be less than budget
    prob += (
        lpSum(drivers.loc[i, "price"] * x_d[i] for i in d_idx)
        + lpSum(cons.loc[j, "price"] * x_c[j] for j in c_idx)
        <= budget
    )

    # Optional: max drivers per team
    if max_drivers_per_team is not None:
        for team in drivers["team_key"].unique():
            team_driver_indices = drivers.index[drivers["team_key"] == team].tolist()
            prob += lpSum(x_d[i] for i in team_driver_indices) <= max_drivers_per_team

    # Optional: require at least N drivers from each selected constructor
    if require_driver_from_each_constructor:
        for j in c_idx:
            team = cons.loc[j, "team_key"]
            team_driver_indices = drivers.index[drivers["team_key"] == team].tolist()

            if not team_driver_indices:
                raise ValueError(f"No drivers found for constructor/team '{team}' in drivers df.")

            prob += (
                lpSum(x_d[i] for i in team_driver_indices)
                >= min_drivers_per_selected_constructor * x_c[j]
            )

    #Optional: Transfer aware constraints
    # Optional: Transfer aware constraints
    if last_week_lineup is not None:
        # Prior lineup should now use database IDs, not names/acronyms
        prior_driver_ids = {
            int(driver_id)
            for driver_id in last_week_lineup["drivers"]
        }

        prior_constructor_ids = {
            int(constructor_id)
            for constructor_id in last_week_lineup["constructors"]
        }

        for i in d_idx:
            driver_id = int(drivers.loc[i, "driver_id"])

            if driver_id in prior_driver_ids:
                prob += t_d[i] == 0  # same driver, no transfer # type: ignore
            else:
                prob += t_d[i] == x_d[i]  # selected new driver counts as transfer # type: ignore

        for j in c_idx:
            constructor_id = int(cons.loc[j, "constructor_id"])

            if constructor_id in prior_constructor_ids:
                prob += t_c[j] == 0  # same constructor, no transfer # type: ignore
            else:
                prob += t_c[j] == x_c[j]  # selected new constructor counts as transfer # type: ignore

        total_transfers = (
            lpSum(t_d[i] for i in d_idx) + # type: ignore
            lpSum(t_c[j] for j in c_idx) # type: ignore
        )

        paid_transfers = LpVariable("paid_transfers", lowBound=0, cat="Integer")
        prob += paid_transfers >= total_transfers - free_transfers_avail

        obj -= 10 * paid_transfers


    prob += obj #prob is just the optimization container

    ########SOLVE############
    cbc_path = Path(r"C:\Users\jackg\miniconda3\envs\f1_dev\Library\bin\cbc.exe")

    solver = pulp.COIN_CMD(
        path=str(cbc_path),
        msg=solver_msg
    )

    prob.solve(solver)

    # Extract results
    picked_driver_rows = [i for i in d_idx if value(x_d[i]) == 1]
    picked_cons_rows = [j for j in c_idx if value(x_c[j]) == 1]

    drivers_sel = (
        drivers.loc[picked_driver_rows]
        .copy()
        .sort_values(points_col, ascending=False)
        .reset_index(drop=True)
    )
    cons_sel = (
        cons.loc[picked_cons_rows]
        .copy()
        .sort_values(points_col, ascending=False)
        .reset_index(drop=True)
    )

    #DRIVER TRANSFER IN FLAG
    if last_week_lineup is not None:

        prior_driver_ids = {
            int(driver_id)
            for driver_id in last_week_lineup["drivers"]
        }

        drivers_sel["is_transfer_in"] = (
            ~drivers_sel["driver_id"].isin(prior_driver_ids)
        )

    else:
        drivers_sel["is_transfer_in"] = False


    #CONSTRUCTOR TRANSFER IN FLAG
    if last_week_lineup is not None:

        prior_constructor_ids = {
            int(constructor_id)
            for constructor_id in last_week_lineup["constructors"]
        }

        cons_sel["is_transfer_in"] = (
            ~cons_sel["constructor_id"].isin(prior_constructor_ids)
        )

    else:
        cons_sel["is_transfer_in"] = False



    # DRS driver
    drs_driver = None
    if use_drs:
        drs_picks = [i for i in d_idx if value(z_drs[i]) == 1] # type: ignore
        if drs_picks:
            drs_driver = drivers.loc[drs_picks[0], "driver_id"]

    total_price = float(drivers_sel["price"].sum() + cons_sel["price"].sum())
    gross_points = float(drivers_sel[points_col].sum() + cons_sel[points_col].sum())

    if use_drs and drs_driver is not None:
        drs_points = float(
            drivers_sel.loc[drivers_sel["driver_id"] == drs_driver, points_col].iloc[0]
        )
        gross_points += (drs_multiplier - 1.0) * drs_points
    
    if last_week_lineup is not None:
        total_transfers_val = int(round(value(total_transfers))) # type: ignore
        paid_transfers_val = int(round(value(paid_transfers))) # type: ignore
        transfer_penalty = paid_transfers_val * 10
        net_points = gross_points - transfer_penalty

    if last_week_lineup is not None:
        summary = {
            "status": prob.status,
            "budget": budget,
            "points_column_used": points_col,
            "total_price": round(total_price, 2),
            "gross_points": round(gross_points, 2),
            "total_transfers": total_transfers_val, # type: ignore
            "free_transfers_avail": free_transfers_avail,
            "paid_transfers": paid_transfers_val, # type: ignore
            "transfer_penalty": transfer_penalty, # type: ignore
            "net_points": round(net_points, 2), # type: ignore
            "drs_driver": drs_driver,
        }

    else:
        summary = {
            "status": prob.status,
            "budget": budget,
            "points_column_used": points_col,
            "total_price": round(total_price, 2),
            "total_points": round(gross_points, 2),
            "drs_driver": drs_driver,
        }

    return drivers_sel, cons_sel, summary
