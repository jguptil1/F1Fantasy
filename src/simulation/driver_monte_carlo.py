import duckdb
import pandas as pd
import numpy as np
DATABASE_PATH = "data/database/f1_fantasy.duckdb"



def load_current_driver_predictions(race_id_to_sim, prediction_run_id):

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        current_preds = con.execute(f"""
            SELECT
                dp.race_id,
                dp.driver_id,
                dp.constructor_id,
                dp.price,
                dp.predicted_points,
                CASE
                    WHEN dp.predicted_points < 20 THEN '00_20'
                    ELSE '20_plus'
                END AS prediction_bucket
            FROM fact_driver_predictions dp
            WHERE dp.race_id = ?
            AND dp.prediction_run_id = ?;
        """, [race_id_to_sim, prediction_run_id]).df()
        return current_preds

def load_driver_residual_samples():
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        residuals = con.execute("""
            SELECT
                prediction_bucket,
                residual
            FROM driver_prediction_residuals
            WHERE residual IS NOT NULL
        """).df()

    bucket_residuals = {
        bucket: group["residual"].to_numpy()
        for bucket, group in residuals.groupby("prediction_bucket")
    }

    return bucket_residuals

def simulate_driver_points(current_preds, bucket_residuals, n_sims=10000, random_seed=42):
    rng = np.random.default_rng(random_seed)

    sim_rows = []

    for _, row in current_preds.iterrows():
        bucket = row["prediction_bucket"]
        residual_pool = bucket_residuals[bucket]

        sampled_residuals = rng.choice(
            residual_pool,
            size=n_sims,
            replace=True
        )

        simulated_points = row["predicted_points"] + sampled_residuals

        driver_sim_df = pd.DataFrame({
            "simulation_id": np.arange(n_sims),
            "race_id": row["race_id"],
            "driver_id": row["driver_id"],
            "constructor_id": row["constructor_id"],
            "price": row["price"],
            "predicted_points": row["predicted_points"],
            "prediction_bucket": bucket,
            "sampled_residual": sampled_residuals,
            "simulated_points": simulated_points
        })

        sim_rows.append(driver_sim_df)

    return pd.concat(sim_rows, ignore_index=True)

def summarize_driver_simulations(driver_simulations):

    summary = (
        driver_simulations
        .groupby([
            "driver_id",
            "constructor_id",
            "price",
            "predicted_points",
            "prediction_bucket"
        ])
        .agg(
            mean_sim_points=("simulated_points", "mean"),
            std_sim_points=("simulated_points", "std"),

            p05=("simulated_points", lambda x: x.quantile(0.05)),
            p10=("simulated_points", lambda x: x.quantile(0.10)),
            p25=("simulated_points", lambda x: x.quantile(0.25)),
            median=("simulated_points", lambda x: x.quantile(0.50)),
            p75=("simulated_points", lambda x: x.quantile(0.75)),
            p90=("simulated_points", lambda x: x.quantile(0.90)),
            p95=("simulated_points", lambda x: x.quantile(0.95))
        )
        .reset_index()
    )

    return summary

def enrich_driver_sim_summary(driver_summary):

    with duckdb.connect(DATABASE_PATH, read_only=True) as con:

        driver_dim = con.execute("""
            SELECT
                driver_id,
                driver_name
            FROM dim_driver
        """).df()

        constructor_dim = con.execute("""
            SELECT
                constructor_id,
                constructor_name
            FROM dim_constructor
        """).df()

    enriched = (
        driver_summary
        .merge(driver_dim, on="driver_id", how="left")
        .merge(constructor_dim, on="constructor_id", how="left")
    )

    cols_order = [
        "driver_id",
        "driver_name",
        "constructor_id",
        "constructor_name",
        "price",
        "predicted_points",
        "mean_sim_points",
        "std_sim_points",
        "p05",
        "p10",
        "p25",
        "median",
        "p75",
        "p90",
        "p95",
        "prediction_bucket"
    ]

    enriched = enriched[cols_order]

    return enriched


def simulate_lineup(driver_simulations, selected_driver_ids):
    lineup_sim = (
        driver_simulations[
            driver_simulations["driver_id"].isin(selected_driver_ids)
        ]
        .groupby("simulation_id")
        .agg(
            lineup_points=("simulated_points", "sum")
        )
        .reset_index()
    )

    return lineup_sim


def summarize_lineup(lineup_sim):
    summary = {
        "mean_lineup_points": lineup_sim["lineup_points"].mean(),
        "std_lineup_points": lineup_sim["lineup_points"].std(),
        "p05": lineup_sim["lineup_points"].quantile(0.05),
        "p10": lineup_sim["lineup_points"].quantile(0.10),
        "p25": lineup_sim["lineup_points"].quantile(0.25),
        "median": lineup_sim["lineup_points"].quantile(0.50),
        "p75": lineup_sim["lineup_points"].quantile(0.75),
        "p90": lineup_sim["lineup_points"].quantile(0.90),
        "p95": lineup_sim["lineup_points"].quantile(0.95),
    }

    return summary


def main():
    current_preds = load_current_driver_predictions(
            race_id_to_sim=77,
            prediction_run_id=11
        )
    print(current_preds)


    bucket_residuals = load_driver_residual_samples()

    for bucket, residual_values in bucket_residuals.items():
        print(bucket, len(residual_values), residual_values[:5])


    driver_simulations = simulate_driver_points(
        current_preds=current_preds,
        bucket_residuals=bucket_residuals,
        n_sims=10000
    )

    print(driver_simulations.head())
    print(driver_simulations.shape)

    driver_summary = summarize_driver_simulations(driver_simulations)

    driver_summary = enrich_driver_sim_summary(driver_summary).sort_values(["predicted_points", 'prediction_bucket', "constructor_name"], ascending=[False, False, True])
    driver_summary["p90_per_price"] = driver_summary["p90"] / driver_summary["price"]
    driver_summary["mean_per_price"] = driver_summary["mean_sim_points"] / driver_summary["price"]
    driver_summary["risk_range"] = driver_summary["p90"] - driver_summary["p10"]
    driver_summary["downside_gap"] = driver_summary["mean_sim_points"] - driver_summary["p10"]

    driver_summary.reset_index(drop=True)
    driver_summary.to_csv("driver_risk_summary_5_15.csv")


    selected_driver_ids = [22, 20, 35, 44, 65]

    lineup_sim = simulate_lineup(
        driver_simulations=driver_simulations,
        selected_driver_ids=selected_driver_ids
    )

    lineup_summary = summarize_lineup(lineup_sim)
    print(lineup_summary)   


if __name__ == "__main__":
    main()