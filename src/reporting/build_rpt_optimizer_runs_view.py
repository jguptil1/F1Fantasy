import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_optimizer_runs.parquet")


def build_rpt_optimizer_runs():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    r.optimizer_run_id,
                    r.created_at,

                    r.year,
                    r.race_id,
                    dr.race_num,
                    dr.race_name,
                    dr.country_name,
                    dr.circuit_short_name,
                    dr.date_start,
                    dr.date_end,
                    dr.is_sprint_weekend,

                    r.fantasy_team_name,

                    r.driver_prediction_run_id,
                    r.constructor_prediction_run_id,

                    r.budget,
                    r.points_col,
                    r.free_transfers_avail,
                    r.total_transfers,
                    r.paid_transfers,
                    r.transfer_penalty,

                    r.use_drs,
                    r.drs_driver_id,
                    d.driver_name AS drs_driver_name,

                    r.total_price,
                    r.gross_points,
                    r.net_points,

                    r.solver_status,
                    r.solver_name,
                    r.is_production_run

                FROM optimizer_run r

                LEFT JOIN dim_race dr
                    ON r.race_id = dr.race_id

                LEFT JOIN dim_driver d
                    ON r.drs_driver_id = d.driver_id

                ORDER BY r.created_at DESC
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_optimizer_runs()