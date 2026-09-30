"""
Shared matplotlib styling.

Every figure produced by the pipeline uses the same dark "control room"
palette as the HMI, so the plots that go into the report and the plots
embedded in the web UI look like one product.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")                      # headless: no window server needed

import matplotlib.pyplot as plt

from src.config import PLOT_DIR, PLOT_PALETTE, THEME

CLASS_COLORS = {
    "Normal": "#22c55e",
    "TWF": "#f59e0b",
    "HDF": "#ef4444",
    "PWF": "#a78bfa",
    "OSF": "#38bdf8",
}


def use_industrial_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": THEME["bg"],
        "axes.facecolor": THEME["panel"],
        "savefig.facecolor": THEME["bg"],
        "axes.edgecolor": THEME["grid"],
        "axes.labelcolor": THEME["text"],
        "axes.titlecolor": THEME["text"],
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.grid": True,
        "grid.color": THEME["grid"],
        "grid.alpha": 0.55,
        "grid.linewidth": 0.7,
        "xtick.color": THEME["muted"],
        "ytick.color": THEME["muted"],
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "text.color": THEME["text"],
        "legend.facecolor": THEME["panel"],
        "legend.edgecolor": THEME["grid"],
        "legend.labelcolor": THEME["text"],
        "legend.fontsize": 9,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "font.family": "DejaVu Sans",
        "axes.prop_cycle": plt.cycler(color=PLOT_PALETTE),
    })


def save(fig, name: str, subdir: str = "") -> str:
    """Save a figure into artifacts/plots and return its path."""
    out_dir = PLOT_DIR / subdir if subdir else PLOT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (name if name.endswith(".png") else name + ".png")
    fig.savefig(path)
    plt.close(fig)
    print("    saved  {}".format(path.relative_to(PLOT_DIR.parents[1])))
    return str(path)
