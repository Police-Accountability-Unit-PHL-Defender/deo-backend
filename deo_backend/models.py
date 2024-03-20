from pydantic import BaseModel
import json
import numpy as np
import os
import sqlite3
from datetime import date
import pandas as pd
from datetime import datetime
from datetime import timedelta
from enum import Enum
from enum import auto
from functools import lru_cache
import deo_backend

SEASON_QUARTER_MAPPING = {
    "Q1": "Jan-Mar",
    "Q2": "Apr-June",
    "Q3": "July-Sept",
    "Q4": "Oct-Dec",
}
SEASON_START_MAPPING = {"Q1": "Jan", "Q2": "Apr", "Q3": "Jul", "Q4": "Oct"}
SEASON_END_MAPPING = {"Q1": "Mar", "Q2": "Jun", "Q3": "Sep", "Q4": "Dec"}

ALL_QUARTERS = pd.date_range(
    "2014-01-01", datetime.now() - timedelta(days=95), freq="QS-JAN", inclusive="left"
)
YEARS = list(range(ALL_QUARTERS[0].year, datetime.now().year))
DEO_YEARS = list(range(2021, datetime.now().year))
MOST_RECENT_QUARTER = f"{ALL_QUARTERS[-1].year}-Q{ALL_QUARTERS[-1].quarter}"
FIRST_QUARTER = f"{ALL_QUARTERS[0].year}-Q{ALL_QUARTERS[0].quarter}"
FOUR_QUARTERS_AGO = f"{ALL_QUARTERS[-4].year}-Q{ALL_QUARTERS[-4].quarter}"

DIVISION_TO_DISTRICTS_MAPPING = {
    "SPD": ["01", "03", "17"],
    "NEPD": ["02", "07", "08", "15", "25"],
    "NWPD": ["05", "14", "35", "39"],
    "CPD": ["06", "09", "22"],
    "SWPD": ["12", "16", "18", "19"],
    "EPD": ["24", "25", "26"],
}

VIOLATION_CATEGORIES_OPERATIONAL = [
    "Failure to Obey Traffic Sign/Light",
    "Improper Pass, Lane, One Way",
    "Improper Turn/Signal",
    "Red Light/Stop Sign/Yield",
    "Speeding/Reckless/Careless Driving",
]
VIOLATION_CATEGORIES_DEO_IMPACTED = [
    "Display License Plate",
    "Inspection/Emission Sticker",
    "Lights",
    "Registration",
    "Windshield Obstruction",
]


def english_comma_separated(lst):
    if len(lst) > 1:
        return ", ".join(lst[:-1]) + " and " + lst[-1]
    elif lst:
        return lst[0]
    return ""


@lru_cache
def df_shootings_raw():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")
    print(f"SQLITE: {sqlite_file} shootings")
    return pd.read_sql(
        "select * from shootings",
        sqlite3.connect(sqlite_file),
    )


@lru_cache
def police_districts_geojson():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    # https://opendata.arcgis.com/datasets/62ec63afb8824a15953399b1fa819df2_0.geojson
    # taken from https://opendataphilly.org/datasets/police-districts/
    return json.load(open(os.path.join(DATA_DIR, "police_districts.geojson"), "r"))


@lru_cache
def hin_sample_locations_df():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")
    print(f"SQLITE: {sqlite_file} hin sample locations")
    df = pd.read_sql(
        "select * from hin_random_sample",
        sqlite3.connect(sqlite_file),
    )
    return df


@lru_cache
def df_raw_by_hin():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")
    print(f"SQLITE: {sqlite_file} raw by hin")
    df = pd.read_sql(
        "select * from car_ped_stops_hin_pct",
        sqlite3.connect(sqlite_file),
    )
    return df


@lru_cache
def hin_geojson():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    print("Loading hin geojson")
    return json.load(open(os.path.join(DATA_DIR, "hin.geojson")))


@lru_cache
def df_raw():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")
    print(f"SQLITE: {sqlite_file} raw")
    df = pd.read_sql(
        "select * from car_ped_stops_quarterly",
        sqlite3.connect(sqlite_file),
    )
    return df


@lru_cache
def df_raw_reasons():
    DATA_DIR = os.path.dirname(deo_backend.__file__)
    sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")
    print(f"SQLITE: {sqlite_file} raw reasons")
    df = pd.read_sql(
        "select * from car_ped_stops_quarterly_reason",
        sqlite3.connect(sqlite_file),
    )
    return df


class TimeAggregation(str, Enum):
    quarter = "quarter"
    year = "year"


class DfType(str, Enum):
    stops = "stops"
    stops_by_reason = "stops_by_reason"
    stops_by_hin = "stops_by_hin"


