from __future__ import annotations

import argparse
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "model.yaml"
QUICK_EVALUATIONS = 4000


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a Zprime simplified-DM benchmark scan.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs" / "scan")
    parser.add_argument("--no-native-backend", action="store_true")
    parser.add_argument(
        "--quick",
        action="store_true",
        help=f"serial_random with {QUICK_EVALUATIONS} evaluations: a mechanics demo, not a fit "
        "(the model's own scan.yaml is a full best-fit search)",
    )
    args = parser.parse_args()

    model = load_model(args.model)
    if args.quick:
        model.scan.engine = "serial_random"
        model.scan.seed = 1
        model.scan.settings["max_evaluations"] = QUICK_EVALUATIONS
        model.statistics.enabled = False
    compiled = compile_model(model, build_backend=not args.no_native_backend)
    result = run_scan(model, compiled, run_directory=args.run_dir)
    print(result.summary)


if __name__ == "__main__":
    main()
