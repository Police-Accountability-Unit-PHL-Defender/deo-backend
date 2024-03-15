from dash import Dash, html, dcc, callback, Output, Input
import uuid
from typing import Literal
from typing import Annotated
import fastapi
import dash_ag_grid as dag
from datetime import date
from datetime import timedelta
from datetime import datetime
import numpy as np
import plotly.express as px
import pandas as pd
import sqlite3

from models import PoliceAction
from models import PoliceActionName
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import Quarter
from models import QuarterHow
from demographics.constants import (
    DEMOGRAPHICS_DISTRICT,
)
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    police_action_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
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
        "Is traffic enforcement different in districts where most residents are white, compared to districts where most residents are people of color?  Comparing majority white districts to majority non-white districts, how many "
    ),
    police_action_dropdown(f"{prefix}-action-noun", word_type=ActionWordType.noun),
    html.Span("did Philadelphia police make from the start of "),
    qyear_dropdown(f"{prefix}-start-qyear", default="2023-Q1"),
    html.Span(" through the end of "),
    qyear_dropdown(
        f"{prefix}-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
    ),
    html.Span(
        "? During this time period, what was the intrusion rate and contraband hit rate across districts?"
    ),
    dcc.Graph(id=f"{prefix}-graph1"),
    dcc.Graph(id=f"{prefix}-graph2"),
    dcc.Graph(id=f"{prefix}-graph3"),
]


@callback(
    Output(f"{prefix}-graph1", "figure"),
    Output(f"{prefix}-graph2", "figure"),
    Output(f"{prefix}-graph3", "figure"),
    Output(f"{prefix}-result-api", "href"),
    [
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
        Input(f"{prefix}-action-noun", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    start_qyear: quarter_annotation,
    end_qyear: quarter_annotation,
    police_action: Annotated[PoliceActionName, Query(description="Police Action")],
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    geo_filtered = FilteredDf(start_date=start_qyear, end_date=end_qyear)
    df_filtered = geo_filtered.df
    police_action = PoliceAction.from_value(police_action)

    whiteness_of_districts = (
        (DEMOGRAPHICS_DISTRICT["white"] / DEMOGRAPHICS_DISTRICT["total"]).sort_values()
        * 100
    ).round(1)
    df_grouped = df_filtered.groupby("districtoccur")[
        [col for col in df_filtered.columns if col.startswith("n_")]
    ].sum()
    df_grouped = df_grouped[
        df_grouped.index != "77"
    ]  # District 77 is airport, has no residents

    df_grouped = (
        (df_grouped.join(whiteness_of_districts.to_frame("whiteness")).reset_index())
        .dropna()
        .sort_values("whiteness")
        .reset_index()
    )
    df_grouped["n_people"] = df_grouped["districtoccur"].apply(
        lambda x: DEMOGRAPHICS_DISTRICT.loc[x].total
    )
    df_grouped["intrusion_rate"] = (
        df_grouped["n_intruded"] / df_grouped["n_stopped"] * 100
    ).round(1)
    df_grouped["intrusion_miss_rate"] = (
        (df_grouped["n_intruded"] - df_grouped["n_contraband"])
        / df_grouped["n_intruded"]
        * 100
    ).round(1)
    df_grouped["contraband_hit_rate"] = (
        df_grouped["n_contraband"] / df_grouped["n_intruded"] * 100
    ).round(1)

    def _get_bar_fig(column, title="", labels={}, hovertemplate_suffix=""):
        labels[
            "districtoccur"
        ] = "Majority Non-White Districts → Majority White Districts"

        fig = px.bar(
            df_grouped.sort_values("whiteness"),
            x="districtoccur",
            y=column,
            title=title,
            labels=labels,
            hover_data=["whiteness", "n_intruded"],
        )
        for trace in fig.data:
            trace.hovertemplate = (
                "District %{x}<br>%{customdata[0]}% of residents are white<br>"
                + hovertemplate_suffix
            )

        trendline = px.scatter(
            df_grouped.sort_values("whiteness"),
            x="whiteness",
            y=column,
            trendline="ols",
        )
        trendline_data = trendline.data[1]
        trendline_data.x = df_grouped.districtoccur.values
        trendline_data.y = np.maximum(trendline_data.y, 0)
        trendline_data.hovertemplate = None
        fig.add_trace(trendline_data)

        return fig

    fig = _get_bar_fig(
        f"{police_action.sql_column}",
        title=f"Number of {police_action.noun.title()} in Majority Non-White Districts vs. Majority White Districts from {geo_filtered.date_range_str}",
        labels={
            police_action.sql_column: f"Number of {police_action.noun.title()}",
        },
        hovertemplate_suffix="%{y:,} " + police_action.noun,
    )
    fig2 = _get_bar_fig(
        "intrusion_rate",
        title=f"PPD Intrusion Rate During Traffic Stops in Majority Non-White Districts vs. Majority White Districts from {geo_filtered.date_range_str}",
        labels={"intrusion_rate": "Intrusion Rate"},
        hovertemplate_suffix="%{customdata[1]:,} intrusions<br>%{y}% intrusion rate",
    )
    fig3 = _get_bar_fig(
        "contraband_hit_rate",
        title=f"Contraband Hit Rate in Majority Non-White Districts vs. Majority White Districts from {geo_filtered.date_range_str}",
        labels={"contraband_hit_rate": "Contraband Hit Rate"},
        hovertemplate_suffix="%{y}% contraband hit rate",
    )
    return endpoint.output(fig_barplot=fig, fig_barplot2=fig2, fig_barplot3=fig3)
