from dash import html
from dash_helpers import (
    Subtitle,
)
from .num_accidents import LAYOUT as NUM_ACCIDENTS_LAYOUT
from .hin_map import LAYOUT as HIN_MAP_LAYOUT
from .shootings_vs_stops_maps import LAYOUT as SHOOTINGS_VS_STOPS_MAPS_LAYOUT

PAGE_TITLE = "Do traffic stops promote safety?"
SUBTITLE_1 = Subtitle(name="Do traffic stops happen where car accidents happen?")
SUBTITLE_2 = Subtitle(
    name="Do changes in traffic stops over time relate to changes in shootings?"
)


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
    + NUM_ACCIDENTS_LAYOUT
    + HIN_MAP_LAYOUT
    + [SUBTITLE_2.h2]
    + SHOOTINGS_VS_STOPS_MAPS_LAYOUT
)
