from dash import html, dcc
from models import police_districts_geojson
import plotly.graph_objects as go
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
from models import QuarterHow
from models import hin_geojson
from models import hin_sample_locations_df
from models import df_shootings_raw
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


def shootings_vs_stops_map(start, end, title):
    df_shootings = df_shootings_raw()
    df_year_start = FilteredDf(start_date=start[0], end_date=start[1]).df
    df_year_start = df_year_start.merge(
        df_shootings[["districtoccur", "quarter", "n_shootings", "n_outside"]],
        on=["quarter", "districtoccur"],
        how="left",
    )
    df_year_start_by_district = (
        df_year_start.groupby("districtoccur")[["n_stopped", "n_shootings"]]
        .sum()
        .rename(
            columns={
                "n_stopped": "n_stopped_start",
                "n_shootings": "n_shootings_start",
            }
        )
    )
    df_year_end = FilteredDf(start_date=end[0], end_date=end[1]).df
    df_year_end = df_year_end.merge(
        df_shootings, on=["quarter", "districtoccur"], how="left"
    )
    df_year_end_by_district = (
        df_year_end.groupby("districtoccur")[["n_stopped", "n_shootings"]]
        .sum()
        .rename(
            columns={"n_stopped": "n_stopped_end", "n_shootings": "n_shootings_end"}
        )
    )
    df_pct_change = df_year_start_by_district.join(df_year_end_by_district)

    df_pct_change["pct_change_stopped"] = (
        100
        * (df_pct_change["n_stopped_end"] - df_pct_change["n_stopped_start"])
        / df_pct_change["n_stopped_start"]
    )

    df_pct_change["pct_change_shootings"] = (
        100
        * (df_pct_change["n_shootings_end"] - df_pct_change["n_shootings_start"])
        / df_pct_change["n_shootings_start"]
    )
    df_pct_change = df_pct_change[
        df_pct_change.index != "77"
    ]  # District 77 is airport, has no shooting data

    # Adding a Rank Column
    df_pct_change = df_pct_change.sort_values("pct_change_stopped", ascending=False)
    df_pct_change["ranked_stop_increase"] = df_pct_change["pct_change_stopped"].rank(
        method="min", ascending=False
    )
    df_pct_change["ranked_stop_increase_str"] = df_pct_change[
        "ranked_stop_increase"
    ].apply(lambda x: f"{x:.0f}")
    df_pct_change = df_pct_change.sort_values("pct_change_shootings", ascending=False)
    df_pct_change["ranked_shooting_decrease"] = df_pct_change[
        "pct_change_shootings"
    ].rank(method="max", ascending=True)

    df_pct_change["ranked_shooting_decrease_str"] = df_pct_change[
        "ranked_shooting_decrease"
    ].apply(lambda x: f"{x:.0f}")

    df_pct_change = df_pct_change.reset_index()[
        [
            "districtoccur",
            "pct_change_stopped",
            "pct_change_shootings",
            "ranked_stop_increase",
            "ranked_shooting_decrease",
            "ranked_stop_increase_str",
            "ranked_shooting_decrease_str",
        ]
    ]
    n_dist = 5
    most_stopped = df_pct_change.sort_values("pct_change_stopped", ascending=False)[
        :n_dist
    ]
    least_shootings = df_pct_change.sort_values("pct_change_shootings", ascending=True)[
        :n_dist
    ]

    colorscale_stops = [
        [0, "rgba(0,255,0,0)"],  # Transparent
        [1, "rgba(0,255,0,1)"],  # Green
    ]

    # Define the magentas color scale
    colorscale_shootings = [
        [0, "rgba(255,0,255,0)"],  # Transparent
        [1, "rgba(255,0,255,1)"],  # Magenta
    ]
    green_light = "#b7f7b4"  # Light green
    green_dark = "#086e00"  # Dark green
    magenta_light = "#f2bbf2"  # Light magenta
    magenta_dark = "#94008a"  # Dark magenta

    # Create a color scale for green from light to dark
    colorscale_stops = [[0, green_light], [1, green_dark]]

    # Create a color scale for magenta from light to dark
    colorscale_shootings = [[0, magenta_light], [1, magenta_dark]]
    # Create Choroplethmapbox trace

    original_geojson = police_districts_geojson()

    features = []
    for feature in original_geojson["features"]:
        dist_numc = feature["properties"]["DIST_NUMC"]

        rows = df_pct_change[df_pct_change["districtoccur"] == dist_numc]

        if not rows.empty:
            row = rows.iloc[0]
            is_top_5_shootings_decrease = bool(row["ranked_shooting_decrease"] <= 5)
            is_top_5_stops_increase = bool(row["ranked_stop_increase"] <= 5)

            feature["properties"]["shooting_decrease"] = is_top_5_shootings_decrease
            feature["properties"]["stops_increase"] = is_top_5_stops_increase
            feature["properties"][
                "hovertext"
            ] = f"<b>District {row['districtoccur']}<br><b>Traffic stop increase: Ranked #{row['ranked_stop_increase_str']}<br><b>Shootings decrease: Ranked #{row['ranked_shooting_decrease_str']}"
            if is_top_5_shootings_decrease or is_top_5_stops_increase:
                features.append(feature)
    geojson = {"type": "FeatureCollection", "features": features}

    shootings_stops = pd.concat([least_shootings, most_stopped])
    hovertext = [
        f"<b>District {row['districtoccur']}<br><b>Traffic stop increase: Ranked #{row['ranked_stop_increase_str']}<br><b>Shootings decrease: Ranked #{row['ranked_shooting_decrease_str']}"
        for i, row in shootings_stops.iterrows()
    ]
    choropleth_mapbox_shootings = go.Choroplethmapbox(
        geojson=geojson,
        featureidkey="properties.DIST_NUMC",
        locations=shootings_stops["districtoccur"],
        z=shootings_stops["ranked_shooting_decrease"]
        * shootings_stops["ranked_stop_increase"],
        colorscale=colorscale_shootings,
        marker_opacity=0.7,
        hovertemplate="%{text}<extra></extra>",
        text=hovertext,
    )
    # Create Mapbox figure

    fig = go.Figure(choropleth_mapbox_shootings)

    fig.update_layout(
        title=title,
        mapbox_style="carto-positron",
        mapbox_zoom=10,
        mapbox_center={"lat": 39.9526, "lon": -75.1652},
    )
    return fig


