"""
============================================================
 ALARM & MAINTENANCE RECOMMENDATION ENGINE
============================================================
Turns a prediction into something a maintenance technician can act
on: a severity band, a plain-language cause, and a concrete
instruction.

The severity is decided by THREE independent signals, and the worst
one wins. This is deliberate defence in depth:

  1. the Random Forest's predicted class and its confidence
  2. the continuous physics stress ratio
  3. a hard deterministic check of the actual threshold rules

If the model were ever wrong - a retrained model, an out-of-
distribution reading, a sensor drifting - signal 3 still fires,
because it is arithmetic on the reading itself and cannot be fooled
by a bad model. An industrial system should never let a learned
component be the only thing standing between a fault and the
operator.

WHAT A PREDICTED CLASS MEANS HERE
---------------------------------
The classifier is trained on `label_horizon`, so a predicted "HDF"
means "heading for heat-dissipation failure", NOT "has failed". Every
message this module produces is worded in that predictive tense. The
distinction matters to a technician: a PREDICTED fault is an
instruction to intervene while the machine still runs; a BREACHED
threshold (signal 3) is a report that the limit has already gone.

PERSISTENCE FILTERING
---------------------
Phase 1's evaluation measured a genuine nuisance-alarm rate of 10.8%
of healthy-machine readings - single readings that flicker into a
failure class and back. Raising the decision threshold would suppress
them, but at the cost of the recall the whole project depends on.

Instead, an escalated band must be reached on N CONSECUTIVE readings
before it is published, which removes isolated flickers while leaving
a genuine degradation trend - which persists by definition - fully
intact. Real threshold breaches bypass the filter entirely: those are
arithmetic facts, not opinions, and are never delayed.
"""

from __future__ import annotations

from src.config import FAILURE_INFO, PREDICTION_HORIZON

# Severity ordering, lowest to highest
LEVELS = ["NORMAL", "ADVISORY", "WARNING", "CRITICAL"]
LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

LEVEL_STYLE = {
    "NORMAL":   {"color": "#22c55e", "label": "Normal",   "priority": 0},
    "ADVISORY": {"color": "#38bdf8", "label": "Advisory", "priority": 1},
    "WARNING":  {"color": "#f59e0b", "label": "Warning",  "priority": 2},
    "CRITICAL": {"color": "#ef4444", "label": "Critical", "priority": 3},
}

# Band edges
P_FAIL_CRITICAL = 0.50
P_FAIL_WARNING = 0.30
P_FAIL_ADVISORY = 0.12

STRESS_CRITICAL = 0.97
STRESS_WARNING = 0.85
STRESS_ADVISORY = 0.70

# Consecutive readings a band must hold before it is published.
# NORMAL is never delayed - de-escalation is always immediate, because
# holding an alarm up after the machine has recovered is its own kind
# of nuisance.
PERSISTENCE_REQUIRED = {
    "NORMAL": 1,
    "ADVISORY": 2,
    "WARNING": 2,
    "CRITICAL": 3,
}


def _worst(*levels: str) -> str:
    return max(levels, key=lambda lv: LEVEL_RANK.get(lv, 0))


# ==================================================================
def level_from_model(predicted_class: str, p_fail: float) -> str:
    """
    Band from the model alone.

    A named failure class carries more weight than a bare probability:
    if the forest has committed to a mechanism we escalate one band
    earlier than the probability thresholds alone would.
    """
    if predicted_class != "Normal":
        if p_fail >= P_FAIL_CRITICAL:
            return "CRITICAL"
        if p_fail >= P_FAIL_ADVISORY:
            return "WARNING"
        return "ADVISORY"

    if p_fail >= P_FAIL_CRITICAL:
        return "CRITICAL"
    if p_fail >= P_FAIL_WARNING:
        return "WARNING"
    if p_fail >= P_FAIL_ADVISORY:
        return "ADVISORY"
    return "NORMAL"


def level_from_stress(overall_stress: float) -> str:
    if overall_stress >= STRESS_CRITICAL:
        return "CRITICAL"
    if overall_stress >= STRESS_WARNING:
        return "WARNING"
    if overall_stress >= STRESS_ADVISORY:
        return "ADVISORY"
    return "NORMAL"


def level_from_breaches(breach_list) -> str:
    """Any real threshold violation is at least a warning."""
    if not breach_list:
        return "NORMAL"
    # TWF alone is a scheduled tool change, not an emergency
    modes = {b["mode"] for b in breach_list}
    if modes - {"TWF"}:
        return "CRITICAL"
    return "WARNING"


