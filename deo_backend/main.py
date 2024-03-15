from dash import Dash, html, dcc, callback, Output, Input, register_page
import dash_ag_grid as dag
from datetime import date
from datetime import timedelta
from datetime import datetime
import plotly.express as px
import pandas as pd
import sqlite3

from models import PoliceAction
from models import AgeGroup
from models import DemographicCategory
from models import GenderGroup
from models import RacialGroup
from models import Geography
import os
import dash

app = Dash(__name__, use_pages=True)


app_layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    dcc.Link(
                        f"{page['supplied_name']} ({page['path']})",
                        href=page["relative_path"],
                    )
                )
                for page in dash.page_registry.values()
            ]
        ),
        dash.page_container,
    ]
)

app.layout = app_layout


if __name__ == "__main__":
    app.run(debug=True, port=10000, host="0.0.0.0")
