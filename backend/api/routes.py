"""
============================================================
 REST API  -  every endpoint the HMI consumes
============================================================
Grouped by the screen that uses them:

  PREDICTION      POST /api/predict            manual entry panel
                  POST /api/predict/batch      CSV / Excel upload
                  GET  /api/predict/template   blank CSV to fill in

  PLANT           GET  /api/machines           overview cards
                  POST /api/machines           register a machine
                  GET  /api/machines/{id}      machine HMI detail
                  GET  /api/machines/{id}/history   trend charts
                  DEL  /api/machines/{id}

  SIMULATION      GET  /api/simulate/catalogue trajectories on offer
                  POST /api/simulate/start
                  POST /api/simulate/stop
                  GET  /api/simulate/status
                  GET  /api/simulate/stream/{id}    SSE live feed

  ALARMS          GET  /api/alarms
                  POST /api/alarms/{id}/acknowledge
                  POST /api/alarms/acknowledge-all

  INSIGHTS        GET  /api/model/info
                  GET  /api/model/metrics      Phase 1 evaluation
                  GET  /api/model/verify       explainer self-check

  SYSTEM          GET  /api/health
                  POST /api/system/reset
"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from src.config import (
    EXPANDED_CSV,
    FAILURE_CLASSES,
    FAILURE_INFO,
    HEALTH_BANDS,
    MACHINE_TYPES,
    METRICS_PATH,
    SENSORS,
    THRESHOLDS,
)
from backend.api.schemas import (
    AcknowledgeIn,
    MachineIn,
    ReadingIn,
    SimulationIn,
)
from backend.core import alarms as alarm_engine
from backend.core import database as db
from backend.services import predictor, simulator

router = APIRouter(prefix="/api", tags=["pdm"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024        # 25 MB
MAX_UPLOAD_ROWS = 20000


# ==================================================================
#  PREDICTION
# ==================================================================
@router.post("/predict", summary="Predict from one sensor reading")
def predict_one(payload: ReadingIn):
    reading = payload.model_dump(
        include={"machine_type", "air_temperature", "process_temperature",
                 "rotational_speed", "torque", "tool_wear"})
    mid = payload.machine_id

    try:
        result = predictor.predict(
            reading,
            stress_history=db.stress_history(mid) if mid else None,
            recent_levels=db.recent_levels(mid) if mid else None,
            explain=payload.explain,
            machine_id=mid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if payload.save:
        if not mid:
            raise HTTPException(
                status_code=422,
                detail="machine_id is required when save=true.")
        reading_id = db.save_reading(mid, result, cycle=payload.cycle,
                                     source="manual")
        alarm_id = db.log_alarm(mid, result, reading_id)
        result["reading_id"] = reading_id
        result["alarm_id"] = alarm_id
        result["saved"] = True

    return result


@router.post("/predict/batch", summary="Predict over an uploaded CSV/Excel file")
async def predict_batch(file: UploadFile = File(...),
                        explain: bool = Query(False),
                        save: bool = Query(False)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File is larger than {} MB.".format(MAX_UPLOAD_BYTES // 1048576))

    name = (file.filename or "upload.csv").lower()
    try:
        if name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not parse {!r}: {}".format(file.filename, exc))

    if df.empty:
        raise HTTPException(status_code=422, detail="No rows found in the file.")
    if len(df) > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=413,
            detail="File has {:,} rows; the limit is {:,}."
                   .format(len(df), MAX_UPLOAD_ROWS))

    try:
        out = predictor.predict_batch(df, explain=explain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    out["filename"] = file.filename

    if save:
        saved = 0
        for rec in out["results"]:
            mid = rec.get("machine_id")
            if not mid:
                continue
            single = _record_to_result(rec)
            rid = db.save_reading(mid, single, source="batch")
            db.log_alarm(mid, single, rid)
            saved += 1
        out["saved_rows"] = saved

    return out


def _record_to_result(rec: dict) -> dict:
    """Adapt a flat batch row back into the shape save_reading expects."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reading": {
            "machine_type": rec["machine_type"],
            **{k: rec[k] for k in SENSORS},
        },
        "derived": {},
        "prediction": {
            "class": rec["predicted_class"],
            "p_failure": rec["p_failure"],
            "confidence": rec["confidence"],
        },
        "physics": {
            "overall_stress": rec["overall_stress"],
            "dominant_mode": rec["dominant_mode"],
        },
        "health": {"index": rec["health_index"]},
        "rul": {"readings": rec["rul_readings"], "hours": rec["rul_hours"]},
        "alarm": {
            "level": rec["alarm_level"],
            "mode": rec["dominant_mode"],
            "mode_name": FAILURE_INFO.get(rec["dominant_mode"], {}).get("name", ""),
            "message": rec["alarm_message"],
            "cause": FAILURE_INFO.get(rec["dominant_mode"], {}).get("cause", ""),
            "recommended_action": rec["recommended_action"],
            "threshold_breaches": [],
            "persistence": {"raw_level": rec["alarm_level"]},
        },
    }


