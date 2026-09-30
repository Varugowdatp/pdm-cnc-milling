# Essential Website Test Cases — CNC Milling Machine PdM

These are the **12 test cases that must pass on the website** before a demo or
viva. Together they touch every screen and every failure mode once. The full
159-case list is still in `01_TEST_CASES_AND_EXPECTED_OUTPUT.pdf`; you do not need
to run all of it.

**Setup:** `.\.venv\Scripts\python.exe -m backend.app`, then open
**http://127.0.0.1:8000/** in Chrome/Edge. Run the tests in order.

Expected values below were recorded from a real browser run on 2026-09-21
(`docs/evidence.json`). The health index is shown rounded on screen (34.7 → 35).

---

| # | Screen | Steps | Expected result | Pass? |
|---|---|---|---|---|
| **TC-01** | Any | Open the site. | Header reads **PREDICTIVE MAINTENANCE / CNC MILLING MACHINE MONITORING**. Status dot is green ("online"). All 6 tabs open without a blank screen. | ☐ |
| **TC-02** | Plant Overview | Press **▶ Start Demo Plant**, wait ~10 s. | 4 machine cards appear and their reading counters increase. Status LEDs change colour as machines degrade. | ☐ |
| **TC-03** | Machine HMI | Pick a running machine from the list. | 5 dials (air temp, process temp, rotational speed, torque, tool wear), health ring, RUL and live trend lines all update. Press **STOP**: updates freeze. Press **START**: they resume. | ☐ |
| **TC-04** | Manual Input | Press preset **Healthy machine** (M, 298.0 K, 308.0 K, 1558 rpm, 38.5 Nm, 71 min). | Prediction **Normal**, 99.3 % confidence. Health **97, NORMAL**. Action: *"No maintenance action required."* | ☐ |
| **TC-05** | Manual Input | Press **Approaching heat failure** (L, 303.05, 312.17, 1208 rpm, 46.7 Nm, 101.2 min). | Prediction **HDF**, 92.2 % confidence. Banner **WARNING — Heat Dissipation Failure** with a **PREDICTED** tag. Health **35**. Action begins *"Check the coolant supply and concentration…"*. | ☐ |
| **TC-06** | Manual Input | Press **Approaching power failure** (M, 302.56, 312.75, 2121 rpm, 38.6 Nm, 78.3 min). | Prediction **PWF**, 95.2 % confidence. **WARNING**. Health **30**. Action begins *"Check the spindle motor drive…"*. | ☐ |
| **TC-07** | Manual Input | Press **Approaching overstrain** (M, 300.27, 309.53, 1230 rpm, 45.2 Nm, 85.4 min). | Prediction **OSF**, 42.5 % confidence. **WARNING**. Health **40**. Action begins *"Reduce feed rate and depth of cut immediately…"*. | ☐ |
| **TC-08** | Manual Input | Press **Approaching tool wear failure** (L, 301.41, 312.08, 2975 rpm, 23.3 Nm, 198.1 min). | Prediction **TWF**, 79.3 % confidence. **WARNING**. Health **31**. Action begins *"Change the end mill (or re-grind it)…"*. | ☐ |
| **TC-09** | Manual Input | Enter M, 298.0 K, **306.0 K**, **1300 rpm**, 38.0 Nm, 90 min. Press **ANALYSE**. | Limit actually crossed (8.0 K < 8.6 K at 1300 rpm < 1380 rpm). Prediction **HDF**. Alarm **CRITICAL** with **LIMIT BREACHED**, not "predicted". Health **5**. | ☐ |
| **TC-10** | Manual Input | Set **Rotational Speed = -5**, press **ANALYSE**. Then set **Torque = 95** with valid other values. | -5 is rejected with *"Input should be greater than 0"* and no prediction is shown. 95 Nm is accepted but shows the warning *"Torque = 95 Nm is outside the typical range 3-80 Nm."* | ☐ |
| **TC-11** | Batch Analysis | Upload `batch_testing/03_Run_To_Failure_Real_Dataset/HDF_Heat_Dissipation/MC-009_type_L_188_readings.xlsx`. Then upload `batch_testing/08_Invalid_Inputs/Expect_Rejected_File/missing_torque_column.xlsx`. | First file: all **188** rows scored, **140 Normal / 48 HDF**, with the first HDF at row **129** (early warning well before the end of the run). **Annotated CSV** downloads. Second file: rejected with *"Uploaded file is missing required column(s): torque"*, and nothing is scored. | ☐ |
| **TC-12** | Alarms → Model Insights → Overview | On **Alarms**, press **Acknowledge** on one row. Open **Model Insights**. Finally, on Overview press **Reset Plant** and confirm. | The alarm is marked acknowledged. Model Insights shows mean lead time **8.67 h** and **97.6 %** warned before failure; its live explanation self-check reads **exact**. Reset returns an empty plant. | ☐ |

---

### Result

| Tested by | Date | Browser | Passed | Failed |
|---|---|---|---|---|
| | | | / 12 | |

If any case fails, note the screen, the exact values entered, and what appeared
instead.
