import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_simulation_run.parquet")


def build_rpt_simulation_run():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    sr.simulation_run_id,
                    sr.created_at AS simulation_created_at,

                    sr.race_id,
                    r.year,
                    r.race_num,
                    r.race_name,
                    r.country_name,
                    r.circuit_short_name,
                    r.is_sprint_weekend,

                    sr.driver_prediction_run_id,
                    sr.constructor_prediction_run_id,

                    sr.n_sims,
                    sr.random_seed,
                    sr.residual_source_table,
                    sr.residual_bucket_strategy,
                    sr.notes

                FROM simulation_run sr
                LEFT JOIN dim_race r
                    ON sr.race_id = r.race_id

                ORDER BY
                    sr.simulation_run_id DESC
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_simulation_run()