# ==================================================================
#  PERSISTENCE FILTER
# ==================================================================
def apply_persistence(raw_level: str, recent_levels=None,
                      bypass: bool = False) -> dict:
    """
    Hold an escalation back until it has been reached on enough
    consecutive readings.

    `recent_levels` is this machine's raw (unfiltered) band history,
    oldest first, NOT including `raw_level`. When the history is too
    short to confirm an escalation, the alarm is published one band
    lower - never suppressed to NORMAL, so a developing fault is
    always visible somewhere on the HMI.

    `bypass` is set by the caller when a hard threshold breach is
    present: arithmetic facts are published immediately.
    """
    need = PERSISTENCE_REQUIRED.get(raw_level, 1)

    if bypass or need <= 1 or raw_level == "NORMAL":
        return {"level": raw_level, "raw_level": raw_level,
                "held": False, "streak": need, "required": need}

    history = list(recent_levels or [])
    streak = 1
    for lv in reversed(history):
        if LEVEL_RANK.get(lv, 0) >= LEVEL_RANK[raw_level]:
            streak += 1
        else:
            break

    if streak >= need:
        return {"level": raw_level, "raw_level": raw_level,
                "held": False, "streak": streak, "required": need}

    # Not yet confirmed - publish one band down
    lowered = LEVELS[max(0, LEVEL_RANK[raw_level] - 1)]
    return {"level": lowered, "raw_level": raw_level,
            "held": True, "streak": streak, "required": need}


# ==================================================================
def evaluate(predicted_class: str, p_fail: float, overall_stress: float,
             dominant_mode: str, breach_list=None,
             recent_levels=None) -> dict:
    """
    Produce the complete alarm record for one reading.

    `predicted_class` is a HORIZON label - "heading for this failure",
    not "has failed" - so predictive wording is used throughout.
    `recent_levels` is the machine's raw band history (oldest first)
    used by the persistence filter; omit it for one-off manual
    readings, where there is no history to confirm against.
    """
    breach_list = breach_list or []

    lv_model = level_from_model(predicted_class, p_fail)
    lv_stress = level_from_stress(overall_stress)
    lv_rules = level_from_breaches(breach_list)
    raw_level = _worst(lv_model, lv_stress, lv_rules)

    # A real threshold breach is arithmetic, not opinion - never delay it
    persistence = apply_persistence(raw_level, recent_levels,
                                    bypass=bool(breach_list))
    level = persistence["level"]

    # Which mechanism is this alarm about?
    if predicted_class != "Normal":
        mode = predicted_class
    elif breach_list:
        mode = breach_list[0]["mode"]
    elif level != "NORMAL":
        mode = dominant_mode
    else:
        mode = "Normal"

    info = FAILURE_INFO.get(mode, FAILURE_INFO["Normal"])
    horizon_hours = PREDICTION_HORIZON * 10.0 / 60.0

    # ---- message, in the correct tense --------------------------------
    if breach_list:
        # The limit has ALREADY gone - report it as fact, present tense
        message = breach_list[0]["detail"] + "."
    elif predicted_class != "Normal":
        message = ("{} predicted within the next {} readings "
                   "(~{:.1f} operating hours) - {:.0f}% confidence. "
                   "The machine is still running; act now."
                   .format(info["name"], PREDICTION_HORIZON,
                           horizon_hours, p_fail * 100.0))
    elif level == "NORMAL":
        message = "All monitored parameters within the safe operating envelope."
    else:
        message = ("Early degradation trend on {} - stress at {:.0f}% of "
                   "its limit.".format(info["name"], overall_stress * 100.0))

    if persistence["held"]:
        message += (" [{} pending confirmation: {} of {} consecutive readings]"
                    .format(persistence["raw_level"].title(),
                            persistence["streak"], persistence["required"]))

    style = LEVEL_STYLE[level]
    return {
        "level": level,
        "priority": style["priority"],
        "color": style["color"],
        "label": style["label"],
        "mode": mode,
        "mode_name": info["name"],
        "message": message,
        "cause": info["cause"],
        "recommended_action": info["action"],
        "threshold_breaches": breach_list,
        "predicted": predicted_class != "Normal",
        "has_breached": bool(breach_list),
        "horizon_readings": PREDICTION_HORIZON,
        "sources": {
            "model": lv_model,
            "physics_stress": lv_stress,
            "rule_check": lv_rules,
        },
        "persistence": persistence,
        "acknowledged": False,
    }
