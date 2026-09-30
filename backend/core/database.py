"""
============================================================
 PERSISTENCE LAYER  (SQLite)
============================================================
The software stand-in for the synopsis's "cloud data store".

Three tables:

    machines   the plant register - one row per monitored machine
    readings   every sensor reading with the verdict it produced
    alarms     the alarm/maintenance log, acknowledgeable by an operator

WHY SQLITE
----------
It is in the standard library, needs no server, and the whole plant
history for a demo fits comfortably. Every query here is ordinary SQL,
so moving to PostgreSQL later is a connection-string change, not a
rewrite.

CONCURRENCY
-----------
FastAPI serves requests on a thread pool and the replay simulator
writes from a background task, so more than one thread will touch the
database at once. Two settings make that safe:

    check_same_thread=False   allow a connection across threads
    WAL journal mode          readers never block the writer

plus one lock around writes. SQLite handles the rest.

TIME
----
Everything is stored as an ISO-8601 UTC string. SQLite has no native
datetime type, and storing local time in a system that is meant to
model a 24-hour factory would be a bug waiting for a clock change.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.config import ROOT

DB_PATH = ROOT / "data" / "pdm.sqlite3"

_write_lock = threading.Lock()
_initialised = False


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================================================================
#  CONNECTION
# ==================================================================
def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session(db_path: Path | str | None = None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================================================================
#  SCHEMA
# ==================================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS machines (
    machine_id     TEXT PRIMARY KEY,
    name           TEXT,
    machine_type   TEXT NOT NULL DEFAULT 'L',
    location       TEXT,
    commissioned   TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id         TEXT NOT NULL,
    ts                 TEXT NOT NULL,
    cycle              INTEGER,
    machine_type       TEXT,
    air_temperature    REAL NOT NULL,
    process_temperature REAL NOT NULL,
    rotational_speed   REAL NOT NULL,
    torque             REAL NOT NULL,
    tool_wear          REAL NOT NULL,
    temp_delta         REAL,
    power              REAL,
    strain             REAL,
    predicted_class    TEXT,
    p_failure          REAL,
    confidence         REAL,
    overall_stress     REAL,
    dominant_mode      TEXT,
    health_index       REAL,
    alarm_level        TEXT,
    raw_alarm_level    TEXT,
    rul_readings       INTEGER,
    rul_hours          REAL,
    source             TEXT,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_readings_machine_ts
    ON readings(machine_id, id);

CREATE TABLE IF NOT EXISTS alarms (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id     TEXT NOT NULL,
    reading_id     INTEGER,
    ts             TEXT NOT NULL,
    level          TEXT NOT NULL,
    mode           TEXT,
    mode_name      TEXT,
    message        TEXT,
    cause          TEXT,
    recommended_action TEXT,
    health_index   REAL,
    rul_hours      REAL,
    breaches_json  TEXT,
    acknowledged   INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT,
    acknowledged_at TEXT,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alarms_machine ON alarms(machine_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_ack     ON alarms(acknowledged, id DESC);
"""


def init_db(db_path: Path | str | None = None, force: bool = False) -> None:
    """Create the schema. Safe to call repeatedly."""
    global _initialised
    if _initialised and not force and db_path is None:
        return
    with session(db_path) as conn:
        conn.executescript(SCHEMA)
    if db_path is None:
        _initialised = True


# ==================================================================
#  MACHINES
# ==================================================================
def register_machine(machine_id: str, name=None, machine_type="L",
                     location=None, commissioned=None,
                     db_path=None) -> dict:
    """Idempotent: registering an existing machine updates its details."""
    with _write_lock, session(db_path) as conn:
        conn.execute(
            """INSERT INTO machines (machine_id, name, machine_type, location,
                                     commissioned, created_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(machine_id) DO UPDATE SET
                   name         = COALESCE(excluded.name, machines.name),
                   machine_type = excluded.machine_type,
                   location     = COALESCE(excluded.location, machines.location),
                   commissioned = COALESCE(excluded.commissioned, machines.commissioned)
            """,
            (machine_id, name or machine_id, str(machine_type).upper(),
             location, commissioned, utcnow()),
        )
    return get_machine(machine_id, db_path=db_path)


def get_machine(machine_id: str, db_path=None):
    with session(db_path) as conn:
        r = conn.execute("SELECT * FROM machines WHERE machine_id=?",
                         (machine_id,)).fetchone()
    return dict(r) if r else None


