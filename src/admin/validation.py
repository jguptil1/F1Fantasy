from pathlib import Path
import duckdb


DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")


EXPECTED_TABLES = [
    "dim_driver",
    "dim_constructor",
    "dim_race",
    "fact_driver_race",
    "fact_constructor_race",
    "pre_race_driver_features",
    "pre_race_constructor_features",
    "current_race_driver_features",
    "current_race_constructor_features",
    "prediction_run",
    "fact_driver_predictions",
    "fact_constructor_predictions",
    "staged_qualifying_results_table",
]


EXPECTED_GRAINS = {
    "dim_driver": ["driver_id"],
    "dim_constructor": ["year", "constructor_id"],
    "dim_race": ["race_id"],
    "fact_driver_race": ["race_id", "driver_id"],
    "fact_constructor_race": ["race_id", "constructor_id"],
    "pre_race_driver_features": ["race_id", "driver_id"],
    "pre_race_constructor_features": ["race_id", "constructor_id"],
    "current_race_driver_features": ["race_id", "driver_id"],
    "current_race_constructor_features": ["race_id", "constructor_id"],
    "prediction_run": ["prediction_run_id"],
    "fact_driver_predictions": ["prediction_run_id", "race_id", "driver_id"],
    "fact_constructor_predictions": ["prediction_run_id", "race_id", "constructor_id"],
    "staged_qualifying_results_table" : ["race_id", "driver_id"]
}


REQUIRED_COLUMNS = {
    "dim_driver": ["driver_id", "driver_name", "name_acronym"],
    "dim_constructor": ["constructor_id", "year", "constructor_name"],
    "dim_race": ["race_id", "year", "race_num", "race_name"],

    "fact_driver_race": [
        "race_id", "year", "driver_id", "constructor_id",
        "price", "fantasy_points", "elo_before"
    ],

    "fact_constructor_race": [
        "race_id", "year", "constructor_id",
        "price", "fantasy_points"
    ],

    "pre_race_driver_features": [
        "race_id", "year", "driver_id", "constructor_id",
        "price", "elo_before", "avg_quali_last_5", "quali_vs_teammate_last_5"
    ],

    "pre_race_constructor_features": [
        "race_id", "year", "constructor_id", "price"
    ],

    "current_race_driver_features": [
        "race_id", "year", "driver_id", "constructor_id",
        "price", "elo_before", "avg_quali_last_5", "quali_vs_teammate_last_5",
    ],

    "current_race_constructor_features": [
        "race_id", "year", "constructor_id", "price"
    ],

    "prediction_run": [
        "prediction_run_id", "created_at", "model_name",
        "model_version", "feature_set_version", "target",
        "train_cutoff_race_id", "asset_type"
    ],

    "fact_driver_predictions": [
        "prediction_run_id", "year", "race_id", "driver_id",
        "constructor_id", "price", "predicted_points"
    ],

    "fact_constructor_predictions": [
        "prediction_run_id", "year", "race_id", "constructor_id",
        "price", "predicted_points"
    ],


    "staged_qualifying_results_table": [
        "year",
        "race_id",
        "meeting_key",
        "session_key",
        "driver_number",
        "driver_name",
        "driver_id",
        "qualifying_position",
        "qualifying_laps",
        "q1_time",
        "q2_time",
        "q3_time",
        "dnf",
        "dns",
        "dsq",
    ]
}


REQUIRED_NOT_NULL_COLUMNS = {
    table: cols for table, cols in REQUIRED_COLUMNS.items()
}

REQUIRED_NOT_NULL_COLUMNS["staged_qualifying_results_table"] = [
    "year",
    "race_id",
    "meeting_key",
    "session_key",
    "driver_number",
    "driver_name",
    "driver_id",
]


def connect_db(database_path: Path = DATABASE_PATH):
    return duckdb.connect(str(database_path), read_only=True)


def get_table_names(con) -> set[str]:
    rows = con.execute("SHOW TABLES").fetchall()
    return {row[0] for row in rows}


def get_column_names(con, table_name: str) -> list[str]:
    df = con.execute(f"DESCRIBE {table_name}").df()
    return df["column_name"].tolist()


def validate_table_exists(con, table_name: str):
    existing_tables = get_table_names(con)

    if table_name not in existing_tables:
        raise ValueError(f"Missing expected table: {table_name}")

    print(f"PASS: {table_name} exists")


def validate_no_column_whitespace(con, table_name: str):
    columns = get_column_names(con, table_name)
    bad_columns = [col for col in columns if col != col.strip()]

    if bad_columns:
        raise ValueError(
            f"{table_name} has columns with leading/trailing whitespace: {bad_columns}"
        )

    print(f"PASS: {table_name} has no column whitespace issues")


def validate_required_columns(con, table_name: str, required_columns: list[str]):
    existing_columns = set(get_column_names(con, table_name))
    missing_columns = [col for col in required_columns if col not in existing_columns]

    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {missing_columns}"
        )

    print(f"PASS: {table_name} has required columns")


