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
    qyear_dropdown,
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
        "How many traffic stops did Philadelphia police make in ",
    ),
    location_dropdown(f"{prefix}-location"),
    html.Span(" by "),
    TimeAggregationChoice.dropdown(id=f"{prefix}-time-aggregation"),
    html.Span("?"),
    html.Br(),
    html.Br(),
    html.Div(id=f"{prefix}-result-text1"),
    dcc.Graph(id=f"{prefix}-graph1"),
    html.Div(id=f"{prefix}-result-text2"),
]


@callback(
    [
        Output(f"{prefix}-result-text1", "children"),
        Output(f"{prefix}-result-text2", "children"),
        Output(f"{prefix}-graph1", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-time-aggregation", "value"),
        Input(f"{prefix}-location", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    time_aggregation: Annotated[
        TimeAggregationChoice, Query(description="Time Aggregation")
    ] = "year",
    location: location_annotation = "*",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(location=location)
    df_geo_all_time = geo_filter.df
    geo_level_str = geo_filter.geography.string

    # Graph2
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

    value_2014_to_2018 = FilteredDf(
        location=location, start_date="2014-Q1", end_date="2018-Q4"
    ).get_avg_monthly_value(police_action)

    value_2019_surge = FilteredDf(
        location=location, start_date="2019-Q1", end_date="2019-Q4"
    ).get_avg_monthly_value(police_action)

    value_covid = FilteredDf(
        location=location, start_date="2020-Q2", end_date="2021-Q1"
    ).get_avg_monthly_value(police_action)

    num_total = df_geo_total_all_time[police_action.sql_column].sum()
    df_grouped = (
        df_geo_all_time.groupby(time_aggregation)[[police_action.sql_column]]
        .sum()
        .reset_index()
    )
    df_grouped["x_label"] = (
        df_grouped["quarter"].apply(Quarter.year_quarter_to_year_season)
        if time_aggregation == "quarter"
        else df_grouped["year"]
    )

    fig1 = px.bar(
        df_grouped,
        x="x_label",
        y=police_action.sql_column,
        title=f"Number of PPD {police_action.noun.title()} in {geo_level_str} from {geo_filter.get_date_range_str(time_aggregation)}",
        labels={
            police_action.sql_column: "Number of Traffic Stops",
            "x_label": "Quarter" if time_aggregation == "quarter" else "Year",
        },
    )
    for trace in fig1.data:
        trace.hovertemplate = "%{x}<br>%{y:,} " + police_action.noun

    full_data_sentence = f"From {geo_filter.get_date_range_str_long(time_aggregation)}, Philadelphia police made a total of <span>{num_total:,}</span> {police_action.noun} in {geo_level_str}."
    data_over_time_sentences = f"""
    In {geo_level_str}:

    From the start of 2014 through the end of 2018, Philadelphia police made an average of <span>{value_2014_to_2018:,}</span> {police_action.noun} per month.

    During a surge in traffic stops in 2019, Philadelphia police made an average of <span>{value_2019_surge:,}</span> traffic stops per month.

    From the start of April 2020 through the end of March 2021 (pandemic), Philadelphia police made an average of <span>{value_covid:,}</span> {police_action.noun} per month.
        """

    return endpoint.output(
        text_full_data_sentence=full_data_sentence,
        text_data_over_time_sentences=data_over_time_sentences,
        fig_barplot=fig1,
    )
