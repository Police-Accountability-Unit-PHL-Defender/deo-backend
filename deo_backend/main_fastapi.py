from fastapi.responses import RedirectResponse
from fastapi import status

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pages.snapshot  # required before `from routers import ROUTERS` to load the routes
import pages.stops  # required before `from routers import ROUTERS` to load the routes
import pages.neighborhoods  # required before `from routers import ROUTERS` to load the routes
import pages.safety
import pages.reasons  # required before `from routers import ROUTERS` to load the routes
from routers import ROUTERS


origins = [
    "https://driving-equality.vercel.app",
    "https://deo-web-dashboard.vercel.app",
    "https://driving-equality.phillydefenders.org",
    "https://deo-fastapi.onrender.com",
    "https://deo-api.onrender.com",
    "http://localhost:10000",
    "http://localhost:3000",
    "https://deo-web-dashboard-git-beta-philadefender.vercel.app",
]

os.environ["SERVER_TYPE"] = "fastapi"


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_main():
    return RedirectResponse(url="/docs", status_code=status.HTTP_302_FOUND)


[app.include_router(router) for router in ROUTERS.values()]


if __name__ == "__main__":
    uvicorn.run("main_fastapi:app", port=8123, reload=True)
