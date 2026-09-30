"""
============================================================
 HEALTH INDEX  &  REMAINING USEFUL LIFE (RUL)
============================================================
Turns a model prediction plus a physics stress profile into the two
numbers the synopsis block diagram calls for:

    * Health Index   0-100   (the HMI's main gauge)
    * RUL estimate           (readings / operating hours to failure)

HEALTH INDEX
------------
A blend of two independent opinions:

    health_physics = 100 * (1 - overall_stress)
        continuous, monotone, derived from first principles

    health_model   = 100 * P(Normal)
        the Random Forest's own confidence that this machine is NOT
        on the approach to a failure

Neither alone is adequate. Physics alone ignores everything the model
learned about combinations of sensors; the model alone reports the
likelihood of a coming failure without saying how far the degradation
has already progressed. The blend is weighted towards physics for
smoothness and pulled down by the model whenever it predicts a fault.

NOTE ON THE MODEL'S LABEL MEANING
---------------------------------
The classifier is trained on `label_horizon`. A predicted class of
"HDF" therefore means "heading for heat-dissipation failure", NOT
"has already failed" - and empirically it fires a mean of 52 readings
(8.7 operating hours) ahead of the event.

That matters here: an incipient-failure prediction must NOT slam the
health gauge to zero, because at that moment the machine is still
running and the operator still has hours to act. Health is instead
capped on a sliding scale by the model's confidence, and only driven
into the critical band once a physical limit is actually breached.
Getting this wrong would throw away the very lead time Phase 1 was
rebuilt to obtain.

RUL
---
Two regimes, because the amount of information available differs:

  * WITH history (live monitoring / batch upload of a machine's run):
    fit a straight line to the recent stress trajectory and
    extrapolate to stress = 1.0. This is a real measurement of how
    fast THIS machine is degrading.

  * WITHOUT history (a single manual reading):
    no trend can be measured, so we fall back to a nominal-rate
    estimate assuming the machine degrades over a typical service
    life. This is clearly flagged as `nominal` in the response so the
    UI never presents a guess as a measurement.
"""

from __future__ import annotations

import numpy as np

from src.config import HEALTH_BANDS

# One sensor reading every 10 minutes (matches the dataset's cadence)
MINUTES_PER_READING = 10.0

# Typical commissioning-to-failure life, from the expanded dataset.
# Used only as the nominal degradation rate when no history exists.
NOMINAL_LIFE_READINGS = 295.0

# Longest RUL we are willing to state. Beyond this the extrapolation
# is meaningless and the UI shows "> 999".
RUL_CAP = 999

# Blend weights for the health index
W_PHYSICS = 0.60
W_MODEL = 0.40

# Curvature of the stress -> health mapping.
#
# health_physics = 100 * (1 - stress**STRESS_EXPONENT)
#
# A LINEAR map (exponent 1) is wrong, and measurably so: `overall_stress`
# is the MAX over four mechanisms, so even a perfectly healthy machine
# carries a floor of consumed margin - a tool at 30% of its life alone
# put the median healthy machine at 81 health, inside the "Monitor" band.
#
# A machine that has used 30% of a consumable is not 70% healthy. Damage
# accumulation is also genuinely non-linear: the last 20% of margin
# disappears far faster than the first 20%. An exponent of 2.5 keeps
# healthy machines near 95, then falls away sharply once stress passes
# ~0.7, which is where the alarm bands start.
STRESS_EXPONENT = 2.5

# Sliding cap applied when the model predicts an INCIPIENT failure.
# At the lowest actionable confidence the machine is only "Degrading";
# at full confidence it sits at the top of the critical band. It is
# never forced to zero by a prediction alone - see the module docstring.
CAP_AT_LOW_CONFIDENCE = 62.0     # upper end of the WARNING/Degrading band
CAP_AT_FULL_CONFIDENCE = 32.0    # inside CRITICAL, but not "dead"
CAP_CONFIDENCE_FLOOR = 0.30      # p_fail at which the sliding cap starts

# A machine that has actually breached a HARD physical limit HAS failed,
# and the gauge should say so regardless of what the smooth curves read.
# "Hard" excludes entering the tool-wear window - see physics.has_hard_breach().
CAP_ON_BREACH = 12.0