def list_machines(db_path=None) -> list:
    """
    The plant overview: every machine with its LATEST verdict.

    A correlated subquery on max(id) gives the most recent reading per
    machine in one round trip - the alternative (N+1 queries from the
    route) would put a query per machine card on every dashboard poll.
    """
    with session(db_path) as conn:
        rows = conn.execute("""
            SELECT m.*,
                   r.ts             AS last_seen,
                   r.predicted_class,
                   r.p_failure,
                   r.health_index,
                   r.alarm_level,
                   r.overall_stress,
                   r.dominant_mode,
                   r.rul_hours,
                   r.tool_wear,
                   r.cycle,
                   (SELECT COUNT(*) FROM readings x WHERE x.machine_id=m.machine_id)
                       AS reading_count,
                   (SELECT COUNT(*) FROM alarms a
                     WHERE a.machine_id=m.machine_id AND a.acknowledged=0)
                       AS open_alarms
            FROM machines m
            LEFT JOIN readings r
                   ON r.id = (SELECT MAX(id) FROM readings y
                               WHERE y.machine_id = m.machine_id)
            ORDER BY
                CASE r.alarm_level WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1
                                   WHEN 'ADVISORY' THEN 2 ELSE 3 END,
                m.machine_id
        """).fetchall()
    return [dict(r) for r in rows]


def delete_machine(machine_id: str, db_path=None) -> bool:
    with _write_lock, session(db_path) as conn:
        cur = conn.execute("DELETE FROM machines WHERE machine_id=?", (machine_id,))
    return cur.rowcount > 0


# ==================================================================
#  READINGS
# ==================================================================
def save_reading(machine_id: str, result: dict, cycle=None,
                 source="manual", db_path=None) -> int:
    """
    Persist one prediction result (the dict from predictor.predict).

    Auto-registers an unknown machine so the simulator and the manual
    form never have to care whether it exists yet.
    """
    reading = result["reading"]
    derived = result.get("derived", {})
    pred = result["prediction"]
    phys = result["physics"]

    if not get_machine(machine_id, db_path=db_path):
        register_machine(machine_id, machine_type=reading.get("machine_type", "L"),
                         db_path=db_path)

    with _write_lock, session(db_path) as conn:
        cur = conn.execute("""
            INSERT INTO readings (
                machine_id, ts, cycle, machine_type,
                air_temperature, process_temperature, rotational_speed,
                torque, tool_wear, temp_delta, power, strain,
                predicted_class, p_failure, confidence,
                overall_stress, dominant_mode, health_index,
                alarm_level, raw_alarm_level, rul_readings, rul_hours, source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            machine_id, result.get("timestamp") or utcnow(), cycle,
            reading.get("machine_type"),
            reading["air_temperature"], reading["process_temperature"],
            reading["rotational_speed"], reading["torque"], reading["tool_wear"],
            derived.get("temp_delta"), derived.get("power"), derived.get("strain"),
            pred["class"], pred["p_failure"], pred["confidence"],
            phys["overall_stress"], phys["dominant_mode"],
            result["health"]["index"],
            result["alarm"]["level"],
            result["alarm"].get("persistence", {}).get("raw_level"),
            result["rul"].get("readings"), result["rul"].get("hours"),
            source,
        ))
        return int(cur.lastrowid)


def recent_readings(machine_id: str, limit: int = 120, db_path=None) -> list:
    """Most recent readings, returned OLDEST FIRST for charting."""
    with session(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM (
                   SELECT * FROM readings WHERE machine_id=?
                   ORDER BY id DESC LIMIT ?
               ) ORDER BY id ASC""",
            (machine_id, int(limit))).fetchall()
    return [dict(r) for r in rows]


def stress_history(machine_id: str, limit: int = 60, db_path=None) -> list:
    """The stress trajectory the RUL trend fit consumes."""
    with session(db_path) as conn:
        rows = conn.execute(
            """SELECT overall_stress FROM (
                   SELECT id, overall_stress FROM readings WHERE machine_id=?
                   ORDER BY id DESC LIMIT ?
               ) ORDER BY id ASC""",
            (machine_id, int(limit))).fetchall()
    return [r["overall_stress"] for r in rows if r["overall_stress"] is not None]


def recent_levels(machine_id: str, limit: int = 5, db_path=None) -> list:
    """Raw (pre-persistence) alarm bands, oldest first."""
    with session(db_path) as conn:
        rows = conn.execute(
            """SELECT raw_alarm_level FROM (
                   SELECT id, raw_alarm_level FROM readings WHERE machine_id=?
                   ORDER BY id DESC LIMIT ?
               ) ORDER BY id ASC""",
            (machine_id, int(limit))).fetchall()
    return [r["raw_alarm_level"] for r in rows if r["raw_alarm_level"]]


def reading_count(machine_id=None, db_path=None) -> int:
    with session(db_path) as conn:
        if machine_id:
            r = conn.execute("SELECT COUNT(*) c FROM readings WHERE machine_id=?",
                             (machine_id,)).fetchone()
        else:
            r = conn.execute("SELECT COUNT(*) c FROM readings").fetchone()
    return int(r["c"])


