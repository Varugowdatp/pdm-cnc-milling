"""
============================================================
 PHASE 1 - STEP 6 : MODEL EVALUATION
============================================================
Evaluates the trained Random Forest on the held-out, group-disjoint
test split and produces every figure and number quoted in the report.

  09  confusion matrix (counts + row-normalised)
  10  ROC curves, one-vs-rest, with AUC per failure mode
  11  precision-recall curves (the honest view under imbalance)
  12  feature importance: Gini vs permutation
  13  learning curve - is more data still helping?
  14  EARLY-WARNING LEAD TIME - how many readings before the fault
      formally trips does the model first flag it?  This is the
      number that decides whether the system is genuinely PREDICTIVE
      rather than merely reactive.

Usage:  python -m src.evaluation.evaluate
"""

from __future__ import annotations

import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    auc,
    balanced_accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    matthews_corrcoef,
    precision_recall_curve,
    roc_curve,
)
from sklearn.model_selection import learning_curve

from src.config import (
    BUNDLE_PATH,
    CV_FOLDS,
    EXPANDED_CSV,
    FAILURE_CLASSES,
    METRIC_DIR,
    METRICS_PATH,
    RANDOM_STATE,
    TARGET_COLUMN,
    THEME,
)
from src.features.build_features import (
    FEATURE_COLUMNS,
    build_groups,
    clean,
    engineer_features,
    to_matrix,
)
from src.plot_style import CLASS_COLORS, save, use_industrial_style

import matplotlib.pyplot as plt

SUBDIR = "evaluation"


# ==================================================================
def load_everything():
    bundle = joblib.load(BUNDLE_PATH)
    df = pd.read_csv(EXPANDED_CSV, parse_dates=["timestamp"])
    df = engineer_features(clean(df, verbose=False))

    split = np.load(METRIC_DIR / "split_indices.npz")
    train_idx, test_idx = split["train_idx"], split["test_idx"]

    X = to_matrix(df)
    y = df[TARGET_COLUMN].to_numpy()
    return bundle, df, X, y, train_idx, test_idx


def present(classes, y_true):
    return [c for c in FAILURE_CLASSES if c in classes]


