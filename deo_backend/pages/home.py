import dash
from dash import html


layout = html.Div(
    [
        html.H1(
            "Traffic Stops in Philadelphia",
            style={"textAlign": "center"},
        ),
        html.H3(
            "Explore this dashboard to learn more about racial disparities in the Philadelphia Police Department’s traffic enforcement, how traffic stops have changed over time, and the history of Driving Equality."
        ),
    ]
)

dash.register_page(__name__, path="/", supplied_name="Home", order=0)
