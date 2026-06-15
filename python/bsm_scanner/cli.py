from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from bsm_scanner import __version__, compile_model, load_model, run_scan
from bsm_scanner.exceptions import ModelValidationError

try:
    from bsm_scanner import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _core = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bsm-scanner",
        description="Run YAML-defined BSMScanner model scans.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Run a scan from a model YAML file.")
    model_source = run_parser.add_mutually_exclusive_group(required=True)
    model_source.add_argument("--model", type=Path, help="Path to the model YAML file.")
    model_source.add_argument(
        "--example",
        choices=["quadratic"],
        help="Run a built-in lightweight example model.",
    )
    run_parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Directory where scan artifacts will be written.",
    )
    run_parser.add_argument(
        "--no-native-backend",
        action="store_true",
        help="Compile only the Python plan before launching engines that still require the native adapter.",
    )
    return parser


def _run(args: argparse.Namespace) -> int:
    try:
        if args.example:
            resource = resources.files("bsm_scanner.examples").joinpath(f"{args.example}.yaml")
            with resources.as_file(resource) as model_path:
                model = load_model(model_path)
        else:
            model = load_model(args.model)
        if model.scan.engine == "diver" and (_core is None or not _core.has_diver_support()):
            raise RuntimeError(
                "This model requests the Diver engine, but this build does not include Diver support. "
                "Reinstall with BSM_SCANNER_BUILD_DIVER enabled or choose a model/configuration using "
                "serial_random, de_scipy, adaptive_diver, or basin_scan."
            )
        compiled = compile_model(model, build_backend=not args.no_native_backend)
        results = run_scan(model, compiled, run_directory=args.run_dir)
    except (FileNotFoundError, ModelValidationError, RuntimeError) as exc:
        print(f"bsm-scanner: error: {exc}", file=sys.stderr)
        return 2

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
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
