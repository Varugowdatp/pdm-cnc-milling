# AI-BASED PREDICTIVE MAINTENANCE FOR CNC MILLING MACHINES
## Final Project Report

**Institution:** Government Engineering College, K. R. Pete
**Department:** Electronics & Communication Engineering
**Source requirements:** `Main synopsis (2).pdf`
**Date:** 10 September 2026
**Status:** ✅ All three phases complete

---

## Abstract

This project delivers a complete, working predictive-maintenance system for
**CNC milling machines**: from raw dataset to a trained Random Forest, through an
inference engine and REST API, to a SCADA-style operator interface.

The system predicts which of four failure mechanisms a machine is heading toward
**a mean of 52 readings — 8.67 operating hours — before the failure occurs**, and
warns before failure on **97.6% of unseen machines**. It states not only *what*
will fail but *how healthy the machine is now*, *how long is left*, *what to do
about it*, and — through exact decision-path attribution — *why it believes any of
that*.

It is implemented entirely in software, with no hardware, and runs offline from a
single command.

---

## 0. Monitored machine — CNC Milling Machine

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

## 1. Objectives and how they were met

| Synopsis objective | Delivered | Evidence |
|---|---|---|
| Collect machine operating data | UCI AI4I 2020 (10,000 real rows) + physics-informed expansion to 74,979 rows / 220 machines | §3 |
| Apply ML to predict failures | Random Forest on a 15-reading horizon target | §5 |
| Predict failure **in advance** | **+52 readings (8.67 h)** mean lead time, 97.6% warned | §6 |
| Identify the failure type | 4 mechanisms classified; ROC-AUC 0.95–0.99 per class | §6 |
| Estimate remaining life | RUL by stress-trend extrapolation with confidence | §7 |
| Alert the operator | 4-band alarm engine with persistence filtering + actions | §7 |
| Provide a monitoring dashboard | 6-screen SCADA HMI, zero dependencies | §9 |

---

## 2. Scope decision: a fully software realisation

The synopsis specifies a hardware sensing chain — temperature, vibration and
current sensors on a NodeMCU/ESP8266 uploading to the cloud. This implementation
**deliberately replaces that chain with software equivalents while keeping the
rest of the block diagram intact.**

### Hardware → software mapping

| Synopsis block (hardware) | Software equivalent | Where |
|---|---|---|
| Temperature / current / speed sensors | Sensor **schema** — identical field names, units and physical ranges | `src/config.py` `SENSORS` |
| NodeMCU acquisition | Manual entry form + CSV/Excel upload | Screens 3 and 4 |
| Wi-Fi upload to cloud | HTTP POST to a local REST API | `POST /api/predict` |
| Cloud data store | SQLite: machines, readings, alarm log | `backend/core/database.py` |
| Continuous sensor stream | Dataset **replay simulator** — real run-to-failure trajectories at controllable speed | `backend/services/simulator.py` |
| ML inference server | FastAPI service, model loaded once | `backend/services/predictor.py` |
| Operator dashboard / alert | SCADA HMI with live SSE feed | `frontend/` |

Every component consumes the same ten-field reading, so **replacing the simulator
with real sensors requires no change to the model, the API, or the UI — only a new
data producer.** The hardware path is not precluded; it is abstracted.

---

## 3. Dataset

### 3.1 Real base data

**AI4I 2020 Predictive Maintenance Dataset** (UCI): 10,000 rows, 339 failures
(3.39%) — TWF 46, HDF 115, PWF 95, OSF 98, RNF 19.

AI4I has one property that makes it unusable alone here: **each row is an
independent product snapshot, not a time series.** No machine identity, no cycle
counter, no run-to-failure history — so nothing in it can teach a model what
*approaching* a failure looks like.

### 3.2 Physics-informed expansion

220 simulated machines are grown into run-to-failure histories, giving **74,979
rows** (mean life 295 readings ≈ 49.2 h at one reading per 10 min).

Each machine gets a stable operating point drawn from the real population, then
degrades according to **the exact rules that generate the real AI4I labels** —
rules recovered from the real data and verified against it:

| Mode | Rule | Reproduces real labels |
|---|---|---|
| HDF | `temp_delta < 8.6 K` AND `speed < 1380 rpm` | 115/115 ✓ |
| PWF | `power` outside 3,500–9,000 W | 95/95 ✓ |
| OSF | `tool_wear × torque > {L:11000, M:12000, H:13000}` | 98/98 ✓ |
| TWF | wear in the 200–240 min window (**stochastic**) | 46 of 801 |

210 of 220 machines fail by their assigned mechanism. Real rows are retained with
a `source` flag, so any result can be recomputed on real data alone.

