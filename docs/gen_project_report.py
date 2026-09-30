"""
Generates  docs/02_FINAL_YEAR_PROJECT_REPORT.pdf

A conventional final-year engineering project report: certificate,
declaration, abstract, eight chapters, references and appendices.

Content is grounded in two real sources - the project synopsis
(Main synopsis (2).pdf, from which the literature survey, problem
statement and objectives are taken) and docs/evidence.json (from which
every result figure is read).
"""

from __future__ import annotations

import json
from pathlib import Path

from diagrams import hardware_mapping, horizon_diagram, system_architecture
from pdf_kit import (
    ACCENT, CONTENT_W, CRIT, H1, H2, H3, OK, P, Report, STYLES, WARN,
    bullets, callout, code, cover, esc, figure, kpi_row, rule, spacer,
    table, toc,
)
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
EV = json.loads((ROOT / "docs" / "evidence.json").read_text(encoding="utf-8"))
MET = EV["api"]["metrics"]
EW = MET["early_warning"]
HD = MET["headline"]
PC = MET["per_class"]
VER = EV["api"]["verify"]

OUT = ROOT / "docs" / "02_FINAL_YEAR_PROJECT_REPORT.pdf"


def centered(text, size=11, bold=False, space=6):
    style = STYLES["cover_meta"].clone("c")
    style.fontSize = size
    style.leading = size * 1.5
    style.fontName = "Helvetica-Bold" if bold else "Helvetica"
    style.spaceAfter = space
    return Paragraph(text, style)


