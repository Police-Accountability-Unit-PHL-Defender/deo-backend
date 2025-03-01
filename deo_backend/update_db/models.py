from pydantic import BaseModel
from shapely import wkb
import json
from rtree import index
from shapely.geometry import shape
from collections import defaultdict

from tqdm import tqdm

import zipfile
import io
import os

from datetime import datetime, date
import sqlite3
import pandas as pd

import requests


def get_quarter_start_date(quarter_str):
    # Extract the year and quarter
    year, quarter = quarter_str.split("-Q")
    year = int(year)
    quarter = int(quarter)

    # Map quarters to their starting months
    quarter_start_month = {1: 1, 2: 4, 3: 7, 4: 10}

    # Get the starting month for the quarter
    start_month = quarter_start_month[quarter]

    # Return the start date as a string in YYYY-MM-DD format
    return f"{year}-{start_month:02d}-01"


def get_previous_quarter(dt):
    # Get today's date

    # Calculate the current quarter
    current_quarter = (dt.month - 1) // 3 + 1

    # Determine the previous quarter
    if current_quarter == 1:
        # If current quarter is Q1, the previous quarter is Q4 of the last year
        previous_quarter = 4
        year = dt.year - 1
    else:
        # Otherwise, subtract one quarter within the same year
        previous_quarter = current_quarter - 1
        year = dt.year

    return f"{year}-Q{previous_quarter}"


# Used to get dtype dict
def get_pandas_dtype_and_parse_dates(query):
    response = requests.get(f"https://phl.carto.com/api/v2/sql?q={query} limit 0")
    schema = response.json()["fields"]

    def convert_to_pandas_dtype(schema):
        dtype_map = {
            "int4": "int32",
            "int8": "int64",
            "text": "str",
            "numeric": "float",
            # Add more mappings as needed
        }

        parse_dates = []  # list to keep track of date columns
        dtype_dict = {}  # dict to hold the resulting dtype mappings

        for column, info in schema.items():
            if info["type"] in ["geometry", "string"]:
                dtype_dict[column] = "str"
            elif info["type"] == "number":
                dtype_dict[column] = dtype_map.get(
                    info["pgtype"], "float"
                )  # Default to float if not specified
            elif info["type"] == "date":
                parse_dates.append(
                    column
                )  # Add to parse_dates list for later use with pandas
            else:
                raise ValueError(column, info)
        return dtype_dict, parse_dates

    return convert_to_pandas_dtype(schema)


def get_q_end_from_q_start_str(q_start_str):
    q_start = pd.to_datetime(q_start_str)
    if q_start.month in [1, 2, 3]:
        q_end = datetime.combine(date(q_start.year, 3, 31), datetime.max.time())
    elif q_start.month in [4, 5, 6]:
        q_end = datetime.combine(date(q_start.year, 6, 30), datetime.max.time())
    elif q_start.month in [7, 8, 9]:
        q_end = datetime.combine(date(q_start.year, 9, 30), datetime.max.time())
    else:
        q_end = datetime.combine(date(q_start.year, 12, 31), datetime.max.time())
    return q_end


GEOJSON_PSA = json.load(open("deo_backend/maps/police_psas.geojson"))

idx = index.Index()
polygons = []
for pos, feature in enumerate(GEOJSON_PSA["features"]):
    polygon = shape(feature["geometry"])
    polygons.append(
        (polygon, feature["properties"])
    )  # Store the polygon and its properties
    idx.insert(pos, polygon.bounds)  # Insert polygon bounds into the spatial index


# Function to find the feature containing a point
def find_new_psa(point):
    matches = list(idx.intersection(point.bounds))
    for match in matches:
        polygon, properties = polygons[match]
        if polygon.contains(point):
            return properties["PSA_NUM"][-1]
    return "-1"