**Class imbalance: 138.5 : 1** (Normal : rarest) — which drives the use of
`class_weight` and macro-F1 rather than accuracy.

---

## 4. Feature engineering

Ten features, built by a module **shared between training and live inference** so
the transform cannot drift between them.

| Engineered feature | Formula | Why |
|---|---|---|
| `temp_delta` | process − air | the quantity HDF depends on |
| `power` | torque × speed × 2π/60 | the quantity PWF depends on |
| `strain` | tool_wear × torque | the quantity OSF depends on |
| `torque_speed_ratio` | torque / speed | drive load regime |

plus the five raw sensors and the encoded machine variant.

**Two deliberate omissions:**

- **No "margin to threshold" features.** *"How far is strain below its 12,000
  limit"* is the signed distance to the decision boundary — target leakage
  dressed as feature engineering. The forest must find the thresholds itself.
- **No scaler.** Random Forest splits are axis-aligned and invariant to monotone
  rescaling; a scaler would only add a component that could silently desynchronise
  between training and serving.

The importances in §6 show this worked: the four physics quantities carry ~73% of
the weight — **the model rediscovered the governing physics unaided.**

---

## 5. The central engineering decision

This is the most important result in the project.

### The first model was accurate and useless

Trained on `failure_class` — the machine's physics-true state **right now** — it
scored:

| Metric | Value |
|---|---|
| Accuracy | **0.9899** |
| Macro F1 | 0.9005 |
| HDF/PWF recall | 1.0000 |

And its measured early-warning lead time was **−3.7 readings**: the system raised
the alarm roughly **37 minutes *after* the fault had already occurred.**

The reason is structural, not a bug. `failure_class` is defined by threshold
crossings, so a model trained on it can only report *"a threshold has been
crossed"*. That is a **condition monitor**, not a predictor — and it fails the
project's actual objective, however good the accuracy looks.

### The fix

The target was changed to **`label_horizon`**: the failure class extended
backwards over the **15 readings (2.5 h) preceding the trip**. The model is no
longer asked *"has the limit been exceeded?"* but *"is this machine on the
approach to a limit, and which one?"* — a question about trajectory, not state.

### Result

| Early-warning metric | Old target | **New target** |
|---|---|---|
| Mean lead time | −3.7 readings (−0.62 h) | **+52.0 readings (+8.67 h)** |
| Median lead time | −3.0 | **+38.0** |
| Warned before failure | 13.8% | **97.6%** |
| HDF / OSF / PWF / TWF | −9.3 / −3.0 / −6.5 / +6.1 | **+47.6 / +64.2 / +49.8 / +45.8** |

**Accuracy fell from 0.9899 to 0.9071 and macro F1 from 0.9005 to 0.6644 — and
this is the correct direction.** The old task is nearly trivial (the label is a
deterministic function of the features). The new task — recognising an approach
hours ahead from readings that still look near-normal — is genuinely hard, and is
the task the project requires.

---

## 6. Model and results

**Random Forest Classifier** — 300 trees, `max_depth=14`, `max_features=log2`,
`min_samples_leaf=4`, `class_weight=balanced_subsample`. Randomised search over
12 candidates × 3 grouped folds scoring macro-F1; total pipeline 373 s.

**Group-aware splitting is mandatory here.** Consecutive readings from one machine
are strongly autocorrelated; a random split would put reading #240 in training and
#241 in test and report memorisation as accuracy. All splits use
`StratifiedGroupKFold` on `machine_id`, and the training script asserts **zero
group overlap**.

### Held-out test set — 15,195 rows, 42 unseen machines

| Metric | Value |
|---|---|
| Accuracy | 0.9071 |
| Balanced accuracy | 0.8483 |
| Macro F1 | 0.6644 |
| Macro recall | 0.8483 |
| MCC | 0.5907 |

| Class | Precision | Recall | F1 | ROC-AUC | Support |
|---|---|---|---|---|---|
| Normal | 0.9852 | 0.9131 | 0.9478 | 0.9521 | 13,997 |
| TWF | 0.5649 | 0.9583 | 0.7108 | 0.9950 | 336 |
| HDF | 0.2641 | 0.8347 | 0.4012 | 0.9748 | 242 |
| PWF | 0.4645 | 0.6644 | 0.5467 | 0.9803 | 295 |
| OSF | 0.6073 | 0.8708 | 0.7155 | 0.9914 | 325 |

### Reading these numbers honestly

**Recall is high where it matters** (0.83–0.96) and **ROC-AUC is 0.95–0.995 for
every class** — the model separates the classes very well. The modest precision was
investigated rather than accepted, by measuring how far each apparent false
positive sits from its machine's real failure:

