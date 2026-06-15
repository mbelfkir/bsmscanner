import argparse
import json
from pathlib import Path

from bsm_scanner import compile_model, load_model, run_scan


ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model_no.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch a scan for the arXiv:2006.03058 Weinberg-operator model."
    )
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs" / "smoke")
    args = parser.parse_args()

    model = load_model(args.model)
    compiled = compile_model(model, build_backend=False)
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
