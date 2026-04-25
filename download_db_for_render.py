"""
Downloads the current DB file from GitHub Releases if not already present.
Run during Render build: python scripts/fetch_db.py
Upload DB files to the 'db-latest' release on GitHub before deploying.
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from deo_backend.env import DATA_DIR, DB_FILENAME

GITHUB_REPO = "Police-Accountability-Unit-PHL-Defender/deo-backend"
RELEASE_TAG = "db-latest"
URL = f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/{DB_FILENAME}"
DEST = os.path.join(DATA_DIR, DB_FILENAME)

if os.path.exists(DEST):
    print(f"DB already present: {DEST}")
    sys.exit(0)

print(f"Downloading {DB_FILENAME} from GitHub Releases...")
os.makedirs(DATA_DIR, exist_ok=True)
urllib.request.urlretrieve(URL, DEST)
print(f"Saved to {DEST}")
