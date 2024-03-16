from dash import Dash, html, dcc, callback, Output, Input
import uuid
from typing import Literal
from typing import Annotated
import fastapi
from fastapi import APIRouter, Query
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
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import (
    QUARTERS,
    MOST_RECENT_QUARTER,
    SEASON_QUARTER_MAPPING,
    FOUR_QUARTERS_AGO,
)
from models import Quarter
from models import QuarterHow
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from models import df_raw
import os

from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]

LAYOUT = [
    html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api"),
    html.Span("In "),
    location_dropdown(f"{prefix}-location"),
    html.Span(", from the start of quarter"),
    qyear_dropdown(f"{prefix}-q1-start-qyear", default=FOUR_QUARTERS_AGO),
    html.Span(" through the end of "),
    qyear_dropdown(
        f"{prefix}-q1-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
    ),
    html.Span(", "),
    html.Span(id=f"{prefix}-result-text3"),
]


@callback(
    [
        Output(f"{prefix}-result-text3", "children"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-q1-start-qyear", "value"),
        Input(f"{prefix}-q1-end-qyear", "value"),
        Input(f"{prefix}-location", "value"),
    ],
)
@router.get(API_URL)
def stops__num_stops_time_slice(
    start_qyear: quarter_annotation = FOUR_QUARTERS_AGO,
    end_qyear: quarter_annotation = MOST_RECENT_QUARTER,
    location: location_annotation = "*",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(
        location=location, start_date=start_qyear, end_date=end_qyear
    )
    geo_level_str = geo_filter.geography.string
    df_geo = geo_filter.df
    total = df_geo[police_action.sql_column].sum()
    total_per_month = geo_filter.get_avg_monthly_value(police_action)

    return endpoint.output(
        text_time_slice_sentence=f"Philadelphia police made an average of <span>{total_per_month:,}</span> traffic stops per month in {geo_level_str}, totaling <span>{total:,}</span> traffic stops during that period.",
    )
