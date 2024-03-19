from dash import Dash, html, dcc, callback, Output, Input, register_page
import numpy as np

import plotly.graph_objects as go
import dash_ag_grid as dag
from datetime import date
from datetime import timedelta
from datetime import datetime
import plotly.express as px
import pandas as pd
import sqlite3

from models import PoliceAction
from models import PolicePostStopAction
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import FilteredDf
from models import Geography
from models import QUARTERS
from models import df_raw
from models import df_raw_reasons
import os

from demographics.constants import (
    DEMOGRAPHICS_DISTRICT,
)

PAGE_TITLE = "Do police make traffic stops for safety reasons?"

query = """
select
gender,
districtoccur,
  race, mvc_code, count(*) as n_stopped,
  count(*)/ CAST(SUM(COUNT(*)) OVER (PARTITION BY mvc_code) as float) * 100 as pct_by_violation_category,
  count(*)/ CAST(SUM(COUNT(*)) OVER (PARTITION BY race) as float) * 100 as pct_by_race,
  count(*)/ CAST(SUM(COUNT(*)) OVER (PARTITION BY districtoccur) as float) * 100 as pct_by_district
 from car_ped_stops  where mvc_code IN ('4524E1', '3112A31', '3323B', '4303B', '1301A', '4303A', '3111A', '3714')  and     

 extract(
        year
        from
          datetimeoccur
      ) = 2022
group by race, gender, mvc_code, districtoccur

"""
import requests

# response = requests.get("https://phl.carto.com/api/v2/sql", params={"q": query})
# df_reasons = pd.DataFrame(response.json()["rows"])
# df_reasons.to_csv("reasons.csv", index=False)
# df_reasons = pd.read_csv("reasons.csv", dtype={"districtoccur": str})
"""
df_reasons = pd.read_csv(
    "car_ped_stops_quarterly_reason.csv", dtype={"districtoccur": str}
)
"""

Q1_LAYOUT = [
    html.H1(
        children=PAGE_TITLE,
        style={"textAlign": "center"},
    ),
    html.Span(
        "When Philadelphia police provided a reason, what were the primary reasons why police stopped Black and white drivers in Philadelphia in "
    ),
    dcc.Dropdown(
        options=[
            {"label": 2022, "value": 2022},
            {"label": 2023, "value": 2023},
        ],
        value=2022,
        id="p5-q1a-year",
        style={"display": "inline-block", "width": "150px"},
    ),
    html.Span("?"),
    dcc.Graph(id="p5-q1-graph2"),
    dcc.Graph(id="p5-q1-graph3"),
    dcc.Graph(id="p5-q1-graph4"),
    dcc.Graph(id="p5-q1-graph5"),
    dcc.Graph(id="p5-q1-graph6"),
]


@callback(
    [
        Output("p5-q1-graph2", "figure"),
        Output("p5-q1-graph3", "figure"),
        Output("p5-q1-graph4", "figure"),
        Output("p5-q1-graph5", "figure"),
        Output("p5-q1-graph6", "figure"),
    ],
    [
        Input("p5-q1a-year", "value"),
    ],
)
def q1a(year):
    df_reasons = FilteredDf(
        start_date=datetime(year, 1, 1),
        end_date=datetime(year, 12, 31),
        include_reasons=True,
    ).df
    # df_reasons = df_raw_reasons().copy()
    # df_reasons = df_reasons[df_reasons["year"] == year]
    df_reasons = df_reasons[df_reasons["violation_category"] != "Other"]

    df_reasons_grouped = (
        df_reasons.groupby(["Race", "violation_category"])["n_stopped"]
        .sum()
        .reset_index()
    )

    def pct_stop_fig(df, col, val, col_text):
        df_filt = df[df[col] == val].sort_values("n_stopped")
        df_filt["pct_stopped"] = 100 * df_filt["n_stopped"] / df_filt["n_stopped"].sum()
        fig = px.bar(
            df_filt,
            x="violation_category",
            y="pct_stopped",
            barmode="stack",
            color="violation_category",
        )
        fig.update_yaxes(title_text=f"% of Stops  where {col_text} was {val}")
        return fig

    fig2 = pct_stop_fig(df_reasons_grouped, "Race", "White", "driver")
    fig3 = pct_stop_fig(df_reasons_grouped, "Race", "Black", "driver")

    # By neighborhood
    whiteness_of_districts = (
        DEMOGRAPHICS_DISTRICT["white"] / DEMOGRAPHICS_DISTRICT["total"]
    ).sort_values()
    districts_by_nonwhiteness = whiteness_of_districts.index
    majority_white_districts = whiteness_of_districts[
        whiteness_of_districts > 0.5
    ].index
    majority_nonwhite_districts = whiteness_of_districts[
        whiteness_of_districts <= 0.5
    ].index

    df_reasons.loc[
        df_reasons[df_reasons["districtoccur"].isin(majority_white_districts)].index,
        "majority_district",
    ] = "White"
    df_reasons.loc[
        df_reasons[df_reasons["districtoccur"].isin(majority_nonwhite_districts)].index,
        "majority_district",
    ] = "Non-white"

    df_reasons_grouped_neighborhood = (
        df_reasons.groupby(["violation_category", "majority_district"])["n_stopped"]
        .sum()
        .reset_index()
    )
    fig4 = pct_stop_fig(
        df_reasons_grouped_neighborhood, "majority_district", "White", "neighborhood"
    )
    fig5 = pct_stop_fig(
        df_reasons_grouped_neighborhood,
        "majority_district",
        "Non-white",
        "neighborhood",
    )

    return [
        fig2,
        fig3,
        fig4,
        fig5,
        px.bar(
            df_reasons.groupby(["Race", "violation_category"])
            .size()
            .rename("count")
            .reset_index(),
            x="Race",
            y="count",
            barmode="stack",
            color="violation_category",
        ),
    ]


register_page(__name__, path="/reasons", supplied_name=PAGE_TITLE)
layout = html.Div(Q1_LAYOUT)
