"""Multi-seed best-fit scan of the corrected scotogenic model.

Usage:
    python run_best_fit.py [--seeds 1 2 3] [--out runs]

Without --seeds the seed configured in scan.yaml is used. Each run uses the
engine settings of scan.yaml unchanged (except `scan.seed` when --seeds is
given) and writes to <out>/seed_<n>/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bsm_scanner.api import compile_model, load_model_mapping, run_scan
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "runs")
    args = parser.parse_args()

    seeds = args.seeds or [load_model_mapping(ROOT / "model_no.yaml")["scan"]["seed"]]
    for seed in seeds:
        mapping = load_model_mapping(ROOT / "model_no.yaml")
        mapping["scan"]["seed"] = seed
        mapping["scan"]["settings"]["verbose"] = 0
        model = ModelDefinition.from_mapping(mapping)
        run_dir = args.out / f"seed_{seed}"
        result = run_scan(model, compile_model(model), run_directory=run_dir)
        print(json.dumps({"seed": seed, **{k: result.summary[k] for k in (
            "evaluations", "valid_points", "best_metric_value")},
            "stop_reason": result.summary["engine_details"].get("stop_reason")}), flush=True)


if __name__ == "__main__":
    main()
