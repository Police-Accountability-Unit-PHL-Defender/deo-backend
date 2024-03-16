from dash import Dash, html, dcc, callback, Output, Input, no_update
from models import QuarterHow
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
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING, FIRST_QUARTER
from models import Quarter
from fastapi_models import Endpoint, location_annotation, quarter_annotation
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
prefix = prefixes[0].replace("_", "-") + "-" + prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Div(
        "Do Philadelphia police intrude upon some drivers and/or their vehicles more often than others?"
    ),
    html.Div(
        [
            html.Span("Show data by "),
            demographic_dropdown(f"{prefix}-demographic-category"),
            html.Span(" in "),
            location_dropdown(f"{prefix}-location"),
            html.Span(" from the start of quarter"),
            qyear_dropdown(
                f"{prefix}-start-qyear", default=FIRST_QUARTER, how=QuarterHow.start
            ),
            html.Span(" to the end of "),
            qyear_dropdown(
                f"{prefix}-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
            ),
            html.Span(", compared to a baseline of people who are "),
            dcc.Dropdown(
                options=[],
                id=f"{prefix}-default",
                style={"display": "inline-block", "width": "150px"},
            ),
            html.Span("."),
        ]
    ),
    dcc.Graph(id=f"{prefix}-graph"),
    html.Span(
        "How many times do Philadelphia police intrude during traffic stops without finding any contraband?"
    ),
    dcc.Graph(id=f"{prefix}-graph2"),
    html.Span(
        "When Philadelphia police intrude during traffic stops, how often do they find contraband?"
    ),
    dcc.Graph(id=f"{prefix}-graph3"),
    html.Div(id=f"{prefix}-text"),
]


@callback(
    [
        Output(f"{prefix}-default", "options"),
        Output(f"{prefix}-default", "value"),
    ],
    [
        Input(f"{prefix}-demographic-category", "value"),
    ],
)
def demo_dropdown_choice(demographic_category):
    match demographic_category:
        case DemographicCategory.race.value:
            return [
                [{"label": dc.value, "value": dc.value} for dc in RacialGroup],
                DemographicCategory.race.default_value,
            ]
        case DemographicCategory.gender.value:
            return [
                [{"label": dc.value, "value": dc.value} for dc in GenderGroup],
                DemographicCategory.gender.default_value,
            ]
        case DemographicCategory.age_range.value:
            return [
                [{"label": dc.value, "value": dc.value} for dc in AgeGroup],
                DemographicCategory.age_range.default_value,
            ]


