import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_driver_residuals.parquet")


def build_rpt_driver_residuals():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                SELECT
                    p.prediction_run_id,
                    p.year,
                    p.race_id,
                    r.race_num,
                    r.race_name,
                    r.country_name,
                    r.circuit_short_name,
                    r.is_sprint_weekend,

                    p.driver_id,
                    d.driver_name,
                    d.name_acronym as driver_acronym,
                    p.constructor_id,
                    c.constructor_name,

                    p.predicted_points,
                    a.fantasy_points AS actual_points,
                    a.fantasy_points - p.predicted_points AS residual,
                    ABS(a.fantasy_points - p.predicted_points) AS abs_residual,

                    CASE
                        WHEN p.predicted_points < 0 THEN '< 0'
                        WHEN p.predicted_points < 5 THEN '0-5'
                        WHEN p.predicted_points < 10 THEN '5-10'
                        WHEN p.predicted_points < 15 THEN '10-15'
                        WHEN p.predicted_points < 20 THEN '15-20'
                        ELSE '20+'
                    END AS prediction_bucket,

                    p.model_name,
                    p.model_version,
                    p.feature_set_version,
                    p.target_variable,
                    p.is_production_run,
                    p.prediction_timestamp

                FROM fact_driver_predictions p
                LEFT JOIN fact_driver_race a
                    ON p.race_id = a.race_id
                    AND p.driver_id = a.driver_id
                LEFT JOIN dim_driver d
                    ON p.driver_id = d.driver_id
                LEFT JOIN dim_constructor c
                    ON p.constructor_id = c.constructor_id
                LEFT JOIN dim_race r
                    ON p.race_id = r.race_id
                WHERE a.fantasy_points IS NOT NULL
                ORDER BY p.prediction_run_id, ABS(a.fantasy_points - p.predicted_points) DESC
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_driver_residuals()