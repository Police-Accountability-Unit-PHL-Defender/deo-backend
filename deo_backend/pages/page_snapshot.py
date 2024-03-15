import os
from dash import register_page  # This registers the pages
from .snapshot import PAGE_TITLE as SNAPSHOT_PAGE_TITLE, layout

if os.environ.get("SERVER_TYPE", "dash") == "dash":
    register_page(
        __name__, path="/snapshot", supplied_name=SNAPSHOT_PAGE_TITLE, order=0
    )
