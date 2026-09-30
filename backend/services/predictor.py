"""
============================================================
 PREDICTION SERVICE  -  the inference orchestrator
============================================================
One reading in, one complete operator-facing verdict out.

This is the only place the whole chain is assembled, and every other
component (REST routes, batch upload, the replay simulator, the tests)
goes through it. That matters: it means the manual-entry form, a CSV
upload and the live stream cannot possibly disagree about what a given
reading means.

THE CHAIN
---------
    raw reading
      -> build_features.engineer_features()   [SHARED with training]
      -> RandomForest.predict_proba()         [the learned opinion]
      -> physics.stress_profile()             [the first-principles opinion]
      -> physics.breaches()                   [the deterministic rule check]
      -> health.health_index() + estimate_rul()
      -> alarms.evaluate()                    [worst-of-three, persisted]
      -> explainer.explain_for_class()        [why, exactly]

WHAT THE PREDICTION MEANS
-------------------------
The model is trained on `label_horizon`, so a predicted class of "HDF"
means "this machine is heading for heat-dissipation failure within the
prediction horizon", NOT "this machine has failed". Phase 1 measured a
mean lead time of 52 readings (8.7 operating hours). Everything this
module emits is worded accordingly.

The model is loaded ONCE at import and reused. Loading an 11 MB bundle
per request would dominate the response time.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from src.config import (
    BUNDLE_PATH,
    FAILURE_CLASSES,
    MACHINE_TYPES,
    PREDICTION_HORIZON,
    SENSORS,
)
from src.features.build_features import (
    FEATURE_COLUMNS,
    FEATURE_LABELS,
    FEATURE_UNITS,
    engineer_features,
    to_matrix,
)
from backend.core import alarms, health, physics
from backend.services import explainer

# One reading every 10 minutes, matching the dataset cadence
MINUTES_PER_READING = 10.0

_bundle = None
_lock = threading.Lock()


# ==================================================================
#  MODEL LOADING
# ==================================================================
def get_bundle() -> dict:
    """Load the trained bundle once, thread-safely."""
    global _bundle
    if _bundle is None:
        with _lock:
            if _bundle is None:
                if not BUNDLE_PATH.exists():
                    raise FileNotFoundError(
                        "Model bundle not found at {}. Run Phase 1 first:\n"
                        "  python run_phase1.py".format(BUNDLE_PATH)
                    )
                _bundle = joblib.load(BUNDLE_PATH)
    return _bundle


def model_info() -> dict:
    """Metadata for the HMI's 'Model Insights' screen."""
    b = get_bundle()
    meta = dict(b.get("metadata", {}))
    meta.update({
        "classes": list(b["classes"]),
        "features": list(b["feature_columns"]),
        "n_estimators": int(len(b["model"].estimators_)),
        "prediction_horizon_readings": PREDICTION_HORIZON,
        "prediction_horizon_hours": round(
            PREDICTION_HORIZON * MINUTES_PER_READING / 60.0, 2),
        "target_semantics": (
            "Classes are HORIZON labels: a predicted failure class means the "
            "machine is on the approach to that failure within the next {} "
            "readings, not that it has already failed."
            .format(PREDICTION_HORIZON)
        ),
    })
    return meta


# ==================================================================
#  INPUT VALIDATION
# ==================================================================
def validate_reading(reading: dict) -> tuple[dict, list]:
    """
    Coerce and sanity-check one raw reading.

    Returns (clean_reading, warnings). Out-of-range values are kept, not
    rejected: an extreme torque IS the fault we are looking for. They are
    only flagged, so the HMI can show a hint without hiding the reading.
    """
    warnings = []
    out = {}

    mt = str(reading.get("machine_type", "L")).strip().upper()
    if mt not in MACHINE_TYPES:
        warnings.append("Unknown machine variant {!r}; defaulted to L.".format(mt))
        mt = "L"
    out["machine_type"] = mt

    for name, spec in SENSORS.items():
        if name not in reading or reading[name] is None:
            raise ValueError("Missing required sensor value: {}".format(name))
        try:
            v = float(reading[name])
        except (TypeError, ValueError):
            raise ValueError("{} must be numeric, got {!r}".format(name, reading[name]))
        if not np.isfinite(v):
            raise ValueError("{} must be a finite number.".format(name))
        if v < spec["min"] or v > spec["max"]:
            warnings.append(
                "{} = {:g} {} is outside the typical range {:g}-{:g} {}."
                .format(spec["label"], v, spec["unit"],
                        spec["min"], spec["max"], spec["unit"])
            )
        out[name] = v

    if out["rotational_speed"] <= 0:
        raise ValueError("Rotational speed must be greater than zero.")

    return out, warnings


