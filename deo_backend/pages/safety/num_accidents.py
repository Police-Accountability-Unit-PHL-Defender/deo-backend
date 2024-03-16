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
from models import before_deo_filter, after_deo_filter
from models import PoliceActionName
from models import QuarterHow
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
        "How often did Philadelphia police make traffic stops on High Injury Network (HIN) roads in "
    ),
    location_dropdown(f"{prefix}-location"),
    html.Span(" by "),
    TimeAggregationChoice.dropdown(id=f"{prefix}-time-aggregation"),
    html.Span("?"),
    dcc.Graph(id=f"{prefix}-result-graph"),
    html.Span(
        "Driving Equality came into effect on March 3, 2022. In the year after Driving Equality, "
    ),
    html.Span(id=f"{prefix}-result-text"),
    html.Span(
        " compared to 2021 (see What is Driving Equality? to learn more about these date comparisons). However, in 2023, most traffic stops by the Philadelphia police still did not happen on the HIN."
    ),
]


@callback(
    [
        Output(f"{prefix}-result-text", "children"),
        Output(f"{prefix}-result-graph", "figure"),
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
    geo_filter = FilteredDf(location=location)
    geo_level_str = geo_filter.geography.string
    df_geo_all_time = geo_filter.df

    # Graph2
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

    def _get_value_and_pct(start_date, end_date):
        value = (
            FilteredDf(location=location, start_date=start_date, end_date=end_date)
            .df["n_stopped_locatable_on_hin"]
            .mean()
        )
        value_stop = (
            FilteredDf(location=location, start_date=start_date, end_date=end_date)
            .df["n_stopped_locatable"]
            .mean()
        )
        pct = value / value_stop * 100
        return value, pct

    df_grouped = (
        df_geo_all_time.groupby(time_aggregation)[
            ["n_stopped_locatable", "n_stopped_locatable_on_hin"]
        ]
        .sum()
        .reset_index()
    )
    df_grouped["pct_in_hin"] = (
        100
        * df_grouped["n_stopped_locatable_on_hin"]
        / df_grouped["n_stopped_locatable"]
    ).round(1)
    fig1 = px.bar(
        df_grouped,
        x=time_aggregation,
        y="pct_in_hin",
        title=f"Percent of PPD Traffic Stops on the HIN in {geo_level_str} from {geo_filter.get_date_range_str(time_aggregation)}",
        labels={
            "pct_in_hin": "Percentage (%)",
            time_aggregation: "Quarter" if time_aggregation == "quarter" else "Year",
        },
    )
    for trace in fig1.data:
        trace.hovertemplate = "%{x}<br>%{y:}% of traffic stops on HIN"

    # Comparing Before vs After DEO
    before_deo_ratio_on_hin = (
        before_deo_filter.df["n_stopped_locatable_on_hin"].sum()
        / before_deo_filter.df["n_stopped_locatable"].sum()
    )
    after_deo_ratio_on_hin = (
        after_deo_filter.df["n_stopped_locatable_on_hin"].sum()
        / after_deo_filter.df["n_stopped_locatable"].sum()
    )
    pct_increase_on_hin_with_deo = (
        100
        * (after_deo_ratio_on_hin - before_deo_ratio_on_hin)
        / before_deo_ratio_on_hin
    ).round(1)
    return endpoint.output(
        text_sentence1=f"""
        the proportion of traffic stops Philadelphia police made along the HIN increased by {pct_increase_on_hin_with_deo}%
        """,
        fig_barplot=fig1,
    )
