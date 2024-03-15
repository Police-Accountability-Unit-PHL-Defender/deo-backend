from fastapi import APIRouter
from dash import Dash, html, dcc, callback, Output, Input
from dash_helpers import (
    Subtitle,
)
from .num_stops import LAYOUT as NUM_STOPS_LAYOUT
from .num_stops_time_slice import LAYOUT as NUM_STOPS_TIME_SLICE_LAYOUT
from .seasonal import LAYOUT as SEASONAL_LAYOUT
from .by_demographic_category import LAYOUT as BY_DEMOGRAPHIC_CATEGORY_LAYOUT
from .most_frequent_stops import LAYOUT as MOST_FREQUENT_STOPS_LAYOUT
from .group_comparison import LAYOUT as GROUP_COMPARISON_LAYOUT

PAGE_TITLE = "How many stops do police make, and who do they stop?"
SUBTITLE_1 = Subtitle(name="How many traffic stops do police make?")
SUBTITLE_2 = Subtitle(name="Who are police stopping in traffic stops?")


MENU_LAYOUT = [
    html.H1(
        children=PAGE_TITLE,
        style={"textAlign": "center"},
    ),
    SUBTITLE_1.a_href,
    html.Div(),
    SUBTITLE_2.a_href,
    html.Div(),
    SUBTITLE_1.h2,
]

layout = html.Div(
    MENU_LAYOUT
    + NUM_STOPS_LAYOUT
    + NUM_STOPS_TIME_SLICE_LAYOUT
    + SEASONAL_LAYOUT
    + [SUBTITLE_2.h2]
    + BY_DEMOGRAPHIC_CATEGORY_LAYOUT
    + MOST_FREQUENT_STOPS_LAYOUT
    + GROUP_COMPARISON_LAYOUT
)
