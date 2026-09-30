# Project Reports

Three PDF documents, plus the machinery that generates them.

| File | For whom | Contents |
|---|---|---|
| **`01_TEST_CASES_AND_EXPECTED_OUTPUT.pdf`** | Examiner / tester | 159 test cases with their **exact** expected values, screen by screen. 36 pages. |
| **`02_FINAL_YEAR_PROJECT_REPORT.pdf`** | Academic submission | Certificate, declaration, abstract, eight chapters, references, appendices. 29 pages. |
| **`ESSENTIAL_WEBSITE_TEST_CASES.md`** | Demo / viva check | The 12 must-pass website tests, with exact expected values. |
| **`03_USER_INTERFACE_GUIDE.pdf`** | Anyone, no background needed | Every element of every screen explained in plain English. 26 pages. |
| **`04_PROJECT_FILE_GUIDE.pdf`** | Anyone | Every file in the project, folder by folder: what it is and what produces it. Built by `gen_file_guide.py`. |

---

## The documents are generated, not written by hand

Every number quoted in the reports — predictions, health indices, alarm
messages, lead times, the values printed on the screenshots — is read from
`evidence.json`, which is produced by **running the real system in a real
browser**. Nothing is typed in by hand, so a report can never quietly drift out
of step with the software it describes.

```
  the running system
        │
        ├─ capture_evidence.py ──► screenshots/*.png   (real browser, Chromium)
        │                     └──► evidence.json       (exact API responses)
        │
        └─ gen_*.py ───────────────► the three PDFs
```

## Regenerating everything

```bash
# 1. start the application in one terminal
.\.venv\Scripts\python.exe -m backend.app

# 2. capture fresh evidence in another  (about 5 minutes)
.\.venv\Scripts\python.exe docs/capture_evidence.py

# 3. rebuild the PDFs
cd docs
..\.venv\Scripts\python.exe gen_test_report.py
..\.venv\Scripts\python.exe gen_project_report.py
..\.venv\Scripts\python.exe gen_ui_guide.py
..\.venv\Scripts\python.exe gen_file_guide.py
```

First time only:

```bash
.\.venv\Scripts\python.exe -m pip install reportlab playwright pymupdf
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Files

| File | Purpose |
|---|---|
| `capture_evidence.py` | Drives the HMI in Chromium, takes the 16 screenshots, records the exact API responses. Fails loudly if any screen logs a JavaScript error. |
| `machine_capture.py` | The two Machine-HMI states the guide is built around — *warned but still running*, and *limit actually crossed*. Separate module because making it reproducible was genuinely fiddly; the docstring records why. |
| `pdf_kit.py` | Shared PDF toolkit: page templates, styles, tables, callouts, figure placement with automatic whitespace trimming and region cropping. |
| `diagrams.py` | Vector block diagrams (architecture, hardware→software mapping, the labelling change) drawn as SVG-style shapes so they stay sharp and print in black and white. |
| `gen_test_report.py` | Document 1. |
| `gen_project_report.py` | Document 2. |
| `gen_ui_guide.py` | Document 3. |
| `gen_file_guide.py` | Document 4. Walks the project folder; fails if a file has no description. |
| `evidence.json` | The recorded run the three documents are built from. |
| `screenshots/` | 16 browser screenshots plus four Phase-1 analysis figures. |
| `_prepared/` | Auto-generated trimmed and cropped images. Safe to delete; rebuilt on demand. |

## A note on the capture

`capture_evidence.py` doubles as the **browser-level test** the earlier phases
could not run. It drives all six screens and records every console error; the
run reports `console errors -> 0`. That is how the blank-page defect described
in Document 1, section 9 would now be caught.

`machine_capture.py` also verifies its own output: if the screenshot labelled
*breached* does not actually show a breached limit, it prints a warning rather
than letting a figure contradict its own caption.