@router.get("/predict/template", response_class=PlainTextResponse,
            summary="Blank CSV template for batch upload")
def batch_template():
    cols = ["machine_id", "machine_type"] + list(SENSORS.keys())
    example = ["MC-001", "M", "298.1", "308.6", "1551", "42.8", "108"]
    body = ",".join(cols) + "\n" + ",".join(example) + "\n"
    return PlainTextResponse(
        body, headers={"Content-Disposition":
                       "attachment; filename=pdm_batch_template.csv"})


@router.get("/predict/schema", summary="What a batch upload must contain")
def batch_schema():
    return predictor.expected_columns()


@router.get("/predict/sample", response_class=PlainTextResponse,
            summary="A real run-to-failure trajectory as a ready-to-upload CSV")
def batch_sample(rows: int = Query(300, ge=10, le=5000)):
    """
    Exports one machine's actual degradation history as a CSV.

    A one-row template is enough to prove the endpoint parses, but it
    demonstrates nothing: batch analysis is interesting precisely
    because it shows health collapsing across a run. This hands the
    user a file that actually contains a failure.
    """
    if not EXPANDED_CSV.exists():
        raise HTTPException(status_code=503, detail="Dataset not available.")

    df = pd.read_csv(EXPANDED_CSV)

    # Select on the property we actually need - a multi-reading history
    # that ends in a failure - rather than on a `source` label. The
    # 10,000 real AI4I rows are singleton snapshots, so filtering by
    # trajectory length excludes them without hard-coding either label.
    counts = df.groupby("machine_id").size()
    multi = set(counts[counts >= 30].index)

    failing = [m for m in df.loc[df["failure_class"] != "Normal", "machine_id"].unique()
               if m in multi]
    if not failing:
        raise HTTPException(status_code=503, detail="No failing trajectory available.")

    run = df[df["machine_id"] == failing[0]].sort_values("cycle").tail(rows)
    cols = ["machine_id", "machine_type"] + list(SENSORS.keys())
    body = run[cols].to_csv(index=False)

    return PlainTextResponse(
        body,
        headers={"Content-Disposition":
                 "attachment; filename=sample_run_to_failure.csv"})


# ==================================================================
#  MACHINES
# ==================================================================
@router.get("/machines", summary="Plant overview")
def machines():
    return {"machines": db.list_machines(), "summary": db.plant_summary()}


@router.post("/machines", status_code=201, summary="Register a machine")
def add_machine(payload: MachineIn):
    return db.register_machine(**payload.model_dump())


@router.get("/machines/{machine_id}", summary="Machine detail")
def machine_detail(machine_id: str, history: int = Query(120, ge=1, le=2000)):
    m = db.get_machine(machine_id)
    if not m:
        raise HTTPException(status_code=404,
                            detail="Machine {!r} is not registered.".format(machine_id))
    readings = db.recent_readings(machine_id, limit=history)
    return {
        "machine": m,
        "readings": readings,
        "latest": readings[-1] if readings else None,
        "alarms": db.list_alarms(machine_id=machine_id, limit=30),
        "simulation": simulator.status(machine_id),
        "live": simulator.latest(machine_id),
    }


