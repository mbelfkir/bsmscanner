from __future__ import annotations

import argparse
import json
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "model_no.yaml"
DEFAULT_RUN_DIR = ROOT / "runs" / "no_multi_island_smoke"


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a Weinberg multi-island BSMScanner scan.")
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help="Path to the Weinberg model YAML file.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
        help="Directory where scan outputs will be written.",
    )
    parser.add_argument(
        "--no-native-backend",
        action="store_true",
        help="Compile only the model plan without building the native evaluator backend.",
    )
    args = parser.parse_args()

    model = load_model(args.model)
    compiled = compile_model(model, build_backend=not args.no_native_backend)
    results = run_scan(model, compiled, run_directory=args.run_dir)

    print(
        json.dumps(
            {
                "run_directory": str(results.run_directory),
                "points_path": str(results.points_path),
                "metadata_path": str(results.metadata_path),
                "best_fit_path": str(results.best_fit_path),
                "summary_path": str(results.summary_path),
                "summary": results.summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