# ==================================================================
#  SINGLE PREDICTION
# ==================================================================
def predict(reading: dict, stress_history=None, recent_levels=None,
            explain: bool = True, machine_id: str | None = None) -> dict:
    """
    The complete verdict for one sensor reading.

    `stress_history`  previous overall_stress values for this machine,
                      oldest first - enables trend-based RUL.
    `recent_levels`   previous raw alarm bands - enables the persistence
                      filter that suppresses single-reading flicker.
    """
    b = get_bundle()
    model = b["model"]
    classes = list(b["classes"])

    clean_reading, input_warnings = validate_reading(reading)

    # ---- features (identical transform to training) -------------------
    frame = engineer_features(pd.DataFrame([clean_reading]))
    X = to_matrix(frame)                      # DataFrame keeps feature names
    engineered = frame.iloc[0].to_dict()

    # ---- model --------------------------------------------------------
    proba_row = model.predict_proba(X)[0]
    probabilities = {c: float(p) for c, p in zip(classes, proba_row)}
    predicted_class = classes[int(np.argmax(proba_row))]
    p_normal = probabilities.get("Normal", 0.0)
    p_fail = float(1.0 - p_normal)
    confidence = float(np.max(proba_row))

    # ---- physics (independent of the model) ---------------------------
    profile = physics.stress_profile(
        clean_reading["machine_type"],
        clean_reading["air_temperature"],
        clean_reading["process_temperature"],
        clean_reading["rotational_speed"],
        clean_reading["torque"],
        clean_reading["tool_wear"],
    )
    breach_list = physics.breaches(
        clean_reading["machine_type"],
        clean_reading["air_temperature"],
        clean_reading["process_temperature"],
        clean_reading["rotational_speed"],
        clean_reading["torque"],
        clean_reading["tool_wear"],
    )
    hard_breach = physics.has_hard_breach(breach_list)

    # ---- health & RUL --------------------------------------------------
    hi = health.health_index(profile["overall_stress"], p_normal,
                             predicted_class, p_fail, hard_breach)
    band = health.health_band(hi)

    history = list(stress_history or [])
    rul = health.estimate_rul(profile["overall_stress"],
                              history + [profile["overall_stress"]])

    # ---- alarm ----------------------------------------------------------
    alarm = alarms.evaluate(predicted_class, p_fail, profile["overall_stress"],
                            profile["dominant_mode"], breach_list,
                            recent_levels=recent_levels)

    # ---- explanation ----------------------------------------------------
    explanation = None
    if explain:
        explanation = explainer.explain_for_class(
            model, X.to_numpy()[0], predicted_class,
            raw_values=engineered, class_names=classes,
        )

    return {
        "machine_id": machine_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reading": clean_reading,
        "derived": {k: round(float(engineered[k]), 4)
                    for k in ("temp_delta", "power", "strain", "torque_speed_ratio")},
        "prediction": {
            "class": predicted_class,
            "is_failure_predicted": predicted_class != "Normal",
            "meaning": _meaning(predicted_class),
            "confidence": round(confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in probabilities.items()},
            "p_failure": round(p_fail, 4),
            "horizon_readings": PREDICTION_HORIZON,
        },
        "physics": {
            "stress": {k: round(v, 4) for k, v in profile["stress"].items()},
            "dominant_mode": profile["dominant_mode"],
            "overall_stress": round(profile["overall_stress"], 4),
            "threshold_breaches": breach_list,
            "has_hard_breach": hard_breach,
        },
        "health": {
            "index": hi,
            "level": band["level"],
            "color": band["color"],
            "label": band["label"],
        },
        "rul": rul,
        "alarm": alarm,
        "explanation": explanation,
        "input_warnings": input_warnings,
    }


