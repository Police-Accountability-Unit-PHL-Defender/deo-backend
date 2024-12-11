from dash import Dash, html, dcc, callback, Output, Input
from models import TimeAggregation
from models import QuarterHow
from models import PoliceAction
from models import FilteredDf
import dash_ag_grid as dag
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import (
    QUARTERS,
    MOST_RECENT_QUARTER,
    SEASON_QUARTER_MAPPING,
    FOUR_QUARTERS_AGO,
)
from fastapi_models import Endpoint, location_annotation, quarter_annotation
from dash_helpers import (
    location_dropdown,
    qyear_dropdown,
    demographic_dropdown,
    Subtitle,
    TimeAggregationChoice,
)
from routers import ROUTERS

prefixes = __name__.split(".")[-2:]
prefix = prefixes[1].replace("_", "-")
API_URL = f"/{prefixes[0]}/{prefix}"
router = ROUTERS[prefixes[0]]
LAYOUT = [html.A("**API FOR THIS QUESTION**:", id=f"{prefix}-result-api")]
LAYOUT = LAYOUT + [
    html.Div(
        [
            html.Span(
                "Which demographic groups did Philadelphia police most frequently stop in "
            ),
            location_dropdown(f"{prefix}-location"),
            html.Span(" from the start of quarter"),
            qyear_dropdown(f"{prefix}-start-qyear", default=FOUR_QUARTERS_AGO),
            html.Span(" through the end of "),
            qyear_dropdown(
                f"{prefix}-end-qyear", default=MOST_RECENT_QUARTER, how=QuarterHow.end
            ),
            html.Span("?"),
        ]
    ),
    html.Div(id=f"{prefix}-summary"),
    html.H3(
        id=f"{prefix}-title",
        style={"textAlign": "center"},
    ),
    html.Div(id=f"{prefix}-table"),
]


@callback(
    Output(f"{prefix}-table", "children"),
    Output(f"{prefix}-title", "children"),
    Output(f"{prefix}-summary", "children"),
    Output(f"{prefix}-result-api", "href"),
    [
        Input(f"{prefix}-location", "value"),
        Input(f"{prefix}-start-qyear", "value"),
        Input(f"{prefix}-end-qyear", "value"),
    ],
)
@router.get(API_URL)
def stops__most_frequent_stops(
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

    # Most stopped folks
    total = df_geo[police_action.sql_column].sum()
    sorted_values = (
        df_geo.groupby([v for v in DemographicCategory])[police_action.sql_column]
        .sum()
        .sort_values(ascending=False)
        / total
        * 100
    ).reset_index()
    most_value = sorted_values.iloc[0]
    race = most_value[DemographicCategory.race.value]
    gender = most_value[DemographicCategory.gender.value]
    age_range = most_value[DemographicCategory.age_range.value]
    amount = most_value[police_action.sql_column].round(1)

    # Ranked Demographics
    sorted_values = (
        (
            df_geo.groupby([v.value for v in DemographicCategory])[
                police_action.sql_column
            ]
            .sum()
            .sort_values(ascending=False)
            / total
            * 100
        )
        .round(1)
        .reset_index()
        .rename(
            columns={
                police_action.sql_column: f"% of {police_action.noun}",
                "age_range": "age range",
            }
        )
    )
    sorted_values = sorted_values[sorted_values[f"% of {police_action.noun}"] > 0]

    return endpoint.output(
        table_demo=dag.AgGrid(
            rowData=sorted_values.to_dict("records"),
            columnDefs=[{"field": c} for c in sorted_values.columns],
            columnSize="sizeToFit",
            defaultColDef={"resizable": True, "sortable": True, "filter": True},
            dashGridOptions={"pagination": False},
        ),
        text_sentence1=f"Demographic Groups Stopped by PPD in {geo_filter.geography.string} from {geo_filter.get_date_range_str(TimeAggregation.quarter)}",
        text_sentence2=f"Philadelphia police most frequently {police_action.past_tense} <span>{race.title()} {gender.lower()} {age_range}</span> year old drivers in {geo_filter.geography.string} from {geo_filter.get_date_range_str_long(TimeAggregation.quarter)}, or <span>{amount}%</span> of stops.",
    )
