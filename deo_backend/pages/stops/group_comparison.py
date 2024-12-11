from dash import Dash, html, dcc, callback, Output, Input
from models import TimeAggregation
from typing import Annotated
from fastapi import APIRouter, Query
from models import (
    QUARTERS,
    MOST_RECENT_QUARTER,
    SEASON_QUARTER_MAPPING,
    FOUR_QUARTERS_AGO,
)
from models import QuarterHow
from models import PoliceAction
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
)
from models import Quarter
import plotly.express as px
from models import FilteredDf
import pandas as pd
from routers import ROUTERS
from fastapi_models import Endpoint, location_annotation, quarter_annotation

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]

LAYOUT = [
    html.Hr(),
    html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api"),
    html.Div(
        [
            html.Span(
                "How many times did Philadelphia police stop one demographic group compared to another in "
            ),
            location_dropdown(f"{prefix}-location"),
            html.Span(" from the start of quarter "),
            qyear_dropdown(f"{prefix}-start-qyear", default=FOUR_QUARTERS_AGO),
            html.Span(" through the end of "),
            qyear_dropdown(
                f"{prefix}-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
            ),
            html.Span("? Select two demographic groups and compare:"),
        ]
    ),
    html.Div(
        [
            html.Span("GROUP 1"),
            html.Div("Age Range(s): "),
            dcc.Dropdown(
                [e.value for e in AgeGroup],
                placeholder="actions",
                id=f"{prefix}-age-group-noun-1",
                multi=True,
                value=["25-34"],
                style={"display": "inline-block", "width": "400px"},
            ),
            html.Div(" Gender(s): "),
            dcc.Dropdown(
                [e.value for e in GenderGroup],
                placeholder="actions",
                id=f"{prefix}-gender-group-noun-1",
                multi=True,
                value=["Male"],
                style={"display": "inline-block", "width": "150px"},
            ),
            html.Div(" Race(s): "),
            dcc.Dropdown(
                [e.value for e in RacialGroup],
                placeholder="actions",
                id=f"{prefix}-racial-group-noun-1",
                multi=True,
                value=["Black"],
                style={"display": "inline-block", "width": "400px"},
            ),
        ]
    ),
    html.Div(
        [
            html.Span("GROUP 2"),
            html.Div("Age Range(s): "),
            dcc.Dropdown(
                [e.value for e in AgeGroup],
                placeholder="actions",
                id=f"{prefix}-age-group-noun-2",
                multi=True,
                value=["25-34"],
                style={"display": "inline-block", "width": "400px"},
            ),
            html.Div(" Gender(s): "),
            dcc.Dropdown(
                [e.value for e in GenderGroup],
                placeholder="actions",
                id=f"{prefix}-gender-group-noun-2",
                multi=True,
                value=["Male"],
                style={"display": "inline-block", "width": "150px"},
            ),
            html.Div(" Race(s): "),
            dcc.Dropdown(
                [e.value for e in RacialGroup],
                placeholder="actions",
                id=f"{prefix}-racial-group-noun-2",
                multi=True,
                value=["White"],
                style={"display": "inline-block", "width": "400px"},
            ),
        ]
    ),
    dcc.Graph(id=f"{prefix}-graph"),
]


@callback(
    [
        Output(f"{prefix}-graph", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-age-group-noun-1", "value"),
        Input(f"{prefix}-gender-group-noun-1", "value"),
        Input(f"{prefix}-racial-group-noun-1", "value"),
        Input(f"{prefix}-age-group-noun-2", "value"),
        Input(f"{prefix}-gender-group-noun-2", "value"),
        Input(f"{prefix}-racial-group-noun-2", "value"),
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
    ],
)
@router.get(API_URL)
def q2_groups(
    age_group1: Annotated[
        list[AgeGroup],
        Query(
            description="Age groups",
        ),
    ],
    gender_group1: Annotated[
        list[GenderGroup],
        Query(
            description="Genders",
        ),
    ],
    racial_group1: Annotated[
        list[RacialGroup],
        Query(
            description="Racial groups",
        ),
    ],
    age_group2: Annotated[
        list[AgeGroup],
        Query(
            description="Age groups",
        ),
    ],
    gender_group2: Annotated[
        list[GenderGroup],
        Query(
            description="Genders",
        ),
    ],
    racial_group2: Annotated[
        list[RacialGroup],
        Query(
            description="Racial groups",
        ),
    ],
    location: location_annotation = "*",
    start_qyear: quarter_annotation = FOUR_QUARTERS_AGO,
    end_qyear: quarter_annotation = MOST_RECENT_QUARTER,
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(
        location=location, start_date=start_qyear, end_date=end_qyear
    )
    df_geo = geo_filter.df

    ## Comparing specific demographic groups
    df_group1 = df_geo.copy().loc[
        (
            (df_geo[DemographicCategory.age_range.value].isin(age_group1))
            & (df_geo[DemographicCategory.gender.value].isin(gender_group1))
            & (df_geo[DemographicCategory.race.value].isin(racial_group1))
        )
    ]
    df_group1["group"] = "Group 1"
    df_group2 = df_geo.copy().loc[
        (
            (df_geo[DemographicCategory.age_range.value].isin(age_group2))
            & (df_geo[DemographicCategory.gender.value].isin(gender_group2))
            & (df_geo[DemographicCategory.race.value].isin(racial_group2))
        )
    ]
    df_group2["group"] = "Group 2"
    df_groups = (
        pd.concat([df_group1, df_group2])
        .groupby(["group", "quarter"])
        .sum(numeric_only=True)
        .reset_index()
    )
    df_groups["season"] = df_groups["quarter"].apply(
        Quarter.year_quarter_to_year_season
    )
    fig = px.bar(
        df_groups,
        title=f"Number of PPD {police_action.noun.title()} in {geo_filter.geography.string}, Comparing Group 1 to Group 2, from {geo_filter.get_date_range_str(TimeAggregation.quarter)}",
        x="season",
        y=police_action.sql_column,
        labels={
            police_action.sql_column: f"Number of {police_action.noun.title()}",
            "season": "Quarter",
        },
        barmode="group",
        color="group",
        hover_data=["group"],
    )
    for trace in fig.data:
        trace.hovertemplate = (
            "%{x}<br>%{customdata[0]}<br>%{y:,} "
            + police_action.noun
            + "<extra></extra>"
        )
    fig.update_traces(showlegend=False)

    return endpoint.output(fig_barplot=fig)
