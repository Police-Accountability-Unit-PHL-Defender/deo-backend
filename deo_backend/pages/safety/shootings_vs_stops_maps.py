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
from demographic_constants import (
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
from pydantic import BaseModel

prefixes = __name__.split(".")[-2:]
prefix = prefixes[0].replace("_", "-") + "-" + prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]


class ChangeType(str, Enum):
    decrease = "decrease"
    increase = "increase"


class MapColAttributes(BaseModel):
    column: str
    plural_noun: str
    change_type: ChangeType

    @classmethod
    def from_column(cls, col: str, change_type: str):
        match col:
            case "n_stopped":
                return cls.stopped(change_type=change_type)
            case "n_shootings":
                return cls.shootings(change_type=change_type)
            case _:
                raise NotImplementedError(
                    f"columns must be n_stopped or n_shootings but received: {col}"
                )

    @property
    def is_shootings(self):
        return self.column == MapColAttributes.shootings(change_type="decrease").column

    @property
    def is_stopped(self):
        return self.column == MapColAttributes.stopped(change_type="increase").column

    @classmethod
    def stopped(cls, change_type):
        return cls(
            column="n_stopped", plural_noun="traffic stops", change_type=change_type
        )

    @classmethod
    def shootings(cls, change_type):
        return cls(
            column="n_shootings", plural_noun="shootings", change_type=change_type
        )


