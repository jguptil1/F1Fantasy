import duckdb
from pathlib import Path

DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_PATH = Path("data/reporting/rpt_model_evaluation.parquet")


def build_rpt_model_evaluation():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        con.execute(f"""
            COPY (
                WITH production_flags AS (
                    SELECT
                        prediction_run_id,
                        MAX(CAST(is_production_run AS INTEGER))::BOOLEAN AS is_production_run
                    FROM fact_driver_predictions
                    GROUP BY prediction_run_id

                    UNION ALL

                    SELECT
                        prediction_run_id,
                        MAX(CAST(is_production_run AS INTEGER))::BOOLEAN AS is_production_run
                    FROM fact_constructor_predictions
                    GROUP BY prediction_run_id
                ),

                production_flags_deduped AS (
                    SELECT
                        prediction_run_id,
                        MAX(CAST(is_production_run AS INTEGER))::BOOLEAN AS is_production_run
                    FROM production_flags
                    GROUP BY prediction_run_id
                )

                SELECT
                    mr.prediction_run_id,

                    pr.created_at,
                    pr.asset_type,
                    pr.model_name,
                    pr.model_version,
                    pr.feature_set_version,
                    pr.target,
                    pr.train_cutoff_race_id,

                    pf.is_production_run,

                    CASE
                        WHEN mr.model_type IN ('Random Forest', 'RandomForest')
                            THEN 'RandomForest'
                        ELSE mr.model_type
                    END AS model_type,

                    mr.cv_mae,
                    mr.cv_mae_std,
                    mr.train_mae,
                    mr.train_rmse,
                    mr.test_mae,
                    mr.test_rmse,

                    nb.test_mae AS naive_test_mae,
                    nb.test_rmse AS naive_test_rmse,

                    mr.expected_improvement,
                    mr.realized_improvement,
                    mr.overfit_underfit,
                    mr.rmse_overfit_underfit_gap,
                    mr.generalization,

                    CASE
                        WHEN nb.test_mae IS NULL THEN NULL
                        ELSE nb.test_mae - mr.test_mae
                    END AS mae_vs_naive,

                    CASE
                        WHEN nb.test_rmse IS NULL THEN NULL
                        ELSE nb.test_rmse - mr.test_rmse
                    END AS rmse_vs_naive,

                    CASE
                        WHEN nb.test_mae IS NULL OR nb.test_mae = 0 THEN NULL
                        ELSE (nb.test_mae - mr.test_mae) / nb.test_mae
                    END AS mae_pct_improvement_vs_naive,

                    CASE
                        WHEN nb.test_rmse IS NULL OR nb.test_rmse = 0 THEN NULL
                        ELSE (nb.test_rmse - mr.test_rmse) / nb.test_rmse
                    END AS rmse_pct_improvement_vs_naive

                FROM fact_model_results mr

                LEFT JOIN prediction_run pr
                    ON mr.prediction_run_id = pr.prediction_run_id

                LEFT JOIN production_flags_deduped pf
                    ON mr.prediction_run_id = pf.prediction_run_id

                LEFT JOIN fact_niave_baselines nb
                    ON mr.prediction_run_id = nb.prediction_run_id

                ORDER BY
                    pr.created_at DESC,
                    pr.asset_type,
                    mr.test_mae ASC
            )
            TO '{OUTPUT_PATH.as_posix()}'
            (FORMAT PARQUET);
        """)

    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    build_rpt_model_evaluation()