class TableFromZip(BaseModel):
    name: str
    dtype_dict: dict[str, str]
    dtype_query: str
    dt_col: str
    district_col: str = "districtoccur"
    psa_col: str | None = "psa"
    processing_query: str
    regroupby_cols: list[str]

    @property
    def filename_prefix(self):
        return self.name + "_year"

    def fetch_updated_dtype_dict_using_query(self):
        return get_pandas_dtype_and_parse_dates(self.dtype_query)

    def get_sorted_csvs_with_prefix(self, filenames):
        return sorted([f for f in filenames if f.endswith(".csv") and self.name in f])

    def get_processing_query(self, most_recent_quarter_start_dt):
        most_recent_quarter_end_dt = get_q_end_from_q_start_str(
            most_recent_quarter_start_dt
        )
        return self.processing_query.format(
            most_recent_quarter_end_dt=most_recent_quarter_end_dt
        )

    def get_single_csv_from_other_zip_file(self, zip_filename, csv_filename):
        with open(zip_filename, "rb") as file:
            zip_data = file.read()
            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z:
                csv_files = self.get_sorted_csvs_with_prefix(z.namelist())
                for available_filename in csv_files:
                    # in case the zip structure changed
                    if os.path.basename(available_filename) == os.path.basename(
                        csv_filename
                    ):
                        with z.open(available_filename) as csv_file:
                            return pd.read_csv(
                                csv_file,
                                dtype=self.dtype_dict,
                                parse_dates=[self.dt_col],
                            )

    def process_csv_file(
        self,
        z,
        filename,
        /,
        *,
        zip_filename_override,
        most_recent_quarter_start_dt,
        remap_districts: bool = True,
    ):
        filename_raw = os.path.basename(filename)
        if zip_filename_override:
            print(f"Overriding for {zip_filename_override}: {filename_raw}")
            this_df = self.get_single_csv_from_other_zip_file(
                zip_filename_override, filename
            )
        else:
            with z.open(filename) as csv_file:
                this_df = pd.read_csv(
                    csv_file, dtype=self.dtype_dict, parse_dates=[self.dt_col]
                )
        this_df[f"{self.dt_col}_local"] = (
            this_df[self.dt_col].dt.tz_convert("America/New_York").dt.tz_localize(None)
        )

        # Dramatically improves speed for some reason.
        this_df["id"] = this_df.index
        this_df = this_df.sort_values("id").reset_index(drop=True)
        con = sqlite3.connect(":memory:")

        if remap_districts:
            districtoccurs = []
            psas = []
            for row in this_df.itertuples():
                if getattr(row, self.district_col) in ["06", "09"]:
                    # map districts 6 and 9 to 9
                    districtoccur = "09"
                elif getattr(row, self.district_col) in ["6", "9"]:
                    # map districts 6 and 9 to 9
                    districtoccur = "9"
                else:
                    districtoccur = getattr(row, self.district_col)
                districtoccurs.append(districtoccur)

            this_df = this_df.rename(
                columns={self.district_col: f"old_{self.district_col}"}
            )
            this_df[self.district_col] = districtoccurs

            if self.psa_col:
                for row in this_df.itertuples():
                    if getattr(row, self.district_col) in ["06", "09", "6", "9"]:
                        if (
                            getattr(row, self.district_col) in ["06", "6"]
                            and getattr(row, self.psa_col) == "1"
                        ):
                            # 061 got directly mapped to 092
                            psa = "2"
                        else:
                            point = wkb.loads(row.the_geom, hex=True)
                            psa = find_new_psa(point)
                    else:
                        psa = row.psa
                    psas.append(psa)

                this_df = this_df.rename(columns={self.psa_col: f"old_{self.psa_col}"})
                this_df[self.psa_col] = psas

        this_df.to_sql(self.name, if_exists="replace", con=con)

        return pd.read_sql(
            self.get_processing_query(most_recent_quarter_start_dt), con=con
        )


