import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_constructor_predictions.parquet")


def build_rpt_constructor_predictions():
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

                    p.constructor_id,
                    c.constructor_name,

                    p.predicted_points,
                    p.model_name,
                    p.model_version,
                    p.feature_set_version,
                    p.target_variable,
                    p.is_production_run,
                    p.prediction_timestamp

                FROM fact_constructor_predictions p
                LEFT JOIN dim_constructor c
                    ON p.constructor_id = c.constructor_id
                LEFT JOIN dim_race r
                    ON p.race_id = r.race_id
                ORDER BY p.prediction_run_id, p.predicted_points DESC
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_constructor_predictions()