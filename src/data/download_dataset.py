"""
============================================================
 PHASE 1 - STEP 1 : DATASET ACQUISITION
============================================================
Downloads the AI4I 2020 Predictive Maintenance Dataset from the
UCI Machine Learning Repository (ID 601).

Dataset facts
-------------
  Rows      : 10,000
  Features  : Machine type (L/M/H), Air temp [K], Process temp [K],
              Rotational speed [rpm], Torque [Nm], Tool wear [min]
  Targets   : Machine failure + 5 independent failure modes
              TWF / HDF / PWF / OSF / RNF
  Reference : Matzka, S. (2020). "Explainable Artificial Intelligence
              for Predictive Maintenance Applications", AI4I 2020.

Usage:  python -m src.data.download_dataset
"""

from __future__ import annotations

import io
import sys
import zipfile

import pandas as pd
import requests

from src.config import RAW_CSV, RAW_DIR, UCI_MIRRORS, UCI_ZIP_URL

HEADERS = {"User-Agent": "Mozilla/5.0 (PdM-Project/1.0)"}
TIMEOUT = 60


# ------------------------------------------------------------------
def _from_zip() -> pd.DataFrame | None:
    """Primary source: the official UCI .zip archive."""
    try:
        print(f"[1/3] Trying official UCI archive ...\n      {UCI_ZIP_URL}")
        r = requests.get(UCI_ZIP_URL, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not names:
                print("      ! archive contained no CSV")
                return None
            print(f"      + extracted '{names[0]}' from archive")
            with z.open(names[0]) as fh:
                return pd.read_csv(fh)
    except Exception as exc:                       # noqa: BLE001
        print(f"      ! failed: {exc}")
        return None


def _from_mirror() -> pd.DataFrame | None:
    """Fallback: plain-CSV mirrors."""
    for i, url in enumerate(UCI_MIRRORS, start=2):
        try:
            print(f"[{i}/3] Trying mirror ...\n      {url}")
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text))
        except Exception as exc:                   # noqa: BLE001
            print(f"      ! failed: {exc}")
    return None


# ------------------------------------------------------------------
def validate(df: pd.DataFrame) -> None:
    """Fail loudly if the downloaded file is not the real AI4I dataset."""
    required = [
        "Air temperature", "Process temperature", "Rotational speed",
        "Torque", "Tool wear", "Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF",
    ]
    joined = " | ".join(df.columns)
    missing = [c for c in required if c not in joined]
    if missing:
        raise ValueError(f"Downloaded file is not the AI4I 2020 dataset. Missing: {missing}")
    if len(df) != 10_000:
        print(f"      ! WARNING: expected 10,000 rows, got {len(df):,}")


def summarise(df: pd.DataFrame) -> None:
    print("\n" + "=" * 62)
    print(" AI4I 2020 PREDICTIVE MAINTENANCE DATASET - SUMMARY")
    print("=" * 62)
    print(f" Rows            : {len(df):,}")
    print(f" Columns         : {len(df.columns)}")
    print(f" Missing values  : {int(df.isna().sum().sum())}")
    print(f" Duplicate rows  : {int(df.duplicated().sum())}")
    print("\n Columns:")
    for c in df.columns:
        print(f"   - {c:<28} {str(df[c].dtype):<10}")

    fail_col = [c for c in df.columns if "Machine failure" in c][0]
    n_fail = int(df[fail_col].sum())
    print(f"\n Machine failures: {n_fail:,} / {len(df):,}  ({n_fail / len(df) * 100:.2f} %)")
    print(" Failure modes:")
    for mode in ("TWF", "HDF", "PWF", "OSF", "RNF"):
        if mode in df.columns:
            print(f"   - {mode}: {int(df[mode].sum()):>4}")
    print("=" * 62 + "\n")


# ------------------------------------------------------------------
def main() -> int:
    print("\n" + "=" * 62)
    print(" PHASE 1 | STEP 1 : DOWNLOADING DATASET")
    print("=" * 62)

    if RAW_CSV.exists():
        print(f"Dataset already present -> {RAW_CSV}")
        df = pd.read_csv(RAW_CSV)
        summarise(df)
        return 0

    df = _from_zip()
    if df is None:
        df = _from_mirror()
    if df is None:
        print("\nERROR: could not download the dataset from any source.")
        print("Manual fallback: download from")
        print("  https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset")
        print(f"and place 'ai4i2020.csv' into: {RAW_DIR}")
        return 1

    validate(df)
    df.to_csv(RAW_CSV, index=False)
    print(f"\nSaved -> {RAW_CSV}  ({RAW_CSV.stat().st_size / 1024:.1f} KB)")
    summarise(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