# ==================================================================
# 09 - confusion matrix
# ==================================================================
def plot_confusion(y_true, y_pred, labels):
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cmn = cm.astype(float) / np.clip(cm.sum(axis=1, keepdims=True), 1, None)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8))
    for ax, mat, title, fmt in (
        (axes[0], cm, "Counts", "{:,.0f}"),
        (axes[1], cmn * 100, "Row-normalised  (% of true class)", "{:.1f}"),
    ):
        im = ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels); ax.set_yticklabels(labels)
        ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
        ax.set_title(title)
        ax.grid(False)
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, fmt.format(mat[i, j]), ha="center", va="center",
                        fontsize=10, fontweight="bold",
                        color="white" if cmn[i, j] > 0.5 else THEME["text"])
    fig.colorbar(im, ax=axes, shrink=0.8, label="fraction of true class")
    fig.suptitle("09 | Confusion matrix on the held-out test set",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    return save(fig, "09_confusion_matrix", SUBDIR)


# ==================================================================
# 10 / 11 - ROC and precision-recall, one-vs-rest
# ==================================================================
def plot_roc_pr(y_true, proba, classes):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    aucs, aps = {}, {}

    for i, cls in enumerate(classes):
        binary = (y_true == cls).astype(int)
        if binary.sum() == 0:
            continue
        color = CLASS_COLORS.get(cls, THEME["accent"])

        fpr, tpr, _ = roc_curve(binary, proba[:, i])
        a = auc(fpr, tpr); aucs[cls] = float(a)
        axes[0].plot(fpr, tpr, color=color, lw=2,
                     label="{}  AUC={:.4f}".format(cls, a))

        prec, rec, _ = precision_recall_curve(binary, proba[:, i])
        ap = auc(rec, prec); aps[cls] = float(ap)
        axes[1].plot(rec, prec, color=color, lw=2,
                     label="{}  AUC={:.4f}".format(cls, ap))

    axes[0].plot([0, 1], [0, 1], ls="--", color=THEME["muted"], lw=1.2)
    axes[0].set_xlabel("False positive rate"); axes[0].set_ylabel("True positive rate")
    axes[0].set_title("ROC - one-vs-rest"); axes[0].legend(loc="lower right")

    axes[1].set_xlabel("Recall"); axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision-Recall - the honest view under 138:1 imbalance")
    axes[1].legend(loc="lower left")

    fig.suptitle("10 | Discrimination performance per failure mode",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    save(fig, "10_roc_and_pr_curves", SUBDIR)
    return aucs, aps


# ==================================================================
# 12 - feature importance
# ==================================================================
def plot_importance(model, X_test, y_test):
    gini = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS)

    # permutation importance is measured on UNSEEN data and is not biased
    # towards high-cardinality features the way Gini importance is
    perm = permutation_importance(
        model, X_test, y_test, n_repeats=5,
        random_state=RANDOM_STATE, n_jobs=-1, scoring="f1_macro",
    )
    perm_mean = pd.Series(perm.importances_mean, index=FEATURE_COLUMNS)

    order = gini.sort_values(ascending=True).index
    ypos = np.arange(len(order))

    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.6))
    axes[0].barh(ypos, gini[order].values, color=THEME["accent"])
    axes[0].set_yticks(ypos); axes[0].set_yticklabels(order)
    axes[0].set_xlabel("Gini importance (training)")
    axes[0].set_title("Impurity-based importance")
    for i, v in enumerate(gini[order].values):
        axes[0].text(v + 0.004, i, "{:.3f}".format(v), va="center", fontsize=8.5)

    axes[1].barh(ypos, perm_mean[order].values,
                 xerr=perm.importances_std[[FEATURE_COLUMNS.index(c) for c in order]],
                 color=THEME["ok"], ecolor=THEME["muted"], capsize=3)
    axes[1].set_yticks(ypos); axes[1].set_yticklabels(order)
    axes[1].set_xlabel("Drop in macro-F1 when shuffled (test set)")
    axes[1].set_title("Permutation importance - unbiased, on unseen data")

    fig.suptitle("12 | Which sensors actually drive the prediction",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    save(fig, "12_feature_importance", SUBDIR)

    return ({k: float(v) for k, v in gini.items()},
            {k: float(v) for k, v in perm_mean.items()})


# ==================================================================
# 13 - learning curve
# ==================================================================
def plot_learning_curve(model, X_train, y_train, g_train):
    from sklearn.model_selection import StratifiedGroupKFold

    print("    computing learning curve (this takes a moment) ...")
    sizes, train_scores, val_scores = learning_curve(
        model, X_train, y_train, groups=g_train,
        cv=StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE),
        train_sizes=np.linspace(0.15, 1.0, 6),
        scoring="f1_macro", n_jobs=-1, random_state=RANDOM_STATE,
    )

    fig, ax = plt.subplots(figsize=(9, 5.2))
    for scores, color, label in (
        (train_scores, THEME["accent"], "Training score"),
        (val_scores, THEME["ok"], "Cross-validation score"),
    ):
        mean, std = scores.mean(axis=1), scores.std(axis=1)
        ax.plot(sizes, mean, "o-", color=color, lw=2, label=label)
        ax.fill_between(sizes, mean - std, mean + std, color=color, alpha=0.18)

    ax.set_xlabel("training rows used")
    ax.set_ylabel("macro F1")
    ax.set_title("13 | Learning curve - is more data still helping?",
                 color=THEME["accent"])
    ax.legend(loc="lower right")
    save(fig, "13_learning_curve", SUBDIR)

    return {"train_sizes": [int(s) for s in sizes],
            "train_f1": [float(v) for v in train_scores.mean(axis=1)],
            "cv_f1": [float(v) for v in val_scores.mean(axis=1)]}


