from pathlib import Path
import duckdb
import pandas as pd



"""
This module allows for me to get metadata on the database itself
- will use this for troubleshooting moving forward as the database grows

"""


DB_PATH = Path("data/database/f1_fantasy.duckdb")


def get_database_size_mb(db_path: Path) -> float:
    """Return database file size in megabytes."""
    if not db_path.exists():
        return 0.0
    return db_path.stat().st_size / (1024 * 1024)


def get_table_names(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Return a list of user tables in the database."""
    tables_df = con.execute("SHOW TABLES").df()
    if tables_df.empty:
        return []
    return tables_df.iloc[:, 0].tolist()


def get_table_row_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Return row count for a table."""
    query = f"SELECT COUNT(*) AS row_count FROM {table_name}"
    return con.execute(query).fetchone()[0]


def get_table_schema(con: duckdb.DuckDBPyConnection, table_name: str) -> pd.DataFrame:
    """Return schema info for a table."""
    query = f"PRAGMA table_info('{table_name}')"
    return con.execute(query).df()


def build_database_summary(db_path: Path = DB_PATH) -> dict:
    """Build a high-level summary of the DuckDB database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    con = duckdb.connect(str(db_path))

    try:
        table_names = get_table_names(con)

        table_summaries = []
        for table_name in table_names:
            schema_df = get_table_schema(con, table_name)
            row_count = get_table_row_count(con, table_name)

            table_summaries.append({
                "table_name": table_name,
                "row_count": row_count,
                "column_count": len(schema_df),
                "columns": schema_df["name"].tolist(),
                "column_types": schema_df["type"].tolist()
            })

        summary = {
            "database_path": str(db_path),
            "database_size_mb": round(get_database_size_mb(db_path), 4),
            "table_count": len(table_names),
            "tables": table_summaries
        }

        return summary

    finally:
        con.close()


def print_database_summary(summary: dict) -> None:
    """Pretty-print the database summary."""
    print("\nDATABASE SUMMARY")
    print("-" * 60)
    print(f"Path: {summary['database_path']}")
    print(f"Size (MB): {summary['database_size_mb']}")
    print(f"Table count: {summary['table_count']}")

    print("\nTABLE DETAILS")
    print("-" * 60)

    for table in summary["tables"]:
        print(f"\nTable: {table['table_name']}")
        print(f"  Rows: {table['row_count']}")
        print(f"  Columns: {table['column_count']}")

        for col_name, col_type in zip(table["columns"], table["column_types"]):
            print(f"    - {col_name}: {col_type}")


if __name__ == "__main__":
    summary = build_database_summary()
    print_database_summary(summary)