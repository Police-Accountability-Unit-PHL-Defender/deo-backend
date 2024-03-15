from fastapi import APIRouter
from dash import Dash, html, dcc, callback, Output, Input
from .annual_summary import LAYOUT as SUMMARY_LAYOUT

PAGE_TITLE = "Snapshot Summary..."
layout = html.Div(
    [
        html.Br(),
        SUMMARY_LAYOUT,
    ]
)