CarPedStops = TableFromZip(
    name="car_ped_stops",
    dtype_dict={
        "cartodb_id": "int64",
        "the_geom": "str",  # Special handling might be required for geometry
        "the_geom_webmercator": "str",  # Special handling might be required for geometry
        "objectid": "int32",
        "id": "int32",
        "weekday": "str",
        "location": "str",
        "districtoccur": "str",
        "psa": "str",
        "stopcode": "int32",
        "stoptype": "str",
        "inside_or_outside": "str",
        "gender": "str",
        "race": "str",
        "age": "float",
        "individual_frisked": "float",
        "individual_searched": "float",
        "individual_arrested": "float",
        "individual_contraband": "float",
        "vehicle_frisked": "float",
        "vehicle_searched": "float",
        "vehicle_contraband": "float",
        "vehicle_contraband_list": "str",
        "individual_contraband_list": "str",
        "mvc_code": "str",
        "mvc_reason": "str",
        "mvc_code_sec": "str",
        "mvc_code_sec_reason": "str",
        "point_x": "float64",  # Adjusted to 'float64' for numeric
        "point_y": "float64",  # Adjusted to 'float64' for numeric
    },
    dt_col="datetimeoccur",
    dtype_query="select * from car_ped_stops",
    processing_query="""
        SELECT
        (
            strftime('%Y', datetimeoccur_local) || '-' ||
            CASE
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '01' AND '03' THEN '01'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '04' AND '06' THEN '04'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '07' AND '09' THEN '07'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '10' AND '12' THEN '10'
            END || '-01T00:00:00.000000Z'
        ) AS quarter,
        CAST(strftime('%Y', datetimeoccur_local) as int) as year,
        --Replace Above with Postgres equivalents (using extract())
        districtoccur, 
        psa,
        violation_category,
        race as "Race", 
        gender as "Gender", 
        age_range as "Age Range",
        count(*) as n_stopped, 
        sum(n_people_in_car) as n_people_in_stopped_vehicles,
        sum(was_searched) as n_searched,
        sum(was_arrested) as n_arrested,
        sum(was_found_with_contraband) as n_contraband,
        sum(was_frisked) as n_frisked,
        sum(was_intruded) as n_intruded
        FROM (
            SELECT 
            stop.*, driver.race, driver.age_range, driver.gender,datetimeoccur_local, n_people_in_car,
            CASE
                WHEN 
                    (mvc_code_clean LIKE '1332%' AND mvc_code_clean LIKE '%A%' AND mvc_code_clean NOT LIKE '1332AI%') 
                THEN 'Display License Plate'
                WHEN 
                    (mvc_code_clean = '3111') OR
                    (mvc_code_clean LIKE '3111%' AND mvc_code_clean LIKE '%A%')
                THEN 'Failure to Obey Traffic Sign/Light'   
                WHEN
                    (mvc_code_clean LIKE '330%') OR
                    (mvc_code_clean LIKE '3311%' AND mvc_code_clean LIKE '%A%') OR
                    (mvc_code_clean LIKE '3313%') OR
                    (mvc_code_clean LIKE '3315%') OR
                    (mvc_code_clean LIKE '3703%')
                THEN 'Improper Pass, Lane, One Way'  
                WHEN 
                    (mvc_code_clean LIKE '3331%') OR
                    (mvc_code_clean LIKE '3332%') OR
                    (mvc_code_clean LIKE '3334%' AND mvc_code_clean LIKE '%A%') OR
                    (mvc_code_clean LIKE '3334%' AND mvc_code_clean LIKE '%B%') OR
                    (mvc_code_clean LIKE '3335%') OR
                    (mvc_code_clean LIKE '3336%') 
                THEN 'Improper Turn/Signal'
                WHEN 
                    (mvc_code_clean LIKE '4703%') OR
                    (mvc_code_clean LIKE '4706%' AND mvc_code_clean LIKE '%C%')
                THEN 'Inspection/Emission Sticker'   
                WHEN 
                    (mvc_code_clean LIKE '4301%') OR
                    (mvc_code_clean LIKE '4302%') OR
                    (mvc_code_clean LIKE '4303%') OR
                    (mvc_code_clean = '4306') 
                THEN 'Lights'
                WHEN 
                    (mvc_code_clean LIKE '3112%') OR
                    (mvc_code_clean LIKE '3321%') OR
                    (mvc_code_clean LIKE '3322%') OR
                    (mvc_code_clean LIKE '3323%') OR
                    (mvc_code_clean LIKE '3324%') OR
                    (mvc_code_clean LIKE '3325%') OR
                    (mvc_code_clean LIKE '3342%' AND mvc_code_clean LIKE '%A%') OR
                    (mvc_code_clean LIKE '3345%' AND mvc_code_clean LIKE '%A%') OR
                    (mvc_code_clean LIKE '3542%') OR
                    (mvc_code_clean LIKE '3710%')
                THEN 'Red Light/Stop Sign/Yield'
                WHEN 
                    (mvc_code_clean LIKE '1301%' and mvc_code_clean LIKE '%A%') 
                THEN 'Registration'
                WHEN (mvc_code_clean LIKE '3361%') OR
                     (mvc_code_clean LIKE '3362%') OR
                     (mvc_code_clean LIKE '3363%') OR
                     (mvc_code_clean LIKE '3365%') OR
                     (mvc_code_clean LIKE '3367%') OR
                     (mvc_code_clean LIKE '3714%') OR
                     (mvc_code_clean LIKE '3736%') 
                THEN 'Speeding/Reckless/Careless Driving'
                WHEN
                    (mvc_code_clean LIKE '4524%' AND mvc_code_clean NOT LIKE '%A%')
                THEN 'Tint'
                WHEN 
                    (mvc_code_clean LIKE '4524%' AND mvc_code_clean LIKE '%A%')
                THEN 'Windshield Obstruction'
                WHEN mvc_code_clean is not null THEN 'Other'
                ELSE 'None'
            END AS violation_category
            FROM (
                    SELECT car_ped_stops.datetimeoccur as datetimeoccur_d,location as location_d,gender, 
                    n_people_in_car,
                    CASE
                        WHEN race = 'Black - Latino' THEN 'Latino'
                        WHEN race = 'White - Latino' THEN 'Latino'
                        WHEN race = 'White - Non-Latino' THEN 'White'
                        WHEN race = 'Black - Non-Latino' THEN 'Black'
                        WHEN race = 'Asian' THEN 'Asian'
                        WHEN race = 'American Indian' THEN 'All Other Races'
                        WHEN race = 'Unknown' THEN 'All Other Races'
                        ELSE race
                    END as race,
                    CASE
                        WHEN age <25 THEN 'Under 25'
                        WHEN age <35 THEN '25-34'
                        WHEN age <45 THEN '35-44'
                        WHEN age <55 THEN '45-54'
                        WHEN age < 65 THEN '55-64'
                        ELSE '65+'
                    END as age_range
                    FROM (
                        SELECT location as driverl, min(id) as id, count(*) as n_people_in_car
                        FROM car_ped_stops
                        where stoptype='vehicle'
                        GROUP by datetimeoccur, location
                    ) inner_driver
                    LEFT JOIN car_ped_stops
                    ON inner_driver.id = car_ped_stops.id
                ) driver
            LEFT JOIN (
                SELECT datetimeoccur as datetimeoccur_utc, datetimeoccur_local, 
                location, min(districtoccur) as districtoccur, min(psa) as psa,
                CASE 
                    WHEN sum(individual_searched) > 0 or sum(vehicle_searched) > 0 
                    THEN 1 ELSE 0 
                END as was_searched,
                CASE 
                    WHEN sum(individual_arrested) > 0 
                    THEN 1 ELSE 0 
                END as was_arrested,
                CASE 
                    WHEN sum(individual_contraband) > 0 or sum(vehicle_contraband) > 0 
                    THEN 1 ELSE 0 
                END as was_found_with_contraband,
                CASE
                    WHEN sum(individual_frisked) > 0 or sum(vehicle_frisked) > 0 
                    THEN 1 ELSE 0 
                END as was_frisked,
                CASE
                    WHEN
                        sum(individual_frisked) > 0 or sum(vehicle_frisked) > 0
                        or sum(individual_searched) > 0 or sum(vehicle_searched) > 0
                    THEN 1 ELSE 0
                END as was_intruded,
                UPPER(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(max(mvc_code),'i','1'),
                                '(', ''),
                            ')', ''),
                        '-',''),
                    ' ','')
                ) as mvc_code_clean
                FROM car_ped_stops
                WHERE stoptype='vehicle'
                GROUP by datetimeoccur_utc, location
            ) stop
            ON stop.datetimeoccur_utc=driver.datetimeoccur_d
            AND stop.location=driver.location_d
        ) query
        WHERE datetimeoccur_local  <= '{most_recent_quarter_end_dt}'
        GROUP by districtoccur,psa, quarter,race, gender, age_range, violation_category
        """,
    regroupby_cols=[
        "districtoccur",
        "psa",
        "quarter",
        "Race",
        "Gender",
        "Age Range",
        "violation_category",
    ],
)


