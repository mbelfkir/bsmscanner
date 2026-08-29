from __future__ import annotations

import argparse
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "model.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch a Zprime simplified-DM benchmark scan.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs" / "scan")
    parser.add_argument("--no-native-backend", action="store_true")
    args = parser.parse_args()

    model = load_model(args.model)
    compiled = compile_model(model, build_backend=not args.no_native_backend)
    result = run_scan(model, compiled, run_directory=args.run_dir)
    print(result.summary)


if __name__ == "__main__":
    main()