# ==================================================================
#  HEALTH INDEX
# ==================================================================
def health_index(overall_stress: float, p_normal: float,
                 predicted_class: str = "Normal",
                 p_fail: float | None = None,
                 breached: bool = False) -> float:
    """
    Combine physics stress and model confidence into 0-100.

    `predicted_class` is a HORIZON label: anything other than "Normal"
    means "on the approach to this failure", not "already failed".
    `breached` should be physics.has_hard_breach(breach_list) - a HARD
    limit violation, excluding tool-wear window entry - and is the only
    signal that forces the gauge into the floor.
    """
    s = max(0.0, min(1.0, float(overall_stress)))
    health_physics = 100.0 * (1.0 - s ** STRESS_EXPONENT)
    health_model = 100.0 * float(p_normal)

    health = W_PHYSICS * health_physics + W_MODEL * health_model

    if predicted_class != "Normal":
        # p_fail defaults to the complement of P(Normal)
        pf = float(1.0 - float(p_normal)) if p_fail is None else float(p_fail)
        # 0 at the confidence floor -> 1 at full confidence
        t = (pf - CAP_CONFIDENCE_FLOOR) / (1.0 - CAP_CONFIDENCE_FLOOR)
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        cap = CAP_AT_LOW_CONFIDENCE + t * (CAP_AT_FULL_CONFIDENCE
                                           - CAP_AT_LOW_CONFIDENCE)
        health = min(health, cap)

    if breached:
        health = min(health, CAP_ON_BREACH)

    return round(max(0.0, min(100.0, health)), 1)


def health_band(health: float) -> dict:
    """Map a health score onto its status band, colour and label."""
    for lo, hi, level, color, label in HEALTH_BANDS:
        if lo <= health <= hi:
            return {"level": level, "color": color, "label": label}
    return {"level": "CRITICAL", "color": "#ef4444", "label": "Critical"}


# ==================================================================
#  RUL
# ==================================================================
def _readings_to_time(readings: float) -> dict:
    minutes = float(readings) * MINUTES_PER_READING
    return {
        "readings": int(round(readings)),
        "minutes": round(minutes, 1),
        "hours": round(minutes / 60.0, 2),
        "days": round(minutes / 1440.0, 2),
    }


def rul_nominal(overall_stress: float) -> dict:
    """
    Single-reading fallback: assume this machine travels from stress 0
    to stress 1 over a typical service life, and report the remaining
    fraction of that life.
    """
    remaining = max(0.0, 1.0 - float(overall_stress)) * NOMINAL_LIFE_READINGS
    out = _readings_to_time(min(remaining, RUL_CAP))
    out.update({
        "method": "nominal",
        "confidence": "low",
        "basis": "No trend history for this machine. Estimated from current "
                 "stress against a typical {:.0f}-reading service life."
                 .format(NOMINAL_LIFE_READINGS),
    })
    return out


def rul_from_trend(stress_history, min_points: int = 8,
                   window: int = 40) -> dict:
    """
    Fit stress(t) = a*t + b over the most recent `window` readings and
    solve for the time at which stress reaches 1.0.

    A flat or falling trend means the machine is stable or recovering,
    so no finite RUL is reported.
    """
    s = np.asarray([v for v in stress_history if v is not None], dtype=float)
    s = s[np.isfinite(s)]

    if len(s) < min_points:
        return rul_nominal(s[-1] if len(s) else 0.0)

    recent = s[-window:]
    t = np.arange(len(recent), dtype=float)
    slope, intercept = np.polyfit(t, recent, 1)

    current = float(recent[-1])

    # Not degrading fast enough to matter
    if slope <= 1e-5:
        out = _readings_to_time(RUL_CAP)
        out.update({
            "method": "trend",
            "confidence": "high",
            "slope_per_reading": round(float(slope), 6),
            "basis": "Stress trend is flat or improving over the last {} "
                     "readings - no degradation detected.".format(len(recent)),
            "unbounded": True,
        })
        return out

    remaining = (1.0 - current) / slope
    remaining = max(0.0, min(remaining, RUL_CAP))

    # how well the straight line actually fits - our confidence in it
    fitted = slope * t + intercept
    ss_res = float(np.sum((recent - fitted) ** 2))
    ss_tot = float(np.sum((recent - recent.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    out = _readings_to_time(remaining)
    out.update({
        "method": "trend",
        "confidence": "high" if r2 > 0.75 else ("medium" if r2 > 0.4 else "low"),
        "slope_per_reading": round(float(slope), 6),
        "trend_r2": round(float(r2), 3),
        "points_used": int(len(recent)),
        "basis": "Linear extrapolation of the stress trend over the last {} "
                 "readings (R2 = {:.2f}).".format(len(recent), r2),
        "unbounded": False,
    })
    return out


def estimate_rul(overall_stress: float, stress_history=None) -> dict:
    """Public entry point: use the trend if we have one, else nominal."""
    if stress_history and len(stress_history) >= 8:
        return rul_from_trend(stress_history)
    return rul_nominal(overall_stress)
