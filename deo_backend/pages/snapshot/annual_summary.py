from dash import Dash, html, dcc, callback, Output, Input
import numpy as np
from plotly.graph_objs import Figure
import uuid
from typing import Literal
from typing import Annotated
import fastapi
import dash_ag_grid as dag
from datetime import date
from pydantic import BaseModel
from datetime import timedelta
from datetime import datetime
import plotly.express as px
import pandas as pd
import sqlite3

from models import PoliceAction
from models import AgeGroup
from models import before_deo_filter, after_deo_filter
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import Geography
from models import FilteredDf
from models import QUARTERS, MOST_RECENT_QUARTER, SEASON_QUARTER_MAPPING
from models import Quarter
from fastapi_models import Endpoint, location_annotation
from models import ALL_QUARTERS
from dash_helpers import (
    location_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from demographic_constants import DEMOGRAPHICS_TOTAL
import os

from fastapi import APIRouter, Query
from enum import auto, Enum
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]


start_date = ALL_QUARTERS[-4]
end_date = ALL_QUARTERS[-1]


class SnapshotSummaryData(BaseModel):
    filtered_df: FilteredDf
    n_total: int
    avg_monthly_stops: int
    pct_not_found: float
    fig: Figure
    fig_deo_pct: Figure
    fig_deo_total: Figure
    num_stops_year_before_deo: int
    num_stops_year_after_deo: int
    num_stops_white_deo_decrease: int
    num_stops_black_deo_decrease: int

    class Config:
        arbitrary_types_allowed = True


