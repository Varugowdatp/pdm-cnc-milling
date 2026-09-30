"""
============================================================
 PREDICTION EXPLAINER  (Saabas decision-path attribution)
============================================================
Answers the question an operator actually asks when a panel lights
up: **"why does it think that?"**

WHY NOT FEATURE IMPORTANCE
--------------------------
`model.feature_importances_` is a GLOBAL property of the forest. It
says tool wear mattered a lot across 60,000 training rows. It says
nothing whatever about THIS machine at THIS moment, and showing it on
a per-reading panel is quietly dishonest: the bars never move, no
matter what the machine does.

WHY NOT SHAP / LIME
-------------------
Both would work, but both are approximations that cost an extra
dependency and (for KernelSHAP) hundreds of model evaluations per
reading - unacceptable for a live SSE stream. For a tree ensemble
there is an exact method that costs one tree traversal.

THE METHOD (Saabas, 2014)
-------------------------
Any decision tree's prediction can be decomposed EXACTLY:

    prediction = value_at_root + SUM over the path of
                 (value_at_child - value_at_parent)

Each step down the path is caused by exactly one feature - the one
tested at that node - so the change in predicted class probability
across that step is that feature's contribution for this sample. Sum
the contributions over the 300 trees and you have an exact additive
attribution:

    P(class) = base_rate(class) + SUM_over_features contribution_f

This is a local, per-reading, exactly-additive explanation obtained
from the tree structure itself. It is the tree-specific special case
that TreeSHAP generalises, it needs no sampling, and it reproduces the
model exactly - `verify_additivity()` asserts that in the tests.

The reconstruction is exact to floating-point tolerance, so the panel
can honestly say "these numbers ARE the prediction", not "these
numbers approximate the prediction".
"""

from __future__ import annotations

import numpy as np

from src.features.build_features import FEATURE_COLUMNS, FEATURE_LABELS, FEATURE_UNITS


# ==================================================================
#  CORE: one tree
# ==================================================================
def _tree_contributions(tree, x_row: np.ndarray, n_classes: int) -> tuple:
    """
    Walk one tree's decision path for one sample.

    Returns (contributions[n_features, n_classes], bias[n_classes]).
    """
    t = tree.tree_
    feature = t.feature
    threshold = t.threshold
    children_left = t.children_left
    children_right = t.children_right

    # Node value -> class distribution. sklearn stores counts (weighted),
    # so normalise each node to a probability vector.
    values = t.value.reshape(t.node_count, -1)
    totals = values.sum(axis=1, keepdims=True)
    totals[totals == 0.0] = 1.0
    probs = values / totals

    contributions = np.zeros((len(FEATURE_COLUMNS), n_classes), dtype=np.float64)
    bias = probs[0].copy()

    node = 0
    while children_left[node] != -1:          # -1 == leaf
        f = feature[node]
        nxt = (children_left[node]
               if x_row[f] <= threshold[node]
               else children_right[node])
        # the whole change caused by taking this branch is attributed
        # to the feature that was tested here
        contributions[f] += probs[nxt] - probs[node]
        node = nxt

    return contributions, bias


# ==================================================================
#  FOREST
# ==================================================================
def explain(model, x_row, class_names=None) -> dict:
    """
    Exact additive attribution for ONE sample.

    `x_row` is the engineered feature vector in FEATURE_COLUMNS order.
    Returns per-class contributions plus the reconstructed probability.
    """
    # MUST match sklearn's internal precision. The tree code casts X to
    # float32 (`sklearn.tree._tree.DTYPE`) before traversing, so a
    # comparison done in float64 can take the OTHER branch at a node
    # whose threshold sits within float32 rounding distance of the
    # value. That is not hypothetical: temp_delta = 9.620000000000005
    # reconstructed HDF as 0.0374 against the model's true 0.0344.
    # Round-tripping through float32 reproduces the model exactly.
    x = np.asarray(x_row, dtype=np.float32).astype(np.float64).ravel()
    classes = list(class_names if class_names is not None else model.classes_)
    n_classes = len(classes)
    n_trees = len(model.estimators_)

    total_contrib = np.zeros((len(FEATURE_COLUMNS), n_classes), dtype=np.float64)
    total_bias = np.zeros(n_classes, dtype=np.float64)

    for est in model.estimators_:
        c, b = _tree_contributions(est, x, n_classes)
        total_contrib += c
        total_bias += b

    # The forest averages its trees, so the attribution averages too
    total_contrib /= n_trees
    total_bias /= n_trees

    return {
        "classes": classes,
        "bias": total_bias,                 # [n_classes]
        "contributions": total_contrib,     # [n_features, n_classes]
        "reconstructed": total_bias + total_contrib.sum(axis=0),
    }


