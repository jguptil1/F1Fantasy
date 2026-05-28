import duckdb
import pandas as pd
import datetime


def build_optimizer_run():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS optimizer_run (
            optimizer_run_id BIGINT,
            created_at TIMESTAMP,

            year INTEGER,
            race_id BIGINT,
            fantasy_team_name VARCHAR,

            driver_prediction_run_id BIGINT,
            constructor_prediction_run_id BIGINT,

            budget DOUBLE,
            points_col VARCHAR,
                    
            profile_source VARCHAR, 
            profile_strategy VARCHAR,
            optimization_target VARCHAR,

            require_driver_from_each_constructor BOOLEAN,
            min_drivers_per_selected_constructor INTEGER,

            free_transfers_avail INTEGER,
            total_transfers INTEGER,
            paid_transfers INTEGER,
            transfer_penalty DOUBLE,

            use_drs BOOLEAN,
            drs_driver_id BIGINT,

            total_price DOUBLE,
            gross_points DOUBLE,
            net_points DOUBLE,

            solver_status INTEGER,
            solver_name VARCHAR,

            is_production_run BOOLEAN
            );
                        
        """)


def build_optimizer_selection():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""


            CREATE TABLE IF NOT EXISTS optimizer_selection (
            optimizer_run_id BIGINT,

            asset_type VARCHAR, -- 'driver' or 'constructor'

            driver_id BIGINT,
            constructor_id BIGINT,

            selected_asset_id BIGINT,
            selected_asset_name VARCHAR,

            price DOUBLE,
            predicted_points DOUBLE,

            is_drs BOOLEAN,
            is_transfer_in BOOLEAN,

            slot_num INTEGER
            );
                        
        """)


#helper
def get_max_optimization_run():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("""
            SELECT COALESCE(MAX(optimizer_run_id), 0)
            FROM optimizer_run
        """).fetchone()[0] # type: ignore

    return int(result)


def append_optimizer_run(
    drivers_selected,
    constructors_selected,
    summary,
    fantasy_team_name,
    production_run,

    profile_source,
    profile_strategy,
    optimization_target,

    require_driver_from_each_constructor,
    min_drivers_per_selected_constructor
):
    
    optimizer_run_id = get_max_optimization_run() + 1
    created_at = datetime.datetime.now()


    drs_driver_id = summary.get("drs_driver")

    if drs_driver_id is not None:
        drs_driver_id = int(drs_driver_id)

    run_row = pd.DataFrame([{
        "optimizer_run_id": optimizer_run_id,
        "created_at": created_at,

        "year": int(drivers_selected["year"].iloc[0]),
        "race_id": int(drivers_selected["race_id"].iloc[0]),
        "fantasy_team_name": fantasy_team_name,

        "driver_prediction_run_id": int(drivers_selected["prediction_run_id"].iloc[0]),
        "constructor_prediction_run_id": int(constructors_selected["prediction_run_id"].iloc[0]),

        "budget": float(summary["budget"]),
        "points_col": summary["points_column_used"],

        "profile_source": profile_source,
        "profile_strategy": profile_strategy,
        "optimization_target": optimization_target,

        "require_driver_from_each_constructor": 
            bool(require_driver_from_each_constructor),

        "min_drivers_per_selected_constructor":
            int(min_drivers_per_selected_constructor),

        "free_transfers_avail": int(summary.get("free_transfers_avail", 0)),
        "total_transfers": int(summary.get("total_transfers", 0)),
        "paid_transfers": int(summary.get("paid_transfers", 0)),
        "transfer_penalty": float(summary.get("transfer_penalty", 0)),

        "use_drs": bool(drs_driver_id is not None),
        "drs_driver_id": drs_driver_id,

        "total_price": float(summary["total_price"]),
        "gross_points": float(summary.get("gross_points", summary.get("total_points"))),
        "net_points": float(summary.get("net_points", summary.get("total_points"))),

        "solver_status": int(summary["status"]),
        "solver_name": "COIN_CMD",

        "is_production_run": bool(production_run),
    }])

    insert_cols = run_row.columns.tolist()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_optimizer_run", run_row)

        con.execute(f"""
            INSERT INTO optimizer_run ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_optimizer_run
        """)

    print(f"Appended {len(run_row)} row(s) to optimizer_run")

    return optimizer_run_id



def append_optimizer_selection(
    optimizer_run_id,
    drivers_selected,
    constructors_selected,
    summary
):
    selection_rows = []

    # DRS handling
    drs_driver_id = summary.get("drs_driver_id", None)

    # Driver selections
    for slot_num, (_, row) in enumerate(drivers_selected.reset_index(drop=True).iterrows(), start=1):
        driver_id = int(row["driver_id"])

        selection_rows.append({
            "optimizer_run_id": optimizer_run_id,

            "asset_type": "driver",

            "driver_id": driver_id,
            "constructor_id": int(row["constructor_id"]),

            "selected_asset_id": driver_id,
            "selected_asset_name": row.get("driver_name", None),

            "price": float(row["price"]),
            "predicted_points": float(row["predicted_points"]),

            "is_drs": bool(drs_driver_id == driver_id),
            "is_transfer_in": bool(row["is_transfer_in"]),

            "slot_num": slot_num,
        })

    # Constructor selections
    for slot_num, (_, row) in enumerate(constructors_selected.reset_index(drop=True).iterrows(), start=1):
        constructor_id = int(row["constructor_id"])

        selection_rows.append({
            "optimizer_run_id": optimizer_run_id,

            "asset_type": "constructor",

            "driver_id": None,
            "constructor_id": constructor_id,

            "selected_asset_id": constructor_id,
            "selected_asset_name": row.get("constructor_name", None),

            "price": float(row["price"]),
            "predicted_points": float(row["predicted_points"]),

            "is_drs": False,
            "is_transfer_in": bool(row["is_transfer_in"]),

            "slot_num": slot_num,
        })

    selection_df = pd.DataFrame(selection_rows)

    insert_cols = [
        "optimizer_run_id",
        "asset_type",
        "driver_id",
        "constructor_id",
        "selected_asset_id",
        "selected_asset_name",
        "price",
        "predicted_points",
        "is_drs",
        "is_transfer_in",
        "slot_num",
    ]

    selection_df = selection_df[insert_cols].copy()

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.register("temp_optimizer_selection", selection_df)

        con.execute(f"""
            INSERT INTO optimizer_selection ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_optimizer_selection
        """)

    print(f"Appended {len(selection_df)} row(s) to optimizer_selection")

    


def optimizer_tables_controller(
    drivers_selected_df,
    constructors_selected_df,
    summary_dict,
    fantasy_team_name,
    is_production_run,

    profile_source,
    profile_strategy,
    optimization_target, 

    require_drivers_from_each_constructor,
    min_drivers_per_selected_constructor
): 
    
    #init build
    build_optimizer_run()
    build_optimizer_selection()


    #append operations
    optimizer_run_id = append_optimizer_run(
        drivers_selected_df,
        constructors_selected_df,
        summary_dict,
        fantasy_team_name,
        is_production_run,
        profile_source,
        profile_strategy,
        optimization_target,
        require_drivers_from_each_constructor,
        min_drivers_per_selected_constructor
    )

    append_optimizer_selection(
        optimizer_run_id,
        drivers_selected_df,
        constructors_selected_df,
        summary_dict
    )