# ==================================================================
# 14 - EARLY WARNING LEAD TIME
# ==================================================================
def early_warning(model, df, test_idx, X):
    """
    For every simulated machine in the test split, find the first reading
    at which the model raises a non-Normal prediction, and compare it to
    the reading at which the fault physically trips.

    lead time > 0  ->  the system warned BEFORE the failure condition
                       was met: genuinely predictive maintenance.
    """
    test = df.iloc[test_idx]
    synth = test[test["source"] == "SYNTH-RUN2FAIL"]
    if synth.empty:
        return {}

    proba = model.predict_proba(X.iloc[test_idx])
    classes = list(model.classes_)
    normal_i = classes.index("Normal")
    p_fail = 1.0 - proba[:, normal_i]

    tmp = synth.copy()
    tmp["p_fail"] = p_fail[test["source"].to_numpy() == "SYNTH-RUN2FAIL"]

    leads, records = [], []
    for mid, m in tmp.groupby("machine_id"):
        m = m.sort_values("cycle")
        faulted = m[m["machine_failure"] == 1]
        if faulted.empty:
            continue
        fail_cycle = int(faulted["cycle"].iloc[0])

        # first sustained alarm: p_fail above 0.5 for 3 consecutive readings
        flag = (m["p_fail"] > 0.5).to_numpy()
        sustained = flag & np.roll(flag, -1) & np.roll(flag, -2)
        sustained[-2:] = flag[-2:]
        if not sustained.any():
            continue
        first_cycle = int(m["cycle"].to_numpy()[np.argmax(sustained)])

        lead = fail_cycle - first_cycle
        leads.append(lead)
        records.append({"machine_id": mid, "mode": m["degradation_mode"].iloc[0],
                        "fail_cycle": fail_cycle, "first_alarm_cycle": first_cycle,
                        "lead_readings": lead})

    if not leads:
        return {}

    leads = np.array(leads)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(leads, bins=28, color=THEME["accent"], edgecolor=THEME["bg"])
    axes[0].axvline(0, color=THEME["crit"], ls="--", lw=2, label="failure moment")
    axes[0].axvline(leads.mean(), color=THEME["ok"], ls="-", lw=2,
                    label="mean lead {:.1f} readings".format(leads.mean()))
    axes[0].set_xlabel("lead time [readings before the fault trips]")
    axes[0].set_ylabel("machines")
    axes[0].set_title("Early-warning lead time ({} test machines)".format(len(leads)))
    axes[0].legend()

    rec = pd.DataFrame(records)
    rec["mode_base"] = rec["mode"].str.split(":").str[0]
    modes = sorted(rec["mode_base"].unique())
    data = [rec.loc[rec["mode_base"] == md, "lead_readings"].values for md in modes]
    bp = axes[1].boxplot(data, patch_artist=True, tick_labels=modes)
    for patch, md in zip(bp["boxes"], modes):
        patch.set_facecolor(CLASS_COLORS.get(md, THEME["accent"])); patch.set_alpha(0.85)
    for part in ("whiskers", "caps", "fliers"):
        for ln in bp[part]:
            ln.set_color(THEME["muted"])
    axes[1].axhline(0, color=THEME["crit"], ls="--", lw=1.6)
    axes[1].set_ylabel("lead time [readings]")
    axes[1].set_title("Lead time per degradation mechanism")

    fig.suptitle("14 | How far in ADVANCE does the system warn?",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    save(fig, "14_early_warning_lead_time", SUBDIR)

    minutes = float(leads.mean()) * 10.0
    return {
        "machines_evaluated": int(len(leads)),
        "mean_lead_readings": round(float(leads.mean()), 2),
        "median_lead_readings": round(float(np.median(leads)), 2),
        "mean_lead_minutes": round(minutes, 1),
        "mean_lead_hours": round(minutes / 60.0, 2),
        "warned_before_failure_pct": round(float((leads > 0).mean() * 100), 1),
        "per_mode": {md: round(float(np.mean(
            rec.loc[rec["mode_base"] == md, "lead_readings"])), 2) for md in modes},
    }


# ==================================================================
def main() -> int:
    print("\n" + "=" * 68)
    print(" PHASE 1 | STEP 6 : MODEL EVALUATION")
    print("=" * 68)

    if not BUNDLE_PATH.exists():
        print("ERROR: no trained model. Run:  python -m src.models.train_model")
        return 1

    use_industrial_style()
    bundle, df, X, y, train_idx, test_idx = load_everything()
    model = bundle["model"]
    classes = list(model.classes_)

    X_test, y_test = X.iloc[test_idx], y[test_idx]
    X_train, y_train = X.iloc[train_idx], y[train_idx]
    g_train = build_groups(df)[train_idx]

    print("  Model    : {}".format(bundle["metadata"]["algorithm"]))
    print("  Trained  : {}".format(bundle["metadata"]["trained_at"]))
    print("  Test set : {:,} rows (group-disjoint from training)\n".format(len(X_test)))

    y_pred = model.predict(X_test)
    proba = model.predict_proba(X_test)

    # ---------------- headline metrics ----------------
    acc = accuracy_score(y_test, y_pred)
    bal = balanced_accuracy_score(y_test, y_pred)
    mcc = matthews_corrcoef(y_test, y_pred)
    kappa = cohen_kappa_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    print("  " + "-" * 62)
    print("  Accuracy            : {:.4f}".format(acc))
    print("  Balanced accuracy   : {:.4f}".format(bal))
    print("  Macro F1            : {:.4f}".format(report["macro avg"]["f1-score"]))
    print("  Weighted F1         : {:.4f}".format(report["weighted avg"]["f1-score"]))
    print("  Matthews corr coef  : {:.4f}".format(mcc))
    print("  Cohen's kappa       : {:.4f}".format(kappa))
    print("  " + "-" * 62)

    print("\n  Per-class performance:")
    print("    {:<8} {:>10} {:>10} {:>10} {:>9}".format(
        "class", "precision", "recall", "f1", "support"))
    labels = present(classes, y_test)
    for c in labels:
        r = report.get(c, {})
        print("    {:<8} {:>10.4f} {:>10.4f} {:>10.4f} {:>9,}".format(
            c, r.get("precision", 0), r.get("recall", 0),
            r.get("f1-score", 0), int(r.get("support", 0))))

    # ---------------- figures ----------------
    print("\n  Generating evaluation figures ...")
    plot_confusion(y_test, y_pred, labels)
    aucs, aps = plot_roc_pr(y_test, proba, classes)
    gini, perm = plot_importance(model, X_test, y_test)
    lc = plot_learning_curve(
        type(model)(random_state=RANDOM_STATE, n_jobs=-1,
                    **bundle["metadata"]["best_params"]),
        X_train, y_train, g_train)

    print("\n  Early-warning lead-time analysis ...")
    ew = early_warning(model, df, test_idx, X)
    if ew:
        print("    machines analysed        : {}".format(ew["machines_evaluated"]))
        print("    mean lead time           : {:.1f} readings "
              "= {:.2f} operating hours".format(ew["mean_lead_readings"], ew["mean_lead_hours"]))
        print("    warned BEFORE failure    : {} % of machines".format(
            ew["warned_before_failure_pct"]))
        for md, v in ew["per_mode"].items():
            print("      {:<5} {:>7.1f} readings".format(md, v))

    # ---------------- persist ----------------
    metrics = {
        "algorithm": bundle["metadata"]["algorithm"],
        "trained_at": bundle["metadata"]["trained_at"],
        "best_params": bundle["metadata"]["best_params"],
        "test_rows": int(len(X_test)),
        "headline": {
            "accuracy": float(acc),
            "balanced_accuracy": float(bal),
            "macro_f1": float(report["macro avg"]["f1-score"]),
            "weighted_f1": float(report["weighted avg"]["f1-score"]),
            "macro_precision": float(report["macro avg"]["precision"]),
            "macro_recall": float(report["macro avg"]["recall"]),
            "mcc": float(mcc),
            "cohen_kappa": float(kappa),
        },
        "per_class": {c: report[c] for c in labels if c in report},
        "roc_auc": aucs,
        "pr_auc": aps,
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        },
        "feature_importance_gini": gini,
        "feature_importance_permutation": perm,
        "learning_curve": lc,
        "early_warning": ew,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\n  Metrics saved -> {}".format(METRICS_PATH))
    print("=" * 68 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
