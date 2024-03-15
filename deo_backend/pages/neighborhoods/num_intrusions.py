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
        "How many times did Philadelphia police intrude during traffic stops in ",
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
        Output(f"{prefix}-graph1", "figure"),
        Output(f"{prefix}-result-text2", "children"),
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

    def _value_action_pct(start_date, end_date, value_column=police_action.sql_column):
        this_geo_filter = FilteredDf(
            location=location, start_date=start_date, end_date=end_date
        )
        value = this_geo_filter.df[value_column].sum() / this_geo_filter.quarters.num
        value_stop = (
            this_geo_filter.df[PoliceAction.stop.value.sql_column].sum()
            / this_geo_filter.quarters.num
        )
        pct_value = value / value_stop * 100
        return (
            int(np.round(value / 3)),
            int(np.round(value_stop / 3)),
            np.round(pct_value, 1),
        )

    value_2014_to_2018, value_stop_2014_to_2018, pct_2014_to_2018 = _value_action_pct(
        start_date="2014-01-01", end_date="2018-12-31"
    )
    value_2019_surge, value_stop_2019_surge, pct_2019_surge = _value_action_pct(
        start_date="2019-01-01", end_date="2019-12-31"
    )
    value_covid, value_stop_covid, pct_covid = _value_action_pct(
        start_date="2020-03-01", end_date="2021-02-28"
    )
    df_grouped = (
        df_geo_all_time.groupby(time_aggregation)[
            [col for col in df_geo_all_time.columns if col.startswith("n_")]
        ]
        .sum()
        .reset_index()
    )
    df_grouped["intrusion_rate"] = (
        df_grouped["n_intruded"] / df_grouped["n_stopped"] * 100
    ).round(1)

    df_grouped["x_label"] = (
        df_grouped["quarter"].apply(Quarter.year_quarter_to_year_season)
        if time_aggregation == "quarter"
        else df_grouped["year"]
    )

    fig = px.bar(
        df_grouped,
        x="x_label",
        y=police_action.sql_column,
        labels={
            police_action.sql_column: "Number of Intrusions",
            "x_label": "Quarter" if time_aggregation == "quarter" else "Year",
        },
        hover_data=["intrusion_rate"],
        title=f"Number of Intrusions During PPD Traffic Stops in {geo_level_str} from {geo_filter.get_date_range_str(time_aggregation)}",
    )
    for trace in fig.data:
        trace.hovertemplate = (
            "%{x}<br>%{y:,} intrusions<br>%{customdata[0]}% intrusion rate"
        )

    num_total = df_geo_total_all_time[police_action.sql_column].sum()
    pct_total = (
        100
        * df_geo_total_all_time[police_action.sql_column].sum()
        / df_geo_total_all_time[PoliceAction.stop.value.sql_column].sum()
    ).round(1)

    return endpoint.output(
        text_full_data=f"From {geo_filter.get_date_range_str_long(time_aggregation)}, <span>{pct_total}%</span> of traffic stops involved an {police_action.single_noun}, and Philadelphia police made a total of <span>{num_total:,}</span> {police_action.noun}.",
        fig_barplot=fig,
        text_data_over_time=f"""
            From the start of 2014 through the end of 2018, <span>{pct_2014_to_2018}%</span> of traffic stops involved an {police_action.single_noun}, and Philadelphia police made an average of <span>{value_2014_to_2018:,}</span> {police_action.noun} per month.

            During a surge in stops in 2019, <span>{pct_2019_surge}%</span> of traffic stops involved an {police_action.single_noun}, and Philadelphia police made an average of <span>{value_2019_surge:,}</span> {police_action.noun} per month.

            From the start of April 2020 through the end of March 2021 (pandemic), <span>{pct_covid}%</span> of traffic stops involved an {police_action.single_noun}, and Philadelphia police made an average of <span>{value_covid:,}</span> {police_action.noun} per month.""",
    )