| Of 1,217 rows flagged while the label says Normal | |
|---|---|
| On machines that **do** eventually fail | **84.2%** |
| Flagged **before** the failure event | 826 — median **34 readings** ahead |
| Operationally useful flags (of all 2,223) | **82.4%** |
| Genuine nuisance flags (never-failing machines) | 10.8% of healthy rows |

**Strict per-row precision understates the system.** The model detects degradation
*earlier* than the 15-reading label window allows, and every such row is scored as
an error while being exactly the behaviour the project wants.

### Feature importance

`tool_wear 0.238 · strain 0.172 · power 0.164 · temp_delta 0.156 · torque 0.105 ·
speed 0.068 · torque_speed_ratio 0.063`; both raw temperatures ≈ 0.

---

## 7. Inference engine

### Three independent opinions, worst wins

| # | Signal | Nature | Foolable? |
|---|---|---|---|
| 1 | Random Forest class + confidence | learned | yes |
| 2 | Physics stress ratio | first-principles | no |
| 3 | Hard threshold rule check | deterministic | no |

Defence in depth: an industrial system must never let a learned component be the
only thing between a fault and the operator.

### Health index

```
health = 0.60 × 100(1 − stress^2.5) + 0.40 × 100·P(Normal)
```

The **exponent 2.5** matters. `overall_stress` is the max over four mechanisms, so
every healthy machine carries a floor of consumed margin — a tool at 30% of its
life alone put the median healthy machine at 81, inside "Monitor". A machine that
has used 30% of a consumable is not 70% healthy, and damage accumulation is
non-linear. The exponent keeps healthy machines near 95 and falls away past
stress ≈ 0.7.

### RUL — two regimes, honestly labelled

| Regime | Method | Confidence |
|---|---|---|
| With history | least-squares fit of stress(t) extrapolated to 1.0, R² reported | from R² |
| Single reading | remaining fraction of a nominal 295-reading life | always low |

The method is returned in the payload so the UI can never present a guess as a
measurement.

### Alarms

Four bands from the worst of the three signals, each carrying a plain-language
cause and a concrete technician action.

**Persistence filtering** solves the 10.8% nuisance rate *without* touching
recall: an escalated band must hold for N consecutive readings (ADVISORY/WARNING
2, CRITICAL 3) before publishing. Raising the decision threshold would have traded
away the recall the whole project depends on. De-escalation is immediate, and
hard breaches bypass the filter — those are arithmetic facts, not opinions.

### Explainability

Per-prediction attribution by **Saabas decision-path decomposition**, exact for
tree ensembles:

```
P(class) = base_rate + Σ per-feature contributions
```

Verified live against `predict_proba` across 500 rows and every failure class:
**max error 8.9 × 10⁻¹⁶** — machine precision. The panel shows *the* reason for a
prediction, not an approximation.

> *"Thermal Gradient (dT) at 8.6 K, Tool Wear at 113 min and Rotational Speed at
> 1342 rpm raised the likelihood of HDF from a baseline 20% to 46%."*

---

## 8. API

24 REST endpoints across prediction, plant, simulation, alarms, insights and
system, plus an **SSE live stream**. Interactive documentation at `/docs`.

SSE rather than WebSocket: the feed is one-directional, reconnects itself, needs
no extra dependency, and survives a proxy that would drop a socket.

---

## 9. Operator interface

Six screens — Plant Overview, Machine HMI, Manual Input, Batch Analysis, Alarms,
Model Insights — in **3,044 lines of vanilla HTML/CSS/JS with zero external
dependencies**. Every gauge and chart is hand-drawn SVG; there is no framework, no
bundler, and **no CDN**, so the system works with the network unplugged.

Three places where the UI deliberately refuses to overstate certainty:

1. **RUL always shows its basis** — `trend fit · R²=0.87 · high confidence` vs
   `nominal estimate · low confidence`.
2. **A capped extrapolation reads STABLE**, not "166.5 h" — a flat trend is not a
   forecast.
3. **PREDICTED and LIMIT BREACHED are visually distinct** — the gap between them is
   the entire value of Phase 1, and collapsing it in the UI would discard it.

---

## 10. Verification

| Suite | Count | Status |
|---|---|---|
| Engine tests (physics, health, RUL, alarms, explainer) | 29 | ✅ |
| API tests (every endpoint, via TestClient) | 28 | ✅ |
| Widget tests (SVG rendering edge cases) | 29 | ✅ |
| Data-contract check (frontend ↔ API) | all fields | ✅ |
| **Total** | **86** | **✅ all passing** |

