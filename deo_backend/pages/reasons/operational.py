from dash import Dash, html, dcc, callback, Output, Input
import numpy as np
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
from models import TimeAggregation
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
    html.Span("How did Operational vs not change over time? Show results by "),
    TimeAggregationChoice.dropdown(id=f"{prefix}-time-aggregation"),
    html.Span("."),
    dcc.Graph(id=f"{prefix}-graph1"),
]


@callback(
    [
        Output(f"{prefix}-graph1", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-time-aggregation", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    time_aggregation: Annotated[
        TimeAggregationChoice, Query(description="Time Aggregation")
    ] = "year",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(
        start_date=datetime(2022, 1, 1),
        end_date=MOST_RECENT_QUARTER,
        df_type=DfType.stops_by_reason,
    )
    df_reasons = geo_filter.df
    geo_level_str = geo_filter.geography.string
    # Boolean in SQLITE
    df_reasons = df_reasons[df_reasons["violation_is_operational"].astype(int) == 1]
    df_grouped = (
        df_reasons.groupby([time_aggregation, "violation_category"])[
            [police_action.sql_column]
        ]
        .sum()
        .reset_index()
    )
    df_grouped["x_label"] = (
        df_grouped["quarter"].apply(Quarter.year_quarter_to_year_season)
        if time_aggregation == "quarter"
        else df_grouped["year"]
    )
    fig = px.bar(
        df_grouped.sort_values(police_action.sql_column, ascending=False),
        x="x_label",
        y=police_action.sql_column,
        title=f"Number of PPD {police_action.noun.title()} in {geo_level_str} from {geo_filter.get_date_range_str(time_aggregation)}",
        color="violation_category",
        labels={
            police_action.sql_column: "Number of Traffic Stops",
            "x_label": "Quarter" if time_aggregation == "quarter" else "Year",
        },
    )
    for trace in fig.data:
        trace.hovertemplate = "%{x}<br>%{y:,} " + police_action.noun

    return endpoint.output(
        fig_barplot=fig,
        data={},
    )
