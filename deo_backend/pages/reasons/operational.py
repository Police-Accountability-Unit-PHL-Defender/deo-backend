from dash import Dash, html, dcc, callback, Output, Input
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import VIOLATION_CATEGORIES_OPERATIONAL
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
from models import DemographicCategory
from models import DfType
from models import DEO_YEARS
from models import FilteredDf
from models import MOST_RECENT_YEAR
from models import Quarter
from dash_helpers import TimeAggregationChoice, deo_year_dropdown
from fastapi import APIRouter, Query
from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[0].replace("_", "-") + "-" + prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Div(
        "How often do Philadelphia police stop drivers for operational violations? Are there racial disparities in these traffic stops?"
    ),
    html.Span(
        "When Philadelphia police gave a reason, how often did police stop people of different races for operational violations in "
    ),
    dcc.Dropdown(
        placeholder="year",
        options=[{"label": v, "value": v} for v in DEO_YEARS]
        + [{"label": "all years", "value": 0}],
        value=None,
        id=f"{prefix}-year",
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
    ],
)
@router.get(API_URL)
def api_func(
    year: Annotated[
        int | None, Query(description="year, or null if combining all years", ge=2021)
    ] = None,
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    demographic_category = DemographicCategory.race
    police_action = PoliceAction.stop.value
    breakpoint()
    if year:
        geo_filtered = FilteredDf(
            start_date=datetime(year, 1, 1),
            end_date=datetime(year, 12, 31),
            df_type=DfType.stops_by_reason,
        )
    else:
        geo_filtered = FilteredDf(
            start_date=datetime(2021, 1, 1),
            end_date=datetime(MOST_RECENT_YEAR, 12, 31),
            df_type=DfType.stops_by_reason,
        )
    df_filtered = geo_filtered.df
    df_percent_action_by_demo = (
        df_filtered.groupby([demographic_category, "violation_category"])[
            [
                police_action.sql_column,
            ]
        ]
        .sum()
        .reset_index()
    )
    df_percent_action_by_demo_pct = (
        (
            df_percent_action_by_demo[
                df_percent_action_by_demo["violation_category"].isin(
                    VIOLATION_CATEGORIES_OPERATIONAL
                )
            ]
            .groupby(demographic_category)[police_action.sql_column]
            .sum()
            / df_percent_action_by_demo.groupby(demographic_category)[
                police_action.sql_column
            ].sum()
            * 100
        )
        .round(1)
        .to_frame("pct_operational")
        .reset_index()
    )

    df_percent_action_by_demo_pct[demographic_category] = pd.Categorical(
        df_percent_action_by_demo_pct[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )
    fig = px.bar(
        df_percent_action_by_demo_pct.sort_values(demographic_category),
        x=demographic_category.value,
        title=f"Percentage of Operational Stops by Race in {year}",
        labels={"pct_operational": "Percentage (%)"},
        y="pct_operational",
    )
    for trace in fig.data:
        trace.hovertemplate = (
            "%{x}<br>%{y:}% of traffic stops for operational violations<extra></extra>"
        )

    return endpoint.output(
        fig_barplot=fig,
        data={},
    )
