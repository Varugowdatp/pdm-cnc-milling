"""
============================================================
 PHASE 1 - STEP 3 : EXPLORATORY DATA ANALYSIS
============================================================
Produces the figures and the statistics table that justify every
modelling decision taken later in the pipeline:

  01  class distribution + imbalance          -> why class_weight="balanced"
  02  sensor distributions by failure class   -> which sensors separate classes
  03  correlation heatmap                     -> torque/speed collinearity
  04  physics separation plots (4 modes)      -> why engineered features work
  05  failure rate by machine variant         -> why Type is a feature
  06  a real run-to-failure trajectory        -> what the HMI will display
  07  RUL distribution                        -> the prediction target range
  08  sensor boxplots by class                -> outlier / spread check

Everything is written to artifacts/plots/eda/ and
artifacts/metrics/eda_summary.json

Usage:  python -m src.data.eda
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from src.config import EXPANDED_CSV, FAILURE_CLASSES, METRIC_DIR, SENSORS, THEME, THRESHOLDS
from src.plot_style import CLASS_COLORS, save, use_industrial_style

import matplotlib.pyplot as plt

SUBDIR = "eda"
SENSOR_COLS = list(SENSORS.keys())


# ------------------------------------------------------------------
def load() -> pd.DataFrame:
    df = pd.read_csv(EXPANDED_CSV, parse_dates=["timestamp"])
    df["temp_delta"] = df["process_temperature"] - df["air_temperature"]
    df["power"] = df["torque"] * df["rotational_speed"] * 2 * np.pi / 60
    df["strain"] = df["tool_wear"] * df["torque"]
    return df


def _order(df):
    return [c for c in FAILURE_CLASSES if c in df["failure_class"].unique()]


# ------------------------------------------------------------------
# 01 - class distribution
# ------------------------------------------------------------------
def plot_class_distribution(df):
    order = _order(df)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    counts = df["failure_class"].value_counts().reindex(order)
    bars = axes[0].bar(order, counts.values,
                       color=[CLASS_COLORS[c] for c in order], edgecolor=THEME["bg"])
    axes[0].set_yscale("log")
    axes[0].set_title("Failure-class distribution (log scale)")
    axes[0].set_ylabel("rows")
    for b, v in zip(bars, counts.values):
        axes[0].text(b.get_x() + b.get_width() / 2, v * 1.15,
                     "{:,}\n{:.2f}%".format(v, v / len(df) * 100),
                     ha="center", va="bottom", fontsize=8.5, color=THEME["text"])

    ct = pd.crosstab(df["source"], df["failure_class"]).reindex(columns=order, fill_value=0)
    bottom = np.zeros(len(ct))
    for c in order:
        axes[1].barh(ct.index, ct[c], left=bottom, color=CLASS_COLORS[c],
                     label=c, edgecolor=THEME["bg"])
        bottom += ct[c].to_numpy()
    axes[1].set_xscale("log")
    axes[1].set_title("Composition by data source")
    axes[1].set_xlabel("rows (log)")
    axes[1].legend(ncol=5, loc="lower right", framealpha=0.9)

    fig.suptitle("01 | Target distribution - {:,} total readings".format(len(df)),
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    return save(fig, "01_class_distribution", SUBDIR)


# ------------------------------------------------------------------
# 02 - sensor distributions by class
# ------------------------------------------------------------------
def plot_sensor_distributions(df):
    order = _order(df)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.ravel()

    cols = SENSOR_COLS + ["power"]
    for ax, col in zip(axes, cols):
        for cls in order:
            sub = df.loc[df["failure_class"] == cls, col].dropna()
            if len(sub) < 5:
                continue
            ax.hist(sub, bins=45, density=True, alpha=0.55 if cls == "Normal" else 0.8,
                    color=CLASS_COLORS[cls], label=cls,
                    histtype="stepfilled" if cls == "Normal" else "step", linewidth=1.8)
        unit = SENSORS.get(col, {}).get("unit", "W")
        label = SENSORS.get(col, {}).get("label", "Mechanical Power")
        ax.set_title("{} [{}]".format(label, unit))
        ax.set_ylabel("density")
    axes[0].legend(ncol=1, framealpha=0.9)

    fig.suptitle("02 | Sensor distributions per failure class (normalised)",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "02_sensor_distributions", SUBDIR)


# ------------------------------------------------------------------
# 03 - correlation heatmap
# ------------------------------------------------------------------
def plot_correlation(df):
    cols = SENSOR_COLS + ["temp_delta", "power", "strain"]
    corr = df[cols].corr()

    fig, ax = plt.subplots(figsize=(8.2, 6.8))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=42, ha="right")
    ax.set_yticklabels(cols)
    ax.grid(False)
    for i in range(len(cols)):
        for j in range(len(cols)):
            v = corr.iloc[i, j]
            ax.text(j, i, "{:.2f}".format(v), ha="center", va="center",
                    fontsize=8.5, color="white" if abs(v) > 0.55 else THEME["text"])
    fig.colorbar(im, ax=ax, shrink=0.82, label="Pearson r")
    ax.set_title("03 | Feature correlation matrix", color=THEME["accent"], pad=14)
    return save(fig, "03_correlation_matrix", SUBDIR)


# ------------------------------------------------------------------
# 04 - physics separation
# ------------------------------------------------------------------
def plot_physics(df):
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))
    norm = df[df["failure_class"] == "Normal"].sample(
        min(6000, (df["failure_class"] == "Normal").sum()), random_state=0)

    # (a) HDF - temp delta vs speed
    ax = axes[0, 0]
    ax.scatter(norm["temp_delta"], norm["rotational_speed"], s=4, alpha=0.20,
               color=CLASS_COLORS["Normal"], label="Normal")
    hdf = df[df["failure_class"] == "HDF"]
    ax.scatter(hdf["temp_delta"], hdf["rotational_speed"], s=12, alpha=0.85,
               color=CLASS_COLORS["HDF"], label="HDF")
    ax.axvline(THRESHOLDS["temp_delta_min"], color=THEME["warn"], ls="--", lw=1.6)
    ax.axhline(THRESHOLDS["hdf_speed_max"], color=THEME["warn"], ls="--", lw=1.6)
    ax.set_xlabel("temp_delta [K]"); ax.set_ylabel("rotational_speed [rpm]")
    ax.set_title("(a) HDF zone:  delta < 8.6 K  AND  speed < 1380 rpm")
    ax.legend()

    # (b) PWF - power band
    ax = axes[0, 1]
    ax.scatter(norm["torque"], norm["power"], s=4, alpha=0.20,
               color=CLASS_COLORS["Normal"], label="Normal")
    pwf = df[df["failure_class"] == "PWF"]
    ax.scatter(pwf["torque"], pwf["power"], s=12, alpha=0.85,
               color=CLASS_COLORS["PWF"], label="PWF")
    ax.axhspan(THRESHOLDS["power_min"], THRESHOLDS["power_max"],
               color=CLASS_COLORS["Normal"], alpha=0.10)
    ax.axhline(THRESHOLDS["power_min"], color=THEME["warn"], ls="--", lw=1.6)
    ax.axhline(THRESHOLDS["power_max"], color=THEME["warn"], ls="--", lw=1.6)
    ax.set_xlabel("torque [Nm]"); ax.set_ylabel("power [W]")
    ax.set_title("(b) PWF zone:  power outside 3500 - 9000 W")
    ax.legend()

    # (c) OSF - strain vs limit
    ax = axes[1, 0]
    ax.scatter(norm["tool_wear"], norm["torque"], s=4, alpha=0.20,
               color=CLASS_COLORS["Normal"], label="Normal")
    osf = df[df["failure_class"] == "OSF"]
    ax.scatter(osf["tool_wear"], osf["torque"], s=12, alpha=0.85,
               color=CLASS_COLORS["OSF"], label="OSF")
    w = np.linspace(60, 253, 200)
    for t, ls in zip(["L", "M", "H"], ["--", "-.", ":"]):
        ax.plot(w, THRESHOLDS["osf_limit"][t] / w, ls=ls, lw=1.6,
                color=THEME["warn"], label="limit {} = {:,}".format(t, THRESHOLDS["osf_limit"][t]))
    ax.set_ylim(0, 90)
    ax.set_xlabel("tool_wear [min]"); ax.set_ylabel("torque [Nm]")
    ax.set_title("(c) OSF zone:  tool_wear x torque > variant limit")
    ax.legend(fontsize=8)

    # (d) TWF - tool wear
    ax = axes[1, 1]
    ax.hist(norm["tool_wear"], bins=50, color=CLASS_COLORS["Normal"],
            alpha=0.60, label="Normal", density=True)
    twf = df[df["failure_class"] == "TWF"]
    ax.hist(twf["tool_wear"], bins=30, color=CLASS_COLORS["TWF"],
            alpha=0.9, label="TWF", density=True)
    ax.axvspan(THRESHOLDS["tool_wear_min"], THRESHOLDS["tool_wear_max"],
               color=THEME["warn"], alpha=0.16)
    ax.set_xlabel("tool_wear [min]"); ax.set_ylabel("density")
    ax.set_title("(d) TWF zone:  wear inside the 200 - 240 min window")
    ax.legend()

    fig.suptitle("04 | Physical separability of the four failure mechanisms",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "04_physics_separation", SUBDIR)


# ------------------------------------------------------------------
# 05 - failure rate by machine variant
# ------------------------------------------------------------------
def plot_by_type(df):
    order = _order(df)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

    rate = df.groupby("machine_type")["machine_failure"].mean().mul(100)
    counts = df["machine_type"].value_counts().reindex(rate.index)
    bars = axes[0].bar(rate.index, rate.values, color=THEME["accent"], edgecolor=THEME["bg"])
    axes[0].set_title("Failure rate by machine variant")
    axes[0].set_ylabel("% of readings faulted")
    for b, v, n in zip(bars, rate.values, counts.values):
        axes[0].text(b.get_x() + b.get_width() / 2, v + 0.05,
                     "{:.2f}%\n(n={:,})".format(v, n), ha="center", va="bottom",
                     fontsize=9, color=THEME["text"])

    ct = pd.crosstab(df["machine_type"], df["failure_class"], normalize="index") * 100
    ct = ct.reindex(columns=order, fill_value=0)
    bottom = np.zeros(len(ct))
    for c in order:
        if c == "Normal":
            continue
        axes[1].bar(ct.index, ct[c], bottom=bottom, color=CLASS_COLORS[c],
                    label=c, edgecolor=THEME["bg"])
        bottom += ct[c].to_numpy()
    axes[1].set_title("Failure-mode mix within each variant")
    axes[1].set_ylabel("% of that variant's readings")
    axes[1].legend()

    fig.suptitle("05 | Machine variant (L / M / H) influences failure behaviour",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "05_failure_by_machine_type", SUBDIR)


# ------------------------------------------------------------------
# 06 - degradation signatures (the actual early-warning signal)
# ------------------------------------------------------------------
# For each mechanism we plot the GOVERNING PHYSICAL QUANTITY drifting
# towards its limit. This is the signal the Random Forest actually
# learns, and the trend the HMI will render live. (Plotting health vs
# RUL here would be tautological - health is defined from RUL.)
# ------------------------------------------------------------------
SIGNATURES = {
    "HDF": [("temp_delta", "Temp delta [K]", [THRESHOLDS["temp_delta_min"]]),
            ("rotational_speed", "Speed [rpm]", [THRESHOLDS["hdf_speed_max"]])],
    "PWF": [("power", "Mechanical power [W]",
             [THRESHOLDS["power_min"], THRESHOLDS["power_max"]]),
            ("rotational_speed", "Speed [rpm]", [])],
    "OSF": [("strain", "Strain = wear x torque [minNm]", ["OSF"]),
            ("torque", "Torque [Nm]", [])],
    "TWF": [("tool_wear", "Tool wear [min]", [THRESHOLDS["tool_wear_min"],
                                              THRESHOLDS["tool_wear_max"]]),
            ("torque", "Torque [Nm]", [])],
}


def _fmt_limit(v: float) -> str:
    """8.6 -> '8.6',  9000 -> '9,000'  (never round a decimal threshold away)."""
    return "{:,.1f}".format(v).rstrip("0").rstrip(".") if v < 100 else "{:,.0f}".format(v)


def plot_trajectory(df):
    synth = df[df["source"] == "SYNTH-RUN2FAIL"]

    picks = []
    for mode in ["HDF", "PWF", "OSF", "TWF"]:
        ids = synth.loc[synth["degradation_mode"].str.startswith(mode), "machine_id"].unique()
        if len(ids):
            picks.append((mode, ids[len(ids) // 2]))

    fig, axes = plt.subplots(len(picks), 2, figsize=(14.5, 3.0 * len(picks)))

    for row, (mode, mid) in enumerate(picks):
        m = synth[synth["machine_id"] == mid].sort_values("cycle")
        fail = m[m["machine_failure"] == 1]
        fail_at = int(fail["cycle"].iloc[0]) if len(fail) else None

        for col, (field, ylab, limits) in enumerate(SIGNATURES[mode]):
            ax = axes[row, col]
            ax.plot(m["cycle"], m[field], color=CLASS_COLORS[mode], lw=1.5)

            for lim in limits:
                # "OSF" is a placeholder for this machine variant's own limit
                if lim == "OSF":
                    lim = THRESHOLDS["osf_limit"][m["machine_type"].iloc[0]]
                ax.axhline(lim, color=THEME["warn"], ls="--", lw=1.7)
                ax.annotate("limit {}".format(_fmt_limit(lim)),
                            xy=(0.985, lim), xycoords=("axes fraction", "data"),
                            ha="right", va="bottom", fontsize=8, color=THEME["warn"])

            if fail_at is not None:
                ax.axvline(fail_at, color=THEME["crit"], lw=1.6, ls=":")
                ax.axvspan(fail_at, m["cycle"].max(), color=THEME["crit"], alpha=0.16)

            ax.set_ylabel(ylab, fontsize=9)
            if col == 0:
                ax.set_title("{}   {}   -  fault at reading {}".format(
                    mid, mode, fail_at), fontsize=10.5, loc="left")
            if row == len(picks) - 1:
                ax.set_xlabel("reading # (one every 10 min)")

    fig.suptitle("06 | Degradation signatures - the drift the model learns to detect",
                 fontsize=14, fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "06_degradation_signatures", SUBDIR)


# ------------------------------------------------------------------
# 07 - RUL distribution
# ------------------------------------------------------------------
def plot_rul(df):
    rul = df["rul"].dropna()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))

    axes[0].hist(rul, bins=60, color=THEME["accent"], edgecolor=THEME["bg"])
    axes[0].set_title("RUL distribution over all labelled readings")
    axes[0].set_xlabel("RUL [readings until failure]"); axes[0].set_ylabel("count")

    lives = (df[df["source"] == "SYNTH-RUN2FAIL"]
             .groupby("machine_id")["cycle"].max())
    axes[1].hist(lives, bins=32, color=THEME["ok"], edgecolor=THEME["bg"])
    axes[1].set_title("Machine life distribution ({} machines)".format(len(lives)))
    axes[1].set_xlabel("total readings before intervention")
    axes[1].axvline(lives.mean(), color=THEME["warn"], ls="--", lw=1.8,
                    label="mean {:.0f}".format(lives.mean()))
    axes[1].legend()

    fig.suptitle("07 | Remaining Useful Life target", fontsize=14,
                 fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "07_rul_distribution", SUBDIR)


# ------------------------------------------------------------------
# 08 - boxplots by class
# ------------------------------------------------------------------
def plot_boxplots(df):
    order = _order(df)
    cols = SENSOR_COLS + ["temp_delta", "power", "strain"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.ravel()

    for ax, col in zip(axes, cols):
        data = [df.loc[df["failure_class"] == c, col].dropna().values for c in order]
        bp = ax.boxplot(data, patch_artist=True, tick_labels=order, showfliers=False,
                        medianprops=dict(color=THEME["bg"], linewidth=1.7))
        for patch, c in zip(bp["boxes"], order):
            patch.set_facecolor(CLASS_COLORS[c]); patch.set_alpha(0.85)
        for part in ("whiskers", "caps"):
            for ln in bp[part]:
                ln.set_color(THEME["muted"])
        ax.set_title(col, fontsize=10.5)
        ax.tick_params(axis="x", rotation=35)

    for ax in axes[len(cols):]:
        ax.axis("off")

    fig.suptitle("08 | Feature spread per failure class", fontsize=14,
                 fontweight="bold", color=THEME["accent"])
    fig.tight_layout()
    return save(fig, "08_boxplots_by_class", SUBDIR)


# ------------------------------------------------------------------
def build_summary(df) -> dict:
    order = _order(df)
    counts = df["failure_class"].value_counts()
    stats_cols = SENSOR_COLS + ["temp_delta", "power", "strain"]

    return {
        "total_rows": int(len(df)),
        "n_features_raw": len(SENSOR_COLS) + 1,
        "sources": {k: int(v) for k, v in df["source"].value_counts().items()},
        "n_machines_simulated": int(
            df.loc[df["source"] == "SYNTH-RUN2FAIL", "machine_id"].nunique()),
        "missing_values": int(df[stats_cols].isna().sum().sum()),
        "duplicate_rows": int(df.duplicated(subset=stats_cols).sum()),
        "class_counts": {c: int(counts.get(c, 0)) for c in order},
        "class_percent": {c: round(float(counts.get(c, 0)) / len(df) * 100, 3) for c in order},
        "imbalance_ratio_normal_to_rarest": round(
            float(counts.get("Normal", 0)) / max(float(counts.drop("Normal", errors="ignore").min()), 1), 1),
        "overall_failure_rate_pct": round(float(df["machine_failure"].mean() * 100), 3),
        "machine_type_counts": {k: int(v) for k, v in df["machine_type"].value_counts().items()},
        "descriptive_stats": json.loads(
            df[stats_cols].describe().round(3).to_json()),
        "rul": {
            "labelled_rows": int(df["rul"].notna().sum()),
            "min": float(df["rul"].min()),
            "max": float(df["rul"].max()),
            "mean": round(float(df["rul"].mean()), 2),
        },
    }


# ------------------------------------------------------------------
def main() -> int:
    print("\n" + "=" * 66)
    print(" PHASE 1 | STEP 3 : EXPLORATORY DATA ANALYSIS")
    print("=" * 66)

    if not EXPANDED_CSV.exists():
        print("ERROR: {} missing. Run:  python -m src.data.expand_dataset".format(EXPANDED_CSV))
        return 1

    use_industrial_style()
    df = load()
    print("  Loaded {:,} rows x {} columns\n".format(len(df), len(df.columns)))

    print("  Generating figures ...")
    for fn in (plot_class_distribution, plot_sensor_distributions, plot_correlation,
               plot_physics, plot_by_type, plot_trajectory, plot_rul, plot_boxplots):
        fn(df)

    summary = build_summary(df)
    out = METRIC_DIR / "eda_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n  " + "-" * 62)
    print("  Total rows            : {:,}".format(summary["total_rows"]))
    print("  Simulated machines    : {}".format(summary["n_machines_simulated"]))
    print("  Missing values        : {}".format(summary["missing_values"]))
    print("  Duplicate sensor rows : {:,}".format(summary["duplicate_rows"]))
    print("  Overall failure rate  : {} %".format(summary["overall_failure_rate_pct"]))
    print("  Imbalance (Normal:rarest) : {}:1".format(
        summary["imbalance_ratio_normal_to_rarest"]))
    print("  " + "-" * 62)
    print("\n  Summary saved -> {}".format(out))
    print("=" * 66 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