def _meaning(predicted_class: str) -> str:
    if predicted_class == "Normal":
        return ("No failure expected within the next {} readings "
                "(~{:.1f} operating hours)."
                .format(PREDICTION_HORIZON,
                        PREDICTION_HORIZON * MINUTES_PER_READING / 60.0))
    return ("Machine is on the approach to {} - predicted to occur within "
            "the next {} readings (~{:.1f} operating hours) if no action is "
            "taken.".format(predicted_class, PREDICTION_HORIZON,
                            PREDICTION_HORIZON * MINUTES_PER_READING / 60.0))


# ==================================================================
#  BATCH PREDICTION
# ==================================================================
def predict_batch(df: pd.DataFrame, explain: bool = False,
                  group_by_machine: bool = True) -> dict:
    """
    Vectorised prediction over an uploaded CSV/Excel frame.

    The model runs ONCE over the whole frame rather than per row - on a
    5,000-row upload that is the difference between a moment and a
    minute. Per-row physics is cheap and stays in Python.

    When the frame carries a `machine_id`, rows are processed in order
    within each machine so that stress history (RUL trend) and alarm
    persistence work exactly as they do on the live stream.
    """
    b = get_bundle()
    model = b["model"]
    classes = list(b["classes"])

    work = _normalise_columns(df)
    errors = []

    required = ["machine_type"] + list(SENSORS.keys())
    missing = [c for c in required if c not in work.columns]
    if missing:
        raise ValueError(
            "Uploaded file is missing required column(s): {}. Expected: {}."
            .format(", ".join(missing), ", ".join(required))
        )

    # drop rows that cannot be parsed at all, remembering which
    for c in SENSORS:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    bad = work[list(SENSORS.keys())].isna().any(axis=1) | (work["rotational_speed"] <= 0)
    for idx in work.index[bad]:
        errors.append({"row": int(idx) + 2,     # +2 = 1-indexed + header
                       "error": "Non-numeric or non-physical sensor value."})
    work = work[~bad].copy()
    if work.empty:
        raise ValueError("No valid rows found in the uploaded file.")

    work["machine_type"] = (work["machine_type"].astype(str).str.strip().str.upper()
                            .where(lambda s: s.isin(MACHINE_TYPES), "L"))

    # ---- one vectorised model call -----------------------------------
    frame = engineer_features(work)
    X = to_matrix(frame)
    proba = model.predict_proba(X)
    pred_idx = proba.argmax(axis=1)

    has_id = group_by_machine and "machine_id" in work.columns
    if has_id:
        order = work.groupby("machine_id", sort=False).cumcount()
        work = work.assign(_seq=order)

    results = []
    stress_hist: dict = {}
    level_hist: dict = {}

    positions = list(range(len(work)))
    for pos in positions:
        row = work.iloc[pos]
        mid = str(row["machine_id"]) if has_id else None

        profile = physics.stress_profile(
            row["machine_type"], row["air_temperature"], row["process_temperature"],
            row["rotational_speed"], row["torque"], row["tool_wear"])
        breach_list = physics.breaches(
            row["machine_type"], row["air_temperature"], row["process_temperature"],
            row["rotational_speed"], row["torque"], row["tool_wear"])
        hard = physics.has_hard_breach(breach_list)

        pc = classes[pred_idx[pos]]
        probs = {c: float(p) for c, p in zip(classes, proba[pos])}
        p_normal = probs.get("Normal", 0.0)
        p_fail = 1.0 - p_normal

        hist = stress_hist.setdefault(mid, [])
        lv_hist = level_hist.setdefault(mid, [])

        hi = health.health_index(profile["overall_stress"], p_normal, pc, p_fail, hard)
        alarm = alarms.evaluate(pc, p_fail, profile["overall_stress"],
                                profile["dominant_mode"], breach_list,
                                recent_levels=lv_hist)
        rul = health.estimate_rul(profile["overall_stress"],
                                  hist + [profile["overall_stress"]])

        hist.append(profile["overall_stress"])
        lv_hist.append(alarm["persistence"]["raw_level"])

        rec = {
            "row": int(work.index[pos]) + 2,
            "machine_id": mid,
            "machine_type": row["machine_type"],
            **{k: float(row[k]) for k in SENSORS},
            "predicted_class": pc,
            "is_failure_predicted": pc != "Normal",
            "confidence": round(float(proba[pos].max()), 4),
            "p_failure": round(float(p_fail), 4),
            **{"p_{}".format(c): round(probs[c], 4) for c in classes},
            "overall_stress": round(profile["overall_stress"], 4),
            "dominant_mode": profile["dominant_mode"],
            "has_hard_breach": hard,
            "health_index": hi,
            "health_label": health.health_band(hi)["label"],
            "alarm_level": alarm["level"],
            "alarm_message": alarm["message"],
            "recommended_action": alarm["recommended_action"],
            "rul_readings": rul["readings"],
            "rul_hours": rul["hours"],
            "rul_method": rul["method"],
        }
        if explain:
            rec["explanation"] = explainer.explain_for_class(
                model, X.to_numpy()[pos], pc,
                raw_values=frame.iloc[pos].to_dict(), class_names=classes)
        results.append(rec)

    return {
        "rows_in": int(len(df)),
        "rows_scored": len(results),
        "rows_rejected": len(errors),
        "errors": errors[:50],
        "summary": _summarise(results, classes),
        "results": results,
    }