# ==================================================================
#  ALARMS
# ==================================================================
def log_alarm(machine_id: str, result: dict, reading_id=None, db_path=None):
    """
    Record an alarm - but only when it is worth recording.

    A machine sitting in CRITICAL for 40 consecutive readings is ONE
    event, not 40. We therefore log only a CHANGE of band (or of
    mechanism), which is what an operator's log should contain. Without
    this the alarm page becomes an unreadable wall of duplicates and
    the "unacknowledged" count is meaningless.
    """
    alarm = result["alarm"]
    if alarm["level"] == "NORMAL":
        return None

    with session(db_path) as conn:
        last = conn.execute(
            """SELECT level, mode FROM alarms WHERE machine_id=?
               ORDER BY id DESC LIMIT 1""", (machine_id,)).fetchone()

    if last and last["level"] == alarm["level"] and last["mode"] == alarm["mode"]:
        return None

    with _write_lock, session(db_path) as conn:
        cur = conn.execute("""
            INSERT INTO alarms (machine_id, reading_id, ts, level, mode,
                                mode_name, message, cause, recommended_action,
                                health_index, rul_hours, breaches_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            machine_id, reading_id, result.get("timestamp") or utcnow(),
            alarm["level"], alarm["mode"], alarm["mode_name"], alarm["message"],
            alarm["cause"], alarm["recommended_action"],
            result["health"]["index"], result["rul"].get("hours"),
            json.dumps(alarm.get("threshold_breaches", [])),
        ))
        return int(cur.lastrowid)


def list_alarms(machine_id=None, level=None, unacknowledged_only=False,
                limit: int = 200, db_path=None) -> list:
    sql = "SELECT * FROM alarms WHERE 1=1"
    params = []
    if machine_id:
        sql += " AND machine_id=?"
        params.append(machine_id)
    if level:
        sql += " AND level=?"
        params.append(level)
    if unacknowledged_only:
        sql += " AND acknowledged=0"
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))

    with session(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["acknowledged"] = bool(d["acknowledged"])
        try:
            d["threshold_breaches"] = json.loads(d.pop("breaches_json") or "[]")
        except (ValueError, TypeError):
            d["threshold_breaches"] = []
        out.append(d)
    return out


def acknowledge_alarm(alarm_id: int, by: str = "operator", db_path=None) -> bool:
    with _write_lock, session(db_path) as conn:
        cur = conn.execute(
            """UPDATE alarms SET acknowledged=1, acknowledged_by=?,
                                 acknowledged_at=?
               WHERE id=? AND acknowledged=0""",
            (by, utcnow(), int(alarm_id)))
    return cur.rowcount > 0


def acknowledge_all(machine_id=None, by: str = "operator", db_path=None) -> int:
    sql = "UPDATE alarms SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE acknowledged=0"
    params = [by, utcnow()]
    if machine_id:
        sql += " AND machine_id=?"
        params.append(machine_id)
    with _write_lock, session(db_path) as conn:
        cur = conn.execute(sql, params)
    return cur.rowcount


# ==================================================================
#  PLANT SUMMARY
# ==================================================================
def plant_summary(db_path=None) -> dict:
    """The KPI strip on the overview screen, in one query each."""
    with session(db_path) as conn:
        machines = conn.execute("SELECT COUNT(*) c FROM machines").fetchone()["c"]
        readings = conn.execute("SELECT COUNT(*) c FROM readings").fetchone()["c"]
        open_alarms = conn.execute(
            "SELECT COUNT(*) c FROM alarms WHERE acknowledged=0").fetchone()["c"]
        by_level = conn.execute("""
            SELECT r.alarm_level lvl, COUNT(*) c FROM readings r
            WHERE r.id IN (SELECT MAX(id) FROM readings GROUP BY machine_id)
            GROUP BY r.alarm_level""").fetchall()
        agg = conn.execute("""
            SELECT AVG(health_index) h, MIN(health_index) worst FROM readings
            WHERE id IN (SELECT MAX(id) FROM readings GROUP BY machine_id)
        """).fetchone()
        at_risk = conn.execute("""
            SELECT COUNT(*) c FROM readings
            WHERE id IN (SELECT MAX(id) FROM readings GROUP BY machine_id)
              AND predicted_class != 'Normal'""").fetchone()["c"]

    levels = {r["lvl"]: r["c"] for r in by_level if r["lvl"]}
    return {
        "machines": machines,
        "total_readings": readings,
        "open_alarms": open_alarms,
        "machines_at_risk": at_risk,
        "by_alarm_level": {
            "NORMAL": levels.get("NORMAL", 0),
            "ADVISORY": levels.get("ADVISORY", 0),
            "WARNING": levels.get("WARNING", 0),
            "CRITICAL": levels.get("CRITICAL", 0),
        },
        "mean_health": round(agg["h"], 1) if agg["h"] is not None else None,
        "worst_health": round(agg["worst"], 1) if agg["worst"] is not None else None,
    }


def reset(db_path=None) -> None:
    """Drop all operational data. Used by the tests and the demo reset."""
    with _write_lock, session(db_path) as conn:
        conn.execute("DELETE FROM alarms")
        conn.execute("DELETE FROM readings")
        conn.execute("DELETE FROM machines")
