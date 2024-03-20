import sqlite3
from tqdm import tqdm
import json
import os
import pandas as pd
import httpx
import requests
from datetime import datetime


import deo_backend

DATA_DIR = os.path.dirname(deo_backend.__file__)
sqlite_file = os.path.join(DATA_DIR, "open_data_philly.db")

MOST_RECENT_QUARTER_END_DT = datetime.combine(
    pd.date_range(
        "2015-01-01",
        datetime.now(),
        freq="Q-DEC",
    )[-1],
    datetime.max.time(),
)


def make_request(sql: str):
    with httpx.Client(timeout=90) as client:
        response = client.post("https://phl.carto.com/api/v2/sql", data={"q": sql})
        try:
            json = response.json()
            breakpoint()
        except Exception:
            raise ValueError(response.text)
        if "rows" not in json:
            raise ValueError(f"{sql}\n\n{json}")
        return json


"""
--- This shows that 0.0001 is between 8.54427772 and 11.10338786 meters
SELECT ST_Distance(
    ST_GeographyFromText('SRID=4326;POINT(' || -75.14144069 || ' ' || 39.96071159 || ')'),
    ST_GeographyFromText('SRID=4326;POINT(' || (-75.14144069 + 0.0001) || ' ' || 39.96071159 || ')')
) AS distance_in_meters_lng,
ST_Distance(
    ST_GeographyFromText('SRID=4326;POINT(' || -75.14144069 || ' ' || 39.96071159 || ')'),
    ST_GeographyFromText('SRID=4326;POINT(' || (-75.14144069) || ' ' || 39.96071159  + 0.0001 || ')')
) AS distance_in_meters_lat
"""
DIST_FROM_HIN_THRESHOLD = 0.0001


def download_geographies():
    # Get Police Geographies
    # PSA Geographies
    # https://opendataphilly.org/datasets/police-service-areas/
    # https://opendataphilly.org/datasets/police-districts/
    district_url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Boundaries_District/FeatureServer/0/query"
    psa_url = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Boundaries_PSA/FeatureServer/0/query"

    state = "42"  # PA
    county = "101"  # Philly

    params = {"f": "json", "where": "1=1", "returnGeometry": False}
    dist_params = {**params, "outFields": "DIST_NUM,DIV_CODE"}
    psa_params = {**params, "outFields": "PSA_NUM"}

    df_district = pd.DataFrame(
        requests.get(district_url, dist_params).json()["features"]
    )["attributes"].apply(pd.Series)
    df_district["district"] = (
        df_district["DIST_NUM"].astype(str).str.pad(width=2, fillchar="0")
    )
    df_district = df_district.set_index("district")[["DIV_CODE"]]
    df_psa = pd.DataFrame(requests.get(psa_url, psa_params).json()["features"])[
        "attributes"
    ].apply(pd.Series)
    df_psa["district"] = df_psa["PSA_NUM"].str[:2]
    df_psa["psa"] = df_psa["PSA_NUM"].str[2:]
    df_psa = df_psa.set_index("district")

    df_geographies = (
        df_psa.join(df_district)
        .reset_index()
        .rename(columns={"PSA_NUM": "full_psa_num", "DIV_CODE": "division"})[
            ["full_psa_num", "psa", "district", "division"]
        ]
    )
    df_geographies.to_csv(
        f"{DATA_DIR}/demographics/police_geographies.csv", index=False
    )


