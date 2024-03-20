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
from models import DfType
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
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Span(
        "When Philadelphia police provided a reason, what were the primary reasons why police stopped Black and white drivers in Philadelphia in "
    ),
    dcc.Dropdown(
        options=[
            {"label": 2022, "value": 2022},
            {"label": 2023, "value": 2023},
        ],
        value=2022,
        id=f"{prefix}-year",
        style={"display": "inline-block", "width": "150px"},
    ),
    html.Span(" sorted by "),
    dcc.Dropdown(
        options=[
            {"label": "White", "value": "White"},
            {"label": "Black", "value": "Black"},
        ],
        value="Black",
        id=f"{prefix}-race",
        style={"display": "inline-block", "width": "150px"},
    ),
    html.Span("?"),
    dcc.Graph(id=f"{prefix}-graph1"),
]


@callback(
    [
        Output(f"{prefix}-graph1", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-year", "value"),
        Input(f"{prefix}-race", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    year: Annotated[int, Query(description="year", ge=2021)] = 2022,
    race: Annotated[Literal["Black", "White"], Query(description="race")] = "Black",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    df_reasons = FilteredDf(
        start_date=datetime(year, 1, 1),
        end_date=datetime(year, 12, 31),
        df_type=DfType.stops_by_reason,
    ).df
    df_reasons = df_reasons[df_reasons["violation_category"] != "Other"]

    df_reasons_grouped = (
        df_reasons.groupby(["Race", "violation_category"])["n_stopped"]
        .sum()
        .reset_index()
    )

    col = "Race"
    vals = ["White", "Black"]
    df_filt = df_reasons_grouped[df_reasons_grouped[col].isin(vals)].sort_values(
        [col, "n_stopped"], ascending=[race != "White", True]
    )
    total_stops = df_filt.groupby(col)["n_stopped"].sum().to_dict()

    df_filt["pct_stopped"] = 100 * df_filt.apply(
        lambda x: x["n_stopped"] / total_stops[x[col]], axis=1
    )
    fig = px.bar(
        df_filt,
        x="violation_category",
        y="pct_stopped",
        barmode="group",
        color=col,
        color_discrete_map={"White": "Red", "Black": "Blue", "Non-white": "Blue"},
    )
    fig.update_yaxes(title_text="% of Stops By Reason for Drivers By Race")

    return endpoint.output(
        fig_barplot=fig,
        data={},
    )
