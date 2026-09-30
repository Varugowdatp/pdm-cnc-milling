"""
============================================================
 AI-BASED PREDICTIVE MAINTENANCE FOR CNC MILLING MACHINES
 Central configuration: paths, schema, constants
============================================================
Every module imports its paths and constants from here so that
the whole pipeline (data -> features -> model -> API -> UI)
shares one single source of truth.
"""

from pathlib import Path

# ------------------------------------------------------------------
# 0. MONITORED MACHINE
#    AI4I 2020 simulates a CNC milling process (spindle speed, spindle
#    torque, cutter wear, air/process temperature), so every machine in
#    this system is a CNC milling machine.
# ------------------------------------------------------------------
MACHINE_NAME = "CNC Milling Machine"
PROJECT_TITLE = "AI-Based Predictive Maintenance for CNC Milling Machines"

# ------------------------------------------------------------------
# 1. PROJECT PATHS
# ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

MODEL_DIR = ROOT / "models"
ARTIFACT_DIR = ROOT / "artifacts"
PLOT_DIR = ARTIFACT_DIR / "plots"
METRIC_DIR = ARTIFACT_DIR / "metrics"

REPORT_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"

for _d in (RAW_DIR, PROCESSED_DIR, MODEL_DIR, PLOT_DIR, METRIC_DIR, REPORT_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 2. DATASET SOURCE (UCI AI4I 2020)
# ------------------------------------------------------------------
UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
UCI_MIRRORS = [
    "https://raw.githubusercontent.com/AmitVikram/ai4i2020/main/ai4i2020.csv",
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00601/ai4i2020.csv",
]

RAW_CSV = RAW_DIR / "ai4i2020.csv"
EXPANDED_CSV = PROCESSED_DIR / "pdm_expanded_dataset.csv"
FEATURED_CSV = PROCESSED_DIR / "pdm_featured_dataset.csv"

# ------------------------------------------------------------------
# 3. SENSOR SCHEMA  (replaces the physical sensors of the synopsis)
#    Each entry: canonical name -> (unit, min, max, HMI label)
# ------------------------------------------------------------------
SENSORS = {
    "air_temperature":    {"unit": "K",   "min": 290.0, "max": 315.0, "label": "Air Temperature",    "icon": "thermo"},
    "process_temperature":{"unit": "K",   "min": 300.0, "max": 320.0, "label": "Process Temperature","icon": "thermo"},
    "rotational_speed":   {"unit": "rpm", "min": 1000.0,"max": 3000.0,"label": "Rotational Speed",   "icon": "rpm"},
    "torque":             {"unit": "Nm",  "min": 3.0,   "max": 80.0,  "label": "Torque",             "icon": "torque"},
    "tool_wear":          {"unit": "min", "min": 0.0,   "max": 260.0, "label": "Tool Wear",          "icon": "wear"},
}
SENSOR_COLS = list(SENSORS.keys())

MACHINE_TYPES = ["L", "M", "H"]          # Low / Medium / High quality variant
MACHINE_TYPE_DESC = {
    "L": "Low quality variant (50% of production)",
    "M": "Medium quality variant (30% of production)",
    "H": "High quality variant (20% of production)",
}

# ------------------------------------------------------------------
# 4. TARGET: FAILURE MODES
# ------------------------------------------------------------------
FAILURE_CLASSES = ["Normal", "TWF", "HDF", "PWF", "OSF"]

FAILURE_INFO = {
    "Normal": {
        "name": "Normal Operation",
        "severity": "NORMAL",
        "cause": "All monitored parameters are within their safe operating envelope.",
        "action": "No maintenance action required. Continue routine condition monitoring.",
        "color": "#22c55e",
    },
    "TWF": {
        "name": "Tool Wear Failure",
        "severity": "WARNING",
        "cause": "The milling cutter (end mill) has exceeded its usable wear life (200-240 min); edge degradation causes poor surface finish and rising cutting forces.",
        "action": "Change the end mill (or re-grind it) at the next production break and reset the CNC tool-life counter after the tool change.",
        "color": "#f59e0b",
    },
    "HDF": {
        "name": "Heat Dissipation Failure",
        "severity": "CRITICAL",
        "cause": "Temperature difference between the cutting process and the ambient air is below 8.6 K while spindle speed is under 1380 rpm - the milling machine cannot shed its heat.",
        "action": "Check the coolant supply and concentration, clean the coolant filter and spindle-chiller fins, verify the spindle cooling fan. Reduce the cutting load until the temperature delta recovers.",
        "color": "#ef4444",
    },
    "PWF": {
        "name": "Power Failure",
        "severity": "CRITICAL",
        "cause": "Spindle cutting power (torque x angular speed) has drifted outside the 3500-9000 W design window - spindle drive over/under-load.",
        "action": "Check the spindle motor drive, supply voltage and current draw. Verify feed rate and depth of cut, belt/coupling alignment, and inspect the spindle for binding.",
        "color": "#ef4444",
    },
    "OSF": {
        "name": "Overstrain Failure",
        "severity": "CRITICAL",
        "cause": "Product of cutter wear and spindle torque has exceeded the strain limit for this product variant - the end mill and spindle are being overstressed.",
        "action": "Reduce feed rate and depth of cut immediately, replace the worn end mill, and inspect the spindle bearings and tool holder for damage.",
        "color": "#ef4444",
    },
}

# ------------------------------------------------------------------
# 5. PHYSICS THRESHOLDS (from the AI4I 2020 dataset definition)
#    Used by the synthetic expander AND by the rule/alarm engine.
# ------------------------------------------------------------------
THRESHOLDS = {
    "tool_wear_min": 200.0,          # TWF window start  (min)
    "tool_wear_max": 240.0,          # TWF window end    (min)
    "temp_delta_min": 8.6,           # HDF: below this K delta -> poor heat dissipation
    "hdf_speed_max": 1380.0,         # HDF: combined with low speed (rpm)
    "power_min": 3500.0,             # PWF lower bound (W)
    "power_max": 9000.0,             # PWF upper bound (W)
    "osf_limit": {"L": 11000.0, "M": 12000.0, "H": 13000.0},  # OSF: wear*torque minNm
}

# ------------------------------------------------------------------
# 6. ALARM / HEALTH BANDS
# ------------------------------------------------------------------
ALARM_LEVELS = ["NORMAL", "ADVISORY", "WARNING", "CRITICAL"]

HEALTH_BANDS = [
    (85, 100, "NORMAL",   "#22c55e", "Healthy"),
    (65, 85,  "ADVISORY", "#38bdf8", "Monitor"),
    (40, 65,  "WARNING",  "#f59e0b", "Degrading"),
    (0,  40,  "CRITICAL", "#ef4444", "Critical"),
]

# ------------------------------------------------------------------
# 7. MODEL SETTINGS  (ONE ALGORITHM: RANDOM FOREST)
# ------------------------------------------------------------------
ALGORITHM_NAME = "Random Forest Classifier"

# ------------------------------------------------------------------
# TRAINING TARGET
# ------------------------------------------------------------------
# "failure_class"  = the physics-true state of the machine RIGHT NOW.
#                    A model trained on this can only fire once a
#                    threshold has already been crossed, which makes
#                    the system REACTIVE (measured lead time: -3.7
#                    readings, i.e. it alarms after the fault).
#
# "label_horizon"  = the same class, extended backwards over the
#                    PREDICTION_HORIZON readings that precede the
#                    trip. The model must then learn the APPROACH to
#                    the limit rather than the limit itself, which is
#                    the standard predictive-maintenance formulation
#                    ("will this machine fail within the next H
#                    readings?") and is what makes the system
#                    genuinely PREDICTIVE.
TARGET_COLUMN = "label_horizon"
RANDOM_STATE = 42
TEST_SIZE = 0.20
CV_FOLDS = 5

MODEL_PATH = MODEL_DIR / "random_forest_pdm.joblib"
BUNDLE_PATH = MODEL_DIR / "pdm_model_bundle.joblib"
METRICS_PATH = METRIC_DIR / "model_metrics.json"

# ------------------------------------------------------------------
# 8. SYNTHETIC EXPANSION SETTINGS
# ------------------------------------------------------------------
N_MACHINES = 220                 # run-to-failure machine cycles to synthesise
MIN_CYCLE_LEN = 200              # shortest machine life (readings)
MAX_CYCLE_LEN = 460              # longest machine life (readings)
EXPANSION_SEED = 42

# Early-warning horizon: readings before failure that are considered
# "incipient fault" for the lead-time analysis in the final report.
PREDICTION_HORIZON = 15          # readings (= 2.5 operating hours @10 min)

# ------------------------------------------------------------------
# 9. HMI / PLOT THEME
# ------------------------------------------------------------------
THEME = {
    "bg": "#0b1220",
    "panel": "#111c2e",
    "grid": "#1e2d45",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "accent": "#38bdf8",
    "ok": "#22c55e",
    "warn": "#f59e0b",
    "crit": "#ef4444",
}
PLOT_PALETTE = ["#38bdf8", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa", "#f472b6"]
