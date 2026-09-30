"""
Machine-screen capture: the two states the user guide is built around.

Kept in its own module because getting it right took several attempts
and the failure modes are all subtle:

  * the display name (MACHINE-01) is not the dataset trajectory (MC-001);
  * a machine that fails at 96% of its run is still healthy at 87%;
  * a fixed sleep under-runs, because each replay step also performs a
    prediction and a database write;
  * a breach is NOT monotonic - power fluctuates across the limit - so
    polling for a breach and reading the state a moment later can
    disagree with the screenshot.

The last point is why the replay is FROZEN before each capture, and why
one single payload is used for both the picture and the recorded
numbers. If the two ever disagree, the guide would describe a figure
the reader is not looking at.
"""

from __future__ import annotations

import json
import time
import urllib.request as _u

BASE = "http://127.0.0.1:8000"
INTERVAL = 0.25
RUNWAY = 90


def _get(path):
    with _u.urlopen(BASE + path) as r:
        return json.load(r)


def _post(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else b""
    req = _u.Request(BASE + path, data=data, method="POST",
                     headers={"Content-Type": "application/json"} if payload else {})
    with _u.urlopen(req) as r:
        return json.load(r)


def _detail(mid):
    """One fetch -> the payload the screen itself is rendering."""
    det = _get(f"/api/machines/{mid}")
    return det, (det.get("live") or {}), (det.get("simulation") or {})


def snapshot(det, tag, mid):
    """Flatten the payload behind a screenshot into quotable values."""
    live = det.get("live") or {}
    sim = det.get("simulation") or {}
    if not live:
        return {}
    return {
        "tag": tag,
        "machine_id": mid,
        "source_machine": sim.get("source_machine"),
        "position": sim.get("position"),
        "total": sim.get("total"),
        "fails_at_cycle": sim.get("fails_at_cycle"),
        "eventual_failure_mode": sim.get("eventual_failure_mode"),
        "lead_time_readings": sim.get("lead_time_readings"),
        "lead_time_hours": sim.get("lead_time_hours"),
        "predicted_class": live["prediction"]["class"],
        "confidence": live["prediction"]["confidence"],
        "health": live["health"]["index"],
        "health_label": live["health"]["label"],
        "rul_hours": live["rul"].get("hours"),
        "rul_method": live["rul"].get("method"),
        "rul_confidence": live["rul"].get("confidence"),
        "rul_r2": live["rul"].get("trend_r2"),
        "rul_unbounded": live["rul"].get("unbounded", False),
        "alarm_level": live["alarm"]["level"],
        "alarm_mode_name": live["alarm"]["mode_name"],
        "alarm_message": live["alarm"]["message"],
        "alarm_action": live["alarm"]["recommended_action"],
        "predicted_badge": live["alarm"].get("predicted"),
        "breached_badge": live["alarm"].get("has_breached"),
        "stress": live["physics"]["stress"],
        "dominant_mode": live["physics"]["dominant_mode"],
        "sensors": live["reading"],
        "ground_truth": live.get("ground_truth", {}),
    }


def _play_until(mid, predicate, timeout=300, poll=0.5):
    """
    Advance until predicate(live) holds, then FREEZE and re-read once.

    The re-read matters: the page renders the simulator's latest payload,
    so the recorded numbers must come from after the freeze, not from the
    poll that tripped the predicate.

    Note the race this creates. A replay step runs, then waits out its
    interval; a stop issued during that wait still lets the step in
    progress finish. If the interval is short the run can therefore
    advance one reading between the predicate matching and the freeze
    taking effect - which matters when the condition being hunted is not
    monotonic. `_hunt` below handles that by slowing the approach down.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        det, live, sim = _detail(mid)
        if live and predicate(live):
            break
        if not sim.get("running"):
            break
        time.sleep(poll)

    _post(f"/api/simulate/stop?machine_id={mid}")
    time.sleep(1.2)
    return _detail(mid)


def _hunt(mid, source, predicate, start_at, attempts=8,
          interval=1.6, poll=0.25, restart=False):
    """
    Land ON a reading that satisfies `predicate`, frozen.

    NEITHER condition this module hunts for is monotonic. Mechanical
    power fluctuates across its limit from one reading to the next, and
    the model's predicted class flickers between Normal and a failure
    class near the decision boundary. So it is not enough to detect the
    condition and stop - the very next reading may no longer satisfy it,
    and the screenshot would then contradict its own caption.

    Two things make this reliable. The approach runs SLOWLY, so a stop
    issued the moment the predicate matches lands before the next step
    begins. And if the frozen state still does not satisfy the predicate,
    it simply resumes and tries again.
    """
    pos = start_at
    det = live = sim = None
    for attempt in range(attempts):
        _post("/api/simulate/start", {
            "machine_id": mid, "source_machine": source,
            "interval": interval, "restart": restart and attempt == 0,
            "start_at": pos})
        det, live, sim = _play_until(mid, predicate, poll=poll)
        if live and predicate(live):
            return det, live, sim
        pos = sim.get("position") or pos
        if pos >= (sim.get("total") or 0) - 1:
            break
        print(f"      attempt {attempt + 1}: overshot the condition, resuming")
    return det, live, sim


def capture(page, shot, worst):
    """
    Produce 06_machine_predicted and 07_machine_breached.

    `shot(name, note)` is the caller's screenshot helper.
    Returns {"predicted": {...}, "breached": {...}}.
    """
    status = _get(f"/api/simulate/status?machine_id={worst}")
    source = status["source_machine"]
    fail_cycle = status["fails_at_cycle"] or status["total"]
    start_at = max(0, fail_cycle - RUNWAY)

    print(f"   {worst} replays {source}, which fails at cycle {fail_cycle}; "
          f"starting at {start_at}")

    # ---- (a) predicted, but nothing has actually gone yet -------------
    det, live, sim = _hunt(
        worst, source,
        lambda lv: (lv["prediction"]["class"] != "Normal"
                    and not lv["physics"]["has_hard_breach"]),
        start_at=start_at, restart=True)
    predicted = snapshot(det, "predicted", worst)
    print(f"   [predicted] reading {predicted.get('position')}/{predicted.get('total')} "
          f"pred={predicted.get('predicted_class')} health={predicted.get('health')} "
          f"PREDICTED={predicted.get('predicted_badge')} "
          f"BREACHED={predicted.get('breached_badge')}")

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(5000)
    shot("06_machine_predicted", "warned, machine still running")

    # ---- (b) a physical limit has actually been crossed ---------------
    det, live, sim = _hunt(
        worst, source,
        lambda lv: lv["physics"]["has_hard_breach"],
        start_at=predicted.get("position") or start_at)
    breached = snapshot(det, "breached", worst)
    print(f"   [breached ] reading {breached.get('position')}/{breached.get('total')} "
          f"pred={breached.get('predicted_class')} health={breached.get('health')} "
          f"PREDICTED={breached.get('predicted_badge')} "
          f"BREACHED={breached.get('breached_badge')}")

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(6000)
    shot("07_machine_breached", "a physical limit has been crossed")

    if not predicted.get("predicted_badge") or predicted.get("breached_badge"):
        print("   !! WARNING: the predicted shot is not a clean predicted-only state.")
    if not breached.get("breached_badge"):
        print("   !! WARNING: the breached shot does not actually show a breach.")

    return {"predicted": predicted, "breached": breached}
