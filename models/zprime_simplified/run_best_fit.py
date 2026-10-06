"""Best-fit scan of the corrected Z' simplified DM model.

Usage:
    python run_best_fit.py [--seeds 1 2] [--out runs] [--with-dd]

Without --seeds the seed configured in scan.yaml is used. --with-dd adds the LZ direct-detection constraint (constraints/direct_detection.yaml),
which needs its external data tables (model_with_*.yaml); the run directory name records it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bsm_scanner.api import compile_model, load_model_mapping, run_scan
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parent


def build_mapping(with_dd: bool) -> dict:
    return load_model_mapping(ROOT / ('model_with_direct_detection.yaml' if with_dd else 'model.yaml'))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "runs")
    parser.add_argument("--with-dd", action="store_true")
    args = parser.parse_args()

    seeds = args.seeds or [build_mapping(args.with_dd)["scan"]["seed"]]
    for seed in seeds:
        mapping = build_mapping(args.with_dd)
        mapping["scan"]["seed"] = seed
        model = ModelDefinition.from_mapping(mapping)
        tag = "_with_dd" if args.with_dd else ""
        run_dir = args.out / f"seed_{seed}{tag}"
        result = run_scan(model, compile_model(model), run_directory=run_dir)
        print(json.dumps({"seed": seed, "with_dd": args.with_dd,
                          **{k: result.summary[k] for k in ("evaluations", "valid_points", "best_metric_value")},
                          "stop_reason": result.summary["engine_details"].get("stop_reason")}), flush=True)


if __name__ == "__main__":
    main()
