from fastapi import APIRouter

ROUTERS = {
    "stops": APIRouter(tags=["Stops"]),
    "snapshot": APIRouter(tags=["Snapshot"]),
    "neighborhoods": APIRouter(tags=["Neighborhoods"]),
    "safety": APIRouter(tags=["Safety"]),
    "reasons": APIRouter(tags=["Reasons"]),
}
