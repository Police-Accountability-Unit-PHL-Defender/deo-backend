import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from enum import Enum, auto
from typing import Annotated, Literal

import dash_ag_grid as dag
import fastapi
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html
from dash_helpers import (ActionWordType, Subtitle, TimeAggregationChoice,
                          demographic_dropdown, location_dropdown,
                          police_action_dropdown, qyear_dropdown)
from demographic_constants import DEMOGRAPHICS_DISTRICT
from fastapi import APIRouter, Query
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from models import (MOST_RECENT_QUARTER, QUARTERS, SEASON_QUARTER_MAPPING,
                    AgeGroup, DemographicCategory, FilteredDf, GenderGroup,
                    Geography, PoliceAction, PoliceActionName, Quarter,
                    QuarterHow, RacialGroup, hin_geojson_2020,
                    hin_geojson_2025, hin_sample_locations_df)
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[0].replace("_", "-") + "-" + prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]


def hin_map_2025():
    df = hin_sample_locations_df()[:10]
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    df[" "] = df["on_hin"].apply(
        lambda x: "Traffic stop on the HIN" if x is True else "Traffic stop not on the HIN"
    )
    year = ",".join(f"{x}" for x in df["year"].unique())
    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lng",
        zoom=10,
        mapbox_style="carto-positron",
        title=f"Random Sample of 1,000 PPD Traffic Stops in {year} Mapped on HIN Roads",
    )
    hover_cols = ["stname", "stops_objectid", "nearest_objectid", "distance_from_hin", "on_hin", "location", "lat", "lng"]
    fig.update_traces(
        marker_color=df["on_hin"].map({True: "green", False: "red"}),
        customdata=df[hover_cols].values,
        hovertemplate=(
            "stname: %{customdata[0]}<br>stops_objectid: %{customdata[1]}<br>nearest_objectid: %{customdata[2]}<br>"
            "distance from HIN: %{customdata[3]}<br>on HIN: %{customdata[4]}<br>location: %{customdata[5]}<br>"
            "lat: %{customdata[6]}<br>lng: %{customdata[7]}<extra></extra>"
        ),
        showlegend=False,
    )
    fig.update_mapboxes(
        layers=[
            {
                "source": feature,
                "type": "line",
                "line": {"width": 2},
                "below": "",
                "color": "red",
            }
            for feature in hin_geojson_2025()["features"][:1]
        ]
    )
    fig.update_layout(
        width=800,
        height=600,
        mapbox_center={"lat": df["lat"].median(), "lon": df["lng"].median()},
    )
    fig.update_layout(hovermode='closest')

    return fig

@router.get(API_URL)
def api_func():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_hin = hin_map_2025()
    return endpoint.output(
        map_hin=map_hin,
    )


def hin_map_layout():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_hin_2025 = hin_map_2025()
    return [
        html.A("**API FOR THIS QUESTION**:", href=endpoint.full_api_route),
        dcc.Graph(figure=map_hin_2025),
    ]


LAYOUT = [
    html.Div(hin_map_layout()),
]