def shootings_vs_stops_map(start, end, title, decrease_col, increase_col):
    decrease_col_obj = MapColAttributes.from_column(
        decrease_col, change_type="decrease"
    )
    increase_col_obj = MapColAttributes.from_column(
        increase_col, change_type="increase"
    )
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

    df_pct_change["pct_change_n_stopped"] = (
        100
        * (df_pct_change["n_stopped_end"] - df_pct_change["n_stopped_start"])
        / df_pct_change["n_stopped_start"]
    )

    df_pct_change["pct_change_n_shootings"] = (
        100
        * (df_pct_change["n_shootings_end"] - df_pct_change["n_shootings_start"])
        / df_pct_change["n_shootings_start"]
    )
    df_pct_change = df_pct_change[
        df_pct_change.index != "77"
    ]  # District 77 is airport, has no shooting data

    # Adding a Rank Column
    df_pct_change = df_pct_change.sort_values(
        f"pct_change_{increase_col_obj.column}", ascending=False
    )
    df_pct_change[f"ranked_{increase_col_obj.column}_increase"] = df_pct_change[
        f"pct_change_{increase_col_obj.column}"
    ].rank(method="min", ascending=False)
    df_pct_change = df_pct_change.sort_values(
        f"pct_change_{decrease_col_obj.column}", ascending=False
    )
    df_pct_change[f"ranked_{decrease_col_obj.column}_decrease"] = df_pct_change[
        f"pct_change_{decrease_col_obj.column}"
    ].rank(method="max", ascending=True)
    df_pct_change["is_top_5_decrease"] = (
        df_pct_change[f"ranked_{decrease_col_obj.column}_decrease"] <= 5
    )
    df_pct_change["is_top_5_increase"] = (
        df_pct_change[f"ranked_{increase_col_obj.column}_increase"] <= 5
    )

    df_pct_change = df_pct_change.reset_index()
    n_dist = 5
    most_increased = df_pct_change.sort_values(
        f"pct_change_{increase_col_obj.column}", ascending=False
    )[:n_dist]
    most_decreased = df_pct_change.sort_values(
        f"pct_change_{decrease_col_obj.column}", ascending=True
    )[:n_dist]

    # Define the magentas color scale
    green = "#00ff00"
    white = "#000000"
    end = "#fed8b1"  # Dark magenta

    # Create a color scale for magenta from light to dark
    colorscale_shootings = [green, white, end]
    # Create Choroplethmapbox trace

    original_geojson = police_districts_geojson()

    features = []

    def hovertext(row):
        def _rank_str(x):
            int_x = int(x)
            last_digit = int(str(int_x)[-1])
            match last_digit:
                case 1:
                    suffix = "st"
                case 2:
                    suffix = "nd"
                case 3:
                    suffix = "rd"
                case _:
                    suffix = "th"

            if int_x in (11, 12, 13):
                suffix = "th"
            return f"{int_x}{suffix}"

        is_top_5_decrease = row["is_top_5_decrease"]
        is_top_5_increase = row["is_top_5_increase"]

        increase_str = _rank_str(row[f"ranked_{increase_col_obj.column}_increase"])
        decrease_str = _rank_str(row[f"ranked_{decrease_col_obj.column}_decrease"])
        pct_change_for_increase = row[f"pct_change_{increase_col_obj.column}"]
        pct_change_for_decrease = row[f"pct_change_{decrease_col_obj.column}"]
        increase_col_str = increase_col_obj.plural_noun
        decrease_col_str = decrease_col_obj.plural_noun

        pct_change_increase_str = (
            "decrease" if pct_change_for_increase < 0 else "increase"
        )
        increase_sentence = f"<b>{abs(pct_change_for_increase):.1f}% {pct_change_increase_str} in {increase_col_str}"
        pct_change_decrease_str = (
            "decrease" if pct_change_for_decrease < 0 else "increase"
        )
        decrease_sentence = f"<b>{abs(pct_change_for_decrease):.1f}% {pct_change_decrease_str} in {decrease_col_str}"

        if is_top_5_increase:
            increase_sentence = increase_sentence + f" ({increase_str} largest)"
        if is_top_5_decrease:
            decrease_sentence = decrease_sentence + f" ({decrease_str} largest)"
        first_sentence = (
            increase_sentence if increase_col_obj.is_stopped else decrease_sentence
        )
        second_sentence = (
            increase_sentence if increase_col_obj.is_shootings else decrease_sentence
        )

        """



        if is_top_5_decrease:
            first_sentence = f"<b>{decrease_str} largest % decrease in {decrease_col_str} ({pct_change_for_decrease:.1f}%)"
            pct_change_str = "decrease" if pct_change_for_increase < 0 else "increase"
            second_sentence = f"<b>{abs(pct_change_for_increase):.1f}% {pct_change_str} in {increase_col_str}"
        elif is_top_5_increase:
            first_sentence = f"<b>{increase_str} largest % increase in {increase_col_str} ({pct_change_for_increase:.1f}%)"
            pct_change_str = "decrease" if pct_change_for_decrease < 0 else "increase"
            second_sentence = f"<b>{abs(pct_change_for_decrease):.1f}% {pct_change_str} in {decrease_col_str}"
        """
        return f"<b>District {row['districtoccur']}<br>" + "<br>".join(
            [first_sentence, second_sentence]
        )

    shootings_stops = pd.concat([most_decreased, most_increased])
    for feature in original_geojson["features"]:
        dist_numc = feature["properties"]["DIST_NUMC"]
        rows = shootings_stops[shootings_stops["districtoccur"] == dist_numc]

        if rows.empty:
            continue

        is_top_5_decrease = bool(rows.iloc[0]["is_top_5_decrease"])
        is_top_5_increase = bool(rows.iloc[0]["is_top_5_increase"])

        row = rows.iloc[0]
        feature["properties"][
            f"is_top_{decrease_col_obj.column}_change"
        ] = is_top_5_decrease
        feature["properties"][
            f"is_top_{increase_col_obj.column}_change"
        ] = is_top_5_increase
        feature["properties"]["hovertext"] = hovertext(
            row,
        )
        features.append(feature)
    geojson = {"type": "FeatureCollection", "features": features}

    hovertext = [hovertext(row) for i, row in shootings_stops.iterrows()]
    choropleth_mapbox_shootings = go.Choroplethmapbox(
        geojson=geojson,
        featureidkey="properties.DIST_NUMC",
        locations=shootings_stops["districtoccur"],
        z=shootings_stops[f"ranked_{decrease_col}_decrease"]
        * shootings_stops[f"ranked_{increase_col}_increase"],
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
    return (
        fig,
        df_pct_change["n_stopped_start"].sum(),
        df_pct_change["n_stopped_end"].sum(),
    )


YEAR_2018_vs_2019_title = "Districts with Largest % Increases in Traffic Stops vs. Districts with Largest % Decreases in Shootings"
DEO_TITLE = "Before and After Driving Equality: Districts with Largest % Decreases in Traffic Stops vs. Districts with Largest % Increases in Shootings"


def get_text_sentence_surge(n_stops_start: int, n_stops_end: int):
    stops_diff = n_stops_end - n_stops_start
    pct_diff = stops_diff / n_stops_start * 100
    return f"""Comparing 2018 to 2019, the Philadelphia Police Department increased traffic stops across nearly all 21 districts by {stops_diff:,} stops, a {pct_diff:.01f}% increase. The map below compares the 5 districts with the largest percent increases in traffic stops to the 5 districts with the largest percent decreases in shootings. This map attempts to see whether the districts with the largest percent increases in traffic stops also had the largest percent decreases in shootings. Here, only one district, the 18th district, had such an outcome, with the 2nd largest percent increase of traffic stops and the third largest percent decrease in shootings. """


def get_text_sentence_deo(n_stops_start: int, n_stops_end: int):
    stops_diff = n_stops_end - n_stops_start
    pct_diff = stops_diff / n_stops_start * 100
    return f"Comparing before and after Driving Equality, the Philadelphia Police Department decreased traffic stops by {-1*stops_diff:,} stops, a {-1*pct_diff:.01f}% decrease. The map below compares the 5 districts with the largest percent decreases in traffic stops to the 5 districts with the largest percent increases in shootings. This map attempts to see whether the districts with the largest percent decreases in traffic stops also had the largest percent increases in shootings."


@router.get(API_URL)
def api_func():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_surge, n_surge_stops_start, n_surge_stops_end = shootings_vs_stops_map(
        start=("2018-01-01", "2018-12-31"),
        end=("2019-01-01", "2019-12-31"),
        title=YEAR_2018_vs_2019_title,
        decrease_col="n_shootings",
        increase_col="n_stopped",
    )
    map_deo, n_deo_stops_start, n_deo_stops_end = shootings_vs_stops_map(
        start=("2021-01-01", "2021-12-31"),
        end=("2022-04-01", "2023-03-31"),
        title=DEO_TITLE,
        decrease_col="n_stopped",
        increase_col="n_shootings",
    )
    return endpoint.output(
        map_surge=map_surge,
        map_deo=map_deo,
        text_sentence_surge=get_text_sentence_surge(
            n_surge_stops_start, n_surge_stops_end
        ),
        text_sentence_deo=get_text_sentence_deo(n_deo_stops_start, n_deo_stops_end),
    )


def shootings_vs_stops_layout():
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    map_surge, n_surge_stops_start, n_surge_stops_end = shootings_vs_stops_map(
        start=("2018-01-01", "2018-12-31"),
        end=("2019-01-01", "2019-12-31"),
        title=YEAR_2018_vs_2019_title,
        decrease_col="n_shootings",
        increase_col="n_stopped",
    )
    map_deo, n_deo_stops_start, n_deo_stops_end = shootings_vs_stops_map(
        start=("2021-01-01", "2021-12-31"),
        end=("2022-04-01", "2023-03-31"),
        title=DEO_TITLE,
        decrease_col="n_stopped",
        increase_col="n_shootings",
    )
    return [
        html.A("**API FOR THIS QUESTION**:", href=endpoint.full_api_route),
        html.Div(
            "During a surge in traffic stops from 2018 to 2019, which districts had the largest increases in traffic stops? Were these the same districts that had the largest decreases in shootings?"
        ),
        dcc.Markdown(get_text_sentence_surge(n_surge_stops_start, n_surge_stops_end)),
        dcc.Graph(figure=map_surge),
        html.Div(
            "Driving Equality came into effect on March 3, 2022. In the year after Driving Equality, which districts had the largest percent decreases in traffic stops, compared to 2021? (See What is Driving Equality? to learn more about these date comparisons.) Were these the same districts that had the largest percent increases in shootings?"
        ),
        dcc.Markdown(get_text_sentence_deo(n_deo_stops_start, n_deo_stops_end)),
        dcc.Graph(figure=map_deo),
    ]


LAYOUT = [html.Div(shootings_vs_stops_layout())]
