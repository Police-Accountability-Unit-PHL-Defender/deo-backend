import os
from dash import register_page  # This registers the pages
from .safety import PAGE_TITLE as SAFETY_PAGE_TITLE, layout as layout

if os.environ.get("SERVER_TYPE", "dash") == "dash":
    register_page(__name__, path="/safety", supplied_name=SAFETY_PAGE_TITLE, order=3)
