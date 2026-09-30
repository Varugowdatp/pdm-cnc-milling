"""
============================================================
 MACHINE REPLAY SIMULATOR
============================================================
The software replacement for the synopsis's NodeMCU + sensor rig.

It replays a real run-to-failure trajectory out of the expanded
dataset, one reading at a time, at a controllable speed - so the HMI
receives a genuine live feed with a genuine approaching failure,
without any hardware.

WHY REPLAY REAL TRAJECTORIES RATHER THAN GENERATE RANDOM NUMBERS
---------------------------------------------------------------
Random values would exercise the plumbing but demonstrate nothing: the
health curve would jitter around a constant and no failure would ever
develop. Replaying an actual degradation run means the gauges drift the
way they physically must, the alarm bands escalate in the right order,
and the RUL countdown converges on a failure that really does arrive.
The demo shows the SYSTEM working because the DATA is real.

The simulator is also the honest one: it holds out the ground-truth
label of every reading and reports it alongside the prediction, so the
UI can display "predicted HDF / actual HDF in 31 readings" and the
viewer can judge the model rather than take its word.

THREADING
---------
Each machine runs in its own daemon thread with its own stop event.
State lives in a module-level registry behind a lock, because the
FastAPI route that starts a run and the SSE route that streams it are
different requests on different threads.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import pandas as pd

from src.config import EXPANDED_CSV, PREDICTION_HORIZON
from backend.core import database as db
from backend.services import predictor

# ------------------------------------------------------------------
#  DATASET (loaded once - it is 7.9 MB)
# ------------------------------------------------------------------
_dataset = None
_dataset_lock = threading.Lock()

# machine_id -> SimulationRun
_runs: dict = {}
_runs_lock = threading.Lock()

DEFAULT_INTERVAL = 1.0          # seconds of wall-clock per reading
MIN_INTERVAL = 0.05
MAX_INTERVAL = 10.0


def get_dataset() -> pd.DataFrame:
    global _dataset
    if _dataset is None:
        with _dataset_lock:
            if _dataset is None:
                if not EXPANDED_CSV.exists():
                    raise FileNotFoundError(
                        "Expanded dataset not found at {}. Run Phase 1 first."
                        .format(EXPANDED_CSV))
                _dataset = pd.read_csv(EXPANDED_CSV)
    return _dataset


def available_machines(limit: int = 60, only_failing: bool = True) -> list:
    """
    Catalogue of replayable trajectories for the HMI's machine picker.

    Only multi-reading simulated runs are offered: the 10,000 real AI4I
    rows are independent snapshots, so "replaying" one would be a
    single frame and would teach the viewer nothing.
    """
    d = get_dataset()
    g = d.groupby("machine_id")
    out = []
    for mid, grp in g:
        if len(grp) < 30:
            continue
        fails = grp[grp["failure_class"] != "Normal"]
        if only_failing and fails.empty:
            continue
        mode = fails["failure_class"].iloc[0] if not fails.empty else None
        out.append({
            "machine_id": str(mid),
            "machine_type": str(grp["machine_type"].iloc[0]),
            "readings": int(len(grp)),
            "failure_mode": mode,
            "fails_at_cycle": int(fails["cycle"].min()) if not fails.empty else None,
            "life_hours": round(len(grp) * 10.0 / 60.0, 1),
        })
        if len(out) >= limit:
            break
    return out


# ==================================================================
#  ONE RUN
# ==================================================================
class SimulationRun:
    """A single machine replaying its trajectory in a background thread."""

    def __init__(self, machine_id: str, source_machine: str,
                 interval: float = DEFAULT_INTERVAL, loop: bool = False,
                 start_at: int = 0, db_path=None):
        self.machine_id = machine_id
        self.source_machine = source_machine
        self.interval = max(MIN_INTERVAL, min(MAX_INTERVAL, float(interval)))
        self.loop = loop
        self.db_path = db_path

        d = get_dataset()
        rows = d[d["machine_id"] == source_machine].sort_values("cycle")
        if rows.empty:
            raise ValueError("No trajectory found for machine {!r}."
                             .format(source_machine))
        self.rows = rows.reset_index(drop=True)

        fails = self.rows[self.rows["failure_class"] != "Normal"]
        self.fail_cycle = int(fails["cycle"].min()) if not fails.empty else None
        self.true_mode = fails["failure_class"].iloc[0] if not fails.empty else None

        self.position = int(start_at)
        self.running = False
        self.finished = False
        self.started_at = None
        self.latest = None
        self.error = None

        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

        # First prediction of a failure, for the live lead-time readout
        self.first_warning_position = None

    # ----------------------------------------------------------
    def start(self):
        if self.running:
            return self
        self._stop.clear()
        self.running = True
        self.finished = False
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="sim-{}".format(self.machine_id))
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self.running = False
        return self

    def _loop(self):
        try:
            while not self._stop.is_set():
                if self.position >= len(self.rows):
                    if self.loop:
                        self.position = 0
                        self._reset_machine_history()
                    else:
                        self.finished = True
                        self.running = False
                        break
                self.step()
                # wait in small slices so stop() is responsive
                self._stop.wait(self.interval)
        except Exception as exc:                      # keep the thread alive-safe
            self.error = "{}: {}".format(type(exc).__name__, exc)
            self.running = False

    def _reset_machine_history(self):
        """A looped run starts a fresh life, so old history must not leak in."""
        try:
            db.delete_machine(self.machine_id, db_path=self.db_path)
            db.register_machine(self.machine_id,
                                machine_type=str(self.rows["machine_type"].iloc[0]),
                                db_path=self.db_path)
        except Exception:
            pass

    # ----------------------------------------------------------
    def step(self) -> dict:
        """Advance exactly one reading. Also usable for manual stepping."""
        with self._lock:
            if self.position >= len(self.rows):
                return self.latest
            row = self.rows.iloc[self.position]
            pos = self.position
            self.position += 1

        reading = {
            "machine_type": str(row["machine_type"]),
            "air_temperature": float(row["air_temperature"]),
            "process_temperature": float(row["process_temperature"]),
            "rotational_speed": float(row["rotational_speed"]),
            "torque": float(row["torque"]),
            "tool_wear": float(row["tool_wear"]),
        }

        result = predictor.predict(
            reading,
            stress_history=db.stress_history(self.machine_id, db_path=self.db_path),
            recent_levels=db.recent_levels(self.machine_id, db_path=self.db_path),
            explain=False,
            machine_id=self.machine_id,
        )

        reading_id = db.save_reading(self.machine_id, result,
                                     cycle=int(row["cycle"]), source="simulator",
                                     db_path=self.db_path)
        db.log_alarm(self.machine_id, result, reading_id, db_path=self.db_path)

        if (self.first_warning_position is None
                and result["prediction"]["is_failure_predicted"]):
            self.first_warning_position = pos

        # ---- ground truth, held out and reported honestly -------------
        cycle = int(row["cycle"])
        readings_to_failure = (self.fail_cycle - cycle
                               if self.fail_cycle is not None else None)
        result["ground_truth"] = {
            "actual_class": str(row["failure_class"]),
            "horizon_label": str(row.get("label_horizon", row["failure_class"])),
            "eventual_failure_mode": self.true_mode,
            "readings_to_failure": readings_to_failure,
            "hours_to_failure": (round(readings_to_failure * 10.0 / 60.0, 2)
                                 if readings_to_failure is not None else None),
            "has_failed": readings_to_failure is not None and readings_to_failure <= 0,
            "correct": (result["prediction"]["class"]
                        == str(row.get("label_horizon", row["failure_class"]))),
        }
        result["simulation"] = self.status()
        result["reading_id"] = reading_id
        self.latest = result
        return result

    # ----------------------------------------------------------
    def status(self) -> dict:
        lead = None
        if self.first_warning_position is not None and self.fail_cycle is not None:
            warn_cycle = int(self.rows.iloc[self.first_warning_position]["cycle"])
            lead = self.fail_cycle - warn_cycle

        return {
            "machine_id": self.machine_id,
            "source_machine": self.source_machine,
            "running": self.running,
            "finished": self.finished,
            "position": self.position,
            "total": len(self.rows),
            "progress_pct": round(100.0 * self.position / len(self.rows), 1),
            "interval_seconds": self.interval,
            "loop": self.loop,
            "started_at": self.started_at,
            "eventual_failure_mode": self.true_mode,
            "fails_at_cycle": self.fail_cycle,
            "first_warning_position": self.first_warning_position,
            "lead_time_readings": lead,
            "lead_time_hours": round(lead * 10.0 / 60.0, 2) if lead else None,
            "horizon_readings": PREDICTION_HORIZON,
            "error": self.error,
        }


# ==================================================================
#  REGISTRY
# ==================================================================
def start(machine_id: str, source_machine: str = None,
          interval: float = DEFAULT_INTERVAL, loop: bool = False,
          restart: bool = True, start_at: int = 0,
          start_fraction: float | None = None, db_path=None) -> dict:
    """
    Start (or restart) a replay under `machine_id`.

    `start_at` / `start_fraction` jump into the trajectory rather than
    beginning at commissioning. A full run can be several hundred
    readings, so anyone who wants to see a machine in its final decline
    would otherwise have to sit through its entire healthy life. It also
    makes the documentation screenshots reproducible instead of
    depending on how long the capture happened to run.
    """
    source_machine = source_machine or machine_id

    with _runs_lock:
        existing = _runs.get(machine_id)
        if existing and existing.running and not restart:
            return existing.status()
        if existing:
            existing.stop()

        if restart:
            db.delete_machine(machine_id, db_path=db_path)

        run = SimulationRun(machine_id, source_machine, interval, loop,
                            db_path=db_path)

        if start_fraction is not None:
            start_at = int(len(run.rows) * max(0.0, min(1.0, start_fraction)))
        run.position = max(0, min(int(start_at), len(run.rows) - 1))
        db.register_machine(machine_id,
                            machine_type=str(run.rows["machine_type"].iloc[0]),
                            db_path=db_path)
        _runs[machine_id] = run

    return run.start().status()


def stop(machine_id: str) -> dict | None:
    with _runs_lock:
        run = _runs.get(machine_id)
    if not run:
        return None
    return run.stop().status()


def stop_all() -> int:
    with _runs_lock:
        runs = list(_runs.values())
    for r in runs:
        r.stop()
    return len(runs)


def get(machine_id: str):
    with _runs_lock:
        return _runs.get(machine_id)


def status(machine_id: str) -> dict | None:
    run = get(machine_id)
    return run.status() if run else None


def all_status() -> list:
    with _runs_lock:
        return [r.status() for r in _runs.values()]


def latest(machine_id: str) -> dict | None:
    run = get(machine_id)
    return run.latest if run else None