def get_summary():
    police_action = PoliceAction.stop.value
    demographic_category = DemographicCategory.race.value
    date_filter = FilteredDf(start_date=start_date, end_date=end_date)
    df_date = date_filter.df

    avg_monthly_stops = date_filter.get_avg_monthly_value(police_action)
    n_total = df_date[police_action.sql_column].sum()

    # Miss Rate
    pct_not_found = (
        1 - (df_date["n_contraband"].sum() / df_date["n_intruded"].sum())
    ) * 100

    # demographic_breakdown_of_stops_graph
    n_actions_by_demo = df_date.groupby(demographic_category)[
        police_action.sql_column
    ].sum()

    stop_pct_col = "% of traffic stops"
    pop_pct_col = "% of city population"
    df = pd.concat(
        [
            n_actions_by_demo.to_frame(stop_pct_col)
            / sum(n_actions_by_demo.values)
            * 100,
            pd.Series(DEMOGRAPHICS_TOTAL).to_frame(pop_pct_col)
            / sum(DEMOGRAPHICS_TOTAL.values())
            * 100,
            n_actions_by_demo.to_frame("n_traffic_stops"),
            pd.Series(DEMOGRAPHICS_TOTAL).to_frame("n_population"),
        ],
        axis=1,
    ).round(1)
    df_melted = pd.melt(
        df.reset_index(names=demographic_category),
        id_vars=[demographic_category],
        value_vars=[stop_pct_col, pop_pct_col],
        var_name=" ",
        value_name="pcts",
    )
    df_melted = (
        df_melted.set_index(DemographicCategory.race.value)
        .join(df[["n_traffic_stops", "n_population"]])
        .reset_index()
    )

    df_melted[demographic_category] = pd.Categorical(
        df_melted[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )

    fig = px.bar(
        df_melted.sort_values(demographic_category),
        x=demographic_category,
        title=f"Racial Demographics of Traffic Stops vs. City Population from {date_filter.date_range_str}",
        y="pcts",
        labels={
            "pcts": "Percentage (%)",
            demographic_category: demographic_category,
        },
        barmode="group",
        color=" ",
    )
    for trace in fig.data:
        if trace["legendgroup"] == stop_pct_col:
            trace.hovertemplate = "%{x}<br>%{y}% of traffic stops<extra></extra>"
        else:
            trace.hovertemplate = "%{x}<br>%{y}% of city population<extra></extra>"

    value_before_deo = before_deo_filter.df["n_stopped"].sum()
    value_after_deo = after_deo_filter.df["n_stopped"].sum()

    # demographic_breakdown_of_stops_graph
    df_date_before = before_deo_filter.df
    n_actions_by_demo_before = df_date_before.groupby(demographic_category)[
        police_action.sql_column
    ].sum()
    df_date_after = after_deo_filter.df
    n_actions_by_demo_after = df_date_after.groupby(demographic_category)[
        police_action.sql_column
    ].sum()

    pre_deo_pct_col = "% before Driving Equality"
    pre_deo_num_col = "# before Driving Equality"
    post_deo_num_col = "# after Driving Equality"
    post_deo_pct_col = "% after Driving Equality"
    df_deo = pd.concat(
        [
            n_actions_by_demo_before.to_frame(pre_deo_pct_col)
            / sum(n_actions_by_demo_before.values)
            * 100,
            n_actions_by_demo_after.to_frame(post_deo_pct_col)
            / sum(n_actions_by_demo_after.values)
            * 100,
            pd.Series(DEMOGRAPHICS_TOTAL).to_frame(pop_pct_col)
            / sum(DEMOGRAPHICS_TOTAL.values())
            * 100,
            n_actions_by_demo_before.to_frame(pre_deo_num_col),
            n_actions_by_demo_after.to_frame(post_deo_num_col),
            pd.Series(DEMOGRAPHICS_TOTAL).to_frame("n_population"),
        ],
        axis=1,
    ).round(1)
    df_melted_deo = pd.melt(
        df_deo.reset_index(names=demographic_category),
        id_vars=[demographic_category],
        value_vars=[pre_deo_pct_col, post_deo_pct_col, pop_pct_col],
        var_name=" ",
        value_name="pcts",
    )

    df_melted_deo[demographic_category] = pd.Categorical(
        df_melted_deo[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )

    fig_deo_pct = px.bar(
        df_melted_deo.sort_values(demographic_category),
        x=demographic_category,
        title="Racial Demographics of Traffic Stops Before and After Driving Equality vs. City Population",
        y="pcts",
        labels={
            "pcts": "Percentage (%)",
            demographic_category: demographic_category,
        },
        barmode="group",
        color=" ",
    )
    for trace in fig_deo_pct.data:
        if trace["legendgroup"] == pre_deo_pct_col:
            trace.hovertemplate = "Before Driving Equality<br>%{x}<br>%{y}% of traffic stops<extra></extra>"
        elif trace["legendgroup"] == post_deo_pct_col:
            trace.hovertemplate = "After Driving Equality<br>%{x}<br>%{y}% of traffic stops<extra></extra>"
        else:
            trace.hovertemplate = "%{x}<br>%{y}% of city population<extra></extra>"

    df_melted_deo = pd.melt(
        df_deo.reset_index(names=demographic_category),
        id_vars=[demographic_category],
        value_vars=[pre_deo_num_col, post_deo_num_col],
        var_name=" ",
        value_name="count",
    )

    df_melted_deo[demographic_category] = pd.Categorical(
        df_melted_deo[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )

    fig_deo_total = px.bar(
        df_melted_deo.sort_values(demographic_category),
        x=demographic_category,
        title="Number of Traffic Stops by Race Before and After Driving Equality",
        y="count",
        labels={
            "count": "Number of Traffic Stops",
            demographic_category: demographic_category,
        },
        barmode="group",
        color=" ",
    )
    for trace in fig_deo_total.data:
        if trace["legendgroup"] == pre_deo_num_col:
            trace.hovertemplate = (
                "Before Driving Equality<br>%{x}<br>%{y:,} traffic stops<extra></extra>"
            )
        elif trace["legendgroup"] == post_deo_num_col:
            trace.hovertemplate = (
                "After Driving Equality<br>%{x}<br>%{y:,} traffic stops<extra></extra>"
            )
    df_deo_num_stops_decrease = (
        df_deo["# before Driving Equality"] - df_deo["# after Driving Equality"]
    )

    return SnapshotSummaryData(
        filtered_df=date_filter,
        n_total=n_total,
        avg_monthly_stops=avg_monthly_stops,
        pct_not_found=pct_not_found,
        fig=fig,
        fig_deo_pct=fig_deo_pct,
        fig_deo_total=fig_deo_total,
        num_stops_year_before_deo=value_before_deo,
        num_stops_year_after_deo=value_after_deo,
        num_stops_white_deo_decrease=df_deo_num_stops_decrease["White"],
        num_stops_black_deo_decrease=df_deo_num_stops_decrease["Black"],
    )


# Have to do these separately because the plotly layouts are direct rather
# than done like every other page where they are based on callbacks


def get_text_sentence_last_year(summary_data):
    return f"From {summary_data.filtered_df.date_range_str_long}, police made a total of <span>{summary_data.n_total:,}</span> traffic stops in Philadelphia, or an average of <span>{summary_data.avg_monthly_stops:,}</span> traffic stops per month."


def get_text_sentence_pct_deo(summary_data):
    pct_decrease = np.round(
        (summary_data.num_stops_year_before_deo - summary_data.num_stops_year_after_deo)
        / summary_data.num_stops_year_before_deo
        * 100,
        1,
    )
    return f"""
    traffic stops decreased by <span>{pct_decrease}%</span> from <span>{summary_data.num_stops_year_before_deo:,}</span> stops to <span>{summary_data.num_stops_year_after_deo:,}</span> stops"""


def get_text_sentence_num_deo(summary_data):
    pct_decrease = np.round(
        (summary_data.num_stops_year_before_deo - summary_data.num_stops_year_after_deo)
        / summary_data.num_stops_year_before_deo
        * 100,
        1,
    )
    return f"""
    In the year after Driving Equality, Philadelphia police stopped <span>{summary_data.num_stops_black_deo_decrease:,}</span> fewer Black drivers and <span>{summary_data.num_stops_white_deo_decrease:,}</span> fewer white drivers, compared to 2021.
    """


def get_text_sentence_contraband(summary_data):
    return f"""
        From {summary_data.filtered_df.date_range_str_long}, Philadelphia police did not find any contraband <span>{summary_data.pct_not_found:.1f}%</span> of the time they intruded on people and/or vehicles. 
        """


@router.get(API_URL, name="Annual Summary")
def api_func():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    summary_data = get_summary()
    return endpoint.output(
        fig_barplot=summary_data.fig,
        fig_barplot2=summary_data.fig_deo_pct,
        fig_barplot3=summary_data.fig_deo_total,
        text_sentence1=get_text_sentence_last_year(summary_data),
        text_sentence2=get_text_sentence_pct_deo(summary_data),
        text_sentence3=get_text_sentence_num_deo(summary_data),
        text_sentence4=get_text_sentence_contraband(summary_data),
    )


def layout():
    summary_data = get_summary()
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    return [
        html.A("**API FOR THIS QUESTION**:", href=endpoint.full_api_route),
        html.Div(
            [
                html.Span(
                    "How many traffic stops did Philadelphia police make in the last year? "
                ),
                dcc.Markdown(
                    get_text_sentence_last_year(summary_data)
                    .replace("<span>", "**")
                    .replace("</span>", "**"),
                ),
            ],
        ),
        html.Div(
            [
                "In the last year, what were the racial disparities in traffic stops by Philadelphia police? How does the city population compare to who was stopped?",
                dcc.Graph(figure=summary_data.fig),
                dcc.Markdown(
                    "When Philadelphia police intrude during traffic stops, they do not find any contraband most of the time. "
                    + get_text_sentence_contraband(summary_data)
                    .replace("<span>", "**")
                    .replace("</span>", "**")
                ),
            ]
        ),
        html.Div(
            [
                html.H2("How did traffic stops change after Driving Equality?"),
                dcc.Markdown(
                    "Driving Equality came into effect on March 3, 2022. In the year after Driving Equality, "
                    + get_text_sentence_pct_deo(summary_data)
                    .replace("<span>", "**")
                    .replace("</span>", "**")
                    + ", compared to 2021 (see What is Driving Equality? to learn more about these date comparisons). Concerningly, racial disparities in traffic stops have persisted."
                ),
                dcc.Graph(figure=summary_data.fig_deo_pct),
                dcc.Markdown(
                    get_text_sentence_num_deo(summary_data)
                    .replace("<span>", "**")
                    .replace("</span>", "**")
                ),
                dcc.Graph(figure=summary_data.fig_deo_total),
            ]
        ),
    ]


LAYOUT = html.Div(layout())