if __name__ == "__main__":
    # Download the random sampling of stops based on how they are on the HIN
    make_request("select * from car_ped_stops limit 1")
    response_hin = make_request(
        f"""
                SELECT stops.*, hin.street_name is not null as on_hin FROM
                (
                    SELECT * FROM car_ped_stops 
                    where point_y < 42 
                    and extract(year from datetimeoccur) in (
                        '2018','2019','2020','2021','2022','2023'
                    ) 
                    order by random() limit 1000
                ) stops
                LEFT JOIN high_injury_network_2020 hin
                ON ST_DWithin(stops.the_geom, hin.the_geom, {DIST_FROM_HIN_THRESHOLD})
                """
    )
    df_hin = pd.DataFrame(response_hin["rows"])
    df_hin.to_csv(f"{DATA_DIR}/hin_random_sample_1000.csv", index=False)
    # Download the HIN geojson
    response = requests.get(
        "https://phl.carto.com/api/v2/sql?q=SELECT+*+FROM+high_injury_network_2020&filename=high_injury_network_2020&format=geojson&skipfields=cartodb_id"
    )
    geojson = response.json()
    json.dump(geojson, open(f"{DATA_DIR}/hin.geojson", "w"))

    # Download the shootings data

    query = """
        select
        count(*) as n_shootings,
        sum(case WHEN inside='0' THEN 1 else 0 END) as n_outside,
        dist as districtoccur,
        date_trunc('quarter',date_) as quarter_dt
        from shootings
        group by date_trunc('quarter',date_), dist
        order by quarter_dt,dist
    """
    import re

    query = re.sub(r"\s+", " ", query).strip()
    response = requests.get("https://phl.carto.com/api/v2/sql", params={"q": query})
    df_shootings = pd.DataFrame(response.json()["rows"])
    df_shootings["districtoccur"] = (
        df_shootings["districtoccur"].astype(str).str.zfill(2)
    )
    df_shootings["quarter_dt"] = pd.to_datetime(
        df_shootings["quarter_dt"], format="%Y-%m-%dT%H:%M:%SZ"
    )
    df_shootings["quarter"] = (
        df_shootings["quarter_dt"].dt.year.astype(str)
        + "-Q"
        + df_shootings["quarter_dt"].dt.quarter.astype(str)
    )
    df_shootings["quarter_dt_str"] = df_shootings["quarter_dt"].dt.date.apply(
        lambda x: x.isoformat()
    )
    df_shootings.to_csv(f"{DATA_DIR}/shootings.csv", index=False)
    df_shootings.to_sql(
        "shootings",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )

    def per_stop_query_str(*, district: str):
        district_sql = (
            f"AND districtoccur = '{district}' AND psa='1'"
            if district
            else "districtoccur is null"
        )
        return f"""
        SELECT stop.*, driver.race, driver.age_range, driver.gender, 
        datetimeoccur_utc as datetimeoccur -- TODO FIX TO LOCAL TZ
        FROM
         (
            SELECT datetimeoccur as datetimeoccur_d,location as location_d,gender,
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
            END as age_range,
            CASE
                WHEN (mvc_code_clean LIKE '1301%' AND mvc_code_clean NOT LIKE '%A%') OR
                     (mvc_code_clean LIKE '1332%' AND mvc_code_clean NOT LIKE '%A%' AND mvc_code_clean NOT LIKE '1332AI%') 
                THEN 'Display License Plate'
                WHEN (mvc_code_clean IN ('3111')) OR
                     (mvc_code_clean LIKE '3111%' AND mvc_code_clean NOT LIKE '%A%') OR
                     (mvc_code_clean LIKE '3112%') 
                THEN 'Failure to Obey Traffic Sign/Light'
                WHEN (mvc_code_clean LIKE '330%') OR
                     (mvc_code_clean LIKE '3311%' AND mvc_code_clean NOT LIKE '%A%') OR
                     (mvc_code_clean LIKE '3313%') OR
                     (mvc_code_clean LIKE '3315%') OR
                     (mvc_code_clean LIKE '3703%') 
                THEN 'Improper Pass, Lane, One Way'
                WHEN (mvc_code_clean LIKE '3321%') OR
                     (mvc_code_clean LIKE '3322%') OR
                     (mvc_code_clean LIKE '3323%') OR
                     (mvc_code_clean LIKE '3324%') OR
                     (mvc_code_clean LIKE '3325%') OR
                     (mvc_code_clean LIKE '3542%') OR
                     (mvc_code_clean LIKE '3710%') OR
                     ((mvc_code_clean LIKE '3342%' AND mvc_code_clean LIKE '%A%') OR
                     (mvc_code_clean LIKE '3345%' AND mvc_code_clean LIKE '%A%')) 
                THEN 'Red Light/Stop Sign/Yield'
                WHEN (mvc_code_clean LIKE '3331%') OR
                     (mvc_code_clean LIKE '3332%') OR
                     ((mvc_code_clean LIKE '3334%' AND mvc_code_clean LIKE '%A%') OR
                     (mvc_code_clean LIKE '3334%' AND mvc_code_clean LIKE '%B%')) OR
                     (mvc_code_clean LIKE '3335%') OR
                     (mvc_code_clean LIKE '3336%') 
                THEN 'Improper Turn/Signal'
                WHEN (mvc_code_clean LIKE '3361%') OR
                     (mvc_code_clean LIKE '3362%') OR
                     (mvc_code_clean LIKE '3363%') OR
                     (mvc_code_clean LIKE '3365%') OR
                     (mvc_code_clean LIKE '3367%') OR
                     (mvc_code_clean LIKE '3714%') OR
                     (mvc_code_clean LIKE '3736%') 
                THEN 'Speeding/Reckless/Careless Driving'
                WHEN (mvc_code_clean LIKE '4301%') OR
                     (mvc_code_clean LIKE '4302%') OR
                     (mvc_code_clean LIKE '4303%') OR
                     (mvc_code_clean = '4306') 
                THEN 'Lights'
                WHEN ((mvc_code_clean LIKE '4524%' AND mvc_code_clean LIKE '%A%') OR
                     (mvc_code_clean LIKE '4524%' AND mvc_code_clean NOT LIKE '%A%')) 
                THEN 'Windshield Obstruction/Tint'
                WHEN (mvc_code_clean LIKE '4703%') OR
                     ((mvc_code_clean LIKE '4706%' AND mvc_code_clean LIKE '%C%')) 
                THEN 'Inspection/Emission Sticker'
                ELSE 'Other'
            END AS violation_category
            FROM (
                SELECT datetimeoccur as driverdt,location as driverl, min(id) as id
                FROM car_ped_stops
                where stoptype='vehicle'
                {district_sql}
                GROUP by datetimeoccur, location
            ) inner_driver
            LEFT JOIN car_ped_stops
            ON inner_driver.id = car_ped_stops.id
        ) driver
        LEFT JOIN
        (SELECT datetimeoccur as datetimeoccur_utc, the_geom, location, min(districtoccur) as districtoccur, min(psa) as psa,
        CASE WHEN sum(individual_searched) > 0 or sum(vehicle_searched) > 0 THEN 1 ELSE 0 END as was_searched,
        CASE WHEN sum(individual_arrested) > 0 THEN 1 ELSE 0 END as was_arrested,
        CASE WHEN sum(individual_contraband) > 0 or sum(vehicle_contraband) > 0 THEN 1 ELSE 0 END as was_found_with_contraband,
        CASE WHEN sum(individual_frisked) > 0 or sum(vehicle_frisked) > 0 THEN 1 ELSE 0 END as was_frisked,
        max(mvc_code_clean) as mvc_code_clean,
        CASE
            WHEN
                sum(individual_frisked) > 0 or sum(vehicle_frisked) > 0
                or sum(individual_searched) > 0 or sum(vehicle_searched) > 0
            THEN 1 ELSE 0 
        END as was_intruded
        FROM
        (
           select *, UPPER(
            REPLACE(
                REPLACE( 
                    REPLACE(
                        REPLACE(
                            REPLACE(mvc_code,'i','1'), 
                        '(', ''), 
                    ')', ''),
                '-',''),
            ' ','')
            ) as mvc_code_clean from car_ped_stops) car_ped_stops
        where stoptype='vehicle'
        GROUP by datetimeoccur_utc, location, the_geom
        ) stop
        ON stop.datetimeoccur_utc=driver.datetimeoccur_d
        AND stop.location=driver.location_d
        """

    def grouped_query_psa(*, district: str):
        per_stop_query = per_stop_query_str(district=district)
        # This query gives quarterly stop counts over time
        return f"""SELECT 
        (
            strftime('%Y', datetimeoccur) || '-' ||
            CASE
              WHEN strftime('%m', datetimeoccur) BETWEEN '01' AND '03' THEN '01'
              WHEN strftime('%m', datetimeoccur) BETWEEN '04' AND '06' THEN '04'
              WHEN strftime('%m', datetimeoccur) BETWEEN '07' AND '09' THEN '07'
              WHEN strftime('%m', datetimeoccur) BETWEEN '10' AND '12' THEN '10'
            END || '-01T00:00:00.000000Z'
        ) AS quarter,
        districtoccur, psa,
        race as "Race", gender as "Gender", age_range as "Age Range",
        count(*) as n_stopped, mvc_code_clean,
        sum(was_searched) as n_searched, 
        sum(was_arrested) as n_arrested, 
        sum(was_found_with_contraband) as n_contraband, 
        sum(was_frisked) as n_frisked, 
        sum(was_intruded) as n_intruded
        FROM ({per_stop_query}) query 
        WHERE datetimeoccur  <= '{MOST_RECENT_QUARTER_END_DT}'
        GROUP by districtoccur,psa, quarter,race, gender, age_range, mvc_code_clean
    """

    # Download the stop data
    import sqlite3

    con = sqlite3.connect(os.path.join(DATA_DIR, "deo_dashboard.sql"))

    df_origs = []
    district_result = make_request(
        "SELECT distinct(districtoccur) as district from car_ped_stops order by districtoccur"
    )["rows"]
    districts = [r["district"] for r in district_result]

    for i, district in enumerate(districts):
        print(f"{district}, {i+1} of {len(districts)}")
        query = grouped_query_psa(district=district)
        df_district_orig = pd.read_sql(query, con=con)
        # df_district_orig = pd.DataFrame(result["rows"])
        if not df_district_orig.empty:
            df_origs.append(df_district_orig)

    df_orig = pd.concat(df_origs)

    df_quarterly_reason = df_orig.copy()

    def _add_quarterly_columns(df: pd.DataFrame) -> pd.DataFrame:
        df["quarter_dt_str"] = df["quarter"]
        df["quarter_dt"] = pd.to_datetime(df["quarter"], format="%Y-%m-%dT%H:%M:%SZ")
        df["quarter"] = (
            df["quarter_dt"].dt.year.astype(str)
            + "-Q"
            + df["quarter_dt"].dt.quarter.astype(str)
        )
        df["quarter_date"] = df["quarter_dt"].dt.date
        df["q_str"] = "Q" + df["quarter_dt"].dt.quarter.astype(str)
        df["year"] = df["quarter_dt"].dt.year
        return df

    df_quarterly = (
        df_quarterly_reason.drop("mvc_category", axis=1)
        .groupby(
            [
                "districtoccur",
                "psa",
                "quarter",
                "Race",
                "Gender",
                "Age Range",
            ]
        )
        .sum()
    ).reset_index()

    df_quarterly = _add_quarterly_columns(df_quarterly)
    df_quarterly.to_sql(
        "car_ped_stops_quarterly",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )
    df_quarterly_reason = _add_quarterly_columns(df_quarterly_reason)
    df_quarterly_reason.to_sql(
        "car_ped_stops_quarterly_reason",
        con=sqlite3.connect(sqlite_file),
        index=False,
        if_exists="replace",
    )
    df_quarterly.to_csv(f"{DATA_DIR}/car_ped_stops_quarterly.csv", index=False)
    df_quarterly_reason.to_csv(
        f"{DATA_DIR}/car_ped_stops_quarterly_reason.csv", index=False
    )

    download_geographies()
