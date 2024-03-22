import os

MOST_RECENT_YEAR = os.environ.get("MOST_RECENT_YEAR", "2023")
MOST_RECENT_QUARTER_START = os.environ.get("MOST_RECENT_QUARTER_START", "2023-10-01")
DB_FILENAME = os.environ.get("DB_FILENAME", "open_data_philly_2024_03_16.db")
