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
