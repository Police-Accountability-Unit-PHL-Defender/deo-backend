from fastapi import APIRouter
from dash import Dash, html, dcc, callback, Output, Input
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from .comparison_bars import LAYOUT as COMPARISON_BARS_LAYOUT

PAGE_TITLE = "Do police make traffic stops for safety reasons?"
# SUBTITLE_1 = Subtitle(name="How many traffic stops do police make?")


MENU_LAYOUT = [
    html.H1(
        children=PAGE_TITLE,
        style={"textAlign": "center"},
    ),
    html.Div(),
]

layout = html.Div(MENU_LAYOUT + COMPARISON_BARS_LAYOUT)
