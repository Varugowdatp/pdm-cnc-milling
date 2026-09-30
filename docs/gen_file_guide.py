"""
Generates  docs/04_PROJECT_FILE_GUIDE.pdf

A folder-by-folder guide to every file in the project: what it is, what
produces it, and whether it can be regenerated.

The file list is NOT typed by hand. The script walks the real project
folder and fails loudly if it finds a file that has no description, so
the guide can never silently fall out of step with the folder.
Batch-test file descriptions are read from batch_testing/00_TEST_INDEX.xlsx.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
from pdf_kit import (
    CONTENT_W, H1, H2, P, Report, bullets, callout, cover, spacer, table, toc,
)
from reportlab.platypus import PageBreak

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import MACHINE_NAME, PROJECT_TITLE  # noqa: E402

OUT = ROOT / "docs" / "04_PROJECT_FILE_GUIDE.pdf"

# Folders that belong to tools, not to the project. Described once as a
# folder, never walked.
TOOL_DIRS = {
    ".venv": "Python virtual environment: the interpreter and every installed library "
             "(FastAPI, scikit-learn, pandas, ReportLab, Playwright...). Recreate with "
             "<i>py -3.12 -m venv .venv</i> then <i>pip install -r requirements.txt</i>.",
    ".pytest_cache": "Created automatically by pytest to remember the last test run. "
                     "Safe to delete.",
    "__pycache__": "Compiled Python bytecode, created automatically whenever a module is "
                   "imported (appears inside several folders). Safe to delete.",
    ".kilo": "Settings folder left by the Kilo Code editor extension. Not used by the "
             "project.",
    "reports": "Empty folder. Not used by the project.",
    "_prepared": "Inside docs/: whitespace-trimmed and cropped copies of the screenshots, "
                 "made automatically by pdf_kit.py while building the PDFs. Safe to delete; "
                 "rebuilt on the next PDF build.",
}

# ------------------------------------------------------------------
# Descriptions, keyed by path relative to the project root.
# ------------------------------------------------------------------
D = {
    # ---------------------------------------------------------- root
    "README.md": "Start here. Quick start, what each screen shows, requirements, how to "
                 "rebuild everything, tests, project layout, key results, how to use your "
                 "own data, troubleshooting.",
    "PROJECT_REPORT.md": "The complete technical report in Markdown: monitored machine, "
                         "objectives, dataset, features, the prediction-horizon decision, "
                         "results, inference engine, API, interface, verification, lessons, "
                         "limitations and future scope.",
    "Main synopsis (2).pdf": "The original project synopsis (19 pages): objectives, block "
                             "diagram, methodology, hardware/software list and the 10 "
                             "literature reviews. The source of the project's requirements.",
    "requirements-render.txt": "Slim list of only the libraries the web app needs "
                               "when hosted on Render (faster cloud build).",
    ".python-version": "Tells Render (and pyenv) to use Python 3.12.",
    "requirements.txt": "Python libraries the project needs. Install with "
                        "<i>pip install -r requirements.txt</i>.",
    "run_phase1.py": "Runs the whole data-and-model pipeline in order: download dataset, "
                     "expand it, EDA, train, evaluate. Options <i>--from N</i> and "
                     "<i>--only N</i> run part of it.",
    "generate_batch_tests.py": "Rebuilds the whole batch_testing/ folder: creates every "
                               "test Excel file, uploads each one to the real API and writes "
                               "00_TEST_INDEX.xlsx with what the app returned.",
    ".gitignore": "Tells Git which files not to track: the virtual environment, caches, "
                  "the downloaded/expanded datasets, trained models and the runtime "
                  "database.",

    # ---------------------------------------------------------- src
    "src/__init__.py": "Marks src/ as a Python package. Empty.",
    "src/config.py": "Single source of truth for the whole project: the machine name ("
                     f"{MACHINE_NAME}), file paths, the five-sensor schema and limits, "
                     "failure-mode causes and maintenance actions, physics thresholds, "
                     "alarm bands and the colour theme.",
    "src/plot_style.py": "Shared dark 'control room' style for every matplotlib chart, so "
                         "report figures match the web interface.",
    "src/data/__init__.py": "Package marker. Empty.",
    "src/data/download_dataset.py": "Step 1. Downloads the real AI4I 2020 dataset "
                                    "(10,000 rows) from the UCI repository into data/raw/.",
    "src/data/expand_dataset.py": "Step 2. Turns the 10,000 independent snapshots into "
                                  "run-to-failure histories for 220 simulated milling "
                                  "machines (74,979 rows), using the exact failure rules of "
                                  "the real data. Adds machine ID, cycle, time, RUL and "
                                  "labels.",
    "src/data/eda.py": "Step 3. Exploratory data analysis: draws figures 01-08 and writes "
                       "eda_summary.json.",
    "src/features/__init__.py": "Package marker. Empty.",
    "src/features/build_features.py": "Step 4. Turns the 5 raw sensor readings into the "
                                      "10 model features (temperature difference, power, "
                                      "strain...). Used by BOTH training and the live app, "
                                      "so the two can never disagree.",
    "src/models/__init__.py": "Package marker. Empty.",
    "src/models/train_model.py": "Step 5. Trains the Random Forest: grouped "
                                 "cross-validated hyper-parameter search, then a refit on "
                                 "the full training set. Saves the model to models/.",
    "src/evaluation/__init__.py": "Package marker. Empty.",
    "src/evaluation/evaluate.py": "Step 6. Tests the model on 42 machines it never saw: "
                                  "confusion matrix, ROC/PR curves, feature importance, "
                                  "learning curve, early-warning lead time (figures 09-14) "
                                  "and model_metrics.json.",
    "src/evaluation/alarm_quality.py": "Checks whether the model's 'false alarms' are "
                                       "really early warnings on machines that do fail "
                                       "later. Writes false_positive_analysis.json.",

    # ---------------------------------------------------------- backend
    "backend/__init__.py": "Package marker. Empty.",
    "backend/app.py": "Starts the application: one FastAPI server that serves the web "
                      "interface (/), the REST API (/api), API docs (/docs) and the "
                      "figures. Run with <i>python -m backend.app</i>.",
    "backend/api/__init__.py": "Package marker. Empty.",
    "backend/api/routes.py": "Every REST endpoint the web interface uses: predict "
                             "(single and batch upload), machines, live replay and its "
                             "live stream, alarms, model information, reset.",
    "backend/api/schemas.py": "Input/output formats and validation rules. Rejects "
                              "impossible readings (e.g. negative speed) before they "
                              "reach the model.",
    "backend/core/__init__.py": "Package marker. Empty.",
    "backend/core/physics.py": "Physics stress model: how close each reading is to each "
                               "of the four failure limits (0 = safe, 1 = on the limit). "
                               "Independent check alongside the Random Forest.",
    "backend/core/health.py": "Calculates the 0-100 Health Index and the Remaining Useful "
                              "Life (RUL) estimate, including the explanation of how the "
                              "RUL was worked out.",
    "backend/core/alarms.py": "Alarm engine: NORMAL / ADVISORY / WARNING / CRITICAL, the "
                              "worst of three signals wins, plus a persistence filter "
                              "that stops flickering alarms.",
    "backend/core/database.py": "SQLite storage for machines, readings and the alarm "
                                "log (the software stand-in for the synopsis's cloud "
                                "store).",
    "backend/services/__init__.py": "Package marker. Empty.",
    "backend/services/predictor.py": "The inference orchestrator: one reading in, full "
                                     "verdict out (class, probabilities, health, RUL, "
                                     "alarm, action, explanation). Everything goes "
                                     "through here.",
    "backend/services/explainer.py": "Explains each individual prediction exactly "
                                     "(decision-path attribution): which sensor pushed "
                                     "the model toward its answer, and by how much.",
    "backend/services/simulator.py": "Replays a real run-to-failure history one reading at "
                                     "a time, replacing the synopsis's NodeMCU sensor rig. "
                                     "Drives the 'Start Demo Plant' button.",

    # ---------------------------------------------------------- frontend
    "frontend/index.html": "The single web page. Top bar (with 'CNC Milling Machine "
                           "Monitoring'), the six tabs, and the script loading order.",
    "frontend/css/style.css": "All styling: dark SCADA control-room theme, cards, gauges, "
                              "alarm colours. No framework.",
    "frontend/js/api.js": "Talks to the backend API and turns server errors into "
                          "readable messages.",
    "frontend/js/app.js": "Application shell: switches between screens, starts and stops "
                          "each one, shared helpers.",
    "frontend/js/widgets.js": "Hand-drawn SVG gauges, health ring and trend charts, with no "
                              "charting library, so the demo works without internet.",
    "frontend/manifest.json": "PWA manifest: app name, icons and colours so the browser "
                              "can install the HMI as a desktop/phone app.",
    "frontend/sw.js": "PWA service worker: caches the page files so the app opens "
                      "offline; live /api data is never cached.",
    "frontend/js/pwa.js": "Registers the service worker and shows the 'Install PdM "
                          "SCADA' popup and top-bar Install button.",
    "frontend/icons/icon-192.png": "App icon (192 px) used by the installed PWA.",
    "frontend/icons/icon-512.png": "App icon (512 px) used on splash screens and stores.",
    "frontend/icons/icon-maskable-512.png": "Padded app icon Android crops into a "
                                            "circle or rounded square.",
    "frontend/icons/apple-touch-icon.png": "Home-screen icon for iPhone and iPad.",
    "frontend/js/screens/overview.js": "Screen 1, Plant Overview: one status card per "
                                       "machine, worst first; Start Demo / Stop All / "
                                       "Reset.",
    "frontend/js/screens/machine.js": "Screen 2, Machine HMI: five sensor dials, health "
                                      "ring, RUL, stress bars, live trends, alarm banner, "
                                      "START/STOP.",
    "frontend/js/screens/manual.js": "Screen 3, Manual Input: type or slide in one "
                                     "reading, or pick a preset, and get the full verdict.",
    "frontend/js/screens/batch.js": "Screen 4, Batch Analysis: upload a CSV/Excel file, "
                                    "see every row scored, download the annotated file.",
    "frontend/js/screens/alarms.js": "Screen 5, Alarms: the maintenance log with "
                                     "filters and Acknowledge.",
    "frontend/js/screens/model.js": "Screen 6, Model Insights: lead time, metrics, "
                                    "confusion matrix, feature importance and the live "
                                    "explanation self-check.",

    # ---------------------------------------------------------- data & models
    "data/raw/ai4i2020.csv": "The real UCI AI4I 2020 dataset: 10,000 rows, 339 failures. "
                             "Re-download with src/data/download_dataset.py.",
    "data/processed/pdm_expanded_dataset.csv": "The training dataset: 74,979 rows = 10,000 "
                                               "real + 64,979 simulated from 220 "
                                               "run-to-failure machines. Rebuilt (seeded) by "
                                               "expand_dataset.py.",
    "data/pdm.sqlite3": "The live application database: registered machines, every "
                        "reading and the alarm log. Created on first run; 'Reset Plant' "
                        "empties it.",
    "data/pdm.sqlite3-wal": "SQLite write-ahead log, present only while the app is running.",
    "data/pdm.sqlite3-shm": "SQLite shared-memory file, present only while the app is "
                            "running.",
    "models/pdm_model_bundle.joblib": "The model the app actually loads: the trained Random "
                                      "Forest plus its feature list, class names and "
                                      "settings, in one file.",
    "models/random_forest_pdm.joblib": "The trained Random Forest on its own (the bare "
                                       "estimator), kept for use outside the app.",

    # ---------------------------------------------------------- artifacts
    "artifacts/metrics/eda_summary.json": "Numbers from the data analysis: class counts, "
                                          "imbalance ratio, sensor statistics.",
    "artifacts/metrics/model_metrics.json": "All evaluation results: accuracy, F1, "
                                            "per-class scores, ROC-AUC, early-warning lead "
                                            "time (8.67 h, 97.6 % warned). Read by the Model "
                                            "Insights screen.",
    "artifacts/metrics/false_positive_analysis.json": "Output of alarm_quality.py: how "
                                                      "many 'false alarms' were really early "
                                                      "warnings.",
    "artifacts/metrics/training_summary.json": "Training record: best hyper-parameters, "
                                               "search scores, run times, split sizes.",
    "artifacts/metrics/split_indices.npz": "The exact train/test row split (grouped by "
                                           "machine), so evaluation uses the same unseen "
                                           "machines every time.",
    "artifacts/metrics/train_log.txt": "Console log of the last training run.",
    "artifacts/plots/eda/01_class_distribution.png": "How many readings of each class; "
                                                     "shows the 138:1 imbalance.",
    "artifacts/plots/eda/02_sensor_distributions.png": "Each sensor's spread, per "
                                                       "failure class.",
    "artifacts/plots/eda/03_correlation_matrix.png": "Correlation between all sensors "
                                                     "and features.",
    "artifacts/plots/eda/04_physics_separation.png": "Each failure mode sits inside its "
                                                     "physical limit zone.",
    "artifacts/plots/eda/05_failure_by_machine_type.png": "Failure rate and mix for "
                                                          "product grades L / M / H.",
    "artifacts/plots/eda/06_degradation_signatures.png": "How the key quantity drifts "
                                                         "toward its limit before each "
                                                         "failure.",
    "artifacts/plots/eda/07_rul_distribution.png": "Remaining-useful-life and machine "
                                                   "life distributions.",
    "artifacts/plots/eda/08_boxplots_by_class.png": "Box plots of every feature per "
                                                    "failure class.",
    "artifacts/plots/evaluation/09_confusion_matrix.png": "Confusion matrix on the "
                                                          "held-out test machines.",
    "artifacts/plots/evaluation/10_roc_and_pr_curves.png": "ROC and precision-recall "
                                                           "curves per failure mode.",
    "artifacts/plots/evaluation/12_feature_importance.png": "Which features drive the "
                                                            "prediction (impurity and "
                                                            "permutation importance).",
    "artifacts/plots/evaluation/13_learning_curve.png": "Score versus training-set size: "
                                                        "no overfitting, not data-starved.",
    "artifacts/plots/evaluation/14_early_warning_lead_time.png": "How many hours before "
                                                                 "failure the warning "
                                                                 "came, per failure mode.",

    # ---------------------------------------------------------- docs
    "docs/README.md": "Explains the documents in docs/ and how to regenerate them.",
    "docs/01_TEST_CASES_AND_EXPECTED_OUTPUT.pdf": "Full test document: 159 test cases "
                                                  "with exact expected values, screen by "
                                                  "screen.",
    "docs/02_FINAL_YEAR_PROJECT_REPORT.pdf": "The academic project report: certificate, "
                                             "declaration, abstract, 8 chapters, "
                                             "references, appendices.",
    "docs/03_USER_INTERFACE_GUIDE.pdf": "Plain-English guide to every screen, for readers "
                                        "with no technical background.",
    "docs/04_PROJECT_FILE_GUIDE.pdf": "This document.",
    "docs/ESSENTIAL_WEBSITE_TEST_CASES.md": "The 12 must-pass website tests for a demo or "
                                            "viva, with exact expected results and a pass "
                                            "column.",
    "docs/evidence.json": "Recorded outputs of a real browser run (API responses, "
                          "predictions, validation errors). Every number in the PDFs is "
                          "read from here.",
    "docs/capture_evidence.py": "Drives the real app in Chromium: takes the 16 screenshots "
                                "and records evidence.json. Fails if any screen has a "
                                "JavaScript error.",
    "docs/machine_capture.py": "Helper for capture_evidence.py: reliably captures the two "
                               "Machine HMI states (warning predicted / limit breached).",
    "docs/pdf_kit.py": "Shared PDF toolkit: page layout, styles, tables, callouts, cover "
                       "page, figure trimming and cropping.",
    "docs/diagrams.py": "Draws the vector block diagrams used in the project report.",
    "docs/gen_test_report.py": "Builds 01_TEST_CASES_AND_EXPECTED_OUTPUT.pdf.",
    "docs/gen_project_report.py": "Builds 02_FINAL_YEAR_PROJECT_REPORT.pdf.",
    "docs/gen_ui_guide.py": "Builds 03_USER_INTERFACE_GUIDE.pdf.",
    "docs/gen_file_guide.py": "Builds this document (04_PROJECT_FILE_GUIDE.pdf) by "
                              "walking the project folder.",

    # ---------------------------------------------------------- tests
    "tests/__init__.py": "Package marker. Empty.",
    "tests/test_engine.py": "Tests for physics, health, alarms and the explainer, "
                            "including regression tests for bugs fixed in Phase 2.",
    "tests/test_api.py": "API tests (28) run on a temporary database: endpoints, "
                         "validation, batch upload, alarms and reset.",
    "tests/test_widgets.js": "Checks the SVG gauges with extreme and missing values (no "
                             "NaN / undefined output). Run with <i>node</i>.",
    "tests/test_boot.js": "Checks the page loads its scripts in a working order (guards a "
                          "real bug that once blanked the whole interface).",
}

SHOTS = {
    "01_overview_empty": "Plant Overview before the demo starts.",
    "02_overview_starting": "Plant Overview just after Start Demo Plant.",
    "03_overview_running": "Plant Overview with four machines running.",
    "04_machine_picker": "Machine HMI: choosing a machine.",
    "05_machine_hmi": "Machine HMI running normally.",
    "06_machine_predicted": "Machine HMI with a failure PREDICTED (still running).",
    "07_machine_breached": "Machine HMI after the limit was BREACHED.",
    "08_manual_healthy": "Manual Input: healthy preset.",
    "09_manual_hdf": "Manual Input: heat-dissipation preset.",
    "10_manual_pwf": "Manual Input: power-failure preset.",
    "11_manual_osf": "Manual Input: overstrain preset.",
    "12_manual_twf": "Manual Input: tool-wear preset.",
    "13_batch_empty": "Batch Analysis before upload.",
    "14_batch_results": "Batch Analysis with scored results.",
    "15_alarms": "Alarms and maintenance log.",
    "16_model_insights": "Model Insights screen.",
    "art_04_physics_separation": "Copy of EDA figure 04 used in the reports.",
    "art_09_confusion_matrix": "Copy of figure 09 used in the reports.",
    "art_12_feature_importance": "Copy of figure 12 used in the reports.",
    "art_14_early_warning_lead_time": "Copy of figure 14 used in the reports.",
}


# ------------------------------------------------------------------
def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def walk():
    """Every project file, relative posix path -> size. Tool folders skipped."""
    files = {}
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if any(part in TOOL_DIRS for part in rel.parts):
            continue
        if p.is_file():
            files[rel.as_posix()] = p.stat().st_size
    return files


def batch_index():
    df = pd.read_excel(ROOT / "batch_testing" / "00_TEST_INDEX.xlsx",
                       sheet_name="Test Index")
    out = {}
    for _, r in df.iterrows():
        sub = "" if pd.isna(r["Sub-folder"]) or str(r["Sub-folder"]).strip() in ("", "-") else str(r["Sub-folder"]) + "/"
        key = f"batch_testing/{r['Category']}/{sub}{r['File']}"
        out[key] = f"{r['What it tests']} <b>Expected:</b> {r['Expected behaviour']}"
    return out


def describe(path: str, bidx: dict) -> str | None:
    if path in D:
        return D[path]
    if path.startswith("docs/screenshots/"):
        return "Screenshot. " + SHOTS.get(Path(path).stem, "")
    if path == "batch_testing/00_TEST_INDEX.xlsx":
        return ("Index of every batch-test file: what it tests, the expected behaviour, "
                "and what the app actually returned (HTTP status, rows scored, classes, "
                "alarm levels). Open this first.")
    return bidx.get(path)


def section_table(rows):
    return table([["File", "Size", "What it is"]] + rows,
                 widths=[150, 44, CONTENT_W - 194], font_size=8.0)


# ------------------------------------------------------------------
SECTIONS = [
    ("", "Project root", "The top-level files. Open README.md first."),
    ("src/", "src/ - data and model pipeline (Phase 1)",
     "Everything that turns the raw dataset into a trained, evaluated Random Forest. "
     "Run the whole chain with run_phase1.py."),
    ("backend/", "backend/ - engine and API (Phase 2)",
     "The server: prediction, health, RUL, alarms, explanations, storage and the "
     "REST API."),
    ("frontend/", "frontend/ - the web interface (Phase 3)",
     "The SCADA-style operator screens. Plain HTML/CSS/JavaScript, no build step, "
     "served by the backend."),
    ("data/", "data/ - datasets and the live database", ""),
    ("models/", "models/ - trained model", "Produced by src/models/train_model.py."),
    ("artifacts/", "artifacts/ - figures and metrics",
     "Produced by eda.py, evaluate.py and alarm_quality.py. Used by the reports and the "
     "Model Insights screen."),
    ("docs/", "docs/ - documents and their generators",
     "The PDFs are generated from a recorded run of the real app, never typed by hand. "
     "See docs/README.md for how to rebuild them."),
    ("tests/", "tests/ - automated tests",
     "Run with <i>python -m pytest tests/ -q</i>, <i>node tests/test_widgets.js</i> and "
     "<i>node tests/test_boot.js</i>."),
    ("batch_testing/", "batch_testing/ - Excel files for the Batch Analysis screen",
     "Ready-made files to upload on the Batch Analysis screen, grouped by what they test. "
     "Descriptions below come from 00_TEST_INDEX.xlsx. Rebuild the folder with "
     "generate_batch_tests.py."),
]


def build():
    files = walk()
    files.setdefault("docs/04_PROJECT_FILE_GUIDE.pdf", 0)  # this file, first build
    bidx = batch_index()

    missing = [f for f in files if describe(f, bidx) is None]
    if missing:
        raise SystemExit("No description for:\n  " + "\n  ".join(missing))

    story = cover(
        "Project File Guide",
        "What every file and folder in the project is, and what it does",
        "Document 4 - Project File Guide",
        [("Project", PROJECT_TITLE),
         ("Monitored machine", MACHINE_NAME),
         ("Files described", f"{len(files)} project files in {len(SECTIONS)} folders"),
         ("Generated", date.today().strftime("%d %B %Y"))],
    )
    story += toc([(1, "1.  Folder map")] +
                 [(1, f"{i + 2}.  {t}") for i, (_, t, _) in enumerate(SECTIONS)] +
                 [(1, f"{len(SECTIONS) + 2}.  Tool and cache folders")])

    # ------------------------------------------------ folder map
    story += [H1("1.  Folder map")]
    story += [P(
        "The project is split by job: the data-and-model pipeline (src/), the server "
        "(backend/), the web screens (frontend/), and their inputs and outputs. Sizes "
        "are measured on disk when this document is generated.")]
    counts = []
    for prefix, title, _ in SECTIONS:
        sel = [s for f, s in files.items()
               if (f.startswith(prefix) if prefix else "/" not in f)]
        counts.append([prefix or "(root)", str(len(sel)), human_size(sum(sel)),
                       title.split(" - ", 1)[-1]])
    story += [table([["Folder", "Files", "Size", "Contents"]] + counts,
                    widths=[92, 38, 52, CONTENT_W - 182])]
    story += [spacer(8), callout(
        "Where to start",
        "To run the app: <i>.venv\\Scripts\\python.exe -m backend.app</i>, then open "
        "http://127.0.0.1:8000/. To read about the project: README.md, then "
        "docs/02_FINAL_YEAR_PROJECT_REPORT.pdf. To test it quickly: "
        "docs/ESSENTIAL_WEBSITE_TEST_CASES.md.", "info")]
    story += [PageBreak()]

    # ------------------------------------------------ per folder
    for i, (prefix, title, intro) in enumerate(SECTIONS):
        story += [H1(f"{i + 2}.  {title}")]
        if intro:
            story += [P(intro)]
        sel = [f for f in files if (f.startswith(prefix) if prefix else "/" not in f)]
        groups = {}
        for f in sel:
            parent = str(Path(f).parent.as_posix())
            groups.setdefault(parent, []).append(f)
        for parent, members in groups.items():
            if len(groups) > 1:
                story += [H2(parent + "/")]
            rows = [[Path(f).name, human_size(files[f]), describe(f, bidx)]
                    for f in members]
            story += [section_table(rows), spacer(6)]
        story += [PageBreak()]

    # ------------------------------------------------ tool folders
    story += [H1(f"{len(SECTIONS) + 2}.  Tool and cache folders")]
    story += [P(
        "These folders are created by tools, not written as part of the project. Their "
        "contents are not listed. Only .venv is needed to run the app, and it can be "
        "recreated at any time.")]
    story += [table([["Folder", "What it is"]] +
                    [[k + "/", v] for k, v in TOOL_DIRS.items()],
                    widths=[92, CONTENT_W - 92])]

    doc = Report(OUT, "Project File Guide", "Document 4 - Project File Guide")
    doc.build(story)
    print(f"written: {OUT.relative_to(ROOT)}  ({len(files)} files described)")


if __name__ == "__main__":
    build()
