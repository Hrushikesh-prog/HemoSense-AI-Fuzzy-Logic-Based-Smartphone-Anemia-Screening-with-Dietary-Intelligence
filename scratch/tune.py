"""
tune.py
Step 3.4 — Hyperparameter tuning: learning rate, augmentation strength, and head type
(regression vs classification). Uses a lightweight grid search rather than an extra
dependency (keras-tuner) so this runs anywhere train.py runs. Swap in keras-tuner's
Hyperband/BayesianOptimization later if the grid gets too big to brute-force.

Usage:
    python tune.py --variant B --epochs_per_trial 10
"""

import argparse
import itertools
import json
import os

import config
from train import train

# Keep grids small on purpose — this is meant to run overnight, not for a week.
LR_GRID = [1e-3, 1e-4, 3e-5]
AUG_STRENGTH_GRID = [0.5, 1.0, 1.5]
HEAD_GRID = ["regression"]  # add "classification" if you decide to bucket by anemia severity


def run_grid_search(variant, epochs_per_trial=10):
    results = []
    combos = list(itertools.product(LR_GRID, AUG_STRENGTH_GRID, HEAD_GRID))
    print(f"[tune] Running {len(combos)} trials for variant {variant}...")

    for i, (lr, aug_strength, head) in enumerate(combos, 1):
        print(f"\n[tune] Trial {i}/{len(combos)}: lr={lr}, aug_strength={aug_strength}, head={head}")
        run_meta = train(
            variant=variant,
            epochs=epochs_per_trial,
            lr=lr,
            aug_strength=aug_strength,
            dropout=0.3,
            dense_units=128,
            head=head,
        )
        results.append({
            "lr": lr,
            "aug_strength": aug_strength,
            "head": head,
            "run_name": run_meta["run_name"],
            "val_metrics": run_meta["test_metrics"],  # test set here doubles as tuning signal;
                                                        # swap to a dedicated val-only eval if you
                                                        # want to keep the test set fully untouched
                                                        # until the final reported run.
        })

    results.sort(key=lambda r: r["val_metrics"].get("overall_mae", float("inf")))

    out_path = os.path.join(config.RESULTS_DIR, f"tune_results_{variant}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[tune] Best config: {results[0]}")
    print(f"[tune] Full results saved to {out_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["A", "B"], required=True)
    parser.add_argument("--epochs_per_trial", type=int, default=10)
    args = parser.parse_args()
    run_grid_search(args.variant, args.epochs_per_trial)
