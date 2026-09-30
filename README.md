# AI-Based Predictive Maintenance for CNC Milling Machines

A complete predictive-maintenance system for **CNC milling machines**: it predicts **which** failure a machine
is heading toward, **a mean of 8.67 operating hours before it happens**, and warns
before failure on **97.6% of unseen machines** — then shows an operator the health,
the remaining life, the recommended action, and the exact reason for every
prediction.

Built for the Dept. of Electronics & Communication Engineering, Government
Engineering College, K. R. Pete. Fully software — no hardware required.

---

## Monitored machine — CNC Milling Machine

Every machine in this system is a **CNC milling machine**: a motor-driven spindle
turns a multi-point cutter (end mill) that removes metal from a workpiece. The
AI4I 2020 dataset was generated to model exactly this process, so each input maps
directly onto the machine:

| Dataset quantity | On a CNC milling machine |
|---|---|
| Rotational speed [rpm] | Spindle speed (≈ 1,200 – 2,900 rpm in the data) |
| Torque [Nm] | Spindle torque while the cutter is engaged |
| Tool wear [min] | Cutting time on the current end mill |
| Process temperature [K] | Spindle / cutting-zone temperature |
| Air temperature [K] | Ambient shop-floor temperature |
| Type L / M / H | Quality grade of the part being machined |

| Failure | What it means on the milling machine | Maintenance action |
|---|---|---|
| **TWF** | End mill worn out (200–240 min of cutting) | Change / re-grind the end mill, reset the tool-life counter |
| **HDF** | Spindle and cutting zone cannot shed heat | Check coolant supply, clean chiller fins, verify the fan |
| **PWF** | Spindle drive outside the 3,500–9,000 W power window | Check the spindle drive, feed rate and depth of cut |
| **OSF** | Worn cutter × high torque overstresses the spindle | Cut feed / depth immediately, change the end mill, inspect bearings |

The name lives in one place — `MACHINE_NAME` in `src/config.py`.

## Quick start

```bash
cd "AI BASED PREDICTIVE MAINTENCE FOR INDUSTRIAL MACHINES"

# 1. Start the system  (model and dataset are already built)
./.venv/Scripts/python.exe -m backend.app
```

Open **http://127.0.0.1:8000/** and press **▶ Start Demo Plant**.

That is the whole demo. No build step, no `npm install`, and **no internet
connection required.**

---

## What you are looking at

| Screen | What it shows |
|---|---|
| **Plant Overview** | Every machine as a status card, worst first. KPI strip, LED lamps, health bars. |
| **Machine HMI** | Five analogue dials, health ring, RUL countdown, live trends, alarm banner, and the **held-out ground truth** so you can judge the model. |
| **Manual Input** | Type one reading (or use a preset) → full verdict with an exact explanation. |
| **Batch Analysis** | Drop a CSV/Excel file → score every row → download the annotated file. |
| **Alarms** | Maintenance log, one entry per alarm *event*, acknowledgeable. |
| **Model Insights** | Lead time, metrics, confusion matrix, feature importance, and a **live proof** that the explanation panel reproduces the model exactly. |

**Important:** a predicted class means the machine is **heading for** that failure,
not that it has already failed. The UI distinguishes `PREDICTED` (act now, the
machine still runs) from `LIMIT BREACHED` (the limit has already gone).

---

## Requirements

- **Python 3.12** (virtual environment already provisioned at `.venv/`)
- A modern browser
- ~500 MB disk

To recreate the environment from scratch:

```bash
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

---

## Rebuilding from scratch

The trained model and processed dataset ship with the project. To regenerate
everything:

```bash
# full Phase 1 pipeline: download → expand → EDA → train → evaluate   (~10 min)
./.venv/Scripts/python.exe run_phase1.py

# or resume from a stage  (1 download, 2 expand, 3 eda, 4 train, 5 evaluate)
./.venv/Scripts/python.exe run_phase1.py --from 4
./.venv/Scripts/python.exe run_phase1.py --only 5

