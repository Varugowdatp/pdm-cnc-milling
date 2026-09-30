"""
============================================================
 PHASE 1 - STEP 2 : PHYSICS-INFORMED DATASET EXPANSION
============================================================
The raw AI4I 2020 dataset contains 10,000 INDEPENDENT snapshots.
It carries no machine identity, no time ordering, and therefore no
Remaining Useful Life (RUL) label.

Our HMI must show, for one real machine:
    * live sensor trends over time,
    * a degrading health index,
    * an RUL countdown.

So this module synthesises RUN-TO-FAILURE HISTORIES for N virtual
machines using EXACTLY the physics that governs the AI4I dataset
(rules verified empirically against the raw file - 98/98 OSF,
115/115 HDF, 95/95 PWF reproduced):

    power        = torque x speed x 2*pi/60                    [W]
    temp_delta   = process_temperature - air_temperature       [K]
    strain       = tool_wear x torque                          [minNm]

    TWF  tool wear crosses its replacement window (200-240 min)
    HDF  temp_delta < 8.6 K  AND  speed < 1380 rpm
    PWF  power < 3500 W  OR  power > 9000 W
    OSF  strain > {L:11000, M:12000, H:13000} minNm

--------------------------------------------------------------------
 KEY MODELLING INSIGHT
--------------------------------------------------------------------
 The spread in AI4I is BETWEEN 10,000 different products, not WITHIN
 one machine's run. If that full spread is applied as within-machine
 noise, a healthy machine trips a fault threshold by pure chance
 within a few dozen readings.

 So each virtual machine is given its own stable OPERATING POINT drawn
 from the population distribution, and only small within-machine noise
 on top. Population statistics are preserved; individual runs stay
 healthy until degradation actually sets in. This is also what happens
 physically: unit-to-unit variation >> minute-to-minute variation.

 Degradation is then TARGETED: each machine is driven so that its
 assigned mechanism is the one that crosses its limit first, which
 gives a balanced set of failure modes instead of whichever threshold
 random noise happened to hit.
--------------------------------------------------------------------

Usage:  python -m src.data.expand_dataset
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.config import (
    EXPANDED_CSV,
    EXPANSION_SEED,
    MACHINE_TYPES,
    MAX_CYCLE_LEN,
    MIN_CYCLE_LEN,
    N_MACHINES,
    PREDICTION_HORIZON,
    RAW_CSV,
    THRESHOLDS,
)

# Priority used when more than one failure condition is true at once.
MODE_PRIORITY = ["HDF", "PWF", "OSF", "TWF"]

TYPE_PROBS = [0.50, 0.30, 0.20]          # L / M / H - same split as AI4I
SAMPLE_INTERVAL_MIN = 10                 # one sensor reading every 10 minutes

# --- within-machine (minute-to-minute) noise: small ---
NOISE = {
    "air": 0.55,        # K
    "delta": 0.30,      # K
    "torque": 2.4,      # Nm
    "k": 2000.0,        # rpm.Nm
}


# ==================================================================
#  CALIBRATION - inherit the real dataset's statistical fingerprint
# ==================================================================
def calibrate(raw_csv=RAW_CSV) -> dict:
    df = pd.read_csv(raw_csv)
    df.columns = [c.strip() for c in df.columns]

    air = df["Air temperature [K]"]
    proc = df["Process temperature [K]"]
    speed = df["Rotational speed [rpm]"]
    torque = df["Torque [Nm]"]
    k = speed * torque                    # rpm*Nm -> constant-power term

    cal = {
        "air_mean": float(air.mean()),   "air_std": float(air.std()),
        "delta_mean": float((proc - air).mean()), "delta_std": float((proc - air).std()),
        "torque_mean": float(torque.mean()), "torque_std": float(torque.std()),
        "k_mean": float(k.mean()),       "k_std": float(k.std()),
    }
    print("  Calibrated from the real AI4I data:")
    print("    air temperature    : {:.2f} +/- {:.2f} K".format(cal["air_mean"], cal["air_std"]))
    print("    temp delta         : {:.2f} +/- {:.2f} K".format(cal["delta_mean"], cal["delta_std"]))
    print("    torque             : {:.2f} +/- {:.2f} Nm".format(cal["torque_mean"], cal["torque_std"]))
    print("    speed x torque (K) : {:.0f} +/- {:.0f} rpm.Nm".format(cal["k_mean"], cal["k_std"]))
    return cal


# ==================================================================
#  PHYSICS - identical rules applied to real and synthetic rows
# ==================================================================
def power_watt(torque, speed):
    """Mechanical power P = T * omega,  omega = 2*pi*N/60."""
    return torque * speed * 2.0 * np.pi / 60.0


def evaluate_conditions(m_type, air, proc, speed, torque, wear, twf_trigger):
    """Boolean mask per failure mode, straight from the AI4I definition."""
    delta = proc - air
    return {
        "TWF": wear >= twf_trigger,
        "HDF": (delta < THRESHOLDS["temp_delta_min"]) & (speed < THRESHOLDS["hdf_speed_max"]),
        "PWF": (power_watt(torque, speed) < THRESHOLDS["power_min"])
               | (power_watt(torque, speed) > THRESHOLDS["power_max"]),
        "OSF": (wear * torque) > THRESHOLDS["osf_limit"][m_type],
    }


def resolve_class(masks):
    """Collapse the four boolean masks into one class-label array."""
    n = len(next(iter(masks.values())))
    out = np.array(["Normal"] * n, dtype=object)
    for mode in reversed(MODE_PRIORITY):        # highest priority written last
        out[masks[mode]] = mode
    return out


# ==================================================================
#  OU RANDOM WALK - bounded, mean-reverting, like a real sensor
# ==================================================================
def ou_walk(rng, n, mean, std, theta=0.25):
    x = np.empty(n)
    x[0] = mean
    sigma = std * np.sqrt(2.0 * theta)
    for i in range(1, n):
        x[i] = x[i - 1] + theta * (mean - x[i - 1]) + rng.normal(0.0, sigma)
    return x


# ==================================================================
#  ONE MACHINE : COMMISSIONING -> FAILURE
# ==================================================================
def simulate_machine(rng, cal, machine_idx, mode, start_time):
    m_type = str(rng.choice(MACHINE_TYPES, p=TYPE_PROBS))
    osf_limit = THRESHOLDS["osf_limit"][m_type]

    life = int(rng.integers(MIN_CYCLE_LEN, MAX_CYCLE_LEN))
    t = np.arange(life)
    denom = max(life - 1, 1)

    # accelerating degradation: gentle at first, rapid near end-of-life
    deg = (t / denom) ** rng.uniform(1.8, 3.0)          # 0.0 -> 1.0

    # ---------------- 1. machine operating point ----------------
    # drawn from the population, then clamped into a healthy envelope
    air0 = float(np.clip(rng.normal(cal["air_mean"], cal["air_std"]), 295.5, 304.0))
    delta0 = float(np.clip(rng.normal(cal["delta_mean"], cal["delta_std"]), 9.4, 12.0))
    k0 = float(np.clip(rng.normal(cal["k_mean"], cal["k_std"]), 44000.0, 76000.0))

    # ---------------- 2. tool-wear trajectory ----------------
    wear_end = {
        "TWF": rng.uniform(236.0, 253.0),
        "OSF": rng.uniform(200.0, 236.0),
        "HDF": rng.uniform(70.0, 170.0),
        "PWF": rng.uniform(70.0, 170.0),
    }[mode]

    # ---------------- 3. torque operating point ----------------
    # chosen so the machine's OWN mechanism is the one that trips first
    if mode == "TWF":
        # keep strain safely under the OSF limit so TWF wins the race
        t_hi = min(52.0, 0.80 * osf_limit / wear_end)
        torque0 = float(rng.uniform(max(22.0, t_hi - 14.0), t_hi))
    elif mode == "OSF":
        torque0 = float(np.clip(rng.normal(cal["torque_mean"], 6.0), 28.0, 50.0))
    else:
        torque0 = float(np.clip(rng.normal(cal["torque_mean"], 7.0), 26.0, 54.0))

    # ---------------- 4. baseline signals ----------------
    air = ou_walk(rng, life, air0, NOISE["air"])
    delta = ou_walk(rng, life, delta0, NOISE["delta"])
    torque = ou_walk(rng, life, torque0, NOISE["torque"])
    k = ou_walk(rng, life, k0, NOISE["k"])

    wear = wear_end * (t / denom) ** rng.uniform(0.9, 1.15)
    wear = np.maximum.accumulate(wear + rng.normal(0, 0.30, life)).clip(0, 253)

    twf_trigger = (
        float(rng.uniform(THRESHOLDS["tool_wear_min"], THRESHOLDS["tool_wear_max"]))
        if mode == "TWF" else 1e9
    )

    # ---------------- 5. TARGETED degradation ----------------
    # each ramp is sized so the mechanism crosses its limit at deg ~= 1
    sub_mode = ""

    if mode == "HDF":
        # cooling capacity fades: ambient climbs toward the process
        # temperature and the loaded spindle slows down
        delta_drop = (delta0 - THRESHOLDS["temp_delta_min"]) + rng.uniform(0.9, 2.0)
        air_rise = rng.uniform(1.5, 3.0)
        # speed must end below 1380 rpm -> shrink K, raise torque
        torque_rise = rng.uniform(4.0, 10.0)
        target_speed = THRESHOLDS["hdf_speed_max"] - rng.uniform(50.0, 160.0)
        k_end = target_speed * (torque0 + torque_rise)

        air = air + deg * air_rise
        delta = delta - deg * delta_drop
        torque = torque + deg * torque_rise
        k = k + deg * (k_end - k0)

    elif mode == "PWF":
        sub_mode = str(rng.choice(["overload", "underload"]))
        if sub_mode == "overload":
            k_end = (THRESHOLDS["power_max"] + rng.uniform(250.0, 1200.0)) * 60.0 / (2.0 * np.pi)
        else:
            k_end = (THRESHOLDS["power_min"] - rng.uniform(250.0, 900.0)) * 60.0 / (2.0 * np.pi)
        k = k + deg * (k_end - k0)

    elif mode == "OSF":
        # rising cutting resistance: torque climbs until wear x torque
        # exceeds this machine variant's strain limit
        torque_end = (osf_limit * rng.uniform(1.06, 1.18)) / wear_end
        torque_end = float(np.clip(torque_end, torque0 + 4.0, torque0 + 34.0))
        torque = torque + deg * (torque_end - torque0)

    elif mode == "TWF":
        torque = torque + deg * rng.uniform(0.5, 2.5)

    # ---------------- 6. derived signals ----------------
    torque = np.clip(torque, 3.5, None)
    speed = np.clip(k / torque, 900.0, 3200.0)
    proc = air + delta

    # ---------------- 7. label every reading ----------------
    masks = evaluate_conditions(m_type, air, proc, speed, torque, wear, twf_trigger)
    labels = resolve_class(masks)
    faulted = labels != "Normal"

    # a newly commissioned machine must run clean for a while
    if faulted[: max(int(0.30 * life), 8)].any():
        return None
    if not faulted.any():
        return None                       # degradation never bit - regenerate

    fail_idx = int(np.argmax(faulted))

    # keep a short alarm tail AFTER the fault appears, before the
    # operator intervenes - this is where the fault signature lives
    end = min(fail_idx + int(rng.integers(8, 32)), life)
    n = end

    rul = np.clip(fail_idx - t[:n], 0, None)
    health = np.clip(100.0 * (rul / max(fail_idx, 1)) ** 0.75, 0.0, 100.0)

    # early-warning label: the mechanism is already incipient in the
    # PREDICTION_HORIZON readings before it formally trips
    horizon_label = labels[:n].copy()
    incipient = (rul > 0) & (rul <= PREDICTION_HORIZON)
    horizon_label[incipient] = mode

    return pd.DataFrame({
        "machine_id": "MC-{:03d}".format(machine_idx),
        "cycle": t[:n],
        "timestamp": [start_time + timedelta(minutes=SAMPLE_INTERVAL_MIN * int(i))
                      for i in range(n)],
        "machine_type": m_type,
        "air_temperature": np.round(air[:n], 2),
        "process_temperature": np.round(proc[:n], 2),
        "rotational_speed": np.round(speed[:n]).astype(int),
        "torque": np.round(torque[:n], 2),
        "tool_wear": np.round(wear[:n], 1),
        "failure_class": labels[:n],
        "label_horizon": horizon_label,
        "machine_failure": faulted[:n].astype(int),
        "rul": rul,
        "health_target": np.round(health, 1),
        "degradation_mode": mode + ((":" + sub_mode) if sub_mode else ""),
        "source": "SYNTH-RUN2FAIL",
    })


# ==================================================================
#  REAL AI4I ROWS -> UNIFIED SCHEMA
# ==================================================================
def load_real(raw_csv=RAW_CSV) -> pd.DataFrame:
    df = pd.read_csv(raw_csv)
    df.columns = [c.strip() for c in df.columns]

    out = pd.DataFrame({
        "machine_id": df["Product ID"],
        "cycle": 0,
        "timestamp": pd.NaT,
        "machine_type": df["Type"],
        "air_temperature": df["Air temperature [K]"],
        "process_temperature": df["Process temperature [K]"],
        "rotational_speed": df["Rotational speed [rpm]"],
        "torque": df["Torque [Nm]"],
        "tool_wear": df["Tool wear [min]"],
    })

    # Resolve the 5 one-hot mode columns into a single class label.
    # RNF ("random failure") is unpredictable measurement noise, not a
    # learnable mechanism, so RNF-only rows remain Normal - the standard
    # treatment of RNF in the AI4I literature.
    labels = np.array(["Normal"] * len(df), dtype=object)
    for mode in reversed(MODE_PRIORITY):
        labels[df[mode].to_numpy() == 1] = mode

    out["failure_class"] = labels
    out["label_horizon"] = labels
    out["machine_failure"] = (out["failure_class"] != "Normal").astype(int)
    out["rul"] = np.nan
    out["health_target"] = np.nan
    out["degradation_mode"] = ""
    out["source"] = "AI4I-2020"
    return out


# ==================================================================
def main() -> int:
    print("\n" + "=" * 66)
    print(" PHASE 1 | STEP 2 : PHYSICS-INFORMED DATASET EXPANSION")
    print("=" * 66)

    if not RAW_CSV.exists():
        print("ERROR: raw dataset not found at {}".format(RAW_CSV))
        print("Run:  python -m src.data.download_dataset")
        return 1

    cal = calibrate()
    rng = np.random.default_rng(EXPANSION_SEED)

    print("\n  Simulating {} run-to-failure machine histories ...".format(N_MACHINES))
    modes = [MODE_PRIORITY[i % len(MODE_PRIORITY)] for i in range(N_MACHINES)]
    rng.shuffle(modes)

    base_time = datetime(2025, 1, 1, 6, 0, 0)
    frames, made, attempts = [], 0, 0

    while made < N_MACHINES and attempts < N_MACHINES * 60:
        attempts += 1
        df_m = simulate_machine(rng, cal, made + 1, modes[made],
                                base_time + timedelta(days=int(made) * 3))
        if df_m is None:
            continue
        frames.append(df_m)
        made += 1
        if made % 40 == 0:
            print("    ... {}/{} machines  ({:,} readings)".format(
                made, N_MACHINES, sum(len(f) for f in frames)))

    synth = pd.concat(frames, ignore_index=True)
    real = load_real()
    combined = pd.concat([real, synth], ignore_index=True)
    combined.to_csv(EXPANDED_CSV, index=False)

    # ------------------------- report -------------------------
    print("\n" + "-" * 66)
    print("  Real AI4I rows       : {:,}".format(len(real)))
    print("  Synthetic rows       : {:,}  from {} machines".format(len(synth), made))
    print("  TOTAL DATASET        : {:,} rows".format(len(combined)))
    print("  Simulation attempts  : {}  (rejected {} invalid runs)".format(
        attempts, attempts - made))
    print("  Mean machine life    : {:.0f} readings ({:.1f} operating hours)".format(
        len(synth) / made, len(synth) / made * SAMPLE_INTERVAL_MIN / 60))
    print("-" * 66)

    print("\n  Failure-class distribution (combined):")
    for cls, cnt in combined["failure_class"].value_counts().items():
        print("    {:<8} {:>7,}  ({:5.2f} %)".format(cls, cnt, cnt / len(combined) * 100))

    print("\n  Class distribution by source:")
    print(pd.crosstab(combined["source"], combined["failure_class"]).to_string())

    print("\n  Assigned mechanism vs. mechanism that actually tripped (synthetic):")
    assigned = synth["degradation_mode"].str.split(":").str[0]
    trip = synth[synth["machine_failure"] == 1].groupby(
        synth["machine_id"])["failure_class"].first()
    asg = assigned.groupby(synth["machine_id"]).first()
    print(pd.crosstab(asg.loc[trip.index], trip).to_string())

    print("\n  RUL available on {:,} rows (range {:.0f} - {:.0f} readings)".format(
        int(combined["rul"].notna().sum()), combined["rul"].min(), combined["rul"].max()))
    print("\nSaved -> {}  ({:.1f} MB)".format(EXPANDED_CSV, EXPANDED_CSV.stat().st_size / 1e6))
    print("=" * 66 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
