from pathlib import Path
import duckdb
import matplotlib.pyplot as plt


DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
OUTPUT_DIR = Path("reports/linkedin_assets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


PREDICTION_TABLE = "fact_driver_predicted"
# Expected columns:
# year, race_id or race_num, driver/driver_name/driver_id,
# predicted_points, actual_points


def save_fig(filename):
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=200, bbox_inches="tight")
    plt.close()


def connect_db():
    return duckdb.connect(str(DATABASE_PATH), read_only=True)


def prediction_vs_actual(con):
    df = con.execute(f"""
        SELECT
            predicted_points,
            actual_points
        FROM {PREDICTION_TABLE}
        WHERE predicted_points IS NOT NULL
          AND actual_points IS NOT NULL
    """).df()

    plt.figure(figsize=(8, 6))
    plt.scatter(df["predicted_points"], df["actual_points"], alpha=0.7)

    min_val = min(df["predicted_points"].min(), df["actual_points"].min())
    max_val = max(df["predicted_points"].max(), df["actual_points"].max())
    plt.plot([min_val, max_val], [min_val, max_val], linestyle="--")

    plt.title("Predicted vs Actual Driver Fantasy Points")
    plt.xlabel("Predicted Points")
    plt.ylabel("Actual Points")

    save_fig("prediction_vs_actual.png")


def mae_by_race(con):
    df = con.execute(f"""
        SELECT
            year,
            race_id,
            AVG(ABS(actual_points - predicted_points)) AS mae
        FROM {PREDICTION_TABLE}
        WHERE predicted_points IS NOT NULL
          AND actual_points IS NOT NULL
        GROUP BY year, race_id
        ORDER BY year, race_id
    """).df()

    df["race_label"] = df["year"].astype(str) + " R" + df["race_id"].astype(str)

    plt.figure(figsize=(10, 6))
    plt.plot(df["race_label"], df["mae"], marker="o")

    plt.title("Driver Model MAE by Race")
    plt.xlabel("Race")
    plt.ylabel("Mean Absolute Error")
    plt.xticks(rotation=45)

    save_fig("mae_by_race.png")


def residual_distribution(con):
    df = con.execute(f"""
        SELECT
            actual_points - predicted_points AS residual
        FROM {PREDICTION_TABLE}
        WHERE predicted_points IS NOT NULL
          AND actual_points IS NOT NULL
    """).df()

    plt.figure(figsize=(8, 6))
    plt.hist(df["residual"], bins=25)
    plt.axvline(0, linestyle="--")

    plt.title("Driver Model Residual Distribution")
    plt.xlabel("Actual Points - Predicted Points")
    plt.ylabel("Count")

    save_fig("residual_distribution.png")


def top_prediction_misses(con):
    df = con.execute(f"""
        SELECT
            year,
            race_id,
            driver,
            predicted_points,
            actual_points,
            actual_points - predicted_points AS residual,
            ABS(actual_points - predicted_points) AS abs_error
        FROM {PREDICTION_TABLE}
        WHERE predicted_points IS NOT NULL
          AND actual_points IS NOT NULL
        ORDER BY abs_error DESC
        LIMIT 10
    """).df()

    df = df.sort_values("abs_error")

    labels = df["driver"] + " " + df["year"].astype(str) + " R" + df["race_id"].astype(str)

    plt.figure(figsize=(10, 6))
    plt.barh(labels, df["abs_error"])

    plt.title("Largest Driver Prediction Misses")
    plt.xlabel("Absolute Error")
    plt.ylabel("Driver / Race")

    save_fig("largest_prediction_misses.png")


def best_prediction_hits(con):
    df = con.execute(f"""
        SELECT
            year,
            race_id,
            driver,
            predicted_points,
            actual_points,
            ABS(actual_points - predicted_points) AS abs_error
        FROM {PREDICTION_TABLE}
        WHERE predicted_points IS NOT NULL
          AND actual_points IS NOT NULL
        ORDER BY abs_error ASC
        LIMIT 10
    """).df()

    df = df.sort_values("abs_error", ascending=False)

    labels = df["driver"] + " " + df["year"].astype(str) + " R" + df["race_id"].astype(str)

    plt.figure(figsize=(10, 6))
    plt.barh(labels, df["abs_error"])

    plt.title("Closest Driver Predictions")
    plt.xlabel("Absolute Error")
    plt.ylabel("Driver / Race")

    save_fig("closest_predictions.png")


def safe_run(name, func, con):
    try:
        func(con)
        print(f"Created: {name}")
    except Exception as e:
        print(f"Skipped {name}: {e}")


def main():
    with connect_db() as con:
        safe_run("prediction_vs_actual.png", prediction_vs_actual, con)
        safe_run("mae_by_race.png", mae_by_race, con)
        safe_run("residual_distribution.png", residual_distribution, con)
        safe_run("largest_prediction_misses.png", top_prediction_misses, con)
        safe_run("closest_predictions.png", best_prediction_hits, con)

    print(f"\nCharts saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()