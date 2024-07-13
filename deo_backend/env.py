import os

MOST_RECENT_YEAR = os.environ.get("MOST_RECENT_YEAR", "2024")
MOST_RECENT_QUARTER_START = os.environ.get("MOST_RECENT_QUARTER_START", "2024-04-01")
DB_FILENAME = os.environ.get("DB_FILENAME", "open_data_philly_2024_07_01.db")