CarPedStopsOnHin = TableFromZip(
    name="car_ped_stops_on_hin",
    dtype_dict={
        "cartodb_id": "int64",
        "the_geom": "str",
        "the_geom_webmercator": "str",
        "objectid": "int32",
        "id": "int32",
        "weekday": "str",
        "location": "str",
        "districtoccur": "str",
        "psa": "str",
        "stopcode": "int32",
        "stoptype": "str",
        "inside_or_outside": "str",
        "gender": "str",
        "race": "str",
        "age": "float",  # had to manually update this, I think the CSV downloader converts it from int
        "individual_frisked": "int32",
        "individual_searched": "int32",
        "individual_arrested": "int32",
        "individual_contraband": "int32",
        "vehicle_frisked": "int32",
        "vehicle_searched": "int32",
        "vehicle_contraband": "int32",
        "vehicle_contraband_list": "str",
        "individual_contraband_list": "str",
        "mvc_code": "str",
        "mvc_reason": "str",
        "mvc_code_sec": "str",
        "mvc_code_sec_reason": "str",
        "point_x": "float",
        "point_y": "float",
        "n_stopped_locatable_on_hin": "int32",
        "n_stopped_locatable": "int32",
    },
    dt_col="datetimeoccur",
    dtype_query="""
        SELECT 
        car_ped_stops.*,
        (CASE WHEN hin.street_name is not null 
        AND st_y(car_ped_stops.the_geom)<42 and car_ped_stops.the_geom is not null
        THEN 1 ELSE 0 END
        ) as n_stopped_locatable_on_hin,
        (
        case when st_y(car_ped_stops.the_geom)<42 and car_ped_stops.the_geom is not null then 1 else 0 end
        ) as n_stopped_locatable
        FROM car_ped_stops
        LEFT JOIN high_injury_network_2020 hin
        ON ST_DWithin(car_ped_stops.the_geom, hin.the_geom, 0) -- dont return any joined results
        """,
    processing_query="""
        SELECT
        (
            strftime('%Y', datetimeoccur_local) || '-' ||
            CASE
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '01' AND '03' THEN '01'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '04' AND '06' THEN '04'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '07' AND '09' THEN '07'
              WHEN strftime('%m', datetimeoccur_local) BETWEEN '10' AND '12' THEN '10'
            END || '-01T00:00:00.000000Z'
        ) AS quarter,
        CAST(strftime('%Y', datetimeoccur_local) as int) as year,
        districtoccur, 
        psa,
        sum(n_stopped_locatable_on_hin) as n_stopped_locatable_on_hin,
        sum(n_stopped_locatable) as n_stopped_locatable
        FROM car_ped_stops_on_hin
        WHERE datetimeoccur_local  <= '{most_recent_quarter_end_dt}'
        GROUP BY districtoccur,psa, quarter, year
        """,
    regroupby_cols=[
        "districtoccur",
        "psa",
        "quarter",
        "year",
    ],
)