YEAR_2018_vs_2019_title = "Comparing 2018 to 2019: Districts with Largest Increase in Traffic Stops vs. Districts with Largest Decrease in Shootings"
DEO_TITLE = "Before and After Driving Equality: Districts with Largest Increase in Traffic Stops vs. Districts with Largest Decrease in Shootings"


@router.get(API_URL)
def api_func():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_surge = shootings_vs_stops_map(
        start=("2018-01-01", "2018-12-31"),
        end=("2019-01-01", "2019-12-31"),
        title=YEAR_2018_vs_2019_title,
    )
    map_deo = shootings_vs_stops_map(
        start=("2021-01-01", "2021-12-31"),
        end=("2022-04-01", "2023-03-31"),
        title=DEO_TITLE,
    )
    return endpoint.output(
        map_surge=map_surge,
        map_deo=map_deo,
    )


def shootings_vs_stops_layout():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_surge = shootings_vs_stops_map(
        start=("2018-01-01", "2018-12-31"),
        end=("2019-01-01", "2019-12-31"),
        title=YEAR_2018_vs_2019_title,
    )
    map_deo = shootings_vs_stops_map(
        start=("2021-01-01", "2021-12-31"),
        end=("2022-04-01", "2023-03-31"),
        title=DEO_TITLE,
    )
    return [
        html.A("**API FOR THIS QUESTION**:", href=endpoint.full_api_route),
        html.Div(
            "During a surge in traffic stops from 2018 to 2019, which districts had the largest increase in traffic stops? Were these the same districts that had the largest decrease in shootings?"
        ),
        dcc.Graph(figure=map_surge),
        html.Div(
            "Comparing the year before Driving Equality to the year after the law was implemented, which districts had the largest increase in traffic stops? Were these the same districts that had the largest decrease in shootings?"
        ),
        dcc.Graph(figure=map_deo),
    ]


LAYOUT = [html.Div(shootings_vs_stops_layout())]
