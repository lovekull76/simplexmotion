"""FastAPI entrypoint for the SimplexMotion tuning tool.

Run with:

    uvicorn tuning_tool.app:app --host 0.0.0.0 --port 8000

Requires exclusive access to the motor's serial port -- stop the fermenter
service (or whatever else owns it) first. See tuning_tool/README.md.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import connect, live, params, profiles, recorder
from .state import state

app = FastAPI(title="SimplexMotion tuning tool")

app.include_router(connect.router)
app.include_router(params.router)
app.include_router(live.router)
app.include_router(recorder.router)
app.include_router(profiles.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.on_event("shutdown")
def _shutdown():
    if state.connected:
        state.disconnect()
