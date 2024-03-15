from dash import html
from dash_helpers import (
    Subtitle,
)
from .num_intrusions import LAYOUT as NUM_INTRUSIONS_LAYOUT
from .searches_vs_frisks import LAYOUT as SEARCHES_VS_FRISKS_LAYOUT
from .by_demographic_category import LAYOUT as BY_DEMOGRAPHIC_CATEGORY_LAYOUT
from .by_neighborhood import LAYOUT as BY_NEIGHBORHOOD_LAYOUT
from .compare_districts import LAYOUT as COMPARE_DISTRICTS_LAYOUT

PAGE_TITLE = "Do police treat people and neighborhoods differently?"
SUBTITLE_1 = Subtitle(name="How intrusive are police during traffic stops?")
SUBTITLE_2 = Subtitle(name="During traffic stops, do police treat people differently?")
SUBTITLE_3 = Subtitle(
    name="During traffic stops, do police treat neighborhoods differently?"
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
    SUBTITLE_3.a_href,
    html.Div(),
    SUBTITLE_1.h2,
]

layout = html.Div(
    MENU_LAYOUT
    + NUM_INTRUSIONS_LAYOUT
    + [html.Hr()]
    + SEARCHES_VS_FRISKS_LAYOUT
    + [html.Hr(), SUBTITLE_2.h2]
    + BY_DEMOGRAPHIC_CATEGORY_LAYOUT
    + [SUBTITLE_3.h2]
    + BY_NEIGHBORHOOD_LAYOUT
    + COMPARE_DISTRICTS_LAYOUT
)
