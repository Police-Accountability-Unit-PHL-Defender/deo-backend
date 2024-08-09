import pandas as pd
import traceback
import pdb
from models import ProcessZip
import click
import sqlite3
import os

from deo_backend.env import MOST_RECENT_QUARTER_START, ZIP_FILENAME, DATA_DIR


def add_quarterly_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["quarter_dt_str"] = df["quarter"]
    df["quarter_dt"] = pd.to_datetime(df["quarter"])
    df["quarter"] = (
        df["quarter_dt"].dt.year.astype(str)
        + "-Q"
        + df["quarter_dt"].dt.quarter.astype(str)
    )
    df["quarter_date"] = df["quarter_dt"].dt.date
    df["q_str"] = "Q" + df["quarter_dt"].dt.quarter.astype(str)
    df["year"] = df["quarter_dt"].dt.year
    return df


def make_db(df_tables, sqlite_file):
    df_quarterly_reason = pd.concat(df_tables["car_ped_stops"])
    print("Pulling Quarterly Stops")
    df_quarterly = (
        df_quarterly_reason.drop("violation_category", axis=1)
        .groupby(
            [
                "districtoccur",
                "psa",
                "quarter",
                "Race",
                "Gender",
                "Age Range",
            ]
        )
        .sum()
    ).reset_index()
    df_quarterly = add_quarterly_columns(df_quarterly)
    df_quarterly.to_sql(
        "car_ped_stops_quarterly",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )
    df_quarterly_reason = add_quarterly_columns(df_quarterly_reason)
    df_quarterly_reason.to_sql(
        "car_ped_stops_quarterly_reason",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )
    print("Pulling from HIN")
    # df_hin = get_hin_random_sample_from_odp()
    df_hin = pd.read_csv(os.path.join(DATA_DIR, "car_ped_stops_hin_random_sample.csv"))
    df_hin.to_sql(
        "car_ped_stops_hin_random_sample",
        if_exists="replace",
        con=sqlite3.connect(sqlite_file),
        index=False,
    )
    # df_hin_by_quarter = get_hin_by_quarter_from_odp()
    df_hin_by_quarter = pd.concat(df_tables["car_ped_stops_on_hin"])
    df_hin_by_quarter = add_quarterly_columns(df_hin_by_quarter)
    df_hin_by_quarter.to_sql(
        "car_ped_stops_hin_pct",
        if_exists="replace",
        con=sqlite3.connect(sqlite_file),
        index=False,
    )

    print("Get Shooting data")
    # df_shootings = get_shootings_from_odp()
    df_shootings = pd.concat(df_tables["shootings"])
    df_shootings = add_quarterly_columns(df_shootings)

    df_shootings.to_sql(
        "shootings",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )
    print(f"Complete and saved to {sqlite_file}")


@click.command
@click.option("--debug", is_flag=True)
def cli(debug):
    try:
        run = ProcessZip(
            zip_filename=ZIP_FILENAME,
            data_dir=DATA_DIR,
            most_recent_quarter_start_dt=MOST_RECENT_QUARTER_START,
        )
        sqlite_file = os.path.join(DATA_DIR, f"open_data_philly_{run.db_name}.db")
        df_tables = run.get_df_quarterly_reason_from_zipfiles()
        make_db(df_tables, sqlite_file)
    except KeyboardInterrupt:
        raise
    except Exception:
        if debug:
            traceback.print_exc()
            pdb.post_mortem()
        raise


if __name__ == "__main__":
    cli()
