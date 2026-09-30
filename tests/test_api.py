"""
Phase 2 API tests, driven through FastAPI's TestClient.

Every test runs against a TEMPORARY database, monkeypatched over the
module-level DB_PATH, so running the suite can never touch the demo
plant history.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.config import EXPANDED_CSV, SENSORS
from backend.core import database as db


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdmdb") / "test.sqlite3"
    db.DB_PATH = path                     # every helper defaults to this
    db.init_db(path, force=True)

    from backend.app import app
    with TestClient(app) as c:
        yield c

    from backend.services import simulator
    simulator.stop_all()


VALID = {
    "machine_type": "M",
    "air_temperature": 298.1,
    "process_temperature": 308.6,
    "rotational_speed": 1551,
    "torque": 42.8,
    "tool_wear": 108,
}


# ==================================================================
#  SYSTEM
# ==================================================================
def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["model_loaded"] is True
    assert body["database_ready"] is True
    assert body["status"] == "ok"


def test_reference_endpoint_gives_the_ui_its_constants(client):
    body = client.get("/api/reference").json()
    assert set(body["sensors"]) == set(SENSORS)
    assert "CRITICAL" in body["alarm_levels"]
    assert len(body["health_bands"]) == 4


# ==================================================================
#  PREDICTION
# ==================================================================
def test_predict_valid_reading(client):
    body = client.post("/api/predict", json=VALID).json()
    assert body["prediction"]["class"] in ("Normal", "TWF", "HDF", "PWF", "OSF")
    assert 0.0 <= body["prediction"]["confidence"] <= 1.0
    assert 0 <= body["health"]["index"] <= 100
    assert body["alarm"]["level"] in ("NORMAL", "ADVISORY", "WARNING", "CRITICAL")
    assert body["explanation"]["top_drivers"]

    # probabilities are rounded to 4 dp for display, so the sum can drift
    # by up to half a unit in the last place per class
    probs = body["prediction"]["probabilities"]
    assert abs(sum(probs.values()) - 1.0) < 1e-3
    assert set(probs) == {"Normal", "TWF", "HDF", "PWF", "OSF"}


def test_prediction_is_stated_as_a_forecast(client):
    """The horizon semantics must reach the operator, not just the docs."""
    body = client.post("/api/predict", json=VALID).json()
    assert "horizon_readings" in body["prediction"]
    assert "next" in body["prediction"]["meaning"].lower()


def test_predict_rejects_impossible_values(client):
    for bad in ({"rotational_speed": -5}, {"rotational_speed": 0},
                {"air_temperature": 0}, {"torque": -1}):
        r = client.post("/api/predict", json={**VALID, **bad})
        assert r.status_code == 422, bad


def test_predict_rejects_missing_field(client):
    payload = dict(VALID)
    payload.pop("torque")
    assert client.post("/api/predict", json=payload).status_code == 422


def test_predict_flags_but_accepts_extreme_values(client):
    """An extreme torque IS the fault - it must be scored, not rejected."""
    r = client.post("/api/predict", json={**VALID, "torque": 95.0})
    assert r.status_code == 200
    assert r.json()["input_warnings"]


def test_predict_unknown_variant_is_rejected_by_schema(client):
    assert client.post("/api/predict",
                       json={**VALID, "machine_type": "Z"}).status_code == 422


def test_predict_with_save_persists_and_requires_id(client):
    r = client.post("/api/predict", json={**VALID, "save": True})
    assert r.status_code == 422          # save without machine_id

    r = client.post("/api/predict",
                    json={**VALID, "save": True, "machine_id": "T-SAVE"})
    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert client.get("/api/machines/T-SAVE").status_code == 200


# ==================================================================
#  BATCH
# ==================================================================
def _csv_bytes(df) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def test_batch_upload_scores_every_row(client):
    df = pd.read_csv(EXPANDED_CSV).head(60)[
        ["machine_id", "machine_type"] + list(SENSORS)]
    r = client.post("/api/predict/batch",
                    files={"file": ("run.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["rows_scored"] == 60
    assert body["summary"]["total"] == 60
    assert len(body["results"]) == 60


def test_batch_accepts_raw_ai4i_column_names(client):
    """Real uploads use the UCI spellings - the aliases must absorb them."""
    df = pd.DataFrame({
        "Type": ["M", "L"],
        "Air temperature [K]": [298.1, 299.0],
        "Process temperature [K]": [308.6, 309.1],
        "Rotational speed [rpm]": [1551, 1408],
        "Torque [Nm]": [42.8, 46.3],
        "Tool wear [min]": [108, 190],
    })
    r = client.post("/api/predict/batch",
                    files={"file": ("ai4i.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 200
    assert r.json()["rows_scored"] == 2


def test_batch_rejects_file_missing_required_columns(client):
    df = pd.DataFrame({"torque": [40.0], "tool_wear": [100.0]})
    r = client.post("/api/predict/batch",
                    files={"file": ("bad.csv", _csv_bytes(df), "text/csv")})
    assert r.status_code == 422
    assert "missing required column" in r.json()["detail"].lower()


def test_batch_reports_bad_rows_without_failing_the_upload(client):
    df = pd.DataFrame({
        "machine_type": ["M", "M"],
        "air_temperature": [298.1, 298.1],
        "process_temperature": [308.6, 308.6],
        "rotational_speed": [1551, 1551],
        "torque": [42.8, "not-a-number"],
        "tool_wear": [108, 108],
    })
    body = client.post("/api/predict/batch",
                       files={"file": ("mixed.csv", _csv_bytes(df), "text/csv")}).json()
    assert body["rows_scored"] == 1
    assert body["rows_rejected"] == 1
    assert body["errors"][0]["row"] == 3        # 1-indexed, past the header


def test_batch_rejects_empty_file(client):
    assert client.post("/api/predict/batch",
                       files={"file": ("e.csv", b"", "text/csv")}).status_code == 422


def test_batch_sample_is_a_real_degrading_trajectory(client):
    """
    The sample must show a machine actually failing - a single row would
    prove the endpoint parses but demonstrate nothing.
    """
    r = client.get("/api/predict/sample?rows=200")
    assert r.status_code == 200
    df = pd.read_csv(io.StringIO(r.text))
    assert len(df) == 200
    assert df["machine_id"].nunique() == 1          # one trajectory, not a mixed bag

    scored = client.post("/api/predict/batch",
                         files={"file": ("s.csv", r.text.encode(), "text/csv")}).json()
    assert scored["rows_scored"] == 200
    health = [x["health_index"] for x in scored["results"]]
    assert health[0] > health[-1], "the sample should degrade over its run"
    assert any(x["is_failure_predicted"] for x in scored["results"])


def test_batch_template_is_downloadable_and_valid(client):
    r = client.get("/api/predict/template")
    assert r.status_code == 200
    df = pd.read_csv(io.StringIO(r.text))
    assert set(SENSORS).issubset(df.columns)
    # the template must survive a round trip through the batch endpoint
    assert client.post("/api/predict/batch",
                       files={"file": ("t.csv", r.text.encode(), "text/csv")}
                       ).json()["rows_scored"] == 1


# ==================================================================
#  MACHINES
# ==================================================================
def test_register_and_list_machines(client):
    r = client.post("/api/machines", json={
        "machine_id": "CNC-01", "name": "Milling Machine 1",
        "machine_type": "H", "location": "Bay B"})
    assert r.status_code == 201

    body = client.get("/api/machines").json()
    assert any(m["machine_id"] == "CNC-01" for m in body["machines"])
    assert "summary" in body


def test_machine_detail_404_for_unknown(client):
    assert client.get("/api/machines/NOPE-999").status_code == 404


def test_history_returns_chartable_series(client):
    for i in range(5):
        client.post("/api/predict", json={
            **VALID, "save": True, "machine_id": "HIST-1",
            "tool_wear": 100 + i * 10, "explain": False})
    body = client.get("/api/machines/HIST-1/history").json()
    assert body["count"] == 5
    assert len(body["series"]["health_index"]) == 5
    assert len(body["series"]["tool_wear"]) == 5


# ==================================================================
#  SIMULATION
# ==================================================================
def test_catalogue_offers_failing_trajectories(client):
    machines = client.get("/api/simulate/catalogue?limit=5").json()["machines"]
    assert machines
    assert all(m["readings"] >= 30 for m in machines)
    assert all(m["failure_mode"] for m in machines)


def test_simulation_start_status_stop(client):
    src = client.get("/api/simulate/catalogue?limit=1").json()["machines"][0]["machine_id"]

    st = client.post("/api/simulate/start", json={
        "machine_id": "SIM-T", "source_machine": src, "interval": 0.05}).json()
    assert st["running"] is True
    assert st["eventual_failure_mode"]

    import time
    time.sleep(1.0)

    st = client.get("/api/simulate/status?machine_id=SIM-T").json()
    assert st["position"] > 0

    st = client.post("/api/simulate/stop?machine_id=SIM-T").json()
    assert st["running"] is False

    # readings actually landed in the database
    assert client.get("/api/machines/SIM-T").json()["readings"]


def test_simulation_start_rejects_unknown_trajectory(client):
    r = client.post("/api/simulate/start",
                    json={"machine_id": "X", "source_machine": "NO-SUCH-MACHINE"})
    assert r.status_code == 422


def test_stream_404_without_a_running_simulation(client):
    assert client.get("/api/simulate/stream/NOT-RUNNING").status_code == 404


# ==================================================================
#  ALARMS
# ==================================================================
def test_alarm_log_and_acknowledge(client):
    critical = {"machine_type": "M", "air_temperature": 298.0,
                "process_temperature": 305.0, "rotational_speed": 1300,
                "torque": 38.0, "tool_wear": 95,
                "machine_id": "ALARM-1", "save": True}
    client.post("/api/predict", json=critical)

    body = client.get("/api/alarms?machine_id=ALARM-1").json()
    assert body["count"] >= 1
    alarm_id = body["alarms"][0]["id"]

    assert client.post("/api/alarms/{}/acknowledge".format(alarm_id),
                       json={"by": "tester"}).status_code == 200
    # acknowledging twice is not an error the second time - it is a 404
    assert client.post("/api/alarms/{}/acknowledge".format(alarm_id),
                       json={"by": "tester"}).status_code == 404


def test_alarm_filter_rejects_bad_level(client):
    assert client.get("/api/alarms?level=BANANA").status_code == 422


# ==================================================================
#  MODEL INSIGHTS
# ==================================================================
def test_model_info_states_horizon_semantics(client):
    body = client.get("/api/model/info").json()
    assert body["n_estimators"] > 0
    assert body["prediction_horizon_readings"] > 0
    assert "not that it has already failed" in body["target_semantics"]


def test_model_metrics_exposes_phase1_results(client):
    body = client.get("/api/model/metrics").json()
    assert "headline" in body
    assert body["early_warning"]["mean_lead_readings"] > 0     # predictive, not reactive


def test_explainer_self_check_is_exact(client):
    body = client.get("/api/model/verify?samples=10").json()
    assert body["exact"] is True
