import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")

PROFILE_OUTPUT_PATH = Path("data/reporting/rpt_simulation_profile_results.parquet")
DRIVER_OUTPUT_PATH = Path("data/reporting/rpt_simulation_driver_summary.parquet")


def build_rpt_simulation_profile_results():
    PROFILE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    sr.simulation_run_id,
                    sr.created_at AS simulation_created_at,

                    sr.race_id,
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

                    spr.profile_name,
                    spr.profile_source,
                    spr.profile_strategy,
                    spr.optimizer_run_id,

                    spr.mean_lineup_points,
                    spr.std_lineup_points,
                    spr.p05,
                    spr.p10,
                    spr.p25,
                    spr.median,
                    spr.p75,
                    spr.p90,
                    spr.p95,

                    spr.p90 - spr.p10 AS lineup_risk_range,
                    spr.mean_lineup_points - spr.p10 AS lineup_downside_gap

                FROM simulation_profile_result spr
                LEFT JOIN simulation_run sr
                    ON spr.simulation_run_id = sr.simulation_run_id
                LEFT JOIN dim_race r
                    ON sr.race_id = r.race_id

                ORDER BY
                    sr.simulation_run_id DESC,
                    spr.mean_lineup_points DESC
            )
            TO '{PROFILE_OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {PROFILE_OUTPUT_PATH}")


def build_rpt_simulation_driver_summary():
    DRIVER_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    sr.simulation_run_id,
                    sr.created_at AS simulation_created_at,

                    sds.race_id,
                    r.race_num,
                    r.race_name,
                    r.country_name,
                    r.circuit_short_name,
                    r.is_sprint_weekend,

                    sr.driver_prediction_run_id,
                    sr.constructor_prediction_run_id,
                    sr.n_sims,
                    sr.random_seed,
                    sr.residual_bucket_strategy,

                    sds.driver_id,
                    d.driver_name,
                    sds.constructor_id,
                    c.constructor_name,

                    sds.price,
                    sds.predicted_points,
                    sds.prediction_bucket,

                    sds.mean_sim_points,
                    sds.std_sim_points,
                    sds.p05,
                    sds.p10,
                    sds.p25,
                    sds.median,
                    sds.p75,
                    sds.p90,
                    sds.p95,

                    sds.mean_per_price,
                    sds.p90_per_price,
                    sds.risk_range,
                    sds.downside_gap

                FROM simulation_driver_summary sds
                LEFT JOIN simulation_run sr
                    ON sds.simulation_run_id = sr.simulation_run_id
                LEFT JOIN dim_driver d
                    ON sds.driver_id = d.driver_id
                LEFT JOIN dim_constructor c
                    ON sds.constructor_id = c.constructor_id
                LEFT JOIN dim_race r
                    ON sds.race_id = r.race_id

                ORDER BY
                    sr.simulation_run_id DESC,
                    sds.mean_sim_points DESC
            )
            TO '{DRIVER_OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {DRIVER_OUTPUT_PATH}")


def build_rpt_simulation_results():
    build_rpt_simulation_profile_results()
    build_rpt_simulation_driver_summary()


if __name__ == "__main__":
    build_rpt_simulation_results()