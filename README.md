This is the backend code for the DEO dashboard. The dashboard calls fastapi endpoints that are served by this code. In order to more quickly iterate on visualizations, a similar version of the dashboard was built in plotly dash, with a fastapi endpoint then created for each unique interaction. 

You can run this for either fastapi or plotly dash, it uses an env var `SERVER_TYPE` of either 'dash' or 'fastapi'

## Seed Check
```
select sum(n_stopped) from car_ped_stops_quarterly where year <2024;
1916962
```

# TO Register a new route

1. You need to create a folder that is a copy from `_template`. In that folder is an `__init__` file which must define a `layout` variable as well as register the page.
2. You must also define the fastapi route in the routers.py dictionary
3. You need to add the import to the top of `main_fastapi.py`

## Development

You need to have [poetry](https://pypi.org/project/poetry/) installed. You can do it by at the system level doing `curl -sSL https://install.python-poetry.org | python3 -`.

```
poetry install
poetry run python deo_backend/main.py
poetry run python deo_backend/main_fastapi.py
```

Check the `env.py` file to see the env vars that can be updated without a redeploy.

## Updating the data

The website currently runs on a copy of the data from Open Data Philly (a zipfile backup that is generated monthly using an odp-data-backups repo).

1. Copy zipfile to the `deo_backend/data` folder.
2. Update the zip filename and quarter start date env vars in `deo_backend/env.py`
3. Execute `poetry run python deo_backend/update_db/update_db.py`
4. Go to render.com and Resume the beta web service. Update the front-end env var MOST_RECENT_QUARTER to the new quarter.
5. Share the beta link.
6. Upon confirmation, update the production web service and update the front-end env var MOST_RECENT_QUARTER to the new quarter.

