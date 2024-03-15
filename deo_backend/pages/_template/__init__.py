from fastapi import APIRouter
from dash import Dash, html, dcc, callback, Output, Input
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)

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

layout = html.Div()