# alarm-quality / false-positive analysis
./.venv/Scripts/python.exe -m src.evaluation.alarm_quality
```

---

## Tests

```bash
./.venv/Scripts/python.exe -m pytest tests/ -q     # 57 engine + API tests
node tests/test_widgets.js                          # 29 SVG widget assertions
node tests/test_boot.js                             # 17 boot / load-order assertions
```

All 103 pass.

---

## Project layout

```
├── Main synopsis (2).pdf        source requirements
├── run_phase1.py                ML pipeline runner
├── requirements.txt
│
├── src/                         PHASE 1 — data & model
│   ├── config.py                single source of truth: paths, schema, thresholds
│   ├── data/                    download, physics-informed expansion, EDA
│   ├── features/                shared feature builder (training AND inference)
│   ├── models/train_model.py
│   └── evaluation/              evaluate.py, alarm_quality.py
│
├── backend/                     PHASE 2 — engine & API
│   ├── app.py                   FastAPI app (serves the API and the HMI)
│   ├── core/                    physics, health, alarms, database
│   ├── services/                predictor, explainer, simulator
│   └── api/                     routes (25 endpoints), schemas
│
├── docs/                        3 PDF reports + their generators
├── frontend/                    PHASE 3 — SCADA HMI (zero dependencies)
│   ├── index.html
│   ├── css/style.css
│   └── js/                      api, widgets (SVG), app, screens/
│
├── tests/                       57 Python + 46 JS assertions
├── data/                        raw + processed datasets, runtime SQLite
├── models/                      trained Random Forest bundle
└── artifacts/                   13 figures + metrics JSON
```

---

## Documentation

### PDF reports (in `docs/`)

| Document | For whom |
|---|---|
| **`docs/01_TEST_CASES_AND_EXPECTED_OUTPUT.pdf`** | 159 test cases with exact expected values (36 pp) |
| **`docs/02_FINAL_YEAR_PROJECT_REPORT.pdf`** | The academic project report (30 pp) |
| **`docs/ESSENTIAL_WEBSITE_TEST_CASES.md`** | The 12 must-pass website tests for a demo / viva |
| **`docs/03_USER_INTERFACE_GUIDE.pdf`** | Every screen explained in plain English (26 pp) |
| **`docs/04_PROJECT_FILE_GUIDE.pdf`** | What every file and folder in the project is (24 pp) |

Every figure in them is captured from the running system — see `docs/README.md`.

### Markdown documents

| Document | Contents |
|---|---|
| **`PROJECT_REPORT.md`** | **The complete report** — start here |

Interactive API documentation is served at **http://127.0.0.1:8000/docs** while
the app is running.

---

## Key results

| | |
|---|---|
| **Mean early warning** | **+52 readings = 8.67 operating hours** |
| **Machines warned before failure** | **97.6%** (of 42 unseen machines) |
| Algorithm | Random Forest, 300 trees, 10 features |
| Dataset | 74,979 rows / 220 machines (UCI AI4I 2020 + physics-informed expansion) |
| Test set | 15,195 rows, group-disjoint by machine |
| Balanced accuracy | 0.8483 · macro recall 0.8483 |
| ROC-AUC per class | 0.95 – 0.995 |
| Explanation exactness | 8.9 × 10⁻¹⁶ (machine precision) |

### Why accuracy is not the headline

An earlier model trained on the machine's *current* state scored **0.9899
accuracy** — and had a lead time of **−3.7 readings**: it raised the alarm about 37
minutes *after* the fault. Retraining on a prediction-horizon target cost 8 points
of accuracy and turned a condition monitor into a genuinely predictive system.

That trade is the point of the project. See `PROJECT_REPORT.md` §5.

---

## Using it with your own data

Upload a CSV or Excel file on the **Batch Analysis** screen. Required columns:

| Column | Unit | Also accepted |
|---|---|---|
| `machine_type` | L / M / H | `Type`, `variant` |
| `air_temperature` | K | `Air temperature [K]` |
| `process_temperature` | K | `Process temperature [K]` |
| `rotational_speed` | rpm | `Rotational speed [rpm]`, `rpm` |
| `torque` | Nm | `Torque [Nm]` |
| `tool_wear` | min | `Tool wear [min]` |

`machine_id` is optional but recommended — with it, rows are processed in order per
machine so the RUL trend and alarm persistence work as they do on the live feed.

Download a blank template at `/api/predict/template`, or a real 300-reading
run-to-failure trajectory at `/api/predict/sample`.

---

## Troubleshooting

**"Model bundle not found"** — run `./.venv/Scripts/python.exe run_phase1.py`.

**Port 8000 already in use** —
`./.venv/Scripts/python.exe -m uvicorn backend.app:app --port 8001`

**The HMI shows "backend offline"** — the API is not running, or it is on a
different port. Check the terminal where you started `backend.app`.

**Reset the demo** — press **Reset Plant** on the Overview screen, or
`POST /api/system/reset`.
