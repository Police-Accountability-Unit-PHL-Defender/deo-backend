from dash import Dash, html, dcc, callback, Output, Input
from models import TimeAggregation
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from models import PoliceAction
from models import (
    QUARTERS,
    MOST_RECENT_QUARTER,
    SEASON_QUARTER_MAPPING,
    QuarterHow,
    FOUR_QUARTERS_AGO,
)
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import FilteredDf
import pandas as pd
import plotly.express as px
from routers import ROUTERS
from fastapi_models import Endpoint, location_annotation, quarter_annotation

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Div(
        [
            html.Span("How often did Philadelphia police stop people of different "),
            demographic_dropdown(f"{prefix}-demographic-category", plural=True),
            html.Span(" from the start of quarter"),
            qyear_dropdown(f"{prefix}-start-qyear", default=FOUR_QUARTERS_AGO),
            html.Span(" to the end of "),
            qyear_dropdown(
                f"{prefix}-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
            ),
            html.Span(" in "),
            location_dropdown(f"{prefix}-location"),
            html.Span("?"),
            dcc.Graph(id=f"{prefix}-graph"),
        ]
    ),
]


@callback(
    [
        Output(f"{prefix}-graph", "figure"),
        Output(f"{prefix}-result-api", "href"),
    ],
    [
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-demographic-category", "value"),
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
    ],
)
@router.get(API_URL)
def api_func(
    location: location_annotation,
    demographic_category,
    start_qyear: quarter_annotation = FOUR_QUARTERS_AGO,
    end_qyear: quarter_annotation = MOST_RECENT_QUARTER,
):
    endpoint = Endpoint(api_route=API_URL, inputs=locals())
    police_action = PoliceAction.stop.value
    geo_filter = FilteredDf(
        location=location, start_date=start_qyear, end_date=end_qyear
    )
    df_geo_all_time = geo_filter.df

    # Demographic
    df_timeseries_demo = (
        df_geo_all_time.groupby(demographic_category)[police_action.sql_column]
        .sum()
        .reset_index()
    )

    df_timeseries_demo["percentage"] = (
        df_timeseries_demo[police_action.sql_column]
        .transform(lambda x: (x / x.sum()) * 100)
        .round(1)
    )
    df_timeseries_demo[demographic_category] = pd.Categorical(
        df_timeseries_demo[demographic_category],
        DemographicCategory(demographic_category).order_of_group,
    )
    df_timeseries_demo = df_timeseries_demo.sort_values(demographic_category)
    df_timeseries_demo[demographic_category] = df_timeseries_demo[
        demographic_category
    ].str.title()

    fig = px.bar(
        df_timeseries_demo,
        x=demographic_category,
        y="percentage",
        barmode="group",
        labels={
            "percentage": "Percentage (%)",
        },
        title=f"Percent of PPD {police_action.noun.title()} in {geo_filter.geography.string} by {demographic_category} from {geo_filter.get_date_range_str(TimeAggregation.quarter)}",
        hover_data=[police_action.sql_column],
    )
    for trace in fig.data:
        trace.hovertemplate = (
            "%{x}<br>%{y}% of "
            + police_action.noun
            + "<br>%{customdata[0]:,} "
            + police_action.noun
        )
    return endpoint.output(
        fig_barplot=fig,
    )
