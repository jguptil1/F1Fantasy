import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_simulation_profile_lineup.parquet")


def build_rpt_simulation_profile_lineup():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    spr.simulation_run_id,
                    sr.created_at AS simulation_created_at,

                    sr.race_id,
                    r.race_num,
                    r.race_name,
                    r.country_name,
                    r.circuit_short_name,
                    r.is_sprint_weekend,

                    spr.profile_name,
                    spr.profile_source,
                    spr.profile_strategy,
                    spr.optimizer_run_id,

                    os.asset_type,
                    os.slot_num,

                    os.driver_id,
                    d.driver_name,

                    os.constructor_id,
                    c.constructor_name,

                    os.selected_asset_id,
                    os.selected_asset_name,

                    os.price,
                    os.predicted_points,
                    os.is_drs,
                    os.is_transfer_in

                FROM simulation_profile_result spr
                LEFT JOIN simulation_run sr
                    ON spr.simulation_run_id = sr.simulation_run_id
                LEFT JOIN dim_race r
                    ON sr.race_id = r.race_id
                LEFT JOIN optimizer_selection os
                    ON spr.optimizer_run_id = os.optimizer_run_id
                LEFT JOIN dim_driver d
                    ON os.driver_id = d.driver_id
                LEFT JOIN dim_constructor c
                    ON os.constructor_id = c.constructor_id

                WHERE spr.optimizer_run_id IS NOT NULL

                ORDER BY
                    spr.simulation_run_id DESC,
                    spr.profile_name,
                    os.asset_type,
                    os.slot_num
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_simulation_profile_lineup()