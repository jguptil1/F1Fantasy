import duckdb


def read_prediction_run():
    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:
        result = con.execute("SELECT * FROM prediction_run").df()
    return result

def get_max_prediction_run_id():

    with duckdb.connect("data/database/f1_fantasy.duckdb") as con:

        result = con.execute("""
            SELECT MAX(prediction_run_id)
            FROM prediction_run
        """).fetchone()

    if result is None:
        raise ValueError("prediction_run query returned no rows")

    max_id = result[0]

    if max_id is None:
        raise ValueError("prediction_run table is empty")

    return max_id