@router.get("/machines/{machine_id}/history", summary="Trend data for charts")
def machine_history(machine_id: str, limit: int = Query(200, ge=1, le=5000)):
    rows = db.recent_readings(machine_id, limit=limit)
    if not rows:
        return {"machine_id": machine_id, "count": 0, "series": {}}

    def col(k):
        return [r.get(k) for r in rows]

    return {
        "machine_id": machine_id,
        "count": len(rows),
        "series": {
            "ts": col("ts"),
            "cycle": col("cycle"),
            **{k: col(k) for k in SENSORS},
            "temp_delta": col("temp_delta"),
            "power": col("power"),
            "strain": col("strain"),
            "health_index": col("health_index"),
            "overall_stress": col("overall_stress"),
            "p_failure": col("p_failure"),
            "rul_hours": col("rul_hours"),
            "alarm_level": col("alarm_level"),
            "predicted_class": col("predicted_class"),
        },
    }


@router.delete("/machines/{machine_id}", summary="Remove a machine and its history")
def remove_machine(machine_id: str):
    simulator.stop(machine_id)
    if not db.delete_machine(machine_id):
        raise HTTPException(status_code=404, detail="No such machine.")
    return {"deleted": machine_id}


# ==================================================================
#  SIMULATION
# ==================================================================
@router.get("/simulate/catalogue", summary="Replayable trajectories")
def catalogue(limit: int = Query(40, ge=1, le=250)):
    try:
        return {"machines": simulator.available_machines(limit=limit)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/simulate/start", summary="Start a live replay")
def simulate_start(payload: SimulationIn):
    try:
        return simulator.start(**payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/simulate/stop", summary="Stop a replay")
def simulate_stop(machine_id: str = Query(...)):
    st = simulator.stop(machine_id)
    if st is None:
        raise HTTPException(status_code=404,
                            detail="No simulation running for {!r}.".format(machine_id))
    return st


@router.post("/simulate/stop-all", summary="Stop every replay")
def simulate_stop_all():
    return {"stopped": simulator.stop_all()}


@router.get("/simulate/status", summary="State of every replay")
def simulate_status(machine_id: str | None = Query(None)):
    if machine_id:
        st = simulator.status(machine_id)
        if st is None:
            raise HTTPException(status_code=404, detail="No such simulation.")
        return st
    return {"simulations": simulator.all_status()}


@router.get("/simulate/stream/{machine_id}", summary="Server-sent live feed")
async def simulate_stream(machine_id: str):
    """
    Push each new reading to the HMI as it is produced.

    SSE rather than WebSocket: the feed is strictly one-directional
    (control goes through the ordinary POST endpoints), and SSE
    reconnects by itself, needs no extra dependency and survives a
    proxy that would drop a socket.

    The generator watches the run's `position` and emits only when it
    advances, so a slow client cannot make the simulation stutter and a
    fast poll cannot duplicate a reading.
    """
    run = simulator.get(machine_id)
    if run is None:
        raise HTTPException(status_code=404,
                            detail="No simulation running for {!r}. "
                                   "POST /api/simulate/start first.".format(machine_id))

    # Poll faster than the simulation produces, so a quick replay is not
    # under-sampled by the stream. Clamped so a slow replay does not spin.
    poll = max(0.05, min(0.25, run.interval / 3.0))

    async def events():
        last_pos = -1
        idle = 0.0
        # tell the client what it has connected to
        yield _sse("status", run.status())

        while True:
            if run.latest is not None and run.position != last_pos:
                last_pos = run.position
                idle = 0.0
                yield _sse("reading", run.latest)
            else:
                idle += poll
                if idle >= 15.0:                 # keep proxies from timing out
                    idle = 0.0
                    yield _sse("ping", {"ts": datetime.now(timezone.utc).isoformat()})

            if not run.running:
                yield _sse("end", run.status())
                return

            await asyncio.sleep(poll)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",     # nginx: do not buffer the stream
        },
    )


def _sse(event: str, data) -> str:
    return "event: {}\ndata: {}\n\n".format(event, json.dumps(data, default=str))


