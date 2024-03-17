from models import QUARTERS, QuarterHow, TimeAggregation
from models import PoliceAction
from enum import auto
from enum import Enum
from models import DemographicCategory
from pydantic import BaseModel
from dash import html, dcc


class Subtitle(BaseModel):
    name: str

    @property
    def _id(self):
        return self.name.replace(" ", "-").replace("?", "").lower()

    @property
    def _href(self):
        return f"#{self._id}"

    @property
    def a_href(self):
        return html.A(self.name, href=self._href)

    @property
    def h2(self):
        return html.H2(self.name, id=self._id)


class ActionWordType(str, Enum):
    noun = "noun"
    verb = "verb"
    single_noun = "single_noun"


def police_action_dropdown(html_id, /, *, word_type: ActionWordType):
    return dcc.Dropdown(
        options=[
            {"label": getattr(e.value, word_type.value), "value": e.value.value}
            for e in PoliceAction
        ],
        placeholder="actions",
        id=html_id,
        value=PoliceAction.stop.value.value,
        style={"display": "inline-block", "width": "100px"},
    )


def demographic_dropdown(html_id, plural: bool = False):
    suffix = "s" if plural else ""
    return dcc.Dropdown(
        placeholder="demographic-category",
        options=[
            {"label": (d.value + suffix).lower(), "value": d.value}
            for d in sorted(DemographicCategory)
        ],
        value=DemographicCategory.race.value,
        id=html_id,
        style={"display": "inline-block", "width": "250px"},
    )


def location_dropdown(html_id):
    return dcc.Dropdown(
        placeholder="location",
        options=[
            {"label": "PSA 22-1", "value": "22-1"},
            {"label": "PSA 19-2", "value": "19-2"},
            {"label": "PSA 9-1", "value": "09-1"},
            {"label": "District 22", "value": "22*"},
            {"label": "District 24", "value": "24*"},
            {"label": "NWPD", "value": "NWPD"},
            {"label": "Philadelphia", "value": "*"},
        ],
        value="*",
        id=html_id,
        style={"display": "inline-block", "width": "200px"},
    )


def qyear_dropdown(html_id, /, *, default, how: QuarterHow = QuarterHow.start):
    return dcc.Dropdown(
        placeholder="quarter-year",
        options=[
            {"label": v.month_and_year(how), "value": v.quarter_and_year}
            for v in QUARTERS.values
        ],
        value=default,
        id=html_id,
        style={"display": "inline-block", "width": "150px"},
    )


class TimeAggregationChoice(str, Enum):
    quarter = TimeAggregation.quarter.value
    year = TimeAggregation.year.value

    @classmethod
    def dropdown(cls, /, *, id, default_value="year"):
        return dcc.Dropdown(
            options=[{"label": v.value, "value": v.value} for v in cls],
            value=default_value,
            id=id,
            style={"display": "inline-block", "width": "100px"},
        )
