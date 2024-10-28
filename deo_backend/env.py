import os

"""
These are the two variables that you must update when you are updating the database.
"""
MOST_RECENT_QUARTER_START = os.environ.get("MOST_RECENT_QUARTER_START", "2024-07-01")
ZIP_FILENAME = os.environ.get("ZIP_FILENAME", "car_ped_stops_2024-10-24T01_17_41.zip")


def find_project_root(current_path):
    while not os.path.isfile(os.path.join(current_path, "pyproject.toml")):
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            raise RuntimeError("Project root not found")
        current_path = parent_path
    return current_path


# Determine the project root directory
PROJECT_ROOT = find_project_root(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "deo_backend", "data")


def db_name(zip_filename):
    # car_ped_stops_2024-03-16T20_22_24.zip -> 2014_03_16
    return (
        zip_filename.replace("car_ped_stops", "open_data_philly")
        .split("T")[0]
        .replace("-", "_")
        + ".db"
    )


# DB_FILENAME is derived from the zip filename: open_data_philly_YYYY_MM_DD.db
DB_FILENAME = os.environ.get("DB_FILENAME") or db_name(ZIP_FILENAME)
