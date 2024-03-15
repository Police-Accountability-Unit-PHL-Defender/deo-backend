import os
from dash import register_page  # This registers the pages
from .neighborhoods import PAGE_TITLE as NEIGHBORHOOD_PAGE_TITLE, layout

if os.environ.get("SERVER_TYPE", "dash") == "dash":
    register_page(
        __name__, path="/neighborhoods", supplied_name=NEIGHBORHOOD_PAGE_TITLE, order=2
    )
