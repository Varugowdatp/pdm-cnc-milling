"""Are the model's 'false positives' actually pre-horizon early warnings?

For every test row the model predicts as a failure class while the horizon
label says Normal, measure how far that row sits from its machine's actual
failure event.  If those rows cluster just outside the 15-reading horizon
window, they are early warnings, not errors.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from src.config import METRIC_DIR, FAILURE_CLASSES, PREDICTION_HORIZON
from src.evaluation.evaluate import load_everything

bundle, df, X, y, train_idx, test_idx = load_everything()
model = bundle["model"] if isinstance(bundle, dict) else bundle

Xte = X.iloc[test_idx]
yte = y[test_idx]
pred = model.predict(Xte)

test = df.iloc[test_idx].copy()
test["y_true"] = yte
test["y_pred"] = pred

# ---- locate each machine's failure event (first row whose true physics
#      state, failure_class, is a failure) --------------------------------
fail_rows = df[df["failure_class"] != "Normal"]
first_fail = fail_rows.groupby("machine_id")["cycle"].min()

test["fail_cycle"] = test["machine_id"].map(first_fail)
test["dist_to_fail"] = test["fail_cycle"] - test["cycle"]   # >0 = before failure

fp = test[(test["y_true"] == "Normal") & (test["y_pred"] != "Normal")]
tn = test[(test["y_true"] == "Normal") & (test["y_pred"] == "Normal")]

print(f"test rows                 : {len(test):,}")
print(f"true-Normal rows          : {(test.y_true=='Normal').sum():,}")
print(f"flagged while label Normal: {len(fp):,}")
print()

on_failing = fp[fp["fail_cycle"].notna()]
on_healthy = fp[fp["fail_cycle"].isna()]
print(f"  ... on machines that DO eventually fail : {len(on_failing):,}"
      f"  ({100*len(on_failing)/max(len(fp),1):.1f}%)")
print(f"  ... on machines that never fail         : {len(on_healthy):,}"
      f"  ({100*len(on_healthy)/max(len(fp),1):.1f}%)")
print()

before = on_failing[on_failing["dist_to_fail"] > 0]
print(f"flagged BEFORE the failure event        : {len(before):,}")
if len(before):
    d = before["dist_to_fail"]
    print(f"   readings ahead of failure  median {d.median():.0f}"
          f"   mean {d.mean():.1f}   p90 {d.quantile(0.90):.0f}")
    for lim in (30, 60, 120):
        print(f"   within {lim:3d} readings of failure: "
              f"{100*(d <= lim).mean():.1f}%")

# how many true-Normal machines are failing machines at all?
print()
share = 100 * len(on_failing) / max(len(fp), 1)
out = {
    "horizon_readings": PREDICTION_HORIZON,
    "flagged_while_label_normal": int(len(fp)),
    "on_failing_machines": int(len(on_failing)),
    "on_failing_machines_pct": round(share, 1),
    "before_failure": int(len(before)),
    "median_readings_ahead": float(before["dist_to_fail"].median()) if len(before) else None,
    "mean_readings_ahead": float(before["dist_to_fail"].mean()) if len(before) else None,
}
(METRIC_DIR / "false_positive_analysis.json").write_text(json.dumps(out, indent=2))
print("saved -> artifacts/metrics/false_positive_analysis.json")

# ---- operational view -------------------------------------------------
flagged = test[test["y_pred"] != "Normal"]
tp = test[(test["y_true"] != "Normal") & (test["y_pred"] != "Normal")]
useful = len(tp) + len(before)
print()
print("OPERATIONAL VIEW")
print(f"  rows flagged (any failure class)   : {len(flagged):,}")
print(f"  in-horizon hits (classic TP)       : {len(tp):,}")
print(f"  pre-horizon early warnings         : {len(before):,}")
print(f"  operationally useful flags         : {useful:,}"
      f"  ({100*useful/len(flagged):.1f}% of all flags)")
nuis = len(on_healthy)
healthy_rows = int((test['fail_cycle'].isna()).sum())
print(f"  nuisance flags (never-fail machine): {nuis:,}"
      f"  = {100*nuis/max(healthy_rows,1):.2f}% of the {healthy_rows:,} healthy-machine rows")
late = len(on_failing) - len(before)
print(f"  post-failure flags (still faulted) : {late:,}")
