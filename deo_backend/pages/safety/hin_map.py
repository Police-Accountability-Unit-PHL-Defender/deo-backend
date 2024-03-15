from dash import Dash, html, dcc, callback, Output, Input
import uuid
from typing import Literal
from typing import Annotated
import fastapi
import dash_ag_grid as dag
from datetime import date
from datetime import timedelta
from datetime import datetime
import plotly.express as px
import pandas as pd
import sqlite3

from models import PoliceAction
from models import PoliceActionName
from models import QuarterHow
from models import hin_geojson
from models import hin_sample_locations_df
from demographics.constants import (
    DEMOGRAPHICS_DISTRICT,
)
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import Quarter
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
    police_action_dropdown,
    ActionWordType,
)
import os

from fastapi import APIRouter, Query
from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[0].replace("_", "-") + "-" + prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]


def hin_map():
    df = hin_sample_locations_df()
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    df[" "] = df["on_hin"].apply(
        lambda x: "Traffic stop on the HIN" if x else "Traffic stop not on the HIN"
    )
    fig = px.scatter_mapbox(
        df,
        lat="point_y",
        lon="point_x",
        color_discrete_map={True: "green", False: "red"},
        zoom=10,
        mapbox_style="carto-positron",
        color=" ",
        title="Random Sample of 1,000 PPD Traffic Stops in 2023 Mapped on HIN Roads",
    )
    fig.update_mapboxes(
        layers=[
            {
                "source": feature,
                "type": "line",
                "line": {"width": 2},
                "below": "",
                "color": "black",
            }
            for feature in hin_geojson()["features"]
        ]
    )
    fig.update_layout(
        width=800,
        height=600,
        mapbox_center={"lat": df["point_y"].mean(), "lon": df["point_x"].mean()},
    )
    fig.update_layout(hovermode=False)

    return fig


@router.get(API_URL)
def api_func():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_hin = hin_map()
    return endpoint.output(
        map_hin=map_hin,
    )


def hin_map_layout():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_hin = hin_map()
    return [
        html.A("**API FOR THIS QUESTION**:", href=endpoint.full_api_route),
        dcc.Graph(figure=map_hin),
    ]


LAYOUT = [
    html.Div(hin_map_layout()),
]
