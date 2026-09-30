"""
============================================================
 PHYSICS STRESS MODEL
============================================================
Converts one raw sensor reading into a normalised STRESS RATIO in
[0, 1] for each of the four failure mechanisms, where

        0.0  =  comfortably inside the safe envelope
        1.0  =  sitting exactly on the failure threshold

Why this exists ALONGSIDE the Random Forest
-------------------------------------------
The classifier is trained on `label_horizon`, so it answers "is this
machine heading for a failure within the prediction horizon, and which
one?" - a class plus a probability. That is the right question, but it
is still a fairly coarse quantity for a dashboard: it says WHICH
mechanism and HOW LIKELY, not HOW FAR ALONG the machine is.

The stress ratios supply that missing axis. They are continuous,
monotone and derived from first principles, so they give the HMI a
smoothly degrading health index and give the RUL estimator a quantity
to extrapolate toward its limit.

They also provide independence: the ratios are arithmetic on the
reading itself, so they keep working if the model is ever wrong, stale
or fed an out-of-distribution reading.

IMPORTANT: these ratios drive only the health gauge, the RUL estimate
and the alarm bands. They are NEVER fed to the classifier - doing so
would leak the label rule into the model's inputs. The prediction
itself stays purely machine-learned.
"""

from __future__ import annotations

from src.config import THRESHOLDS

# Reference points at which a mechanism is considered stress-free (0.0).
#
# CALIBRATED, NOT GUESSED. These are the MEDIANS of the 72,288 healthy
# readings in data/processed/pdm_expanded_dataset.csv, so a typical
# healthy machine reads 0.0 stress by construction and the ratio rises
# only as the reading moves from typical toward its threshold.
#
# The first version of this file used 12.0 K / 2100 rpm, picked as
# "comfortably safe" values rather than measured ones. Because the
# healthy thermal band is narrow (8.2-12.3 K against an HDF limit of
# 8.6 K), that made a perfectly healthy machine report 44% heat stress
# and dragged its health gauge down to 72. Anchoring on the measured
# median fixes it.
STRESS_FREE = {
    "temp_delta": 10.0,      # K   - median healthy thermal gradient
    "speed": 1558.0,         # rpm - median healthy rotational speed
}

# Healthy interquartile range of mechanical power (W), same source.
# Inside this band the drive is doing exactly what it should, so PWF
# stress is zero; outside it, margin is consumed toward the trip.
PWF_HEALTHY_CORE = (5639.0, 7084.0)


def clip01(x: float) -> float:
    """Clamp to [0, 1]; NaN-safe."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if x != x:                      # NaN
        return 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


# ==================================================================
#  DERIVED QUANTITIES
# ==================================================================
def derive(air_temperature, process_temperature, rotational_speed,
           torque, tool_wear) -> dict:
    """The four engineering quantities the thresholds are defined on."""
    speed = float(rotational_speed)
    tq = float(torque)
    return {
        "temp_delta": float(process_temperature) - float(air_temperature),
        "power": tq * speed * 2.0 * 3.141592653589793 / 60.0,
        "strain": float(tool_wear) * tq,
        "torque_speed_ratio": tq / speed if speed else 0.0,
    }


# ==================================================================
#  PER-MECHANISM STRESS
# ==================================================================
def stress_twf(tool_wear: float) -> float:
    """Tool wear approaching its replacement window (200-240 min)."""
    return clip01(float(tool_wear) / THRESHOLDS["tool_wear_max"])


def stress_hdf(temp_delta: float, rotational_speed: float) -> float:
    """
    HDF needs a LOW thermal gradient AND a LOW speed simultaneously.

    For an AND-condition the binding constraint is the one still
    furthest from tripping, so the mechanism's stress is the MINIMUM
    of the two individual stresses - not the maximum, and not the
    product. Using max() here would raise a heat alarm on any machine
    that merely happens to be running slowly.

    That is not a hypothetical: 25% of the healthy readings in the
    dataset run below 1346 rpm, i.e. below the HDF speed condition of
    1380 rpm, while cooling perfectly well. min() is what keeps those
    machines quiet.
    """
    d_lo, d_hi = THRESHOLDS["temp_delta_min"], STRESS_FREE["temp_delta"]
    s_delta = clip01((d_hi - float(temp_delta)) / (d_hi - d_lo))

    s_lo, s_hi = THRESHOLDS["hdf_speed_max"], STRESS_FREE["speed"]
    s_speed = clip01((s_hi - float(rotational_speed)) / (s_hi - s_lo))

    return min(s_delta, s_speed)


def stress_pwf(power: float) -> float:
    """
    Margin consumed toward whichever edge of the 3500-9000 W design
    window the machine is heading for.

    NOT distance from the centre of the window. PWF is a two-sided
    limit with a broad safe interior, so a machine anywhere inside the
    healthy core is under no power stress at all. Measuring from the
    centre made a healthy 4,775 W machine report 54% stress simply for
    running on the low side of nominal.

    The deadband is the healthy interquartile range (5,639-7,084 W,
    measured on the 72,288 healthy readings); stress rises from 0 at
    the edge of that core to 1.0 at the actual trip.
    """
    p = float(power)
    lo, hi = THRESHOLDS["power_min"], THRESHOLDS["power_max"]
    core_lo, core_hi = PWF_HEALTHY_CORE

    if p < core_lo:
        return clip01((core_lo - p) / (core_lo - lo))
    if p > core_hi:
        return clip01((p - core_hi) / (hi - core_hi))
    return 0.0


def stress_osf(strain: float, machine_type: str) -> float:
    """Tool strain as a fraction of this variant's overstrain limit."""
    limit = THRESHOLDS["osf_limit"].get(str(machine_type).upper().strip(),
                                        THRESHOLDS["osf_limit"]["L"])
    return clip01(float(strain) / limit)


