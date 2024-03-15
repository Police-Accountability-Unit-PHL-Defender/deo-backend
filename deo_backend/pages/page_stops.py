import os
from dash import register_page  # This registers the pages
from .stops import PAGE_TITLE as STOPS_PAGE_TITLE, layout

if os.environ.get("SERVER_TYPE", "dash") == "dash":
    register_page(__name__, path="/stops", supplied_name=STOPS_PAGE_TITLE, order=1)
