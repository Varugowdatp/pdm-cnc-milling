"""
============================================================
 FASTAPI APPLICATION
============================================================
Serves the REST API and the SCADA HMI from one process on one port.

    /            the operator HMI (Phase 3)
    /api/*       the REST API
    /docs        interactive OpenAPI documentation
    /artifacts/* the Phase 1 figures, for the Model Insights screen

WHY ONE PROCESS
---------------
The frontend is deliberately build-free vanilla HTML/CSS/JS, so there
is no dev server, no bundler and no CORS problem: FastAPI mounts the
static directory and the whole system starts with one command. For a
demo that has to work on a projector in a lab, "one command, one port"
is worth more than any amount of tooling.

Run:
    python -m backend.app
    # or
    uvicorn backend.app:app --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import ARTIFACT_DIR, ROOT
from backend.api.routes import router
from backend.core import database as db
from backend.services import simulator

FRONTEND_DIR = ROOT / "frontend"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pdm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ---------------------------------------------------
    log.info("Initialising database at %s", db.DB_PATH)
    db.init_db()

    try:
        from backend.services import predictor
        info = predictor.model_info()
        log.info("Model loaded: %s, %s trees, classes=%s",
                 info.get("algorithm", "?"), info.get("n_estimators"),
                 ", ".join(info.get("classes", [])))
        log.info("Prediction horizon: %s readings (~%.1f h) - a predicted "
                 "failure class means APPROACHING that failure.",
                 info.get("prediction_horizon_readings"),
                 info.get("prediction_horizon_hours", 0.0))
    except Exception as exc:
        log.error("MODEL NOT LOADED: %s", exc)
        log.error("Run Phase 1 first:  python run_phase1.py")

    if not FRONTEND_DIR.exists():
        log.warning("Frontend directory %s does not exist yet (Phase 3).",
                    FRONTEND_DIR)

    yield

    # ---- shutdown --------------------------------------------------
    stopped = simulator.stop_all()
    if stopped:
        log.info("Stopped %d running simulation(s).", stopped)


app = FastAPI(
    title="AI-Based Predictive Maintenance for CNC Milling Machines",
    description=(
        "Random Forest predictive-maintenance service.\n\n"
        "**The model predicts the APPROACH to a failure, not its occurrence.** "
        "It is trained on a horizon target, so a predicted class of `HDF` means "
        "the machine is heading for heat-dissipation failure within the "
        "prediction horizon. Phase 1 measured a mean lead time of 52 readings "
        "(8.7 operating hours)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# The HMI is served from the same origin, so CORS is only needed if
# someone opens the frontend from a file:// URL or another port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Never leak a raw traceback to the HMI; always return usable JSON."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "{}: {}".format(type(exc).__name__, exc),
                 "path": request.url.path},
    )


# ------------------------------------------------------------------
#  STATIC
# ------------------------------------------------------------------
if ARTIFACT_DIR.exists():
    app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_DIR)),
              name="artifacts")

if FRONTEND_DIR.exists():
    # html=True makes StaticFiles serve index.html at "/"
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True),
              name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def placeholder():
        return {
            "service": "AI-Based Predictive Maintenance",
            "status": "API running; the HMI is built in Phase 3.",
            "docs": "/docs",
            "api": "/api/health",
        }


def main() -> int:
    import uvicorn
    host = "127.0.0.1"
    port = 8000
    print("=" * 66)
    print(" AI-BASED PREDICTIVE MAINTENANCE FOR CNC MILLING MACHINES")
    print("=" * 66)
    print("  HMI   ->  http://{}:{}/".format(host, port))
    print("  API   ->  http://{}:{}/docs".format(host, port))
    print("=" * 66)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