Shootings = TableFromZip(
    dt_col="date_",
    district_col="dist",
    psa_col=None,
    name="shootings",
    dtype_dict={
        "cartodb_id": "int64",
        "the_geom": "str",
        "the_geom_webmercator": "str",
        "objectid": "float",
        "year": "float",
        "dc_key": "str",
        "code": "str",
        "time": "str",
        "race": "str",
        "sex": "str",
        "age": "str",
        "wound": "str",
        "officer_involved": "str",
        "offender_injured": "str",
        "offender_deceased": "str",
        "location": "str",
        "latino": "float",
        "point_x": "float",
        "point_y": "float",
        "dist": "str",
        "inside": "float",
        "outside": "float",
        "fatal": "float",
    },
    dtype_query="select * from shootings",
    processing_query="""select
        count(*) as n_shootings,
        sum(case WHEN inside='0' THEN 1 else 0 END) as n_outside,
        printf('%02d', dist) AS districtoccur,
         (
            strftime('%Y', date__local) || '-' ||
            CASE
              WHEN strftime('%m', date__local) BETWEEN '01' AND '03' THEN '01'
              WHEN strftime('%m', date__local) BETWEEN '04' AND '06' THEN '04'
              WHEN strftime('%m', date__local) BETWEEN '07' AND '09' THEN '07'
              WHEN strftime('%m', date__local) BETWEEN '10' AND '12' THEN '10'
            END || '-01T00:00:00.000000Z'
        ) AS quarter
        from shootings
        WHERE date__local  <= '{most_recent_quarter_end_dt}'
        group by quarter, dist
        order by quarter,dist""",
    regroupby_cols=[
        "quarter",
        "districtoccur",
    ],
)