def validate_no_nulls(con, table_name: str, required_columns: list[str]):
    failed = {}

    for col in required_columns:
        null_count = con.execute(f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE {col} IS NULL
        """).fetchone()[0]

        if null_count > 0:
            failed[col] = null_count

    if failed:
        for col in failed:
            sample = con.execute(f"""
                SELECT *
                FROM {table_name}
                WHERE {col} IS NULL
                LIMIT 10
            """).df()

            print(f"\nSample rows from {table_name} where {col} is NULL:")
            print(sample)

        raise ValueError(
            f"{table_name} has nulls in required columns: {failed}"
        )

    print(f"PASS: {table_name} has no nulls in required columns")


def validate_unique_grain(con, table_name: str, grain_columns: list[str]):
    grain_sql = ", ".join(grain_columns)

    query = f"""
        SELECT
            {grain_sql},
            COUNT(*) AS row_count
        FROM {table_name}
        GROUP BY {grain_sql}
        HAVING COUNT(*) > 1
    """

    duplicates = con.execute(query).df()

    if not duplicates.empty:
        raise ValueError(
            f"{table_name} failed grain check on {grain_columns}. "
            f"Duplicate groups found: {len(duplicates)}"
        )

    print(f"PASS: {table_name} grain is unique on {grain_columns}")


def validate_table_not_empty(con, table_name: str):
    row_count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    if row_count == 0:
        raise ValueError(f"{table_name} is empty")

    print(f"PASS: {table_name} is not empty ({row_count} rows)")



def validate_qualifying_positions_reasonable(con):
    bad_rows = con.execute("""
        SELECT *
        FROM staged_qualifying_results_table
        WHERE qualifying_position IS NOT NULL
          AND (qualifying_position < 1 OR qualifying_position > 25)
    """).df()

    if not bad_rows.empty:
        print(bad_rows)
        raise ValueError("staged_qualifying_results_table has unreasonable qualifying positions")

    print("PASS: qualifying positions are reasonable")


def validate_qualifying_race_coverage(con):
    coverage = con.execute("""
        SELECT
            year,
            race_id,
            COUNT(*) AS rows,
            COUNT(DISTINCT driver_id) AS drivers
        FROM staged_qualifying_results_table
        GROUP BY year, race_id
        HAVING COUNT(DISTINCT driver_id) < 18
    """).df()

    if not coverage.empty:
        print(coverage)
        raise ValueError("Some qualifying races have suspiciously low driver coverage")

    print("PASS: qualifying race coverage looks reasonable")


def validate_qualifying_driver_resolution(con):
    unresolved = con.execute("""
        SELECT *
        FROM staged_qualifying_results_table
        WHERE race_id IS NULL
           OR driver_id IS NULL
           OR driver_name IS NULL
        LIMIT 25
    """).df()

    if not unresolved.empty:
        print(unresolved)
        raise ValueError("Qualifying staging has unresolved race_id/driver_id/driver_name rows")

    print("PASS: qualifying driver/race resolution succeeded")


def validate_fdr_qualifying_columns(con):
    columns = set(get_column_names(con, "fact_driver_race"))

    required = {"qualifying_position", "qualifying_laps"}
    missing = required - columns

    if missing:
        raise ValueError(f"fact_driver_race missing qualifying columns: {missing}")

    print("PASS: fact_driver_race has qualifying columns")


def validate_fdr_qualifying_join_coverage(con):
    coverage = con.execute("""
        SELECT
            fdr.year,
            fdr.race_id,
            COUNT(*) AS fdr_rows,
            COUNT(fdr.qualifying_position) AS rows_with_quali
        FROM fact_driver_race fdr
        GROUP BY fdr.year, fdr.race_id
        HAVING COUNT(fdr.qualifying_position) = 0
        ORDER BY fdr.year, fdr.race_id
    """).df()

    if not coverage.empty:
        print(coverage)
        raise ValueError("Some fact_driver_race races have zero qualifying coverage")

    print("PASS: fact_driver_race qualifying coverage exists by race")


def validate_driver_quali_features(con):
    bad_avg_quali = con.execute("""
        SELECT *
        FROM pre_race_driver_features
        WHERE avg_quali_last_5 IS NULL
           OR avg_quali_last_5 < 1
           OR avg_quali_last_5 > 25
        LIMIT 25
    """).df()

    if not bad_avg_quali.empty:
        print(bad_avg_quali)
        raise ValueError("Invalid avg_quali_last_5 values found")

    bad_teammate_delta = con.execute("""
        SELECT *
        FROM pre_race_driver_features
        WHERE quali_vs_teammate_last_5 IS NULL
           OR quali_vs_teammate_last_5 < -25
           OR quali_vs_teammate_last_5 > 25
        LIMIT 25
    """).df()

    if not bad_teammate_delta.empty:
        print(bad_teammate_delta)
        raise ValueError("Invalid quali_vs_teammate_last_5 values found")

    print("PASS: qualifying driver features are valid")


def validate_phase_1_mvp(database_path: Path = DATABASE_PATH):
    print("Running Phase 1 database validation checks...")
    print("-" * 60)

    with connect_db(database_path) as con:
        for table_name in EXPECTED_TABLES:
            validate_table_exists(con, table_name)
            validate_table_not_empty(con, table_name)
            validate_no_column_whitespace(con, table_name)

            if table_name in REQUIRED_COLUMNS:
                validate_required_columns(
                    con,
                    table_name,
                    REQUIRED_COLUMNS[table_name]
                )

            if table_name in REQUIRED_NOT_NULL_COLUMNS:
                validate_no_nulls(
                    con,
                    table_name,
                    REQUIRED_NOT_NULL_COLUMNS[table_name]
                )

            if table_name in EXPECTED_GRAINS:
                validate_unique_grain(
                    con,
                    table_name,
                    EXPECTED_GRAINS[table_name]
                )


            print("-" * 60)
    
        validate_qualifying_driver_resolution(con)
        validate_qualifying_positions_reasonable(con)
        validate_qualifying_race_coverage(con)

        # Only run these after you add quali columns to FDR
        validate_fdr_qualifying_columns(con)
        validate_fdr_qualifying_join_coverage(con)

        validate_driver_quali_features(con )

    print("All Phase 1 validation checks passed.")


if __name__ == "__main__":
    validate_phase_1_mvp()