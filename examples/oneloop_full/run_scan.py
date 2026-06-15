import argparse
import json
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan

try:
    from bsm_scanner import _core  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _core = None


ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch a scan for the full oneloop migration example."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL,
        help="Path to the model YAML file.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=ROOT / "runs" / "example_scan",
        help="Directory where scan outputs will be written.",
    )
    args = parser.parse_args()

    model = load_model(args.model)
    if "micromegas_pending" in model.metadata.tags:
        print(
            "Warning: the exact micrOMEGAs-backed DM sector is still deferred in this "
            "milestone. See /Users/mbelfkir/HEP/BSMScanner/docs/dm_status.md"
        )
    if model.scan.engine == "diver" and (_core is None or not _core.has_diver_support()):
        raise SystemExit(
            "This model requests the Diver engine, but the current build does not include "
            "Diver support. Reinstall with "
            "CMAKE_ARGS='-DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=/path/to/Diver' "
            "or change scan.engine to 'serial_random' for a smoke test."
        )

    compiled = compile_model(model, build_backend=False)
    results = run_scan(model, compiled, run_directory=args.run_dir)

    payload = {
        "run_directory": str(results.run_directory),
        "points_path": str(results.points_path),
        "metadata_path": str(results.metadata_path),
        "best_fit_path": str(results.best_fit_path),
        "summary_path": str(results.summary_path),
        "summary": results.summary,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
