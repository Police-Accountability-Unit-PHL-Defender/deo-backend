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
from models import AgeGroup
from models import DemographicCategory
from models import TimeAggregation
from models import english_comma_separated
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import Quarter
from fastapi_models import Endpoint
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from models import df_raw
import os

from fastapi import APIRouter, Query
from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]

LAYOUT = [
    html.Hr(),
    html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api"),
    html.Span(
        "Does traffic enforcement change depending on the time of year? How many traffic stops did Philadelphia police make in certain times of year in "
    ),
    location_dropdown(f"{prefix}-location"),
    html.Span("?"),
    html.Br(),
    html.Span("Select time(s) of year: "),
    dcc.Dropdown(
        options=[
            {"label": val, "value": key} for key, val in SEASON_QUARTER_MAPPING.items()
        ],
        value=["Q3"],
        id=f"{prefix}-q-over-year-select",
        multi=True,
        style={"display": "inline-block", "width": "250px"},
    ),
    dcc.Graph(id=f"{prefix}-graph3"),
    html.Hr(),
]


@callback(
    [
        Output(f"{prefix}-graph3", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-q-over-year-select", "value"),
    ],
)
@router.get("/stops/seasonal")
def stops__seasonal(
    location: Annotated[
        str,
        Query(
            description="A location identifier. Citywide is `*`, a district is a 2-digit number (`22*`) and a PSA is 'district-PSA' (`22-1`)",
        ),
    ] = "*",
    q_over_year_select: Annotated[list[Literal["Q1", "Q2", "Q3", "Q4"]], Query()] = [
        "Q3"
    ],
):
    endpoint = Endpoint(
        api_route="/stops/seasonal",
        inputs={"location": location, "q_over_year_select": q_over_year_select},
    )
    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(location=location)
    df_geo_all_time = geo_filter.df
    geo_level_str = geo_filter.geography.string

    df_geo_total_all_time = (
        df_geo_all_time.groupby(
            [
                "districtoccur",
                "psa",
                "year",
                "quarter",
                "q_str",
            ]
        )[[a.value.sql_column for a in PoliceAction]]
        .sum()
        .reset_index()
    )

    df_geo_quarter_select = (
        df_geo_total_all_time[df_geo_total_all_time.q_str.isin(q_over_year_select)]
        .groupby(df_geo_total_all_time.year)[police_action.sql_column]
        .sum()
    ).reset_index()

    # Seasonal Selection
    q_over_year_select_labels = [
        SEASON_QUARTER_MAPPING[q] for q in sorted(q_over_year_select)
    ]

    q_over_year_select_str = english_comma_separated(q_over_year_select_labels)
    fig2 = px.bar(
        df_geo_quarter_select,
        x="year",
        y=police_action.sql_column,
        title=f"Number of PPD {police_action.noun.title()} in {geo_level_str} for {q_over_year_select_str} from {geo_filter.get_date_range_str(TimeAggregation.year)}",
        labels={
            police_action.sql_column: f"Number of {police_action.noun.title()}",
            "year": f"Times of Year: {q_over_year_select_str}",
        },
    ).update_xaxes(dtick=1)
    for trace in fig2.data:
        trace.hovertemplate = (
            q_over_year_select_str + "<br>%{x}<br>%{y:,} " + police_action.noun
        )

    return endpoint.output(fig_barplot=fig2)
