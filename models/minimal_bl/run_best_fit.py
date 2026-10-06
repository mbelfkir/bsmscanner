"""Best-fit scan of the corrected minimal B-L model.

Usage:
    python run_best_fit.py [--seeds 1 2] [--out runs] [--with-dilepton]

Without --seeds the seed configured in scan.yaml is used. --with-dilepton adds the LHC dilepton constraint (constraints/lhc_dilepton.yaml),
which needs its external data tables (model_with_*.yaml); the run directory name records it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bsm_scanner.api import compile_model, load_model_mapping, run_scan
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parent


def build_mapping(with_dilepton: bool) -> dict:
    return load_model_mapping(ROOT / ('model_with_lhc_dilepton.yaml' if with_dilepton else 'model.yaml'))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    parser.add_argument("--out", type=Path, default=ROOT / "runs")
    parser.add_argument("--with-dilepton", action="store_true")
    args = parser.parse_args()

    seeds = args.seeds or [build_mapping(args.with_dilepton)["scan"]["seed"]]
    for seed in seeds:
        mapping = build_mapping(args.with_dilepton)
        mapping["scan"]["seed"] = seed
        model = ModelDefinition.from_mapping(mapping)
        tag = "_with_dilepton" if args.with_dilepton else ""
        run_dir = args.out / f"seed_{seed}{tag}"
        result = run_scan(model, compile_model(model), run_directory=run_dir)
        print(json.dumps({"seed": seed, "with_dilepton": args.with_dilepton,
                          **{k: result.summary[k] for k in ("evaluations", "valid_points", "best_metric_value")},
                          "stop_reason": result.summary["engine_details"].get("stop_reason")}), flush=True)


if __name__ == "__main__":
    main()