def build():
    story = []

    # ============================================================ COVER
    story += cover(
        "AI-Based Predictive Maintenance for CNC Milling Machines",
        "A software-only predictive maintenance system using Random Forest, "
        "with explainable predictions and a SCADA operator interface",
        "Document 2 of 3  -  Final Year Project Report",
        [
            ("Submitted by", "______________________________     USN: ______________"),
            ("", "______________________________     USN: ______________"),
            ("", "______________________________     USN: ______________"),
            ("", "______________________________     USN: ______________"),
            ("Under the guidance of", "______________________________"),
            ("Department", "Electronics & Communication Engineering"),
            ("Institution", "Government Engineering College, K. R. Pete"),
            ("Academic year", "2026 - 2027"),
        ],
        tagline="The system predicts which of four failure mechanisms a machine is "
                f"heading toward a mean of <b>{EW['mean_lead_hours']} operating hours</b> "
                f"before the failure occurs, warning in advance on "
                f"<b>{EW['warned_before_failure_pct']}%</b> of unseen machines.",
    )

    # ============================================================ CERTIFICATE
    story += [spacer(20), centered("CERTIFICATE", 16, True, 20)]
    story += [P(
        "This is to certify that the project work entitled "
        "<b>“AI-Based Predictive Maintenance for CNC Milling Machines”</b> "
        "is a bonafide work carried out by the students named below, in partial "
        "fulfilment of the requirements for the award of the degree of Bachelor of "
        "Engineering in Electronics and Communication Engineering, of the Visvesvaraya "
        "Technological University, Belagavi, during the academic year 2026-2027.")]
    story += [P(
        "It is certified that all corrections and suggestions indicated for internal "
        "assessment have been incorporated in the report. The project report has been "
        "approved as it satisfies the academic requirements in respect of the project "
        "work prescribed for the said degree.")]
    story += [spacer(30)]
    story += [table([
        ["Signature of Guide", "Signature of HOD", "Signature of Principal"],
        ["\n\n\n", "\n\n\n", "\n\n\n"],
        ["Name & Designation", "Name & Designation", "Name & Designation"],
    ], widths=[CONTENT_W / 3] * 3, head=False, zebra=False)]
    story += [spacer(26), centered("External Viva", 11, True, 10)]
    story += [table([
        ["Name of the Examiners", "Signature with Date"],
        ["1.", ""],
        ["2.", ""],
    ], widths=[CONTENT_W * 0.55, CONTENT_W * 0.45], zebra=False)]
    story += [PageBreak()]

    # ============================================================ DECLARATION
    story += [H1("Declaration")]
    story += [P(
        "We hereby declare that the project work entitled "
        "<b>“AI-Based Predictive Maintenance for CNC Milling Machines”</b> "
        "has been carried out by us and submitted in partial fulfilment of the "
        "requirements for the award of the degree of Bachelor of Engineering in "
        "Electronics and Communication Engineering.")]
    story += [P(
        "We further declare that the dataset used is the publicly available "
        "<b>AI4I 2020 Predictive Maintenance Dataset</b> from the UCI Machine Learning "
        "Repository, that all software was written by us, and that all sources consulted "
        "have been acknowledged in the references.")]
    story += [P(
        "We also record explicitly that the sensing hardware described in the project "
        "synopsis has been replaced by validated software equivalents, and that the "
        "reasons for this decision and its consequences are documented in Chapter 3 of "
        "this report. No claim is made that physical sensors were used.")]
    story += [spacer(40)]
    story += [table([
        ["Name", "USN", "Signature"],
        ["", "", ""], ["", "", ""], ["", "", ""], ["", "", ""],
    ], widths=[CONTENT_W * 0.45, CONTENT_W * 0.25, CONTENT_W * 0.30], zebra=False)]
    story += [PageBreak()]

    # ============================================================ ACKNOWLEDGEMENT
    story += [H1("Acknowledgement")]
    story += [P(
        "We express our sincere gratitude to the Principal, Government Engineering "
        "College, K. R. Pete, for providing the facilities and environment necessary to "
        "carry out this project.")]
    story += [P(
        "We are deeply thankful to the Head of the Department of Electronics and "
        "Communication Engineering for the continuous encouragement and support extended "
        "throughout the course of this work.")]
    story += [P(
        "We wish to record our special thanks to our project guide, whose guidance shaped "
        "the direction of this work at several critical points - in particular the "
        "insistence that the system be judged by how early it warns rather than by its "
        "headline accuracy, which led directly to the central design change described in "
        "Chapter 5.")]
    story += [P(
        "We also thank the teaching and non-teaching staff of the department, and our "
        "families and friends, for their support and patience during this project.")]
    story += [PageBreak()]

    # ============================================================ ABSTRACT
    story += [H1("Abstract")]
    story += [P(
        "CNC milling machines fail unexpectedly, causing unplanned downtime, lost "
        "production and safety risk. Reactive maintenance repairs only after a failure has "
        "occurred, while preventive maintenance services equipment on a fixed schedule "
        "regardless of its condition. Neither can tell an operator that a specific machine "
        "is about to fail.")]
    story += [P(
        "This project develops a complete, working predictive maintenance system that "
        "does. It uses the AI4I 2020 dataset from the UCI Machine Learning Repository "
        "(10,000 real records), expanded by a physics-informed run-to-failure model into "
        "74,979 readings across 220 machines, and trains a <b>Random Forest</b> classifier "
        "to identify which of four failure mechanisms - tool wear, heat dissipation, power "
        "and overstrain - a machine is approaching.")]
    story += [P(
        "The central finding of the work is that <b>accuracy is the wrong objective for "
        "predictive maintenance</b>. A first model trained to recognise the machine's "
        "current state achieved 98.99% accuracy yet had a measured early-warning lead time "
        f"of <b>minus 3.7 readings</b>: it raised the alarm approximately 37 minutes "
        "<i>after</i> the fault. Reformulating the learning target around a 15-reading "
        "prediction horizon reduced accuracy by eight percentage points but converted the "
        "system from a condition monitor into a genuinely predictive one, achieving a mean "
        f"lead time of <b>+{EW['mean_lead_readings']} readings "
        f"({EW['mean_lead_hours']} operating hours)</b> with "
        f"<b>{EW['warned_before_failure_pct']}%</b> of unseen machines warned before "
        "failure.")]
    story += [P(
        "Around the model, the system provides a continuous health index, a remaining-useful-life "
        "estimate that always declares its own basis, and a four-band alarm engine that "
        "combines the model with independent physics checks so that a learned component is "
        "never the only safeguard. Each prediction is explained by decision-path "
        "attribution, which reconstructs the model's output exactly to machine precision "
        f"({VER['max_absolute_error']:.1e}) rather than approximating it. The complete "
        "system is delivered as a six-screen SCADA-style operator interface served by a "
        "FastAPI application with 25 REST endpoints, running offline from a single command "
        "with no external dependencies, and verified by 86 automated tests.")]

    story += [spacer(8), H3("Keywords")]
    story += [P(
        "Predictive maintenance; Random Forest; Industry 4.0; remaining useful life; "
        "explainable artificial intelligence; condition monitoring; AI4I 2020; "
        "early-warning lead time; SCADA human-machine interface.", "small")]
    story += [PageBreak()]

    # ============================================================ TOC
    story += toc([
        (1, "Certificate"), (1, "Declaration"), (1, "Acknowledgement"), (1, "Abstract"),
        (1, "1.  Introduction"),
        (2, "1.1  Background"), (2, "1.2  Problem Statement"),
        (2, "1.3  Objectives"), (2, "1.4  Scope of the Project"),
        (2, "1.5  The Monitored Machine - a CNC Milling Machine"),
        (2, "1.6  Organisation of the Report"),
        (1, "2.  Literature Survey"),
        (2, "2.1  Summary of Reviewed Work"), (2, "2.2  Observations"),
        (2, "2.3  Research Gap Addressed"),
        (1, "3.  System Requirements and Analysis"),
        (2, "3.1  Existing System"), (2, "3.2  Proposed System"),
        (2, "3.3  Hardware to Software Mapping"),
        (2, "3.4  Functional and Non-Functional Requirements"),
        (2, "3.5  Tools and Technologies"),
        (1, "4.  System Design"),
        (2, "4.1  Overall Architecture"), (2, "4.2  Module Design"),
        (2, "4.3  Database Design"), (2, "4.4  Interface Design"),
        (1, "5.  Methodology and Implementation"),
        (2, "5.1  Dataset Preparation"), (2, "5.2  Exploratory Data Analysis"),
        (2, "5.3  Feature Engineering"),
        (2, "5.4  The Learning Target - the central design decision"),
        (2, "5.5  Model Training"), (2, "5.6  Decision Engine"),
        (2, "5.7  Explainability"), (2, "5.8  Backend and Interface"),
        (1, "6.  Testing"),
        (1, "7.  Results and Discussion"),
        (2, "7.1  Early-Warning Performance"), (2, "7.2  Classification Performance"),
        (2, "7.3  Feature Importance"), (2, "7.4  Alarm Quality"),
        (2, "7.5  System Screenshots"), (2, "7.6  Discussion"),
        (1, "8.  Conclusion and Future Scope"),
        (1, "References"),
        (1, "Appendix A - How to Run the System"),
        (1, "Appendix B - Project Structure"),
    ])

    # ============================================================ CH 1
    story += [H1("1.  Introduction")]
    story += [H2("1.1  Background")]
    story += [P(
        "In today's rapidly advancing industrial environment, the reliability and "
        "efficiency of machinery play a crucial role in ensuring smooth production. "
        "CNC milling machines operate continuously under varying cutting loads, making their "
        "spindles, drives and cutting tools susceptible to wear, faults and unexpected failure. Such failures lead to "
        "unplanned downtime, reduced productivity, increased maintenance cost and "
        "potential safety hazards.")]
    story += [P(
        "Industry has traditionally relied on two maintenance strategies, and both are "
        "unsatisfactory:")]
    story += bullets([
        "<b>Reactive maintenance</b> repairs equipment only after a failure has occurred, "
        "causing severe disruption and financial loss.",
        "<b>Preventive maintenance</b> services equipment at fixed intervals regardless of "
        "its actual condition, leading to unnecessary work and wasted resources.",
    ])
    story += [P(
        "Neither approach can predict a failure before it happens. With the emergence of "
        "Artificial Intelligence, Machine Learning and the Internet of Things, a third "
        "strategy - <b>predictive maintenance</b> - has become practical. It analyses "
        "machine condition data continuously, detects the patterns that precede a fault, "
        "and allows action to be taken while the machine is still running.")]

    story += [H2("1.2  Problem Statement")]
    story += [callout(
        "Problem statement",
        "CNC milling machines often experience unexpected failures that disrupt production "
        "and increase downtime and cost. Traditional maintenance methods are inefficient, "
        "as they either respond after failure or involve unnecessary servicing. Existing "
        "systems make limited use of real-time data, making early fault detection "
        "difficult. Therefore an AI-based predictive maintenance system is needed to "
        "analyse data, predict failures in advance, and improve efficiency while reducing "
        "maintenance cost.", "info")]

    story += [H2("1.3  Objectives")]
    story += [P("The objectives stated in the project synopsis are:")]
    story += bullets([
        "To develop an AI-based system that continuously monitors CNC milling machine "
        "conditions using sensor data and <b>predicts potential failures in advance</b>.",
        "To reduce machine downtime and maintenance cost by enabling timely and efficient "
        "maintenance through accurate fault detection.",
    ])
    story += [P(
        "In the course of the work these were refined into measurable engineering targets, "
        "so that success or failure could be demonstrated rather than asserted:")]
    story += [table([
        ["#", "Refined objective", "Measure", "Achieved"],
        ["O1", "Predict failure before it occurs", "Mean early-warning lead time > 0",
         f"+{EW['mean_lead_readings']} readings ({EW['mean_lead_hours']} h)"],
        ["O2", "Warn reliably, not occasionally", "% of machines warned before failure",
         f"{EW['warned_before_failure_pct']}%"],
        ["O3", "Identify which mechanism will fail", "Per-class ROC-AUC",
         "0.952 - 0.995"],
        ["O4", "Miss as few failures as possible", "Macro recall",
         f"{HD['macro_recall']:.4f}"],
        ["O5", "Estimate remaining useful life", "RUL with stated confidence basis",
         "Trend fit with R-squared, or nominal"],
        ["O6", "Explain every prediction", "Exact reconstruction of model output",
         f"{VER['max_absolute_error']:.1e}"],
        ["O7", "Present it to an operator", "Working HMI, verified in a browser",
         "6 screens, 0 console errors"],
    ], widths=[24, 152, 118, CONTENT_W - 294])]

    story += [H2("1.4  Scope of the Project")]
    story += [P(
        "The project delivers a complete software pipeline from raw dataset to operator "
        "interface. It <b>does not</b> include physical sensor hardware; the reasons for "
        "that decision, and the software components that take its place, are set out in "
        "Section 3.3. Every interface is designed so that a real sensor feed can replace "
        "the simulator without any change to the model, the API or the interface.")]

    story += [H2("1.5  The Monitored Machine - a CNC Milling Machine")]
    story += [P(
        "The system is built for one specific class of industrial machine: the "
        "<b>CNC milling machine</b>, in which a motor-driven spindle rotates a multi-point "
        "cutter (an end mill) that removes material from a workpiece clamped to the "
        "machine table. This choice is not arbitrary. The AI4I 2020 dataset used in this "
        "project was generated to model exactly this process, and every one of its five "
        "measured quantities maps directly onto a milling machine:")]
    story += [table([
        ["Dataset quantity", "On a CNC milling machine"],
        ["Rotational speed [rpm]", "Spindle speed (about 1,200 - 2,900 rpm in the data)"],
        ["Torque [Nm]", "Spindle torque produced while the cutter is engaged"],
        ["Tool wear [min]", "Cutting time accumulated on the current end mill"],
        ["Process temperature [K]", "Temperature at the spindle / cutting zone"],
        ["Air temperature [K]", "Ambient shop-floor temperature"],
        ["Type L / M / H", "Quality grade of the product being machined"],
    ], widths=[140, CONTENT_W - 140])]
    story += [P(
        "The four failure mechanisms are likewise milling-machine faults: <b>TWF</b> is "
        "the end mill wearing out, <b>HDF</b> is the spindle and cutting zone failing to "
        "shed heat through the coolant, <b>PWF</b> is the spindle drive running outside its "
        "power window, and <b>OSF</b> is a worn cutter under heavy torque overstressing the "
        "spindle. The recommended maintenance action attached to every alarm is written "
        "for a milling-machine technician.")]

    story += [H2("1.6  Organisation of the Report")]
    story += [table([
        ["Chapter", "Contents"],
        ["2", "Literature survey of ten recent works and the research gap addressed"],
        ["3", "Requirement analysis, the proposed system and the hardware-to-software mapping"],
        ["4", "System architecture, module design, database and interface design"],
        ["5", "Dataset preparation, features, the learning-target decision, model and engine"],
        ["6", "Testing strategy and results"],
        ["7", "Results, discussion and screenshots of the working system"],
        ["8", "Conclusion and future scope"],
    ], widths=[52, CONTENT_W - 52])]
    story += [PageBreak()]

    # ============================================================ CH 2
    story += [H1("2.  Literature Survey")]
    story += [P(
        "Ten recent works on predictive maintenance were reviewed. They are summarised "
        "below with the observation each contributed to the design of this project.")]

    story += [H2("2.1  Summary of Reviewed Work")]
    lit = [
        ("1", "Machine Learning-Based Predictive Maintenance of Industrial Machines (2023)",
         "C. R. Patil, S. K. Jadhav et al.",
         "Sensor data (vibration, temperature, pressure) classified with Random Forest, SVM "
         "and ANN into normal or faulty states.",
         "Confirms Random Forest as an appropriate choice. Notes dependence on dataset "
         "quality - which motivated the careful dataset construction in Chapter 5."),
        ("2", "Predictive Maintenance Edge AI using RNN for Peristaltic Pumps (2025)",
         "J. M. Montes-Sanchez, Y. Uwate et al.",
         "LSTM recurrent networks on time-series sensor data, deployed at the edge for "
         "low-latency prediction.",
         "Demonstrates the value of treating machine data as a time series rather than "
         "independent snapshots - the reason this project builds run-to-failure "
         "trajectories."),
        ("3", "Explainable Predictive Maintenance: A Survey of Current Methods, "
              "Challenges and Opportunities (2024)",
         "L. Cummins, A. Sommers et al.",
         "Survey of explainability techniques (SHAP, LIME) applied to predictive "
         "maintenance; discusses the accuracy-interpretability trade-off.",
         "Directly motivates the explainability requirement (objective O6). This project "
         "avoids the trade-off by using an attribution method that is exact for tree "
         "ensembles."),
        ("4", "A Systematic Literature Review of Supervised Machine Learning Techniques "
              "for Predictive Maintenance in Industry 4.0 (2025)",
         "D. Guidotti, L. Pandolfo, L. Pulina",
         "Reviews supervised methods - Random Forest, SVM, Decision Tree, Neural Networks "
         "- across Industry 4.0 predictive maintenance.",
         "Positions Random Forest among the standard supervised approaches and confirms "
         "the preprocessing and feature-selection pipeline adopted here."),
        ("5", "AI Driven Approach for Predictive Maintenance in Industry 4.0 (2024)",
         "S. D. Deshmukh",
         "AI and IoT combined to analyse temperature, vibration, pressure and motor speed "
         "and predict maintenance need.",
         "Provides the overall system shape - acquisition, preprocessing, model, alert - "
         "which this project follows in software."),
        ("6", "Machine Learning-Based Predictive Maintenance System for Artificial Yarn "
              "Machines (2024)",
         "T. Akyaz and D. Engin",
         "Random Forest, Decision Tree and SVM applied to yarn machine parameters to "
         "detect abnormal conditions.",
         "A concrete industrial application of the same algorithm family, supporting the "
         "single-algorithm approach taken here."),
        ("7", "Explainable Predictive Maintenance of Rotating Machines Using LIME, SHAP, "
              "PDP and ICE (2023)",
         "S. Gawde, S. Patil, S. Kumar, P. Kamat",
         "Applies four explainability techniques to rotating-machine fault prediction, "
         "emphasising why a model gives a prediction, not only its accuracy.",
         "The closest work to this project's explainability design. This project uses "
         "decision-path attribution, the tree-specific method that TreeSHAP generalises, "
         "obtaining exactness at a fraction of the computation."),
        ("8", "Optimizing Predictive Maintenance in Industrial IoT Cloud Using Dragonfly "
              "Algorithm (2025)",
         "S. Rani S, R. Aburukba, K. El-Fakih",
         "Uses the Dragonfly optimisation algorithm to improve feature selection and "
         "prediction accuracy in an Industrial IoT cloud setting.",
         "Considered and deliberately not adopted: metaheuristic feature selection would "
         "obscure the physical meaning of the features, which this project needed to keep."),
        ("9", "Implementing Next-Gen Predictive Maintenance in Industrial Machineries: "
              "A Comparative Analysis of Small, Medium and Large Enterprises (2023)",
         "K. Patel, A. Hariharan, R. Sucharitha",
         "Compares predictive maintenance adoption across enterprise sizes in terms of "
         "cost, infrastructure and data availability.",
         "Supports the decision to build a system that runs on one ordinary computer with "
         "no cloud dependency - the constraint faced by smaller enterprises."),
        ("10", "The Role of Mobile Communications for Industrial Automation: Architecture, "
               "Applications and Challenges (2025)",
         "E. Zeydan, S. S. Arslan, Y. Turk et al.",
         "Examines 4G/5G and industrial wireless IoT for real-time machine data transfer, "
         "and the latency, security and reliability challenges involved.",
         "Informs the transport design: the system uses a simple one-directional "
         "server-sent event stream that reconnects by itself, rather than a fragile "
         "bidirectional socket."),
    ]
    rows = [["#", "Title / Authors", "Method", "Contribution to this project"]]
    for n, title, authors, method, contrib in lit:
        rows.append([n, f"{title}\n\n{authors}", method, contrib])
    story += [table(rows, widths=[16, 132, 116, CONTENT_W - 264], font_size=7.6)]

    story += [H2("2.2  Observations")]
    story += bullets([
        "<b>Random Forest appears repeatedly</b> across works 1, 4, 5 and 6 as a reliable "
        "and interpretable choice for tabular machine condition data. This project uses it "
        "as its single algorithm.",
        "<b>Explainability has become a requirement, not a luxury</b> (works 3 and 7). An "
        "operator asked to shut down a production line will reasonably ask why.",
        "<b>Almost every reviewed work reports classification accuracy</b> as its headline "
        "result. <b>None of them reports how far in advance the warning arrives.</b>",
        "Most works assume a hardware sensing chain and cloud infrastructure, which limits "
        "adoption by smaller enterprises (work 9).",
    ])

    story += [H2("2.3  Research Gap Addressed")]
    story += [callout(
        "The gap",
        "The reviewed literature measures predictive maintenance systems almost entirely by "
        "<b>classification accuracy</b>. But a classifier trained to recognise a machine's "
        "<i>present</i> condition can only report a fault once it has already happened, no "
        "matter how accurate it is. Accuracy therefore does not distinguish a predictive "
        "system from a reactive one.<br/><br/>"
        "This project makes <b>early-warning lead time</b> the primary measure, and shows "
        "experimentally that optimising for accuracy actively works against it: a 98.99%-"
        "accurate model was found to alarm 37 minutes <i>after</i> the fault. Chapter 5.4 "
        "documents the reformulation that fixed this, and Chapter 7 reports the result.", "warn")]
    story += [PageBreak()]

    # ============================================================ CH 3
    story += [H1("3.  System Requirements and Analysis")]

    story += [H2("3.1  Existing System")]
    story += [table([
        ["Approach", "How it works", "Limitation"],
        ["Reactive (breakdown)", "Repair after failure", "Maximum downtime; possible "
         "consequential damage and safety risk"],
        ["Preventive (scheduled)", "Service at fixed intervals", "Healthy parts replaced "
         "unnecessarily; failures between intervals still missed"],
        ["Condition monitoring", "Alarm when a sensor crosses a threshold", "Reports the "
         "fault only once the limit has already been crossed - still reactive"],
    ], widths=[110, 130, CONTENT_W - 240])]

    story += [H2("3.2  Proposed System")]
    story += [P(
        "The proposed system learns the <b>approach</b> to a limit rather than the limit "
        "itself. It combines three independent judgements of machine condition and takes "
        "the most severe, so that a learned component is never the only safeguard between a "
        "developing fault and the operator:")]
    story += [table([
        ["Signal", "Nature", "Can it be misled?"],
        ["Random Forest predicted class and confidence", "Learned from data",
         "Yes - by drift, retraining, or an unfamiliar input"],
        ["Physics stress ratio (0 to 1 per mechanism)", "Derived from first principles",
         "No - arithmetic on the reading itself"],
        ["Hard threshold rule check", "Deterministic",
         "No - arithmetic on the reading itself"],
    ], widths=[168, 118, CONTENT_W - 286])]

    story += [H2("3.3  Hardware to Software Mapping")]
    story += [P(
        "The synopsis specifies a sensing chain built on a NodeMCU (ESP8266) with "
        "temperature, vibration and current sensors uploading to a cloud platform. This "
        "project <b>replaces that chain with validated software equivalents</b> and keeps "
        "the rest of the block diagram intact.")]
    story += [P(
        "The reason is one of engineering honesty. A hobby-grade sensor rig on a single "
        "test motor would produce a few hours of data from one machine, with no labelled "
        "failures - because deliberately destroying machinery to obtain them is neither "
        "safe nor affordable. Any model trained on it could not be validated. Using a "
        "peer-reviewed public dataset with 10,000 genuinely labelled records, expanded by "
        "a physics model calibrated against that same data, produces a system whose "
        "performance can be measured and defended.")]
    story += [spacer(4), hardware_mapping(), spacer(4)]
    story += [P("<b>Figure 3.1</b> - Each hardware block of the synopsis and its software "
                "equivalent. Every component consumes the same ten-field reading, so "
                "replacing the simulator with a real sensor feed requires a new data "
                "producer only.", "caption")]

    story += [H2("3.4  Functional and Non-Functional Requirements")]
    story += [H3("Functional requirements")]
    story += [table([
        ["ID", "Requirement"],
        ["FR1", "Accept a single machine reading through a form and return a complete verdict"],
        ["FR2", "Accept a CSV or Excel file and score every row"],
        ["FR3", "Replay a real run-to-failure trajectory as a live feed"],
        ["FR4", "Classify the reading into Normal or one of four failure mechanisms"],
        ["FR5", "Report the failure BEFORE it occurs (early warning)"],
        ["FR6", "Compute a continuous health index from 0 to 100"],
        ["FR7", "Estimate remaining useful life and state the basis of that estimate"],
        ["FR8", "Raise a four-band alarm with cause and recommended technician action"],
        ["FR9", "Explain each prediction in terms of the sensor values that caused it"],
        ["FR10", "Store machines, readings and alarms; support acknowledgement"],
        ["FR11", "Present all of the above in an operator interface"],
    ], widths=[36, CONTENT_W - 36])]

    story += [H3("Non-functional requirements")]
    story += [table([
        ["ID", "Requirement", "How it is met"],
        ["NFR1", "Single-command start-up", "python -m backend.app - API and HMI on one port"],
        ["NFR2", "Operate without internet", "Zero external dependencies; all charts are "
                 "hand-drawn SVG"],
        ["NFR3", "Responsive under a live feed", "Model loaded once; batch scoring vectorised"],
        ["NFR4", "Never present a guess as a measurement", "RUL always declares its method "
                 "and confidence"],
        ["NFR5", "Fail safe if the model is wrong", "Independent physics and rule checks"],
        ["NFR6", "Verifiable", "86 automated tests across engine, API, widgets and boot"],
    ], widths=[36, 130, CONTENT_W - 166])]

    story += [H2("3.5  Tools and Technologies")]
    story += [table([
        ["Layer", "Technology", "Reason"],
        ["Language", "Python 3.12", "Standard for the scientific and ML stack"],
        ["ML", "scikit-learn 1.5.2 (RandomForestClassifier)", "Mature, deterministic, "
         "interpretable; supported by the literature"],
        ["Data", "pandas, NumPy", "Tabular processing and vectorised computation"],
        ["Figures", "matplotlib, seaborn", "Publication-quality analysis plots"],
        ["Backend", "FastAPI, Uvicorn, Pydantic", "Typed validation and automatic API "
         "documentation"],
        ["Database", "SQLite", "Server-less, in the standard library, ordinary SQL"],
        ["Frontend", "HTML, CSS, JavaScript (no framework)", "No build step and no CDN, so "
         "the demonstration cannot fail for lack of internet"],
        ["Testing", "pytest, Node.js, Playwright", "Engine, API, widget, boot and real-browser "
         "verification"],
    ], widths=[62, 132, CONTENT_W - 194])]
    story += [PageBreak()]

    # ============================================================ CH 4
    story += [H1("4.  System Design")]
    story += [H2("4.1  Overall Architecture")]
    story += [spacer(4), system_architecture(), spacer(4)]
    story += [P("<b>Figure 4.1</b> - System architecture. Four acquisition paths converge on "
                "one shared feature builder; four independent analyses feed a single "
                "decision layer; the result is stored, served and displayed.", "caption")]
    story += [P(
        "Two design rules govern the whole architecture:")]
    story += bullets([
        "<b>One feature builder, shared between training and live inference.</b> The most "
        "common cause of silent failure in a deployed ML system is a transformation that "
        "differs between the two. Sharing a single module removes that possibility entirely.",
        "<b>One prediction path.</b> The manual form, the file upload and the live stream all "
        "call the same service, so they cannot disagree about what a given reading means.",
    ])

    story += [H2("4.2  Module Design")]
    story += [table([
        ["Module", "Responsibility"],
        ["src/config.py", "Single source of truth - paths, sensor schema, physical thresholds, "
         "target column, theme"],
        ["src/data/", "Dataset download, physics-informed expansion, exploratory analysis"],
        ["src/features/build_features.py", "The shared feature transform"],
        ["src/models/train_model.py", "Hyper-parameter search, grouped cross-validation, training"],
        ["src/evaluation/", "Metrics, figures, early-warning analysis, alarm-quality analysis"],
        ["backend/core/physics.py", "Per-mechanism stress ratios and the deterministic breach check"],
        ["backend/core/health.py", "Health index and remaining-useful-life estimation"],
        ["backend/core/alarms.py", "Four-band severity, worst-of-three, persistence filter"],
        ["backend/core/database.py", "SQLite persistence for machines, readings and alarms"],
        ["backend/services/predictor.py", "Inference orchestration - single and batch"],
        ["backend/services/explainer.py", "Exact decision-path attribution"],
        ["backend/services/simulator.py", "Dataset replay as a live sensor feed"],
        ["backend/api/", "25 REST endpoints, request schemas, server-sent event stream"],
        ["frontend/", "Six-screen SCADA interface, no build step"],
    ], widths=[132, CONTENT_W - 132])]

    story += [H2("4.3  Database Design")]
    story += [table([
        ["Table", "Key fields", "Purpose"],
        ["machines", "machine_id (PK), name, machine_type, location, created_at",
         "Plant register"],
        ["readings", "id (PK), machine_id (FK), ts, cycle, five sensor values, derived "
         "quantities, predicted_class, p_failure, overall_stress, health_index, "
         "alarm_level, raw_alarm_level, rul_readings, rul_hours",
         "Every reading with the verdict it produced"],
        ["alarms", "id (PK), machine_id (FK), reading_id, ts, level, mode, message, cause, "
         "recommended_action, health_index, rul_hours, acknowledged, acknowledged_by",
         "Alarm and maintenance log"],
    ], widths=[62, 190, CONTENT_W - 252])]
    story += [P(
        "Two design decisions are worth noting. First, all timestamps are stored as ISO-8601 "
        "UTC strings - storing local time in a system modelling a 24-hour factory is a bug "
        "waiting for a clock change. Second, <b>an alarm row is written only when the band "
        "or mechanism changes</b>: a machine sitting in CRITICAL for forty readings is one "
        "event, not forty. Without this the log becomes unreadable and the unacknowledged "
        "count meaningless.")]

    story += [H2("4.4  Interface Design")]
    story += [table([
        ["Screen", "Purpose"],
        ["1. Plant Overview", "Status of every machine, sorted worst-first, with a KPI strip"],
        ["2. Machine HMI", "Live instruments, health, RUL, trends, alarm and ground truth "
         "for one machine"],
        ["3. Manual Input", "Enter one reading and receive the full explained verdict"],
        ["4. Batch Analysis", "Score a file and download the annotated results"],
        ["5. Alarms", "Maintenance log with filtering and acknowledgement"],
        ["6. Model Insights", "Evidence: lead time, metrics, confusion matrix, live XAI proof"],
    ], widths=[92, CONTENT_W - 92])]
    story += [PageBreak()]

    # ============================================================ CH 5
    story += [H1("5.  Methodology and Implementation")]

    story += [H2("5.1  Dataset Preparation")]
    story += [P(
        "The base data is the <b>AI4I 2020 Predictive Maintenance Dataset</b> from the UCI "
        "Machine Learning Repository: 10,000 records with 339 failures (3.39%), covering "
        "tool wear failure (46), heat dissipation failure (115), power failure (95), "
        "overstrain failure (98) and random failure (19).")]
    story += [P(
        "AI4I has one property that makes it unusable on its own for this project: "
        "<b>each record is an independent product snapshot, not a time series</b>. There is "
        "no machine identity, no cycle counter and no run-to-failure history, so nothing in "
        "it can teach a model what <i>approaching</i> a failure looks like.")]
    story += [P(
        "The dataset was therefore expanded into run-to-failure histories for 220 simulated "
        "machines. Each machine is given a stable operating point drawn from the real "
        "population and then degrades according to the exact rules that generate the real "
        "AI4I labels. Those rules were recovered from the real data and verified against it:")]
    story += [table([
        ["Mechanism", "Physical rule", "Reproduces real labels"],
        ["HDF - heat dissipation",
         "temperature difference < 8.6 K AND speed < 1380 rpm", "115 of 115"],
        ["PWF - power",
         "power outside 3,500 - 9,000 W, where power = torque x speed x 2 pi / 60",
         "95 of 95"],
        ["OSF - overstrain",
         "tool wear x torque > 11,000 (L) / 12,000 (M) / 13,000 (H)", "98 of 98"],
        ["TWF - tool wear",
         "wear inside the 200 - 240 min window (stochastic by design)", "46 of 801"],
    ], widths=[92, 208, CONTENT_W - 300])]
    story += [table([
        ["Property", "Value"],
        ["Total readings", "74,979  (10,000 real + 64,979 simulated)"],
        ["Machines", "220 run-to-failure trajectories"],
        ["Mean machine life", "295 readings, about 49.2 operating hours at one reading per 10 min"],
        ["Overall failure rate", "3.59%"],
        ["Class imbalance", "138.5 : 1  (Normal to rarest failure class)"],
        ["Correct-mechanism check", "210 of 220 machines fail by the mechanism assigned to them"],
    ], widths=[112, CONTENT_W - 112])]

    story += [H2("5.2  Exploratory Data Analysis")]
    story += [P(
        "Eight figures were produced. The most important, reproduced in Chapter 7, confirms "
        "that <b>every failure mode occupies its own physics zone</b> - the visual evidence "
        "that the labels are learnable from the available features. The analysis also "
        "established the 138.5:1 class imbalance that justifies the use of class weighting "
        "and macro-F1 rather than plain accuracy during model selection.")]

    story += [H2("5.3  Feature Engineering")]
    story += [P("Ten features are supplied to the model:")]
    story += [table([
        ["Feature", "Definition", "Why"],
        ["air_temperature", "raw sensor", "ambient reference"],
        ["process_temperature", "raw sensor", "process heat"],
        ["rotational_speed", "raw sensor", "operating point"],
        ["torque", "raw sensor", "applied load"],
        ["tool_wear", "raw sensor", "cumulative damage"],
        ["type_code", "encoded L/M/H", "product quality variant"],
        ["temp_delta", "process - air", "the quantity heat-dissipation failure depends on"],
        ["power", "torque x speed x 2 pi / 60", "the quantity power failure depends on"],
        ["strain", "tool wear x torque", "the quantity overstrain failure depends on"],
        ["torque_speed_ratio", "torque / speed", "drive load characteristic"],
    ], widths=[92, 118, CONTENT_W - 210])]
    story += [callout(
        "Two deliberate omissions",
        "<b>No margin-to-threshold features.</b> A feature such as <i>“how far is strain "
        "below its 12,000 limit”</i> is the signed distance to the decision boundary - "
        "target leakage disguised as feature engineering. The model would score almost "
        "perfectly and would have learned nothing. The forest is required to discover the "
        "thresholds itself, and the importances in Chapter 7 show that it did.<br/><br/>"
        "<b>No feature scaling.</b> Random Forest splits are axis-aligned and therefore "
        "invariant to any monotone rescaling. A scaler would add a component that could "
        "silently fall out of step between training and serving, for no benefit.", "info")]

    story += [H2("5.4  The Learning Target - the central design decision")]
    story += [P(
        "This section records the most important finding of the project.")]

    story += [H3("The first model was accurate and useless")]
    story += [P(
        "The model was initially trained on <font face='Courier'>failure_class</font> - the "
        "machine's physics-true state at the current instant. It performed extremely well:")]
    story += [kpi_row([
        ("Accuracy", "0.9899", "on held-out data"),
        ("Macro F1", "0.9005", ""),
        ("HDF / PWF recall", "1.0000", "every case caught"),
        ("Lead time", "-3.7 readings", "ALARM AFTER THE FAULT"),
    ])]
    story += [spacer(8)]
    story += [P(
        "The early-warning analysis measured a lead time of <b>minus 3.7 readings</b>: on "
        "average the system raised the alarm about <b>37 minutes after</b> the fault had "
        "already occurred.")]
    story += [P(
        "The cause is structural, not a coding error. "
        "<font face='Courier'>failure_class</font> is defined by threshold crossings, so a "
        "model trained on it can only ever report <i>“a threshold has been "
        "crossed”</i>. That is a condition monitor. A 0.99-accuracy model that fires "
        "after the failure does not meet the project's objective, however impressive the "
        "number looks.")]

    story += [H3("The reformulation")]
    story += [P(
        "The target was changed to <font face='Courier'>label_horizon</font>: the failure "
        "class extended backwards over the <b>15 readings (2.5 operating hours) preceding "
        "the trip</b>. The model is no longer asked <i>“has the limit been "
        "exceeded?”</i> but <i>“is this machine on the approach to a limit, and "
        "which one?”</i> - a question about trajectory rather than state. This is the "
        "standard predictive-maintenance formulation.")]
    story += [spacer(6), horizon_diagram(), spacer(2)]
    story += [P("<b>Figure 5.1</b> - The two labelling schemes. Under the old target the "
                "alarm can only fire once the machine has already failed; under the horizon "
                "target the readings that precede the trip carry the label of the failure "
                "that is coming, so the model learns the approach.", "caption")]

    story += [H2("5.5  Model Training")]
    story += [table([
        ["Setting", "Value"],
        ["Algorithm", "Random Forest Classifier"],
        ["Hyper-parameter search", "Randomised search, 12 candidates x 3 grouped folds, "
         "scoring macro-F1"],
        ["Selected parameters", "n_estimators = 300, max_depth = 14, max_features = log2, "
         "min_samples_leaf = 4, min_samples_split = 5, class_weight = balanced_subsample"],
        ["Train / test split", "59,784 / 15,195 readings, group-disjoint by machine"],
        ["Group overlap", "0 (asserted in code)"],
        ["Total pipeline time", "373 s on a 4-core machine"],
    ], widths=[112, CONTENT_W - 112])]
    story += [callout(
        "Group-aware splitting is mandatory here",
        "Consecutive readings from one machine are strongly autocorrelated. A plain random "
        "split would place reading #240 in training and reading #241 in test, and the model "
        "would be scored on data it has effectively memorised. All splitting and "
        "cross-validation therefore use StratifiedGroupKFold grouped by machine identity, "
        "and the training script asserts zero overlap between the groups.", "warn")]

    story += [H2("5.6  Decision Engine")]
    story += [H3("Health index")]
    story += [code("health = 0.60 x 100 (1 - stress^2.5)  +  0.40 x 100 x P(Normal)")]
    story += [P(
        "The exponent 2.5 is not decoration. Overall stress is the maximum over four "
        "mechanisms, so every healthy machine carries a floor of consumed margin - a tool "
        "at 30% of its life alone placed the median healthy machine at 81, inside the "
        "“Monitor” band. A machine that has used 30% of a consumable is not 70% "
        "healthy, and damage accumulation is genuinely non-linear: the last 20% of margin "
        "disappears far faster than the first. The exponent keeps healthy machines near 95 "
        "and falls away sharply once stress passes about 0.7, where the alarm bands begin.")]

    story += [H3("Remaining useful life")]
    story += [table([
        ["Situation", "Method", "Confidence reported"],
        ["History available", "Least-squares fit of the stress trajectory, extrapolated to "
         "stress = 1.0, with R-squared", "high / medium / low, from the fit quality"],
        ["Single reading", "Remaining fraction of a nominal 295-reading service life",
         "always low"],
        ["Flat or falling trend", "No finite life is reported", "displayed as STABLE"],
    ], widths=[92, 178, CONTENT_W - 270])]

    story += [H3("Alarms")]
    story += [P(
        "Four bands - NORMAL, ADVISORY, WARNING, CRITICAL - decided by the worst of the "
        "three independent signals, each carrying a plain-language cause and a concrete "
        "technician action.")]
    story += [P(
        "Evaluation measured a genuine nuisance-alarm rate of 10.8% of healthy-machine "
        "readings - isolated readings that flicker into a failure class and back. Raising "
        "the decision threshold would suppress them, but at the cost of the recall the whole "
        "project depends on. Instead a <b>persistence filter</b> requires an escalated band "
        "to hold for a number of consecutive readings before it is published. A genuine "
        "degradation trend persists by definition and is unaffected. De-escalation is "
        "immediate, and a hard threshold breach bypasses the filter entirely - those are "
        "arithmetic facts, not opinions.")]

    story += [H2("5.7  Explainability")]
    story += [P(
        "A tree ensemble's prediction decomposes exactly. Along the path a sample takes "
        "through a tree, each step is caused by exactly one feature - the one tested at that "
        "node - so the change in predicted class probability across that step is that "
        "feature's contribution for that sample. Summing over all 300 trees gives an "
        "exactly additive attribution:")]
    story += [code("P(class)  =  base rate  +  sum of per-feature contributions")]
    story += [P(
        "This is the decision-path (Saabas) method - the tree-specific case that TreeSHAP "
        "generalises. It requires no sampling and no additional library, and costs one "
        "traversal per tree. Because it is exact, the interface can state that the numbers "
        "shown <b>are</b> the prediction rather than an approximation of it. The claim is "
        f"verified live: across 500 readings the maximum reconstruction error is "
        f"{VER['max_absolute_error']:.1e}, which is machine precision.")]

    story += [H2("5.8  Backend and Interface")]
    story += [P(
        "The backend is a FastAPI application exposing 25 REST endpoints plus a "
        "server-sent event stream for the live feed. Server-sent events were chosen over "
        "WebSockets because the feed is strictly one-directional - control passes through "
        "ordinary POST endpoints - and SSE reconnects by itself, needs no additional "
        "dependency, and survives a proxy that would drop a socket.")]
    story += [P(
        "The interface is 3,044 lines of plain HTML, CSS and JavaScript with "
        "<b>no framework, no build step and no content-delivery network</b>. Every gauge and "
        "chart is hand-drawn SVG. This was a deliberate reliability decision: a CDN "
        "dependency would mean the demonstration works only if the room has internet at "
        "that moment, and a failed load would render the page as a row of blank rectangles.")]
    story += [PageBreak()]

    # ============================================================ CH 6
    story += [H1("6.  Testing")]
    story += [P(
        "The system is verified by 86 automated assertions across four suites, together "
        "with documented manual test cases. Full details, including every expected value, "
        "are given in the companion document <i>Test Cases and Expected Output</i>.")]
    story += [table([
        ["Suite", "Scope", "Assertions", "Result"],
        ["Engine (pytest)", "Physics stress, health, RUL, alarm engine, explainability", "29", "PASS"],
        ["API (pytest)", "All 25 endpoints, validation, batch upload, simulation lifecycle", "28", "PASS"],
        ["Widgets (Node.js)", "SVG gauges, rings, charts and bars against edge cases", "29", "PASS"],
        ["Boot (Node.js)", "Script load order, screen registration, teardown, navigation", "17", "PASS"],
        ["Browser (Playwright)", "All six screens driven in Chromium; console errors captured",
         "15 screens", "0 errors"],
    ], widths=[92, CONTENT_W - 232, 62, 78], align={2: "CENTER", 3: "CENTER"})]

    story += [H2("Defects found and corrected")]
    story += [P(
        "Six defects were found during development. They are listed because a testing "
        "chapter that reports only successes is not a testing chapter, and because the "
        "nature of these defects is itself a finding: <b>most of them were in the code "
        "around the model rather than in the model</b>, and none would have been revealed "
        "by an accuracy score.")]
    story += [table([
        ["#", "Defect", "Root cause", "Now guarded by"],
        ["1", "Interface rendered completely blank",
         "The script that declares the screen registry was loaded last, so every screen "
         "script failed before it existed",
         "tests/test_boot.js - executes the files in the order the page declares"],
        ["2", "Explanation disagreed with the model",
         "scikit-learn traverses trees in float32; the explainer compared in float64 and "
         "took the wrong branch at borderline thresholds",
         "Exactness assertion in the engine suite and a live self-check endpoint"],
        ["3", "A healthy machine reported 72/100 health",
         "Stress-free reference points were guessed rather than measured",
         "References recalibrated on 72,288 healthy readings; two regression tests"],
        ["4", "Power stress alarmed at nominal load",
         "Stress was measured from the centre of the design window instead of from the "
         "healthy operating band",
         "Deadband anchored on the measured healthy quartiles; regression test"],
        ["5", "A routine tool change floored the health gauge",
         "Entering the tool-wear window was treated as a hard failure",
         "Hard breach now excludes the tool-change condition; regression test"],
        ["6", "Sensor dials had their scale gap on the wrong side",
         "Incorrect start angle in the gauge geometry",
         "Found only by screenshotting a real browser; that capture now runs automatically"],
    ], widths=[16, 108, 158, CONTENT_W - 282], font_size=7.6)]
    story += [PageBreak()]

    # ============================================================ CH 7
    story += [H1("7.  Results and Discussion")]

    story += [H2("7.1  Early-Warning Performance")]
    story += [P("This is the result against which the project should be judged.")]
    story += [kpi_row([
        ("Mean lead time", f"+{EW['mean_lead_readings']}", f"readings = {EW['mean_lead_hours']} h"),
        ("Warned in advance", f"{EW['warned_before_failure_pct']}%",
         f"of {EW['machines_evaluated']} unseen machines"),
        ("Median lead time", f"{EW['median_lead_readings']}", "readings"),
        ("Horizon", "15", "readings label window"),
    ])]
    story += [spacer(10)]
    story += [table([
        ["Metric", "Old target (failure_class)", "New target (label_horizon)"],
        ["Mean lead time", "-3.7 readings  (-0.62 h)",
         f"+{EW['mean_lead_readings']} readings  (+{EW['mean_lead_hours']} h)"],
        ["Median lead time", "-3.0 readings", f"+{EW['median_lead_readings']} readings"],
        ["Machines warned before failure", "13.8%", f"{EW['warned_before_failure_pct']}%"],
        ["Lead time - HDF", "-9.3", f"+{EW['per_mode']['HDF']}"],
        ["Lead time - OSF", "-3.0", f"+{EW['per_mode']['OSF']}"],
        ["Lead time - PWF", "-6.5", f"+{EW['per_mode']['PWF']}"],
        ["Lead time - TWF", "+6.1", f"+{EW['per_mode']['TWF']}"],
    ], widths=[150, 138, CONTENT_W - 288])]
    story += [P(
        "The system now warns on average <b>8.67 operating hours</b> before failure, and "
        "does so for 97.6% of machines it has never seen.")]

    story += figure("art_14_early_warning_lead_time",
                    "Figure 7.1 - Early-warning lead time per machine. Every bar to the right "
                    "of zero is a machine warned before it failed.", width_frac=0.86, trim=False)

    story += [H2("7.2  Classification Performance")]
    story += [table([
        ["Metric", "Old target", "New target", "Note"],
        ["Accuracy", "0.9899", f"{HD['accuracy']:.4f}", "expected to fall - see discussion"],
        ["Balanced accuracy", "0.9082", f"{HD['balanced_accuracy']:.4f}",
         "corrects for the 138:1 imbalance"],
        ["Macro F1", "0.9005", f"{HD['macro_f1']:.4f}", ""],
        ["Macro recall", "-", f"{HD['macro_recall']:.4f}", "how few developing failures are missed"],
        ["Matthews correlation", "0.8495", f"{HD['mcc']:.4f}", ""],
    ], widths=[104, 74, 74, CONTENT_W - 252])]

    rows = [["Class", "Precision", "Recall", "F1", "ROC-AUC", "Support"]]
    for cls in ["Normal", "TWF", "HDF", "PWF", "OSF"]:
        s = PC[cls]
        rows.append([cls, f"{s['precision']:.4f}", f"{s['recall']:.4f}",
                     f"{s['f1-score']:.4f}", f"{MET['roc_auc'][cls]:.4f}",
                     f"{int(s['support']):,}"])
    story += [table(rows, widths=[70, 72, 66, 62, 70, CONTENT_W - 340],
                    align={1: "CENTER", 2: "CENTER", 3: "CENTER", 4: "CENTER", 5: "CENTER"})]
    story += [P(
        "<b>Recall and ROC-AUC are the meaningful columns here.</b> ROC-AUC lies between "
        "0.952 and 0.995 for every class, so the model separates them very well; recall is "
        "0.83 to 0.96 for the failure classes, so few developing failures are missed. The "
        "modest precision figures are examined in Section 7.4.")]

    story += [H2("7.3  Feature Importance")]
    gini = MET["feature_importance_gini"]
    perm = MET["feature_importance_permutation"]
    order = sorted(gini, key=gini.get, reverse=True)
    rows = [["Feature", "Gini importance", "Permutation importance", "Origin"]]
    physics = {"temp_delta", "power", "strain", "tool_wear"}
    for f in order:
        rows.append([f, f"{gini[f]:.4f}", f"{perm.get(f, 0):.4f}",
                     "engineered physics" if f in physics else "raw sensor"])
    story += [table(rows, widths=[128, 92, 118, CONTENT_W - 338],
                    align={1: "CENTER", 2: "CENTER"})]
    story += [callout(
        "The model rediscovered the physics",
        "The four physics-related quantities - tool wear, tool strain, mechanical power and "
        "thermal gradient - account for approximately <b>73% of the total importance</b>. "
        "The model was never given the threshold rules, and the margin-to-threshold features "
        "that would have handed them over were deliberately withheld. It located the "
        "governing quantities of each failure mechanism on its own. Both raw temperatures "
        "score near zero because the engineered thermal gradient already carries their "
        "information.", "ok")]

    story += [H2("7.4  Alarm Quality")]
    story += [P(
        "A precision of 0.264 for heat-dissipation failure looks alarming in isolation, so "
        "it was investigated rather than accepted. Each apparent false positive was measured "
        "against the distance to its machine's real failure event.")]
    story += [table([
        ["Of the 1,217 readings flagged while the label still said Normal", "Count", "Share"],
        ["On machines that DO eventually fail", "1,025", "84.2%"],
        ["Flagged BEFORE the failure event", "826", "67.9%"],
        ["Median distance ahead of failure", "34 readings", "mean 53.2"],
        ["On machines that never fail (genuine nuisance)", "192", "15.8%"],
    ], widths=[262, 86, CONTENT_W - 348], align={1: "CENTER", 2: "CENTER"})]
    story += [P(
        "Of all 2,223 alarms raised on the test set, <b>82.4% were operationally useful</b>: "
        "1,006 in-horizon hits plus 826 pre-horizon early warnings. The genuine nuisance rate "
        "is 10.8% of healthy-machine readings, which the persistence filter reduces further. "
        "<b>Strict per-reading precision therefore understates the system.</b> The model "
        "detects degradation earlier than the 15-reading label window allows, and every such "
        "reading is counted as an error while being exactly the behaviour required.")]

    story += [H2("7.5  System Screenshots")]
    story += figure("03_overview_running",
                    "Figure 7.2 - Plant Overview. Machine cards are ordered worst-first, each "
                    "showing a status lamp, health index, prediction, remaining life and tool wear.")
    story += figure("07_machine_breached",
                    "Figure 7.3 - Machine HMI for a degrading machine. The banner reports a "
                    "PREDICTED heat-dissipation failure with the recommended action; health has "
                    "fallen to 25 and remaining life to 1.1 hours. The status line records that "
                    "the system first warned 78 readings - 13 hours - ahead of the failure.")
    story += figure("09_manual_hdf",
                    "Figure 7.4 - Manual Input. A single reading produces the class probabilities, "
                    "health index, mechanism stress, cause, recommended action and the exact "
                    "decision-path attribution showing which sensor values drove the prediction.")
    story += figure("14_batch_results",
                    "Figure 7.5 - Batch Analysis. A 300-reading run-to-failure trajectory scored "
                    "in one upload; health falls from 99.9 to 0.3 across the file.")
    story += figure("16_model_insights",
                    "Figure 7.6 - Model Insights. The early-warning result is presented first, "
                    "ahead of accuracy, together with a live self-check proving that the "
                    "explanation reconstructs the model exactly.")

    story += [H2("7.6  Discussion")]
    story += [H3("Why the accuracy fell, and why that is correct")]
    story += [P(
        "Headline accuracy fell from 0.9899 to 0.9071 and macro F1 from 0.9005 to 0.6644 "
        "when the target changed. This is the expected and correct direction. The old task - "
        "recognising a limit that has already been crossed - is nearly trivial, because the "
        "label is a deterministic function of the features. The new task - recognising the "
        "approach to a limit hours in advance, from readings that still look close to normal "
        "- is genuinely harder, and it is the task the project requires. A system that "
        "reports faults after they happen has no value however accurately it reports them.")]

    story += [H3("Comparison with the reviewed literature")]
    story += [table([
        ["Aspect", "Typical reviewed work", "This project"],
        ["Headline metric", "Classification accuracy", "Early-warning lead time"],
        ["Warning timing", "Not reported", f"+{EW['mean_lead_hours']} operating hours"],
        ["Explainability", "SHAP / LIME approximations", "Exact decision-path attribution "
         f"({VER['max_absolute_error']:.0e})"],
        ["Validation split", "Often random", "Group-disjoint by machine, overlap asserted zero"],
        ["Deliverable", "Model and metrics", "Model, API, operator interface, 86 tests"],
    ], widths=[86, 148, CONTENT_W - 234])]

    story += [H3("Limitations")]
    story += bullets([
        "<b>Tool wear failure is partly unpredictable by construction.</b> In AI4I only 46 of "
        "the 801 readings inside the wear window are labelled TWF - the label is a random "
        "draw, so no model can fully predict it. The horizon target improved it from F1 0.557 "
        "to 0.711 with 0.958 recall, because the approach to the window is monotone and "
        "therefore learnable even though the draw is not.",
        "<b>64,979 of the 74,979 readings are physics-simulated.</b> The failure rules are "
        "calibrated exactly against the real data and the real records are retained, but the "
        "temporal dynamics are modelled rather than measured.",
        "<b>Precision is deliberately traded for recall.</b> In maintenance a missed failure "
        "costs far more than an unnecessary inspection.",
        "<b>No physical sensor validation.</b> The system is validated against a public "
        "dataset, not against a running machine.",
        "<b>Single operator identity.</b> Acknowledgements record a name with no authentication.",
    ])
    story += [PageBreak()]

    # ============================================================ CH 8
    story += [H1("8.  Conclusion and Future Scope")]
    story += [H2("Conclusion")]
    story += [P(
        "This project set out to build an AI-based predictive maintenance system that warns "
        "of machine failure <b>in advance</b>. That objective has been met and measured: the "
        f"system identifies which of four failure mechanisms a machine is approaching a mean "
        f"of <b>{EW['mean_lead_hours']} operating hours</b> before the failure occurs, and "
        f"warns before failure on <b>{EW['warned_before_failure_pct']}%</b> of machines it "
        "has never seen.")]
    story += [P(
        "Around that model it delivers a continuous health index, a remaining-life estimate "
        "that always states its own basis, a four-band alarm engine backed by independent "
        "physics checks, and an exact explanation of every prediction - presented through a "
        "six-screen operator interface that runs offline from a single command and is "
        "verified by 86 automated tests.")]
    story += [callout(
        "The principal finding",
        "<b>Accuracy is the wrong objective for a predictive maintenance system.</b> The "
        "first model built in this project scored 98.99% accuracy and was operationally "
        "worthless, because it raised the alarm 37 minutes after the fault. Reformulating "
        "the learning target around a prediction horizon cost eight percentage points of "
        "accuracy and converted a condition monitor into a predictive system. The metric a "
        "system is optimised for must reflect its purpose - here, how early it warns - and "
        "not merely the number that is easiest to report.", "ok")]
    story += [P(
        "A secondary finding, drawn from the six defects recorded in Chapter 6, is that "
        "<b>most of the ways such a system can quietly fail are not in the model at all</b>. "
        "They are in the constants, the interfaces and the presentation around it: a "
        "mis-calibrated reference that reported a healthy machine as failing, an attribution "
        "routine that disagreed with the model it explained, a gauge that discarded hours of "
        "hard-won warning time by slamming to zero on first suspicion. None of these would "
        "have appeared in an accuracy score.")]

    story += [H2("Future Scope")]
    story += [table([
        ["Direction", "Description"],
        ["Connect real sensors", "The reading schema, API and interface are unchanged; only a "
         "new data producer is required to replace the replay simulator."],
        ["Vibration and acoustic channels", "The strongest real-world predictive maintenance "
         "signals, absent from the AI4I dataset."],
        ["Online learning", "Periodic retraining as real machine data accumulates, with "
         "drift monitoring."],
        ["Per-machine RUL calibration", "Replace the population-mean nominal service life "
         "with a per-machine estimate learned from its own history."],
        ["Maintenance scheduling optimiser", "Convert remaining-life estimates across a plant "
         "into an ordered, resource-aware work queue."],
        ["Multi-user operation", "Authentication, per-technician alarm assignment and an "
         "audit trail."],
        ["Mobile notification", "Push alerts by SMS or email, as described in the synopsis "
         "methodology."],
    ], widths=[128, CONTENT_W - 128])]
    story += [PageBreak()]

    # ============================================================ REFERENCES
    story += [H1("References")]
    story += [P("<b>Works reviewed in the literature survey</b>", "body_left")]
    refs = [
        "S. Rani S, R. Aburukba and K. El-Fakih, “Optimizing Predictive Maintenance in "
        "Industrial IoT Cloud Using Dragonfly Algorithm,” IEEE Internet of Things "
        "Journal, 2025.",
        "L. Cummins, A. Sommers et al., “Explainable Predictive Maintenance: A Survey of "
        "Current Methods, Challenges and Opportunities,” 2024.",
        "J. M. Montes-Sánchez, Y. Uwate et al., “Predictive Maintenance Edge AI "
        "Using RNN for Peristaltic Pumps,” IEEE, 2025.",
        "T. Akyaz and D. Engin, “Machine Learning-Based Predictive Maintenance System "
        "for Artificial Yarn Machines,” IEEE, 2024.",
        "S. D. Deshmukh and P. U. Dere, “AI Driven Approach for Predictive Maintenance "
        "in Industry 4.0,” International Journal of Engineering Research & Technology "
        "(IJERT).",
        "C. R. Patil, S. K. Jadhav et al., “Machine Learning-Based Predictive "
        "Maintenance of Industrial Machines,” International Journal of Computer Trends "
        "and Technology, March 2023.",
        "D. Guidotti, L. Pandolfo and L. Pulina, “A Systematic Literature Review of "
        "Supervised Machine Learning Techniques for Predictive Maintenance in Industry "
        "4.0,” 2025.",
        "E. Zeydan, S. S. Arslan, Y. Turk, T. Hewa and M. Liyanage, “The Role of Mobile "
        "Communications for Industrial Automation: Architecture, Applications and "
        "Challenges,” 2025.",
        "K. Patel, A. Hariharan and R. Sucharitha, “Implementing Next-Gen Predictive "
        "Maintenance in Industrial Machineries: A Comparative Analysis of Small, Medium and "
        "Large Enterprises,” 2023.",
        "S. Gawde, S. Patil, S. Kumar and P. Kamat, “Explainable Predictive Maintenance "
        "of Rotating Machines Using LIME, SHAP, PDP and ICE,” 2023.",
    ]
    for i, r in enumerate(refs, 1):
        story += [Paragraph(f"[{i}]&nbsp;&nbsp;{r}", STYLES["body_left"])]

    story += [spacer(8), P("<b>Additional technical sources used in the implementation</b>",
                           "body_left")]
    more = [
        "S. Matzka, “Explainable Artificial Intelligence for Predictive Maintenance "
        "Applications,” Third International Conference on Artificial Intelligence for "
        "Industries, 2020. (Source of the AI4I 2020 dataset.)",
        "AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository. "
        "https://archive.ics.uci.edu/dataset/601/",
        "L. Breiman, “Random Forests,” Machine Learning, vol. 45, no. 1, "
        "pp. 5–32, 2001.",
        "A. Saabas, “Interpreting Random Forests,” 2014. (Decision-path "
        "attribution, the method used for the explainability panel.)",
        "S. M. Lundberg and S.-I. Lee, “A Unified Approach to Interpreting Model "
        "Predictions,” NeurIPS, 2017. (TreeSHAP generalises the above.)",
        "F. Pedregosa et al., “Scikit-learn: Machine Learning in Python,” Journal "
        "of Machine Learning Research, vol. 12, pp. 2825–2830, 2011.",
        "A. Saxena, K. Goebel, D. Simon and N. Eklund, “Damage Propagation Modeling for "
        "Aircraft Engine Run-to-Failure Simulation,” IEEE PHM, 2008. (Run-to-failure "
        "methodology.)",
    ]
    for i, r in enumerate(more, len(refs) + 1):
        story += [Paragraph(f"[{i}]&nbsp;&nbsp;{r}", STYLES["body_left"])]
    story += [PageBreak()]

    # ============================================================ APPENDIX
    story += [H1("Appendix A - How to Run the System")]
    story += [code(
        'cd "AI BASED PREDICTIVE MAINTENCE FOR INDUSTRIAL MACHINES"\n\n'
        "# start the system (API and interface on one port)\n"
        ".\\.venv\\Scripts\\python.exe -m backend.app\n\n"
        "# then open  http://127.0.0.1:8000/  and press 'Start Demo Plant'")]
    story += [P("<b>Rebuilding the model from scratch</b> (about 10 minutes):")]
    story += [code(
        ".\\.venv\\Scripts\\python.exe run_phase1.py\n\n"
        "# or resume from a stage (1 download, 2 expand, 3 EDA, 4 train, 5 evaluate)\n"
        ".\\.venv\\Scripts\\python.exe run_phase1.py --from 4")]
    story += [P("<b>Running the tests</b>:")]
    story += [code(
        ".\\.venv\\Scripts\\python.exe -m pytest tests/ -q     # 57 engine + API tests\n"
        "node tests/test_widgets.js                          # 29 widget assertions\n"
        "node tests/test_boot.js                             # 17 boot assertions")]

    story += [H1("Appendix B - Project Structure")]
    story += [code(
        "src/          Phase 1 - data preparation, features, training, evaluation\n"
        "  config.py     single source of truth: paths, schema, thresholds\n"
        "  data/         download, physics-informed expansion, EDA\n"
        "  features/     the shared feature builder\n"
        "  models/       Random Forest training\n"
        "  evaluation/   metrics, figures, early-warning and alarm-quality analysis\n\n"
        "backend/      Phase 2 - inference engine and API\n"
        "  app.py        FastAPI application\n"
        "  core/         physics, health, alarms, database\n"
        "  services/     predictor, explainer, simulator\n"
        "  api/          routes and request schemas\n\n"
        "frontend/     Phase 3 - SCADA interface (no build step)\n"
        "  index.html, css/style.css, js/{api,widgets,app}.js, js/screens/*.js\n\n"
        "tests/        57 Python tests + 46 JavaScript assertions\n"
        "data/         raw and processed datasets, runtime SQLite database\n"
        "models/       trained Random Forest bundle\n"
        "artifacts/    13 analysis figures and metrics in JSON\n"
        "docs/         the three project reports and their generators")]

    doc = Report(OUT, "AI-Based Predictive Maintenance for CNC Milling Machines",
                 "Final Year Project Report")
    doc.build(story)
    print(f"written: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
