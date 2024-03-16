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
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import Quarter
from fastapi_models import Endpoint, location_annotation
from dash_helpers import (
    location_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
import os

from fastapi import APIRouter, Query
from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Span(
        "How have Philadelphia police changed the way they intrude during traffic stops in "
    ),
    location_dropdown(f"{prefix}-location"),
    html.Span(" by "),
    TimeAggregationChoice.dropdown(id=f"{prefix}-time-aggregation"),
    html.Span("? How do frisks and searches compare over time?"),
    dcc.Graph(id=f"{prefix}-graph"),
]


@callback(
    [
        Output(f"{prefix}-graph", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-time-aggregation", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    location: location_annotation = "*",
    time_aggregation: Annotated[
        TimeAggregationChoice, Query(description="Time Aggregation")
    ] = "year",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    police_action = PoliceAction.intrusion.value
    geo_filter = FilteredDf(location=location)
    geo_level_str = geo_filter.geography.string
    df_geo_all_time = geo_filter.df
    df_geo_total_all_time = (
        df_geo_all_time.groupby(
            [
                "districtoccur",
                "psa",
                "year",
                "quarter_dt",
                "quarter",
                "q_str",
            ]
        )[[a.value.sql_column for a in PoliceAction]]
        .sum()
        .reset_index()
    )
    df_grouped = (
        df_geo_all_time.groupby(time_aggregation)[
            ["n_frisked", "n_searched", "n_stopped"]
        ]
        .sum()
        .reset_index()
    )
    df_melted = pd.melt(
        df_grouped.rename(
            columns={"n_frisked": "# of frisks", "n_searched": "# of searches"}
        ),
        id_vars=[time_aggregation],
        value_vars=["# of searches", "# of frisks"],
        var_name="group",
        value_name="total_count",
    )
    df_melted["x_label"] = (
        df_melted["quarter"].apply(Quarter.year_quarter_to_year_season)
        if time_aggregation == "quarter"
        else df_melted["year"]
    )
    df_melted = df_melted.set_index(time_aggregation).join(
        df_grouped.set_index(time_aggregation)
    )
    df_melted["search_rate"] = (
        100 * df_melted["n_searched"] / df_melted["n_stopped"]
    ).round(1)
    df_melted["frisk_rate"] = (
        100 * df_melted["n_frisked"] / df_melted["n_stopped"]
    ).round(1)

    df_melted[" "] = df_melted["group"]
    fig = px.bar(
        df_melted,
        x="x_label",
        y="total_count",
        labels={
            "total_count": "Number of Searches or Frisks",
            "x_label": "Quarter" if time_aggregation == "quarter" else "Year",
        },
        title=f"Number of Searches and Frisks During PPD Traffic Stops in {geo_level_str} from {geo_filter.get_date_range_str(time_aggregation)}",
        barmode="group",
        hover_data=["frisk_rate", "search_rate"],
        color=" ",
    )
    for trace in fig.data:
        if trace["legendgroup"] == "# of frisks":
            trace.hovertemplate = (
                "%{x}<br>%{y:,} frisks<br>%{customdata[0]}% frisk rate<extra></extra>"
            )
        if trace["legendgroup"] == "# of searches":
            trace.hovertemplate = "%{x}<br>%{y:,} searches<br>%{customdata[1]}% search rate<extra></extra>"

    return endpoint.output(
        fig_barplot=fig,
    )