class FilteredDf:
    def __init__(
        self,
        /,
        *,
        location: str = "*",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        df_type: DfType = DfType.stops,
    ):
        self.location = location
        self.start_date = start_date
        self.end_date = end_date
        match df_type:
            case DfType.stops:
                self.df = df_raw()
            case DfType.stops_by_reason:
                self.df = df_raw_reasons()
            case DfType.stops_by_hin:
                self.df = df_raw_by_hin()

        # Location Filtering
        if location == "":
            raise NotImplementedError("If looking for city-wide, replace with '*'")
        if location == "*":
            self.geography = Geography()
        elif location in DIVISION_TO_DISTRICTS_MAPPING:
            self.geography = Geography(division=location)
            self.df = self.df.query(self.geography.query)
        else:
            location_list = location.rstrip("*").split("-")
            district = location_list[0]
            psa = location_list[1] if len(location_list) > 1 else None
            self.geography = Geography(district=district, psa=psa)
            self.df = self.df.query(self.geography.query)

        # Time Filtering
        if start_date or end_date:
            self.quarters = Quarters(start_date=start_date, end_date=end_date)

            # Graph1
            self.df = self.df[self.df.quarter.isin(self.quarters.year_quarters)]
            if self.df.empty:
                raise ValueError("Df is empty")
        else:
            self.quarters = Quarters()

        self.date_range_str = (
            f"{self.quarters.start_str} through {self.quarters.end_str}"
        )
        self.date_range_str_long = f"the start of {self.quarters.start_str} through the end of {self.quarters.end_str}"

    def get_date_range_str_long(self, time_aggregation: TimeAggregation):
        match time_aggregation:
            case TimeAggregation.year:
                return f"the start of {self.quarters.years[0]} through the end of {self.quarters.years[-1]}"
            case TimeAggregation.quarter:
                return self.date_range_str_long

    def get_date_range_str(self, time_aggregation: TimeAggregation):
        match time_aggregation:
            case TimeAggregation.year:
                return f"{self.quarters.years[0]} through {self.quarters.years[-1]}"
            case TimeAggregation.quarter:
                return self.date_range_str

    def get_avg_monthly_value(self, police_action):
        total = self.df[police_action.sql_column].sum()
        num_quarters = len(self.df.quarter.unique())
        return int(np.round(total / num_quarters / 3))


class QuarterHow(str, Enum):
    start = auto()
    end = auto()


class Quarters:
    def __init__(self, start_date: date | None = None, end_date: date | None = None):
        self.start_date = start_date
        self.end_date = end_date
        self.values = (
            [
                Quarter(q)
                for q in ALL_QUARTERS
                if (start_date and q >= pd.to_datetime(start_date))
                and (end_date and q <= pd.to_datetime(end_date))
            ]
            if start_date and end_date
            else [Quarter(q) for q in ALL_QUARTERS]
        )
        quarters_str_list = [x.quarter_str for x in self.values]
        self.quarters_str = ",".join([f"'{quarter}'" for quarter in quarters_str_list])
        self.year_quarters = [x.quarter_and_year for x in self.values]
        self.num = len(self.year_quarters)
        self.year_seasons = [x.season_and_year for x in self.values]
        self.start_str = self.values[0].month_and_year(how=QuarterHow.start)
        self.end_str = self.values[-1].month_and_year(how=QuarterHow.end)
        self.years = [x.year for x in self.values]


class Quarter:
    def __init__(self, dt):
        self.dt = dt
        self.quarter_str = dt.isoformat() + "Z"
        self.quarter_and_year = f"{dt.year}-Q{dt.quarter}"
        self.season_and_year = SEASON_QUARTER_MAPPING[f"Q{dt.quarter}"] + f" {dt.year}"
        self.year = dt.year

    def month_and_year(self, how: QuarterHow):
        match how:
            case QuarterHow.start:
                return SEASON_START_MAPPING[f"Q{self.dt.quarter}"] + f" {self.dt.year}"
            case QuarterHow.end:
                return SEASON_END_MAPPING[f"Q{self.dt.quarter}"] + f" {self.dt.year}"
            case _:
                raise NotImplementedError(how)

    @staticmethod
    def year_quarter_to_year_season(quarter_year):
        year, quarter = quarter_year.split("-")
        return f"{SEASON_QUARTER_MAPPING[quarter]} {year}"


class PoliceActionName(str, Enum):
    stop = "stop"
    search = "search"
    frisk = "frisk"
    intrusion = "intrusion"


class PoliceActionType(BaseModel):
    sql_column: str
    past_tense: str
    verb: str
    noun: str
    single_noun: str
    value: PoliceActionName


stop = PoliceActionType(
    sql_column="n_stopped",
    noun="traffic stops",
    past_tense="stopped",
    verb="stop",
    single_noun="stop",
    value=PoliceActionName.stop,
)
frisk = PoliceActionType(
    sql_column="n_frisked",
    noun="frisks",
    past_tense="frisked",
    verb="frisk",
    single_noun="frisk",
    value=PoliceActionName.frisk,
)
search = PoliceActionType(
    sql_column="n_searched",
    noun="searches",
    past_tense="searched",
    verb="search",
    single_noun="search",
    value=PoliceActionName.search,
)
intrusion = PoliceActionType(
    sql_column="n_intruded",
    noun="intrusions",
    past_tense="intruded",
    verb="intrude",
    single_noun="intrusion",
    value=PoliceActionName.intrusion,
)


