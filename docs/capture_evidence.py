"""
============================================================
 EVIDENCE CAPTURE  -  screenshots + exact API outputs
============================================================
Drives the real HMI in a real browser (Chromium via Playwright),
screenshots every screen, and records the exact API responses behind
them.

Two purposes:
  1. Supplies the figures and the verified expected-output values for
     the three PDF reports in docs/.
  2. Acts as the browser-level test the earlier phases could not run -
     it fails loudly if a screen throws a JavaScript error.

Console errors are collected per screen. A blank-page bug like the
script load-order failure would surface here immediately.

Usage:
    python docs/capture_evidence.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOTS = ROOT / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
EVIDENCE = ROOT / "docs" / "evidence.json"

BASE = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1600, "height": 1000}


def wait_for_server(timeout=60):
    import urllib.request
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    from playwright.sync_api import sync_playwright

    if not wait_for_server():
        print("ERROR: server is not running. Start it with:")
        print("   python -m backend.app")
        return 1

    evidence = {"screens": {}, "api": {}, "console_errors": {}}
    shots = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"PAGE ERROR: {e}"))

        def shot(name, note=""):
            path = SHOTS / f"{name}.png"
            page.screenshot(path=str(path), full_page=True)
            shots.append(name)
            evidence["console_errors"][name] = list(errors)
            if errors:
                print(f"   !! {len(errors)} console error(s) on {name}")
                for e in errors[:3]:
                    print(f"      {e[:120]}")
            errors.clear()
            print(f"   captured {name}.png{('  - ' + note) if note else ''}")

        # ---------------------------------------------------------
        print("\n1. PLANT OVERVIEW (empty state)")
        page.goto(BASE + "/#/overview", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot("01_overview_empty", "before any machine is monitored")

        # ---------------------------------------------------------
        print("\n2. START DEMO PLANT")
        page.click("#ov-demo")
        page.wait_for_timeout(3000)
        shot("02_overview_starting", "four machines just started")

        # The demo button runs at 0.7-1.6 s/reading, so in a reasonable
        # capture window the machines are still early in life and all read
        # healthy. Restart them far faster so the report shows a plant that
        # has actually degraded - the interesting state.
        print("   restarting the plant at high speed so machines truly degrade ...")
        import urllib.request as _u
        def _post(path, payload):
            _u.urlopen(_u.Request(BASE + path, data=json.dumps(payload).encode(),
                       headers={"Content-Type": "application/json"}, method="POST"))
        cat = json.load(_u.urlopen(BASE + "/api/simulate/catalogue?limit=24"))["machines"]
        picked, seen = [], set()
        for m in cat:
            if m["failure_mode"] not in seen:
                picked.append(m); seen.add(m["failure_mode"])
            if len(picked) == 4: break
        for i, m in enumerate(picked):
            _post("/api/simulate/start", {"machine_id": f"MACHINE-{i+1:02d}",
                  "source_machine": m["machine_id"], "interval": 0.06, "restart": True})
        print("   running 45 s at 0.06 s/reading (~750 readings each) ...")
        page.wait_for_timeout(45000)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)
        # The fully-loaded overview is captured at the END of the session -
        # see below. A few seconds in, every card still reads healthy.

        # ---------------------------------------------------------
        print("\n3. MACHINE HMI")
        page.goto(BASE + "/#/machine", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot("04_machine_picker", "machine + trajectory picker")

        worst = json.load(_u.urlopen(BASE + "/api/machines"))["machines"][0]["machine_id"]
        page.goto(BASE + f"/#/machine/{worst}", wait_until="networkidle")
        page.wait_for_timeout(7000)
        shot("05_machine_hmi", f"{worst} - live dials, health ring, RUL, trends")

        # The two machine states the user guide is built around. Kept in its
        # own module - getting it reproducible took several attempts and the
        # failure modes are all subtle. See docs/machine_capture.py.
        from machine_capture import capture as capture_machine_states
        evidence["machine_shots"] = capture_machine_states(page, shot, worst)

        # ---------------------------------------------------------
        print("\n4. MANUAL INPUT")
        page.goto(BASE + "/#/manual", wait_until="networkidle")
        page.wait_for_timeout(2500)
        shot("08_manual_healthy", "healthy preset")

        for preset, name in [("hdf", "09_manual_hdf"), ("pwf", "10_manual_pwf"),
                             ("osf", "11_manual_osf"), ("twf", "12_manual_twf")]:
            page.click(f'[data-preset="{preset}"]')
            page.wait_for_timeout(2200)
            shot(name, f"{preset.upper()} preset")

        # ---------------------------------------------------------
        print("\n5. BATCH ANALYSIS")
        page.goto(BASE + "/#/batch", wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot("13_batch_empty", "upload drop zone")

        page.click("#b-sample")
        page.wait_for_timeout(9000)
        shot("14_batch_results", "300-row trajectory scored")

        # ---------------------------------------------------------
        print("\n6. ALARMS")
        page.goto(BASE + "/#/alarms", wait_until="networkidle")
        page.wait_for_timeout(2500)
        shot("15_alarms", "maintenance log")

        # ---------------------------------------------------------
        print("\n7. MODEL INSIGHTS")
        page.goto(BASE + "/#/model", wait_until="networkidle")
        page.wait_for_timeout(6000)
        shot("16_model_insights", "metrics, matrix, live XAI proof")

        # ---------------------------------------------------------
        print("\n8. PLANT OVERVIEW (after the plant has been under load)")
        page.goto(BASE + "/#/overview", wait_until="networkidle")
        page.wait_for_timeout(4000)
        shot("03_overview_running", "plant under load, cards sorted worst-first")

        browser.close()

    # ---------------------------------------------------------
    print("\n9. RECORDING EXACT API OUTPUTS")
    import urllib.request

    def get(p):
        with urllib.request.urlopen(BASE + p) as r:
            return json.load(r)

    def post(p, payload=None):
        data = json.dumps(payload).encode() if payload is not None else b"{}"
        req = urllib.request.Request(p if p.startswith("http") else BASE + p, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    evidence["api"]["health"] = get("/api/health")
    evidence["api"]["reference_keys"] = list(get("/api/reference").keys())
    evidence["api"]["model_info"] = get("/api/model/info")
    evidence["api"]["metrics"] = get("/api/model/metrics")
    evidence["api"]["verify"] = get("/api/model/verify?samples=20")
    evidence["api"]["machines"] = get("/api/machines")
    evidence["api"]["alarms"] = get("/api/alarms?limit=25")
    evidence["api"]["catalogue"] = get("/api/simulate/catalogue?limit=6")

    # canonical single predictions, one per scenario, for the test report
    scenarios = {
        "healthy": dict(machine_type="M", air_temperature=298.0, process_temperature=308.0,
                        rotational_speed=1558, torque=38.5, tool_wear=71),
        "hdf_approach": dict(machine_type="L", air_temperature=303.05, process_temperature=312.17,
                             rotational_speed=1208, torque=46.7, tool_wear=101.2),
        "pwf_approach": dict(machine_type="M", air_temperature=302.56, process_temperature=312.75,
                             rotational_speed=2121, torque=38.6, tool_wear=78.3),
        "osf_approach": dict(machine_type="M", air_temperature=300.27, process_temperature=309.53,
                             rotational_speed=1230, torque=45.2, tool_wear=85.4),
        "twf_window": dict(machine_type="L", air_temperature=301.41, process_temperature=312.08,
                           rotational_speed=2975, torque=23.3, tool_wear=198.1),
        "hdf_breached": dict(machine_type="M", air_temperature=298.0, process_temperature=306.0,
                             rotational_speed=1300, torque=38.0, tool_wear=90),
    }
    evidence["api"]["predictions"] = {}
    for key, reading in scenarios.items():
        evidence["api"]["predictions"][key] = {
            "input": reading,
            "output": post("/api/predict", {**reading, "explain": True}),
        }
        print(f"   {key:15s} -> {evidence['api']['predictions'][key]['output']['prediction']['class']}")

    # validation failures, for the negative test cases
    evidence["api"]["validation"] = {}
    bad_cases = {
        "negative_speed": dict(scenarios["healthy"], rotational_speed=-5),
        "zero_speed": dict(scenarios["healthy"], rotational_speed=0),
        "bad_variant": dict(scenarios["healthy"], machine_type="Z"),
        "missing_torque": {k: v for k, v in scenarios["healthy"].items() if k != "torque"},
    }
    for key, payload in bad_cases.items():
        try:
            post("/api/predict", payload)
            evidence["api"]["validation"][key] = {"status": 200, "detail": "UNEXPECTEDLY ACCEPTED"}
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode())
            evidence["api"]["validation"][key] = {"status": e.code, "detail": body.get("detail")}
        print(f"   {key:15s} -> HTTP {evidence['api']['validation'][key]['status']}")

    # out-of-range but accepted
    try:
        r = post("/api/predict", dict(scenarios["healthy"], torque=95.0))
        evidence["api"]["validation"]["extreme_torque_accepted"] = {
            "status": 200, "warnings": r["input_warnings"]}
        print(f"   extreme_torque  -> HTTP 200 with {len(r['input_warnings'])} warning(s)")
    except Exception as e:
        evidence["api"]["validation"]["extreme_torque_accepted"] = {"error": str(e)}

    evidence["screens"] = shots
    total_errors = sum(len(v) for v in evidence["console_errors"].values())

    EVIDENCE.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 62)
    print(f"  {len(shots)} screenshots -> docs/screenshots/")
    print(f"  evidence        -> docs/evidence.json")
    print(f"  console errors  -> {total_errors}")
    print("=" * 62)
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
