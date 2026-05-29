import duckdb
import pandas as pd
import datetime

DATABASE_PATH = "data/database/f1_fantasy.duckdb"


def build_simulation_run():
    with duckdb.connect(DATABASE_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS simulation_run (
                simulation_run_id BIGINT,
                created_at TIMESTAMP,

                race_id BIGINT,
                driver_prediction_run_id BIGINT,
                constructor_prediction_run_id BIGINT,

                n_sims INTEGER,
                random_seed INTEGER,

                residual_source_table VARCHAR,
                residual_bucket_strategy VARCHAR,

                notes VARCHAR
            );
        """)


def build_simulation_driver_summary():
    with duckdb.connect(DATABASE_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS simulation_driver_summary (
                simulation_run_id BIGINT,

                race_id BIGINT,
                driver_id BIGINT,
                constructor_id BIGINT,

                price DOUBLE,
                predicted_points DOUBLE,
                prediction_bucket VARCHAR,

                mean_sim_points DOUBLE,
                std_sim_points DOUBLE,

                p05 DOUBLE,
                p10 DOUBLE,
                p25 DOUBLE,
                median DOUBLE,
                p75 DOUBLE,
                p90 DOUBLE,
                p95 DOUBLE,

                mean_per_price DOUBLE,
                p90_per_price DOUBLE,
                risk_range DOUBLE,
                downside_gap DOUBLE
            );
        """)


def build_simulation_profile_result():
    with duckdb.connect(DATABASE_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS simulation_profile_result (
                simulation_run_id BIGINT,

                profile_name VARCHAR,
                profile_source VARCHAR,
                profile_strategy VARCHAR,

                optimizer_run_id BIGINT,

                mean_lineup_points DOUBLE,
                std_lineup_points DOUBLE,

                p05 DOUBLE,
                p10 DOUBLE,
                p25 DOUBLE,
                median DOUBLE,
                p75 DOUBLE,
                p90 DOUBLE,
                p95 DOUBLE
            );
        """)


def build_simulation_tables():
    build_simulation_run()
    build_simulation_driver_summary()
    build_simulation_profile_result()


def get_max_simulation_run_id():
    with duckdb.connect(DATABASE_PATH, read_only=True) as con:
        result = con.execute("""
            SELECT COALESCE(MAX(simulation_run_id), 0)
            FROM simulation_run
        """).fetchone()[0] # type: ignore

    return int(result)


def append_simulation_run(
    race_id,
    driver_prediction_run_id,
    constructor_prediction_run_id,
    n_sims,
    random_seed,
    residual_source_table="driver_prediction_residuals",
    residual_bucket_strategy="00_20_vs_20_plus",
    notes=None,
):
    simulation_run_id = get_max_simulation_run_id() + 1
    created_at = datetime.datetime.now()

    run_row = pd.DataFrame([{
        "simulation_run_id": simulation_run_id,
        "created_at": created_at,

        "race_id": int(race_id),
        "driver_prediction_run_id": int(driver_prediction_run_id),
        "constructor_prediction_run_id": int(constructor_prediction_run_id),

        "n_sims": int(n_sims),
        "random_seed": int(random_seed),

        "residual_source_table": residual_source_table,
        "residual_bucket_strategy": residual_bucket_strategy,

        "notes": notes,
    }])

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("temp_simulation_run", run_row)

        con.execute("""
            INSERT INTO simulation_run
            SELECT *
            FROM temp_simulation_run
        """)

    print(f"Appended simulation_run_id {simulation_run_id}")

    return simulation_run_id


def append_simulation_driver_summary(simulation_run_id, driver_summary_df):
    df = driver_summary_df.copy()

    df["simulation_run_id"] = int(simulation_run_id)

    insert_cols = [
        "simulation_run_id",
        "race_id",
        "driver_id",
        "constructor_id",
        "price",
        "predicted_points",
        "prediction_bucket",
        "mean_sim_points",
        "std_sim_points",
        "p05",
        "p10",
        "p25",
        "median",
        "p75",
        "p90",
        "p95",
        "mean_per_price",
        "p90_per_price",
        "risk_range",
        "downside_gap",
    ]

    df = df[insert_cols].copy()

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("temp_simulation_driver_summary", df)

        con.execute(f"""
            INSERT INTO simulation_driver_summary ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_simulation_driver_summary
        """)

    print(f"Appended {len(df)} row(s) to simulation_driver_summary")


def append_simulation_profile_result(simulation_run_id, profile_summary_df):
    df = profile_summary_df.copy()

    df["simulation_run_id"] = int(simulation_run_id)

    insert_cols = [
        "simulation_run_id",
        "profile_name",
        "profile_source",
        "profile_strategy",
        "optimizer_run_id",
        "mean_lineup_points",
        "std_lineup_points",
        "p05",
        "p10",
        "p25",
        "median",
        "p75",
        "p90",
        "p95",
    ]

    df = df[insert_cols].copy()

    with duckdb.connect(DATABASE_PATH) as con:
        con.register("temp_simulation_profile_result", df)

        con.execute(f"""
            INSERT INTO simulation_profile_result ({", ".join(insert_cols)})
            SELECT {", ".join(insert_cols)}
            FROM temp_simulation_profile_result
        """)

    print(f"Appended {len(df)} row(s) to simulation_profile_result")


def simulation_tables_controller(
    race_id,
    driver_prediction_run_id,
    constructor_prediction_run_id,
    n_sims,
    random_seed,
    driver_summary_df,
    profile_summary_df,
    residual_source_table="driver_prediction_residuals",
    residual_bucket_strategy="00_20_vs_20_plus",
    notes=None,
):
    build_simulation_tables()

    simulation_run_id = append_simulation_run(
        race_id=race_id,
        driver_prediction_run_id=driver_prediction_run_id,
        constructor_prediction_run_id=constructor_prediction_run_id,
        n_sims=n_sims,
        random_seed=random_seed,
        residual_source_table=residual_source_table,
        residual_bucket_strategy=residual_bucket_strategy,
        notes=notes,
    )

    append_simulation_driver_summary(
        simulation_run_id=simulation_run_id,
        driver_summary_df=driver_summary_df,
    )

    append_simulation_profile_result(
        simulation_run_id=simulation_run_id,
        profile_summary_df=profile_summary_df,
    )

    return simulation_run_id