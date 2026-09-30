"""
============================================================
 PHASE 1 - STEP 5 : RANDOM FOREST TRAINING
============================================================
ONE algorithm is used for the whole project: a Random Forest
classifier that maps a sensor reading to one of five states

        Normal | TWF | HDF | PWF | OSF

Why Random Forest
-----------------
  * handles the strong class imbalance via class_weight
  * needs no feature scaling (axis-aligned splits)
  * captures the AND-conditions in the failure physics natively
    (HDF = low dT AND low speed is exactly a two-level tree path)
  * exposes feature importances and per-tree vote distributions,
    which give us free explainability for the HMI - directly
    addressing the XAI gap identified in the literature review
  * fast enough to serve a prediction in ~1 ms

Methodology
-----------
  1. clean + engineer features                    (shared module)
  2. GROUP-AWARE stratified split                 (no leakage)
  3. randomised hyper-parameter search, 3-fold grouped CV
  4. refit best configuration on the full training set
  5. 5-fold grouped cross-validation of the final configuration
  6. persist a self-describing model bundle

Usage:  python -m src.models.train_model
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (
    RandomizedSearchCV,
    StratifiedGroupKFold,
    cross_validate,
)

from src.config import (
    ALGORITHM_NAME,
    BUNDLE_PATH,
    CV_FOLDS,
    EXPANDED_CSV,
    FAILURE_CLASSES,
    METRIC_DIR,
    MODEL_PATH,
    PREDICTION_HORIZON,
    RANDOM_STATE,
    TARGET_COLUMN,
    THRESHOLDS,
)
from src.features.build_features import (
    FEATURE_COLUMNS,
    FEATURE_LABELS,
    FEATURE_UNITS,
    build_groups,
    clean,
    engineer_features,
    to_matrix,
)

PARAM_DISTRIBUTION = {
    "n_estimators": [200, 300],
    "max_depth": [None, 14, 22],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf": [1, 2, 4],
    "max_features": ["sqrt", "log2"],
    "class_weight": ["balanced", "balanced_subsample"],
}
N_SEARCH_ITER = 12
SEARCH_FOLDS = 3
SCORING = "f1_macro"          # macro-F1: every failure mode counts equally

# ------------------------------------------------------------------
# SEARCH SUBSAMPLE
# ------------------------------------------------------------------
# 96% of the dataset is the Normal class, and those rows are highly
# redundant - a forest learns the Normal region from 18,000 examples
# just as well as from 58,000. Searching on the full set spends most
# of its time re-reading rows that carry no new information.
#
# So HYPER-PARAMETER SELECTION runs on a stratified subsample that
# keeps EVERY failure row and a fraction of the Normal rows. The
# chosen configuration is then refit on the FULL training set, and
# every number reported in the results comes from full-data training
# evaluated on the untouched, group-disjoint test split. Subsampling
# the search does not touch the reported metrics.
SEARCH_NORMAL_FRACTION = 0.30

# ------------------------------------------------------------------
# PARALLELISM
# ------------------------------------------------------------------
# Only the OUTER loop (the hyper-parameter search) is parallelised.
# Giving n_jobs=-1 to BOTH the search and the forest inside it makes
# each of the N worker processes spawn N threads of its own, so on a
# 4-core machine 16 threads fight over 4 cores and everything crawls.
# Outer parallel + inner serial is the correct configuration.
N_JOBS_SEARCH = -1
N_JOBS_ESTIMATOR = 1


# ==================================================================
def load_dataset() -> pd.DataFrame:
    if not EXPANDED_CSV.exists():
        raise FileNotFoundError(
            "{} missing. Run:  python -m src.data.expand_dataset".format(EXPANDED_CSV))
    df = pd.read_csv(EXPANDED_CSV, parse_dates=["timestamp"])
    return df


def search_subsample(y, seed=RANDOM_STATE):
    """
    Indices (into the training arrays) of every failure row plus a
    random fraction of the Normal rows. Used ONLY to choose
    hyper-parameters - see the note at the top of this file.
    """
    rng = np.random.default_rng(seed)
    is_normal = y == "Normal"
    normal_idx = np.flatnonzero(is_normal)
    keep_n = int(len(normal_idx) * SEARCH_NORMAL_FRACTION)
    keep = rng.choice(normal_idx, size=keep_n, replace=False)
    idx = np.concatenate([np.flatnonzero(~is_normal), keep])
    idx.sort()
    return idx


def grouped_holdout(y, groups, test_fraction=0.2, seed=RANDOM_STATE):
    """
    Take one fold of a StratifiedGroupKFold as the held-out test set.
    Stratified  -> every failure mode is represented on both sides.
    Grouped     -> no simulated machine spans the split.
    """
    n_splits = int(round(1.0 / test_fraction))
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    train_idx, test_idx = next(sgkf.split(np.zeros(len(y)), y, groups))
    return train_idx, test_idx


# ==================================================================
def main() -> int:
    t_start = time.time()
    print("\n" + "=" * 68)
    print(" PHASE 1 | STEP 5 : TRAINING THE RANDOM FOREST")
    print("=" * 68)

    # ---------------- 1. data ----------------
    df = load_dataset()
    print("  Loaded {:,} rows from {}\n".format(len(df), EXPANDED_CSV.name))

    df = clean(df)
    df = engineer_features(df)

    X = to_matrix(df)
    y = df[TARGET_COLUMN].to_numpy()
    groups = build_groups(df)

    print("\n  Training target : {}".format(TARGET_COLUMN))
    if TARGET_COLUMN == "label_horizon":
        print("    the failure class extended back over the {}-reading onset".format(
            PREDICTION_HORIZON))
        print("    window, so the model learns the APPROACH to a limit rather")
        print("    than the limit itself -> genuinely predictive, not reactive")

    print("\n  Feature matrix : {:,} rows x {} features".format(*X.shape))
    print("  Features       : {}".format(", ".join(FEATURE_COLUMNS)))
    print("  Unique groups  : {:,}  (real rows are singleton groups)".format(
        len(np.unique(groups))))

    # ---------------- 2. split ----------------
    train_idx, test_idx = grouped_holdout(y, groups)
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    g_train = groups[train_idx]

    overlap = set(np.unique(groups[train_idx])) & set(np.unique(groups[test_idx]))
    assert not overlap, "GROUP LEAKAGE: {} groups span the split".format(len(overlap))

    print("\n  " + "-" * 62)
    print("  Train : {:,} rows   ({} groups)".format(len(X_train), len(np.unique(g_train))))
    print("  Test  : {:,} rows   ({} groups)".format(
        len(X_test), len(np.unique(groups[test_idx]))))
    print("  Group overlap between train and test : {}  [verified]".format(len(overlap)))
    print("  " + "-" * 62)

    print("\n  Class balance:")
    print("    {:<8} {:>10} {:>10}".format("class", "train", "test"))
    for c in FAILURE_CLASSES:
        print("    {:<8} {:>10,} {:>10,}".format(
            c, int((y_train == c).sum()), int((y_test == c).sum())))

    # ---------------- 3. hyper-parameter search ----------------
    sub = search_subsample(y_train)
    X_sub, y_sub, g_sub = X_train.iloc[sub], y_train[sub], g_train[sub]

    print("\n  Randomised hyper-parameter search")
    print("    candidates : {}   folds : {}   scoring : {}".format(
        N_SEARCH_ITER, SEARCH_FOLDS, SCORING))
    print("    search set : {:,} rows  (all {:,} failure rows + {:.0f}% of Normal)".format(
        len(sub), int((y_train != "Normal").sum()), SEARCH_NORMAL_FRACTION * 100))
    print("    (grouped + stratified CV, so no machine leaks between folds)")

    search_cv = StratifiedGroupKFold(n_splits=SEARCH_FOLDS, shuffle=True,
                                     random_state=RANDOM_STATE)
    search = RandomizedSearchCV(
        estimator=RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=N_JOBS_ESTIMATOR),
        param_distributions=PARAM_DISTRIBUTION,
        n_iter=N_SEARCH_ITER,
        scoring=SCORING,
        cv=search_cv,
        random_state=RANDOM_STATE,
        n_jobs=N_JOBS_SEARCH,
        verbose=1,
        refit=False,               # we refit ourselves, on the FULL training set
    )
    t0 = time.time()
    search.fit(X_sub, y_sub, groups=g_sub)
    search_secs = time.time() - t0

    print("\n    search time    : {:.1f} s".format(search_secs))
    print("    best CV {:<7}: {:.4f}  (on the search subsample)".format(
        SCORING, search.best_score_))
    print("    best parameters:")
    for k, v in sorted(search.best_params_.items()):
        print("       {:<20} {}".format(k, v))

    # ---- refit the chosen configuration on the FULL training set ----
    print("\n  Refitting the chosen configuration on all {:,} training rows ...".format(
        len(X_train)))
    t0 = time.time()
    model = RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1,
                                   **search.best_params_)
    model.fit(X_train, y_train)
    print("    refit time     : {:.1f} s".format(time.time() - t0))

    # ---------------- 4. cross-validate the final configuration ----------------
    print("\n  {}-fold grouped cross-validation of the chosen configuration ...".format(CV_FOLDS))
    cv = StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_res = cross_validate(
        RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=N_JOBS_ESTIMATOR,
                               **search.best_params_),
        X_train, y_train, groups=g_train, cv=cv,
        scoring=["accuracy", "f1_macro", "precision_macro", "recall_macro"],
        n_jobs=N_JOBS_SEARCH,
    )
    cv_summary = {}
    print("\n    {:<18} {:>10} {:>10}".format("metric", "mean", "std"))
    for key in ("accuracy", "f1_macro", "precision_macro", "recall_macro"):
        vals = cv_res["test_" + key]
        cv_summary[key] = {"mean": float(vals.mean()), "std": float(vals.std()),
                           "folds": [float(v) for v in vals]}
        print("    {:<18} {:>10.4f} {:>10.4f}".format(key, vals.mean(), vals.std()))

    # ---------------- 5. feature importance ----------------
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda kv: kv[1], reverse=True,
    )
    print("\n  Feature importance (Gini):")
    for name, imp in importances:
        bar = "#" * int(round(imp * 60))
        print("    {:<22} {:.4f}  {}".format(name, imp, bar))

    # ---------------- 6. persist ----------------
    bundle = {
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "feature_labels": FEATURE_LABELS,
        "feature_units": FEATURE_UNITS,
        "classes": list(model.classes_),
        "thresholds": THRESHOLDS,
        "metadata": {
            "algorithm": ALGORITHM_NAME,
            "sklearn_version": __import__("sklearn").__version__,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "random_state": RANDOM_STATE,
            "n_train_rows": int(len(X_train)),
            "n_test_rows": int(len(X_test)),
            "n_features": len(FEATURE_COLUMNS),
            "best_params": search.best_params_,
            "search_scoring": SCORING,
            "search_best_cv_score": float(search.best_score_),
            "split": "StratifiedGroupKFold holdout (group = simulated machine)",
            "target_column": TARGET_COLUMN,
        },
    }
    joblib.dump(bundle, BUNDLE_PATH, compress=3)
    joblib.dump(model, MODEL_PATH, compress=3)

    # the test split must be reproducible for the evaluation step
    np.savez_compressed(METRIC_DIR / "split_indices.npz",
                        train_idx=train_idx, test_idx=test_idx)

    (METRIC_DIR / "training_summary.json").write_text(json.dumps({
        "algorithm": ALGORITHM_NAME,
        "features": FEATURE_COLUMNS,
        "best_params": search.best_params_,
        "search": {"n_iter": N_SEARCH_ITER, "folds": SEARCH_FOLDS,
                   "scoring": SCORING, "best_score": float(search.best_score_),
                   "seconds": round(search_secs, 1)},
        "cross_validation": cv_summary,
        "feature_importance": {k: float(v) for k, v in importances},
        "rows": {"total": int(len(X)), "train": int(len(X_train)), "test": int(len(X_test))},
        "group_overlap": len(overlap),
    }, indent=2), encoding="utf-8")

    print("\n  " + "-" * 62)
    print("  Model bundle -> {}  ({:.1f} MB)".format(
        BUNDLE_PATH.name, BUNDLE_PATH.stat().st_size / 1e6))
    print("  Summary      -> {}".format((METRIC_DIR / 'training_summary.json').name))
    print("  Total time   : {:.1f} s".format(time.time() - t_start))
    print("  " + "-" * 62)
    print("\n  Next:  python -m src.evaluation.evaluate")
    print("=" * 68 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