# ==================================================================
#  PRESENTATION
# ==================================================================
def explain_for_class(model, x_row, target_class, raw_values=None,
                      class_names=None, top_n: int = 6) -> dict:
    """
    The HMI-ready explanation of why `target_class` was predicted.

    `raw_values` is the engineered feature dict for this reading, so
    each bar can show the value that actually drove it.
    """
    res = explain(model, x_row, class_names)
    classes = res["classes"]

    if target_class not in classes:
        target_class = classes[int(np.argmax(res["reconstructed"]))]
    ci = classes.index(target_class)

    contrib = res["contributions"][:, ci]
    raw_values = raw_values or {}

    drivers = []
    for i, name in enumerate(FEATURE_COLUMNS):
        val = raw_values.get(name)
        drivers.append({
            "feature": name,
            "label": FEATURE_LABELS.get(name, name),
            "unit": FEATURE_UNITS.get(name, ""),
            "value": None if val is None else round(float(val), 3),
            "contribution": round(float(contrib[i]), 5),
            "direction": "increases" if contrib[i] > 0 else "decreases",
        })

    # Rank by magnitude - the strongest evidence either way
    drivers.sort(key=lambda d: abs(d["contribution"]), reverse=True)
    top = [d for d in drivers if abs(d["contribution"]) > 1e-6][:top_n]

    base = float(res["bias"][ci])
    final = float(res["reconstructed"][ci])

    return {
        "target_class": target_class,
        "base_rate": round(base, 5),
        "predicted_probability": round(final, 5),
        "total_contribution": round(final - base, 5),
        "top_drivers": top,
        "all_drivers": drivers,
        "narrative": _narrative(target_class, top, base, final),
        "method": "Saabas decision-path attribution (exact for tree ensembles)",
    }


def _narrative(target_class, top, base, final) -> str:
    """One plain-English sentence a technician can read at a glance."""
    if not top:
        return ("No single sensor stands out - the prediction reflects the "
                "model's baseline expectation for this machine variant.")

    pushing = [d for d in top if d["contribution"] > 0][:3]
    if not pushing:
        return ("Every measured quantity is pushing this reading AWAY from "
                "{}; the machine looks healthy on all fronts.".format(target_class))

    parts = []
    for d in pushing:
        if d["value"] is None:
            parts.append(d["label"])
        else:
            unit = (" " + d["unit"]) if d["unit"] else ""
            parts.append("{} at {:g}{}".format(d["label"], d["value"], unit))

    lead = parts[0]
    rest = parts[1:]
    joined = lead if not rest else "{} and {}".format(", ".join([lead] + rest[:-1]), rest[-1])

    verdict = "Normal operation" if target_class == "Normal" else target_class

    return ("{} raised the likelihood of {} from a baseline {:.0f}% to {:.0f}%."
            .format(joined, verdict, base * 100.0, final * 100.0))


# ==================================================================
#  SELF-CHECK
# ==================================================================
def verify_additivity(model, X, tol: float = 1e-6) -> dict:
    """
    Prove the attribution reconstructs the model exactly.

    If this ever fails, the explanation panel is lying and should not
    be shown - so the API exposes it and the test suite asserts it.
    """
    import pandas as pd

    values = X.to_numpy() if hasattr(X, "to_numpy") else np.asarray(X, dtype=np.float64)
    values = np.atleast_2d(values)
    # Feed a named frame so sklearn does not warn about missing feature names
    proba = model.predict_proba(pd.DataFrame(values, columns=FEATURE_COLUMNS))
    X = values

    worst = 0.0
    for i in range(len(X)):
        rec = explain(model, X[i])["reconstructed"]
        worst = max(worst, float(np.max(np.abs(rec - proba[i]))))

    return {
        "samples": int(len(X)),
        "max_absolute_error": worst,
        "exact": bool(worst < tol),
        "tolerance": tol,
    }