# ==================================================================
#  COMBINED
# ==================================================================
def stress_profile(machine_type, air_temperature, process_temperature,
                   rotational_speed, torque, tool_wear) -> dict:
    """
    Full stress breakdown for one reading.

    Returns the derived quantities, the per-mechanism stress ratios,
    the dominant mechanism and the overall stress (its max).
    """
    d = derive(air_temperature, process_temperature,
               rotational_speed, torque, tool_wear)

    per_mode = {
        "TWF": stress_twf(tool_wear),
        "HDF": stress_hdf(d["temp_delta"], rotational_speed),
        "PWF": stress_pwf(d["power"]),
        "OSF": stress_osf(d["strain"], machine_type),
    }

    dominant = max(per_mode, key=per_mode.get)

    return {
        "derived": d,
        "stress": per_mode,
        "dominant_mode": dominant,
        "overall_stress": per_mode[dominant],
    }


# ==================================================================
#  THRESHOLD BREACH CHECK (used by the alarm engine)
# ==================================================================
def breaches(machine_type, air_temperature, process_temperature,
             rotational_speed, torque, tool_wear) -> list[dict]:
    """
    Which physical limits are ACTUALLY violated right now.
    This is a deterministic rule check, reported alongside - and
    independently of - the model's opinion.
    """
    d = derive(air_temperature, process_temperature,
               rotational_speed, torque, tool_wear)
    out = []

    if (d["temp_delta"] < THRESHOLDS["temp_delta_min"]
            and float(rotational_speed) < THRESHOLDS["hdf_speed_max"]):
        out.append({
            "mode": "HDF",
            "detail": "Thermal gradient {:.2f} K is below the {:.1f} K minimum "
                      "while speed {:.0f} rpm is below {:.0f} rpm".format(
                          d["temp_delta"], THRESHOLDS["temp_delta_min"],
                          float(rotational_speed), THRESHOLDS["hdf_speed_max"]),
        })

    if d["power"] < THRESHOLDS["power_min"]:
        out.append({
            "mode": "PWF",
            "detail": "Mechanical power {:.0f} W is below the {:.0f} W minimum "
                      "(drive under-load)".format(d["power"], THRESHOLDS["power_min"]),
        })
    elif d["power"] > THRESHOLDS["power_max"]:
        out.append({
            "mode": "PWF",
            "detail": "Mechanical power {:.0f} W exceeds the {:.0f} W maximum "
                      "(drive over-load)".format(d["power"], THRESHOLDS["power_max"]),
        })

    limit = THRESHOLDS["osf_limit"].get(str(machine_type).upper().strip(),
                                        THRESHOLDS["osf_limit"]["L"])
    if d["strain"] > limit:
        out.append({
            "mode": "OSF",
            "detail": "Tool strain {:,.0f} minNm exceeds the {:,.0f} minNm limit "
                      "for variant {}".format(d["strain"], limit, machine_type),
        })

    if float(tool_wear) >= THRESHOLDS["tool_wear_min"]:
        out.append({
            "mode": "TWF",
            "detail": "Tool wear {:.0f} min has entered the {:.0f}-{:.0f} min "
                      "replacement window".format(
                          float(tool_wear), THRESHOLDS["tool_wear_min"],
                          THRESHOLDS["tool_wear_max"]),
            "hard": False,
        })

    for b in out:
        b.setdefault("hard", True)

    return out


def has_hard_breach(breach_list) -> bool:
    """
    Has a limit been crossed that means the machine HAS FAILED?

    Entering the tool-wear window is not such a limit. It is a
    scheduled-maintenance condition: the tool is due for change, the
    machine is still cutting, and in AI4I only ~6% of readings inside
    that window are actually labelled TWF. Treating it as a hard
    failure would drive the health gauge to the floor on every machine
    that simply needs a new tool.
    """
    return any(b.get("hard", True) for b in (breach_list or []))
