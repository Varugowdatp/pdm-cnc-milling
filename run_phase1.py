"""
============================================================
 PHASE 1 PIPELINE RUNNER
============================================================
Runs the complete data-and-model pipeline end to end:

    1. download_dataset   real AI4I 2020 data from UCI
    2. expand_dataset     physics-informed run-to-failure expansion
    3. eda                exploratory analysis + 8 figures
    4. train_model        Random Forest + hyper-parameter search
    5. evaluate           held-out evaluation + 6 figures + metrics

Usage
-----
    python run_phase1.py              # run every stage
    python run_phase1.py --from 4     # resume from the training stage
    python run_phase1.py --only 3     # run one stage only
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time

STAGES = [
    ("Download dataset",   "src.data.download_dataset"),
    ("Expand dataset",     "src.data.expand_dataset"),
    ("Exploratory analysis", "src.data.eda"),
    ("Train Random Forest", "src.models.train_model"),
    ("Evaluate model",     "src.evaluation.evaluate"),
]


def run_stage(index: int) -> int:
    title, module_path = STAGES[index]
    print("\n" + "#" * 70)
    print("#  STAGE {}/{}  -  {}".format(index + 1, len(STAGES), title.upper()))
    print("#" * 70)

    module = importlib.import_module(module_path)
    t0 = time.time()
    code = module.main()
    print("   [stage {} finished in {:.1f}s, exit={}]".format(index + 1, time.time() - t0, code))
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 1 pipeline runner")
    ap.add_argument("--from", dest="start", type=int, default=1,
                    help="first stage to run (1-{})".format(len(STAGES)))
    ap.add_argument("--only", type=int, default=None, help="run a single stage")
    args = ap.parse_args()

    if args.only is not None:
        indices = [args.only - 1]
    else:
        indices = list(range(args.start - 1, len(STAGES)))

    if any(i < 0 or i >= len(STAGES) for i in indices):
        print("Stage out of range. Available stages:")
        for i, (title, _) in enumerate(STAGES, 1):
            print("  {}  {}".format(i, title))
        return 2

    t0 = time.time()
    for i in indices:
        code = run_stage(i)
        if code != 0:
            print("\nPipeline stopped: stage {} returned {}".format(i + 1, code))
            return code

    print("\n" + "#" * 70)
    print("#  PHASE 1 COMPLETE  -  total {:.1f}s".format(time.time() - t0))
    print("#" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