@callback(
    [
        Output(f"{prefix}-graph", "figure"),
        Output(f"{prefix}-text", "children"),
        Output(f"{prefix}-graph2", "figure"),
        Output(f"{prefix}-graph3", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-demographic-category", "value"),
        Input(f"{prefix}-default", "value"),
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    demographic_category: Annotated[
        DemographicCategory, Query(description="Demographic Category")
    ],
    demographic_baseline: Annotated[
        str, Query(description="Demographic baseline value")
    ],
    location: location_annotation = "*",
    start_qyear: quarter_annotation = FIRST_QUARTER,
    end_qyear: quarter_annotation = MOST_RECENT_QUARTER,
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    demographic_category = DemographicCategory(demographic_category)
    geo_filtered = FilteredDf(
        location=location, start_date=start_qyear, end_date=end_qyear
    )
    df_filtered = geo_filtered.df
    police_action = PoliceAction.intrusion.value

    df_percent_action_by_demo = (
        (
            100
            * df_filtered.groupby(demographic_category)[police_action.sql_column].sum()
            / df_filtered.groupby(demographic_category)[
                PoliceAction.stop.value.sql_column
            ].sum()
        )
        .to_frame("percentage")
        .round(1)
    )
    if demographic_baseline not in df_percent_action_by_demo.index:
        return no_update

    baseline_percentage = df_percent_action_by_demo.loc[demographic_baseline].values[0]

    df_percent_action_by_demo = df_percent_action_by_demo.reset_index()

    # Calculate percentage difference from the average
    df_percent_action_by_demo["percentage_diff"] = (
        100
        * (df_percent_action_by_demo["percentage"] - baseline_percentage)
        / baseline_percentage
    )

    df_percent_action_by_demo["multiplier"] = (
        df_percent_action_by_demo["percentage"] / baseline_percentage
    )
    df_percent_action_by_demo[demographic_category] = pd.Categorical(
        df_percent_action_by_demo[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )
    df_percent_action_by_demo = df_percent_action_by_demo.sort_values(
        demographic_category
    )
    geo_level_str = geo_filtered.geography.string

    fig = px.bar(
        df_percent_action_by_demo,
        x=demographic_category.value,
        y="percentage",
        barmode="group",
        labels={
            "percentage": "Intrusion Rate (%)",
        },
        title=f"Intrusion Rates by {demographic_category} in {geo_level_str} from {geo_filtered.date_range_str}",
    )
    for trace in fig.data:
        trace.hovertemplate = "%{x}<br>%{y}% intrusion rate"

    # Add text above each bar to show the percentage difference from the average
    for index, row in df_percent_action_by_demo.reset_index().iterrows():
        val_text = f"{np.abs(row['multiplier']):.1f}x"
        if row[demographic_category] == demographic_baseline:
            text = "Baseline"
        else:
            text = f"{val_text} of Baseline"

        fig.add_annotation(
            text=text,
            x=index,
            y=row["percentage"],
            showarrow=False,
            xanchor="center",
            yanchor="bottom",
            font=dict(size=12),
            xref="x",
            yref="y",
        )

    # Create new one that is percent of contraband from the intrusions
    df_percent_action_by_demo = (
        df_filtered.groupby(demographic_category)[
            [
                "n_contraband",
                police_action.sql_column,
            ]
        ]
        .sum()
        .reset_index()
    )

    df_percent_action_by_demo["percentage"] = (
        100
        - (
            df_percent_action_by_demo["n_contraband"]
            / df_percent_action_by_demo[police_action.sql_column]
        )
        * 100
    )

    df_percent_action_by_demo[f"{police_action.sql_column}_no_contraband"] = (
        df_percent_action_by_demo[police_action.sql_column]
        - df_percent_action_by_demo["n_contraband"]
    )
    df_percent_action_by_demo[demographic_category] = pd.Categorical(
        df_percent_action_by_demo[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )
    fig2 = px.bar(
        df_percent_action_by_demo.sort_values(demographic_category),
        x=demographic_category.value,
        title=f"Intrusions Resulting in No Contraband by {demographic_category.value} in {geo_filtered.geography.string} from {geo_filtered.date_range_str}",
        labels={
            f"{police_action.sql_column}_no_contraband": f"Number of {police_action.noun.title()} without Contraband"
        },
        y=f"{police_action.sql_column}_no_contraband",
    )
    for trace in fig2.data:
        trace.hovertemplate = "%{x}<br>%{y:,} intrusions<br>"

    baseline_percentage = df_percent_action_by_demo[
        df_percent_action_by_demo[demographic_category] == demographic_baseline
    ][f"{police_action.sql_column}_no_contraband"].values[0]
    df_percent_action_by_demo["not_found_count_multiplier"] = (
        df_percent_action_by_demo[f"{police_action.sql_column}_no_contraband"]
    ) / (baseline_percentage)

    for i, row in df_percent_action_by_demo.sort_values(
        demographic_category
    ).iterrows():
        val_text = f"{np.abs(row['not_found_count_multiplier']):.2f}x"
        if row[demographic_category] == demographic_baseline:
            text = "Baseline"
        else:
            text = f"{val_text} of Baseline"
        fig2.add_annotation(
            x=row[demographic_category],
            y=row[f"{police_action.sql_column}_no_contraband"],
            text=text,
            showarrow=False,
            xanchor="center",
            yanchor="bottom",
            opacity=0.8,
        )

    fig2.update_layout(barmode="relative")  # Relative bar chart

    # Create the bar chart using Plotly Express
    # Calculate percentage difference from the average
    df_percent_action_by_demo["percentage_found"] = (
        100 - df_percent_action_by_demo["percentage"]
    ).round(1)

    baseline_percentage = df_percent_action_by_demo[
        df_percent_action_by_demo[demographic_category] == demographic_baseline
    ]["percentage_found"].values[0]
    df_percent_action_by_demo["found_multiplier"] = (
        df_percent_action_by_demo["percentage_found"]
    ) / (baseline_percentage)
    fig3 = px.bar(
        df_percent_action_by_demo.sort_values(demographic_category),
        x=demographic_category.value,
        y="percentage_found",
        labels={"percentage_found": "Contraband Hit Rate (%)"},
        title=f"Contraband Hit Rates by {demographic_category} in {geo_filtered.geography.string} from {geo_filtered.date_range_str}",
    )
    for trace in fig3.data:
        trace.hovertemplate = "%{x}<br>%{y:,}% contraband hit rate<br>"

    # Add text above each bar to show the percentage difference from the average
    for index, row in df_percent_action_by_demo.sort_values(
        demographic_category
    ).iterrows():
        val_text = f"{np.abs(row['found_multiplier']):.2f}x"
        if row[demographic_category] == demographic_baseline:
            text = "Baseline"
        else:
            text = f"{val_text} of Baseline"
        fig3.add_annotation(
            text=text,
            x=row[demographic_category],
            y=row["percentage_found"],
            showarrow=False,
            xanchor="center",
            yanchor="bottom",
            font=dict(size=12),
            xref="x",
            yref="y",
        )

    # Totals
    pct_not_found = (
        1
        - (
            df_filtered["n_contraband"].sum()
            / df_filtered[police_action.sql_column].sum()
        )
    ) * 100
    pct_rate = 100 * (
        df_filtered[police_action.sql_column].sum() / df_filtered["n_stopped"].sum()
    )
    return endpoint.output(
        fig_barplot=fig,
        text_markdown=f"""
            In {geo_filtered.date_range_str_long}:

            - When making traffic stops, Philadelphia police intruded upon <span>{pct_rate:.1f}%</span> of people and/or vehicles in {geo_filtered.geography.string} from {geo_filtered.date_range_str_long}.

            - During these intrusions, Philadelphia police did not find any contraband <span>{pct_not_found:.1f}%</span> of the time.
        """,
        fig_barplot2=fig2,
        fig_barplot3=fig3,
    )
