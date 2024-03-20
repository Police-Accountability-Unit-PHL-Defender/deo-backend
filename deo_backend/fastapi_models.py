from dash import dcc
from plotly.graph_objs import Scatter
from flask import request
from typing import Annotated
from fastapi import Query
import numpy as np
import urllib.parse
import os

from models import DemographicCategory

API_DOMAIN = os.environ.get("API_DOMAIN", "http://0.0.0.0:8123")

location_annotation = Annotated[
    str,
    Query(
        description="A location identifier. Citywide is `*`, or division can be one of ('SPD', 'NEPD', 'NWPD', 'CPD', 'SWPD', 'EPD'), or a district is a 2-digit number (`22*`) or a PSA is 'district-PSA' (`22-1`)",
    ),
]
quarter_annotation = Annotated[str, Query(description="A quarter-year identifier")]

demographic_annotation = Annotated[
    DemographicCategory, Query(description="A demographic category")
]


def convert(x):
    if isinstance(x, np.int64):
        return int(x)
    else:
        return x


class Endpoint:
    def __init__(self, api_route, inputs, data=None, **kwargs):
        for kw in kwargs:
            if not (kw.startswith("fig_") or kw.startswith("text_")):
                raise ValueError(f"kwargs must start with fig_ or text_, but got {kw}")
        self.kwargs = kwargs
        self.data = data or {}
        self.inputs = inputs
        self.api_route = api_route

    def output(self, data=None, **kwargs):
        if os.environ.get("SERVER_TYPE", "dash") == "dash":
            return self.plotly(**kwargs)
        else:
            return self.json(data=data, **kwargs)

    def plotly(self, **kwargs):
        self.json(**kwargs)  # to make sure that plotly tests the json works
        flattened_params = []
        for k, v in self.inputs.items():
            if isinstance(v, list):
                for item in v:
                    flattened_params.append((k, item))
            else:
                flattened_params.append((k, v))

        href = f"{self.full_api_route}?{urllib.parse.urlencode(flattened_params)}"
        kwarg_vals = []
        for val in kwargs.values():
            if isinstance(val, str):
                kwarg_vals.append(
                    dcc.Markdown(val.replace("<span>", "**").replace("</span>", "**"))
                )
            elif isinstance(val, dcc.Markdown):
                raise NotImplementedError("Replace with direct string")
            else:
                kwarg_vals.append(val)

        return kwarg_vals + [href]

    @property
    def full_api_route(self) -> str:
        return f"{API_DOMAIN}{self.api_route}"

    def json(self, data=None, **kwargs):
        figures = {}
        texts = []
        tables = {}
        geojsons = []
        for map_key in [kw for kw in kwargs if kw.startswith("map_")]:
            geojson = {
                "type": "FeatureCollection",
                "features": [],
                "properties": {
                    "title": kwargs[map_key].layout.title.text,
                    "map_key": map_key,
                },
            }
            if kwargs[map_key].layout.mapbox.layers:
                # Used by the HIN Map
                geojson["features"].extend(
                    [feature.source for feature in kwargs[map_key].layout.mapbox.layers]
                )
            if kwargs[map_key].data:
                for map_data in kwargs[map_key].data:
                    if getattr(map_data, "geojson", None):
                        # Used by Comparison by District Maps
                        geojson["features"].extend(map_data.geojson["features"])
                    elif map_data.subplot == "mapbox":
                        # Used by the HIN Plotly Points
                        geojson["features"].extend(
                            [
                                {
                                    "type": "Feature",
                                    "properties": {
                                        "name": map_data["name"],
                                    },
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [lon, lat],
                                    },
                                }
                                for lat, lon in zip(map_data["lat"], map_data["lon"])
                            ]
                        )
                    geojsons.append(geojson)
        for fig_key in [kw for kw in kwargs if kw.startswith("fig_")]:
            fig_name = fig_key[len("fig_") :]
            fig = kwargs[fig_key]

            x_axis_name = fig.layout.xaxis.title.text
            y_axis_name = fig.layout.yaxis.title.text

            fig_data = []
            fig_trendlines = []

            for i, this_fig_data in enumerate(fig.data):
                for x_val, y_val, custom_data in zip(
                    this_fig_data.x,
                    this_fig_data.y,
                    (
                        this_fig_data.customdata
                        if this_fig_data.customdata is not None
                        else [(y,) for y in this_fig_data.y]
                    ),
                ):
                    if isinstance(this_fig_data, Scatter):
                        # Indicates a trendline
                        fig_trendlines.append(
                            {
                                "hover_text": this_fig_data.hovertemplate,
                                x_axis_name: convert(x_val),
                                y_axis_name: convert(y_val),
                            }
                        )
                    else:
                        fig_data.append(
                            {
                                "group": this_fig_data["name"] or None,
                                x_axis_name: convert(x_val),
                                y_axis_name: convert(y_val),
                                # "annotation": fig.layout.annotations[i],
                                "hover_text": this_fig_data["hovertemplate"]
                                .replace("%{", "{")
                                .replace("customdata[0]", "z")
                                .replace("customdata[1]", "z2")
                                .replace("<extra></extra>", "")
                                .format(
                                    x=x_val,
                                    y=y_val,
                                    z=custom_data[0],
                                    z2=custom_data[1] if len(custom_data) > 1 else "",
                                )
                                .split("<br>"),
                            }
                        )
            figures[fig_name] = {
                "properties": {
                    "xAxis": x_axis_name,
                    "yAxis": y_axis_name,
                    "title": fig.layout.title.text,
                },
                "trendlines": fig_trendlines,
                "data": fig_data,
            }
        for texts_key in [kw for kw in kwargs if kw.startswith("text_")]:
            if isinstance(kwargs[texts_key], dcc.Markdown):
                text_content = kwargs[texts_key].children
            else:
                text_content = kwargs[texts_key]
            texts.extend([x.strip() for x in text_content.split("\n") if x.strip()])
        for table_key in [kw for kw in kwargs if kw.startswith("table_")]:
            table_name = table_key[len("table_") :]
            table = kwargs[table_key]
            tables[table_name] = table.rowData
        return {
            "text": texts,
            "figures": figures,
            "tables": tables,
            "geojsons": geojsons,
            "data": {k: convert(v) for k, v in data.items()} if data else {},
            "inputs": self.inputs,
        }