def _summarise(results, classes) -> dict:
    n = len(results)
    if not n:
        return {}
    counts = {c: 0 for c in classes}
    levels = {lv: 0 for lv in alarms.LEVELS}
    for r in results:
        counts[r["predicted_class"]] = counts.get(r["predicted_class"], 0) + 1
        levels[r["alarm_level"]] = levels.get(r["alarm_level"], 0) + 1

    at_risk = sum(1 for r in results if r["is_failure_predicted"])
    return {
        "total": n,
        "predicted_normal": counts.get("Normal", 0),
        "predicted_failure": at_risk,
        "failure_rate_pct": round(100.0 * at_risk / n, 2),
        "by_class": counts,
        "by_alarm_level": levels,
        "mean_health": round(float(np.mean([r["health_index"] for r in results])), 1),
        "machines": len({r["machine_id"] for r in results if r["machine_id"]}),
    }


# ==================================================================
#  COLUMN NORMALISATION
# ==================================================================
#  Real uploads never match the schema exactly. Accept the AI4I names,
#  the raw UCI names and common spreadsheet spellings.
COLUMN_ALIASES = {
    "air temperature [k]": "air_temperature",
    "air temperature": "air_temperature",
    "air_temp": "air_temperature",
    "process temperature [k]": "process_temperature",
    "process temperature": "process_temperature",
    "process_temp": "process_temperature",
    "rotational speed [rpm]": "rotational_speed",
    "rotational speed": "rotational_speed",
    "speed": "rotational_speed",
    "rpm": "rotational_speed",
    "torque [nm]": "torque",
    "tool wear [min]": "tool_wear",
    "tool wear": "tool_wear",
    "toolwear": "tool_wear",
    "type": "machine_type",
    "product type": "machine_type",
    "variant": "machine_type",
    "machine": "machine_id",
    "product id": "machine_id",
    "udi": "machine_id",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    renamed = {}
    for col in out.columns:
        key = str(col).strip().lower()
        if key in COLUMN_ALIASES:
            renamed[col] = COLUMN_ALIASES[key]
        else:
            renamed[col] = key.replace(" ", "_")
    return out.rename(columns=renamed)


def expected_columns() -> dict:
    """Describes the upload contract for the HMI's help panel."""
    return {
        "required": ["machine_type"] + list(SENSORS.keys()),
        "optional": ["machine_id", "timestamp"],
        "units": {k: v["unit"] for k, v in SENSORS.items()},
        "machine_type_values": MACHINE_TYPES,
        "accepted_aliases": COLUMN_ALIASES,
    }