# ==================================================================
#  ALARMS
# ==================================================================
@router.get("/alarms", summary="Alarm & maintenance log")
def get_alarms(machine_id: str | None = None,
               level: str | None = None,
               unacknowledged_only: bool = False,
               limit: int = Query(200, ge=1, le=2000)):
    if level and level.upper() not in alarm_engine.LEVELS:
        raise HTTPException(
            status_code=422,
            detail="level must be one of {}.".format(", ".join(alarm_engine.LEVELS)))
    rows = db.list_alarms(machine_id=machine_id,
                          level=level.upper() if level else None,
                          unacknowledged_only=unacknowledged_only,
                          limit=limit)
    return {
        "alarms": rows,
        "count": len(rows),
        "unacknowledged": sum(1 for a in rows if not a["acknowledged"]),
    }


@router.post("/alarms/{alarm_id}/acknowledge", summary="Acknowledge one alarm")
def ack_alarm(alarm_id: int, payload: AcknowledgeIn | None = None):
    by = (payload.by if payload else "operator")
    if not db.acknowledge_alarm(alarm_id, by):
        raise HTTPException(
            status_code=404,
            detail="Alarm {} not found, or already acknowledged.".format(alarm_id))
    return {"acknowledged": alarm_id, "by": by}


@router.post("/alarms/acknowledge-all", summary="Acknowledge every open alarm")
def ack_all(machine_id: str | None = None, by: str = "operator"):
    return {"acknowledged": db.acknowledge_all(machine_id=machine_id, by=by)}


# ==================================================================
#  MODEL INSIGHTS
# ==================================================================
@router.get("/model/info", summary="Model card")
def model_info():
    try:
        return predictor.model_info()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/model/metrics", summary="Phase 1 evaluation results")
def model_metrics():
    if not METRICS_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Metrics not found. Run the Phase 1 evaluation first.")
    with open(METRICS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@router.get("/model/verify", summary="Prove the explainer reproduces the model")
def model_verify(samples: int = Query(20, ge=1, le=200)):
    """
    Runs the additivity check live. If this ever reports exact=false,
    the explanation panel is not trustworthy and the UI says so.
    """
    from src.features.build_features import engineer_features, to_matrix
    from backend.services import explainer

    if not EXPANDED_CSV.exists():
        raise HTTPException(status_code=503, detail="Dataset not available.")

    df = pd.read_csv(EXPANDED_CSV).sample(samples, random_state=0)
    X = to_matrix(engineer_features(df)).to_numpy()
    return explainer.verify_additivity(predictor.get_bundle()["model"], X)


@router.get("/reference", summary="Constants the HMI renders against")
def reference():
    """One call so the frontend never hard-codes a threshold or colour."""
    return {
        "sensors": SENSORS,
        "machine_types": MACHINE_TYPES,
        "failure_classes": FAILURE_CLASSES,
        "failure_info": FAILURE_INFO,
        "thresholds": THRESHOLDS,
        "alarm_levels": alarm_engine.LEVELS,
        "alarm_styles": alarm_engine.LEVEL_STYLE,
        "health_bands": [
            {"min": lo, "max": hi, "level": lv, "color": c, "label": lb}
            for lo, hi, lv, c, lb in HEALTH_BANDS
        ],
    }


# ==================================================================
#  SYSTEM
# ==================================================================
@router.get("/health", summary="Service health check")
def service_health():
    model_ok = True
    try:
        predictor.get_bundle()
    except Exception:
        model_ok = False

    try:
        summary = db.plant_summary()
        db_ok = True
    except Exception:
        summary = {"machines": 0, "total_readings": 0}
        db_ok = False

    return {
        "status": "ok" if (model_ok and db_ok) else "degraded",
        "model_loaded": model_ok,
        "dataset_available": EXPANDED_CSV.exists(),
        "database_ready": db_ok,
        "machines": summary.get("machines", 0),
        "readings": summary.get("total_readings", 0),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/system/reset", summary="Clear all machines, readings and alarms")
def system_reset():
    simulator.stop_all()
    db.reset()
    return {"reset": True, "summary": db.plant_summary()}
