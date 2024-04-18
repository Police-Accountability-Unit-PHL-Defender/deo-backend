from dash import Dash, html, dcc, callback, Output, Input
from models import english_comma_separated
from models import QuarterHow
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
from demographics.constants import (
    DEMOGRAPHICS_DISTRICT,
)
from models import AgeGroup
from models import DemographicCategory
from models import PoliceActionName
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING, FIRST_QUARTER
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
    html.Span("How does traffic enforcement compare in different districts? How many "),
    police_action_dropdown(f"{prefix}-action", word_type=ActionWordType.noun),
    html.Span(" did Philadelphia police make from the start of quarter"),
    qyear_dropdown(
        f"{prefix}-start-qyear", how=QuarterHow.start, default=FIRST_QUARTER
    ),
    html.Span(" through the end of "),
    qyear_dropdown(
        f"{prefix}-end-qyear", how=QuarterHow.end, default=MOST_RECENT_QUARTER
    ),
    html.Span(" in these districts: "),
    dcc.Dropdown(
        placeholder="location",
        options=[
            {"label": f"District {val}", "value": val}
            for val in DEMOGRAPHICS_DISTRICT.index
        ],
        value=["12", "05"],
        id=f"{prefix}-compare-districts",
        multi=True,
        style={"display": "inline-block", "width": "400px"},
    ),
    dcc.Graph(id=f"{prefix}-graph"),
]


@callback(
    Output(f"{prefix}-graph", "figure"),
    Output(f"{prefix}-result-api", "href"),
    [
        Input(f"{prefix}-action", "value"),
        Input(f"{prefix}-compare-districts", "value"),
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    police_action: Annotated[PoliceActionName, Query(description="Police Action")],
    districts: Annotated[
        list[str], Query(description="A set of districts to compare to each other")
    ],
    start_qyear: quarter_annotation = FIRST_QUARTER,
    end_qyear: quarter_annotation = MOST_RECENT_QUARTER,
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    police_action = PoliceAction.from_value(police_action)
    district_bars = []

    for district in districts:
        geo_filter = FilteredDf(
            start_date=start_qyear, end_date=end_qyear, location=district
        )
        district_bars.append(
            {
                "District": geo_filter.geography.string,
                police_action.noun: geo_filter.df[police_action.sql_column].sum(),
            }
        )

    districts_string = english_comma_separated([d["District"][9:] for d in district_bars])
    fig = px.bar(
        pd.DataFrame(district_bars),
        x="District",
        y=police_action.noun,
        title=f"Number of {police_action.noun.title()} in Districts {districts_string} from {geo_filter.get_date_range_str(TimeAggregation.quarter)}",
        labels={
            police_action.noun: f"Number of {police_action.noun.title()}",
        },
    )
    for trace in fig.data:
        trace.hovertemplate = "%{x}<br>%{y:,} " + police_action.noun
    return endpoint.output(
        fig_barplot=fig,
    )
