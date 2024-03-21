from dash import Dash, html, dcc, callback, Output, Input
from models import DEO_YEARS
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
    MAJORITY_WHITE_DISTRICTS,
    MAJORITY_NONWHITE_DISTRICTS,
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
    deo_year_dropdown,
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
    html.Div(
        "Do Philadelphia police make traffic stops for different reasons in districts where most residents are white, compared to districts where most residents are people of color?"
    ),
    html.Span(
        "When Philadelphia police gave a reason, what were the primary reasons why police stopped drivers in majority "
    ),
    dcc.Dropdown(
        options=[
            {
                "label": "white districts, compared to majority non-white districts",
                "value": "White",
            },
            {
                "label": "non-white districts, compared to majority white districts",
                "value": "Non-white",
            },
        ],
        value="Non-white",
        id=f"{prefix}-race",
        style={"display": "inline-block", "width": "300px"},
    ),
    html.Span(" in Philadephia in "),
    deo_year_dropdown(f"{prefix}-year", default=2022),
    html.Span("?"),
    dcc.Graph(id=f"{prefix}-graph1"),
]


class DistrictType(str, Enum):
    majority_white = "Majority white"
    majority_nonwhite = "Majority non-white"


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
    year: Annotated[int, Query(description="year", alias="year")] = 2022,
    race: Annotated[
        Literal["Non-white", "White"], Query(description="race")
    ] = "Non-white",
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())

    df_reasons = FilteredDf(
        start_date=datetime(year, 1, 1),
        end_date=datetime(year, 12, 31),
        df_type=DfType.stops_by_reason,
    ).df
    df_reasons = df_reasons[~df_reasons["violation_category"].isin(["Other", "None"])]

    race_ascending_sort_bool = race != "White"
    title = (
        f"Primary Reasons PPD Stopped Drivers in Majority Non-White Districts, Compared to Majority White Districts, in {year}"
        if race == "Non-white"
        else f"Primary Reasons PPD Stopped Drivers in Majority White Districts, Compared to Majority Non-White Districts, in {year}"
    )

    df_reasons_grouped = (
        df_reasons.groupby(["Race", "violation_category"])["n_stopped"]
        .sum()
        .reset_index()
    )

    df_reasons.loc[
        df_reasons[df_reasons["districtoccur"].isin(MAJORITY_WHITE_DISTRICTS)].index,
        "majority_district",
    ] = DistrictType.majority_white.value
    df_reasons.loc[
        df_reasons[df_reasons["districtoccur"].isin(MAJORITY_NONWHITE_DISTRICTS)].index,
        "majority_district",
    ] = DistrictType.majority_nonwhite.value

    df_reasons_grouped_neighborhood = (
        df_reasons.groupby(["violation_category", "majority_district"])["n_stopped"]
        .sum()
        .reset_index()
    )
    col = "majority_district"
    df_filt = df_reasons_grouped_neighborhood.sort_values(
        [col, "n_stopped"], ascending=[race_ascending_sort_bool, False]
    )
    total_stops = df_filt.groupby(col)["n_stopped"].sum().to_dict()
    df_filt["pct_stopped"] = (
        100 * df_filt.apply(lambda x: x["n_stopped"] / total_stops[x[col]], axis=1)
    ).round(1)
    df_filt["col_str"] = df_filt[col] + " districts"
    fig = px.bar(
        df_filt,
        x="violation_category",
        y="pct_stopped",
        barmode="group",
        color="col_str",
        color_discrete_map={
            f"{DistrictType.majority_white.value} districts": "Red",
            f"{DistrictType.majority_nonwhite.value} districts": "Blue",
        },
        title=title,
        hover_data=["n_stopped"],
        labels={
            "pct_stopped": "Percentage (%)",
            "violation_category": "Primary Reason for Traffic Stop",
        },
    )
    for trace in fig.data:
        if trace["legendgroup"] == f"{DistrictType.majority_nonwhite.value} districts":
            trace.hovertemplate = (
                DistrictType.majority_nonwhite.value
                + " districts<br>%{x}<br>%{y:.01f}% of traffic stops<br>%{customdata[0]:,} traffic stops<extra></extra>"
            )
        elif trace["legendgroup"] == f"{DistrictType.majority_white.value} districts":
            trace.hovertemplate = (
                DistrictType.majority_white.value
                + " districts<br>%{x}<br>%{y:.01f}% of traffic stops<br>%{customdata[0]:,} traffic stops<extra></extra>"
            )

    return endpoint.output(
        fig_barplot=fig,
        data={},
    )
