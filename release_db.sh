#!/usr/bin/env bash
# Upload the current DB file to the db-latest GitHub Release.
# Run this after updating ZIP_FILENAME in deo_backend/env.py and rebuilding the DB.
set -euo pipefail

REPO="Police-Accountability-Unit-PHL-Defender/deo-backend"
TAG="db-latest"

DB_FILENAME=$(python3 -c "
import sys; sys.path.insert(0, '$(dirname "$0")')
from deo_backend.env import DB_FILENAME
print(DB_FILENAME)
")

DB_PATH="deo_backend/data/${DB_FILENAME}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: DB file not found: $DB_PATH"
  exit 1
fi

echo "Releasing: $DB_FILENAME ($(du -sh "$DB_PATH" | cut -f1))"

gh release delete "$TAG" --repo "$REPO" --yes 2>/dev/null || true
DB_DATE=$(echo "$DB_FILENAME" | grep -oE '[0-9]{4}_[0-9]{2}_[0-9]{2}' | tr '_' '-')

gh release create "$TAG" \
  --repo "$REPO" \
  --title "DB ${DB_DATE}" \
  --notes "Latest database: $DB_FILENAME" \
  "$DB_PATH"

echo "Done. Render will now download $DB_FILENAME on next deploy."
