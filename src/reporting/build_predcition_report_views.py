from pathlib import Path
import duckdb


DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")


def build_driver_prediction_results_view(con):
    con.execute("""
        CREATE OR REPLACE VIEW report_driver_prediction_results AS

        SELECT
            fdp.prediction_run_id,
            fdp.model_name,
            fdp.model_version,
            fdp.feature_set_version,

            fdp.year,
            fdp.race_id,

            dd.driver_name AS driver,
            dc.constructor_name AS constructor,

            fdp.predicted_points,
            fdr.fantasy_points AS actual_points,

            fdr.fantasy_points - fdp.predicted_points AS residual,
            ABS(fdr.fantasy_points - fdp.predicted_points) AS abs_error

        FROM fact_driver_predictions AS fdp

        LEFT JOIN fact_driver_race AS fdr
            ON fdp.year = fdr.year
           AND fdp.race_id = fdr.race_id
           AND fdp.driver_id = fdr.driver_id

        LEFT JOIN dim_driver AS dd
            ON fdp.driver_id = dd.driver_id

        LEFT JOIN dim_constructor AS dc
            ON fdp.constructor_id = dc.constructor_id
    """)


def build_constructor_prediction_results_view(con):
    con.execute("""
        CREATE OR REPLACE VIEW report_constructor_prediction_results AS

        SELECT
            fcp.prediction_run_id,
            fcp.model_name,
            fcp.model_version,
            fcp.feature_set_version,

            fcp.year,
            fcp.race_id,

            dc.constructor_name AS constructor,

            fcp.predicted_points,
            fcr.fantasy_points AS actual_points,

            fcr.fantasy_points - fcp.predicted_points AS residual,
            ABS(fcr.fantasy_points - fcp.predicted_points) AS abs_error

        FROM fact_constructor_predictions AS fcp

        LEFT JOIN fact_constructor_race AS fcr
            ON fcp.year = fcr.year
           AND fcp.race_id = fcr.race_id
           AND fcp.constructor_id = fcr.constructor_id

        LEFT JOIN dim_constructor AS dc
            ON fcp.constructor_id = dc.constructor_id
    """)


def validate_view(con, view_name):
    df = con.execute(f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(*) FILTER (WHERE predicted_points IS NULL) AS null_predictions,
            COUNT(*) FILTER (WHERE actual_points IS NULL) AS null_actuals,
            AVG(abs_error) AS avg_abs_error
        FROM {view_name}
    """).df()

    print(f"\n{view_name}")
    print(df)


def main():
    with duckdb.connect(str(DATABASE_PATH)) as con:
        build_driver_prediction_results_view(con)
        build_constructor_prediction_results_view(con)

        print("Prediction report views created successfully.")

        validate_view(con, "report_driver_prediction_results")
        validate_view(con, "report_constructor_prediction_results")


if __name__ == "__main__":
    main()