class PoliceAction(Enum):
    stop = stop
    search = search
    frisk = frisk
    intrusion = intrusion

    @staticmethod
    def from_noun(noun: str):
        matching_action = [e.value for e in PoliceAction if e.value.noun == noun]
        if len(matching_action) != 1:
            raise ValueError(f"{noun} is not a valid action")
        return matching_action[0]

    @staticmethod
    def from_verb(verb: str):
        matching_action = [e.value for e in PoliceAction if e.value.verb == verb]
        if len(matching_action) != 1:
            raise ValueError(f"{verb} is not a valid action")
        return matching_action[0]

    @staticmethod
    def from_value(value: str):
        matching_action = [e.value for e in PoliceAction if e.value.value == value]
        if len(matching_action) != 1:
            raise ValueError(f"{value} is not a valid action")
        return matching_action[0]


class PolicePostStopAction(Enum):
    frisk = frisk
    search = search
    intrusion = intrusion

    @staticmethod
    def from_noun(noun: str):
        matching_action = [
            e.value for e in PolicePostStopAction if e.value.noun == noun
        ]
        if len(matching_action) != 1:
            raise ValueError(f"{noun} is not a valid action")
        return matching_action[0]

    @staticmethod
    def from_verb(verb: str):
        matching_action = [
            e.value for e in PolicePostStopAction if e.value.verb == verb
        ]
        if len(matching_action) != 1:
            raise ValueError(f"{verb} is not a valid action")
        return matching_action[0]


class RacialGroup(str, Enum):
    asian = "Asian"
    black = "Black"
    latino = "Latino"
    white = "White"
    other_race = "All Other Races"


class AgeGroup(str, Enum):
    less_than_twenty_five = "Under 25"
    twenty_five_to_thirty_four = "25-34"
    thirty_five_to_fourty_four = "35-44"
    fourty_five_to_fifty_four = "45-54"
    fifty_five_to_sixty_four = "55-64"
    more_than_sixty_five = "65+"


class GenderGroup(str, Enum):
    male = "Male"
    female = "Female"


class DemographicCategory(str, Enum):
    race = "Race"
    gender = "Gender"
    age_range = "Age Range"

    @property
    def order_of_group(self):
        match self:
            case DemographicCategory.age_range:
                return [v.value for v in AgeGroup]
            case DemographicCategory.gender:
                return [v.value for v in GenderGroup]
            case DemographicCategory.race:
                return [v.value for v in RacialGroup]

    @property
    def default_value(self):
        match self:
            case DemographicCategory.age_range:
                return AgeGroup.thirty_five_to_fourty_four
            case DemographicCategory.gender:
                return GenderGroup.female
            case DemographicCategory.race:
                return RacialGroup.white


class DemographicChoice(BaseModel):
    gender: GenderGroup | None
    race: RacialGroup | None
    age_range: AgeGroup | None

    @property
    def phrase(self):
        return f"{self.race} {self.gender}s aged {self.age_range}".lower()

    @property
    def query(self):
        queries = []
        if self.gender:
            queries.append(f"gender=='{self.gender}'")
        if self.age_range:
            queries.append(f"age_range=='{self.age_range}'")
        if self.race:
            queries.append(f"race=='{self.race}'")
        return "&".join(queries)


class DemographicChoices(list[DemographicChoice]):
    @property
    def query(demographic_choices):
        return "|".join([f"({choice.query})" for choice in demographic_choices])


class Geography(BaseModel):
    division: str | None = None
    district: str | None = None
    psa: str | None = None

    # root_validator: district can't be None if psa is not None

    @property
    def query(self):
        queries = []
        if self.division:
            districts = ",".join(
                [
                    f"'{district}'"
                    for district in DIVISION_TO_DISTRICTS_MAPPING.get(self.division, [])
                ]
            )
            queries.append(f"districtoccur in ({districts})")
        else:
            if self.district:
                queries.append(f"districtoccur=='{self.district}'")
            if self.psa:
                queries.append(f"psa=='{self.psa}'")
        return "&".join(queries) if queries else "tuple()"

    @property
    def string(self):
        if self.psa is not None:
            return f"PSA {self.district}-{self.psa}"
        elif self.district is not None:
            return f"District {self.district}"
        elif self.division is not None:
            return f"Division {self.division}"
        else:
            return "Philadelphia"


QUARTERS = Quarters()


before_deo_filter = FilteredDf(
    location="*", start_date="2021-01-01", end_date="2021-12-31"
)
after_deo_filter = FilteredDf(
    location="*", start_date="2022-04-01", end_date="2023-03-31"
)
before_deo_filter_hin = FilteredDf(
    location="*",
    start_date="2021-01-01",
    end_date="2021-12-31",
    df_type=DfType.stops_by_hin,
)
after_deo_filter_hin = FilteredDf(
    location="*",
    start_date="2022-04-01",
    end_date="2023-03-31",
    df_type=DfType.stops_by_hin,
)