class ProcessZip(BaseModel):
    data_dir: str
    zip_filename: str
    most_recent_quarter_override: str | None = None
    zip_filename_override_dict: dict[str, str] = {}
    remap_districts: bool = True

    @property
    def zip_filepath(self):
        return os.path.join(self.data_dir, self.zip_filename)

    @property
    def db_name(self):
        # car_ped_stops_2024-03-16T20_22_24.zip -> 2014_03_16
        return (
            self.zip_filename.replace("car_ped_stops_", "")
            .split("T")[0]
            .replace("-", "_")
        )

    def get_df_quarterly_reason_from_zipfiles(self):
        with open(self.zip_filepath, "rb") as file:
            zip_data = file.read()
        dfs = defaultdict(pd.DataFrame)
        print(self.zip_filename)
        with zipfile.ZipFile(io.BytesIO(zip_data), "r") as z:
            if not self.most_recent_quarter_override:
                most_recent_quarters = {}
                # Assumes the folder structure is csv/{table}. If there are any other folders, this will not work.
                # Pulls the most recent quarter from the summary.json file for each table
                # which has a last_dt field.
                # So if the last_dt for all tables in something like 2024-12-05, it will use 2024-Q3
                tables = [
                    f[:-1]
                    for f in z.namelist()
                    if f.replace("csvs/", "").endswith("/") and f.startswith("csvs/")
                ]
                for table in tables:
                    if os.path.join(table, "summary.json") in z.namelist():
                        summary = json.load(z.open(os.path.join(table, "summary.json")))
                        if not summary.get("last_dt", None):
                            raise ValueError(
                                f"'last_dt' not found in {table}/summary.json"
                            )
                        most_recent_quarter = get_previous_quarter(
                            pd.to_datetime(summary["last_dt"])
                        )
                    else:
                        raise ValueError(
                            f"File {table}/summary.json not found so most recent quarter can't be guessed. You must set the most recent quarter to use."
                            + f" You might want to add the following cli option: `--most-recent-quarter-override '{get_previous_quarter(datetime.today())}'`"
                        )

                    most_recent_quarters[table] = most_recent_quarter
                unique_quarters = set(
                    [most_recent_quarters.get(table, None) for table in tables]
                )
                if len(unique_quarters) > 1:
                    raise ValueError(
                        f"Multiple unique quarter starts found: {unique_quarters}"
                    )
                elif len(unique_quarters) == 0:
                    raise ValueError(
                        f"No unique quarter starts found for tables {tables}"
                    )
                else:
                    most_recent_quarter = list(unique_quarters)[0]
                    print(
                        "Most recent quarter found in data backup:", most_recent_quarter
                    )
            else:
                most_recent_quarter = self.most_recent_quarter_override

            print(f"Using {most_recent_quarter}")
            csv_files = sorted([f for f in z.namelist() if f.endswith(".csv")])
            pbar = tqdm(total=len(csv_files))
            for filename in csv_files:
                pbar.set_description(filename)
                zip_filename_override = self.zip_filename_override_dict.get(
                    os.path.basename(filename)
                )
                zip_filename_override = (
                    os.path.join(self.data_dir, zip_filename_override)
                    if zip_filename_override
                    else None
                )
                if CarPedStops.filename_prefix in filename:
                    table_from_zip = CarPedStops
                elif CarPedStopsOnHin.filename_prefix in filename:
                    table_from_zip = CarPedStopsOnHin
                elif Shootings.filename_prefix in filename:
                    table_from_zip = Shootings
                else:
                    raise NotImplementedError(
                        f"{filename} doesn't have a matching prefix to one of the tables."
                    )

                df = table_from_zip.process_csv_file(
                    z,
                    filename,
                    zip_filename_override=zip_filename_override,
                    most_recent_quarter_start_dt=get_quarter_start_date(
                        most_recent_quarter
                    ),
                    remap_districts=self.remap_districts,
                )
                dfs[table_from_zip.name] = (
                    pd.concat([dfs[table_from_zip.name], df])
                    .groupby(table_from_zip.regroupby_cols)
                    .sum()
                    .reset_index()
                )
                pbar.update()
        return dfs, most_recent_quarter