Eight tests exist specifically to prevent a fixed bug returning, including the
float32/float64 attribution bug and each of the four calibration errors.

---

## 11. What went wrong, and what it taught

The most valuable findings in this project were failures.

**1. Accuracy was the wrong objective.** A 0.9899-accuracy model was
operationally worthless because it fired after the fault. Measuring the metric
that reflects the *purpose* — lead time — exposed it. *(§5)*

**2. Guessed constants corrupted the whole gauge.** `STRESS_FREE` was set to
"comfortably safe" values of 12.0 K and 2100 rpm. The measured healthy band is
8.2–12.3 K against an 8.6 K limit — so a **perfectly healthy machine reported 44%
heat stress and 72/100 health**. The same error in the power model alarmed a
healthy machine at nominal load. Both were fixed by measuring the 72,288 healthy
rows.

**3. A library's internal precision is part of its contract.** scikit-learn casts
`X` to float32 before traversing a tree. The explainer compared in float64 and
took the *wrong branch* at thresholds within float32 rounding distance,
reconstructing HDF as 0.0374 against the model's true 0.0344. **The live
self-check endpoint is what caught it** — building verification into the system,
rather than trusting it, was what made the difference.

**4. Not every threshold crossing is a failure.** Entering the tool-wear window is
a scheduled tool change; only ~6% of readings inside it are labelled TWF. Treating
it as a hard breach floored the health gauge on every machine that just needed a
new tool.

**5. Most of the damage lives around the model, not in it.** Four of the bugs found
in Phase 2 were in the code *surrounding* the forest, and every one would have
produced a technically-running system that lied to its operator. **None would have
shown up in an accuracy score.**

---

## 12. Limitations

1. **TWF is partly unpredictable by construction** — the AI4I label is a random
   draw among rows in the wear window. Improved by the horizon target (F1 0.557 →
   0.711, recall 0.958) but bounded by the dataset.
2. **64,979 of 74,979 rows are simulated.** The physics rules are exactly
   calibrated to the real data, but temporal dynamics are modelled, not measured.
3. **Precision is deliberately traded for recall.** In maintenance a missed
   failure costs far more than an unnecessary inspection.
4. **No automated browser test** for the UI (contract, widget and API layers are
   automated).
5. **Single-writer SQLite** and **no authentication** — fine at this scale, not a
   plant deployment.
6. **RNF excluded** — random failures carry no signal by definition.

---

## 13. Future scope

- **Connect real sensors.** The reading schema is unchanged; only a new data
  producer is needed to replace the simulator.
- **Online learning** — retrain periodically as real machine data accumulates.
- **Per-machine RUL calibration** rather than a population-mean nominal life.
- **Multi-user operation** with authentication and per-technician alarm assignment.
- **Vibration and acoustic channels** — the strongest real-world PdM signals, absent
  from AI4I.
- **Maintenance scheduling optimiser** — turn RUL estimates across a plant into an
  ordered work queue.

---

## 14. Conclusion

The system meets every objective in the synopsis, in software. It predicts the
failure mechanism a mean of **8.67 operating hours ahead** for **97.6%** of unseen
machines, quantifies health and remaining life, raises actionable banded alarms,
explains every prediction exactly, and presents all of it in an operator interface
that runs offline from one command.

The central lesson is that **a predictive-maintenance system is judged by lead
time, not accuracy** — and that most of the ways it can quietly fail are not in the
model at all, but in the constants, the interfaces and the presentation around it.

---

## References

1. Matzka, S. (2020). *Explainable Artificial Intelligence for Predictive
   Maintenance Applications.* AI4I 2020 Dataset, UCI Machine Learning Repository.
2. Breiman, L. (2001). *Random Forests.* Machine Learning, 45(1), 5–32.
3. Saabas, A. (2014). *Interpreting Random Forests.* — decision-path attribution.
4. Lundberg, S. & Lee, S. (2017). *A Unified Approach to Interpreting Model
   Predictions* (TreeSHAP generalises the above).
5. Pedregosa et al. (2011). *Scikit-learn: Machine Learning in Python.* JMLR 12.
6. Saxena, A. et al. (2008). *Damage Propagation Modeling for Aircraft Engine
   Run-to-Failure Simulation.* IEEE PHM — run-to-failure methodology.
7. Project synopsis: `Main synopsis (2).pdf` — objectives, block diagram,
   methodology, literature review.

### Project documents

| Document | Contents |
|---|---|
| `README.md` | Setup and run instructions |

---

*Final report — 10 September 2026. All three phases complete. 86 tests passing.*
