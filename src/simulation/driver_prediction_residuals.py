import duckdb

def build_driver_prediction_residuals():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        con.execute("""
            CREATE OR REPLACE TABLE driver_prediction_residuals AS
            WITH base AS (
                SELECT
                    dp.prediction_run_id,
                    pr.model_name,
                    pr.model_version,
                    pr.feature_set_version,
                    pr.target,

                    dp.year,
                    dp.race_id,
                    dp.driver_id,

                    fdr.constructor_id,
                    fdr.price,
                    fdr.is_sprint_weekend,
                    fdr.fantasy_points AS actual_points,
                    dp.predicted_points,

                    fdr.fantasy_points - dp.predicted_points AS residual,
                    ABS(fdr.fantasy_points - dp.predicted_points) AS abs_residual,

                    CASE
                        WHEN dp.predicted_points < 20 THEN '00_20'
                        ELSE '20_plus'
                    END AS prediction_bucket

                FROM fact_driver_predictions dp

                LEFT JOIN prediction_run pr
                    ON dp.prediction_run_id = pr.prediction_run_id

                LEFT JOIN fact_driver_race fdr
                    ON dp.race_id = fdr.race_id
                    AND dp.driver_id = fdr.driver_id

                WHERE fdr.fantasy_points IS NOT NULL
                AND dp.predicted_points IS NOT NULL
            )

            SELECT
                *
            FROM base;            
                             
                             
            """).df()
        

def main():
    build_driver_prediction_residuals()


if __name__ == "__main__":
    main()