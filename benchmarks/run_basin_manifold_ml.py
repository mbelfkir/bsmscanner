#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "python"
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bsm_scanner import compile_model, load_model, run_scan  # noqa: E402


def configure_scan(model: Any, args: argparse.Namespace) -> None:
    model.scan.engine = "basin_scan"
    model.scan.save_every = 1
    model.scan.seed = args.seed
    model.scan.settings = {
        "objective": "nll",
        "invalid_penalty": 1.0e12,
        "save_invalid_points": True,
        "verbose": 1 if args.verbose else 0,
        "progress_interval": args.progress_interval,
    }
    selected_cap = min(args.max_selected_points, max(100, args.exploration_points // 5))
    model.scan.basin_scan = {
        "seed": args.seed,
        "exploration": {
            "method": "latin_hypercube",
            "n_points": args.exploration_points,
            "keep_fraction": 0.10,
        },
        "selection": {
            "mode": "balanced_terms",
            "total_top_fraction": 0.20,
            "term_quantile_cut": 0.50,
            "top_fraction": 0.10,
            "max_points": selected_cap,
            "min_points": 50,
            "terms": "auto",
            "fallback_mode": "top_fraction",
            "near_miss": {
                "enabled": True,
                "max_hard_failures": 0,
                "max_fit_failures": 2,
                "objective_cap": 1.0e6,
                "include_full_eval_points": True,
            },
        },
        "clustering": {
            "enabled": True,
            "method": "dbscan",
            "eps_fraction": 0.12,
            "min_samples": 8,
            "max_clusters": 4,
        },
        "boxes": {
            "construction": "quantile",
            "q_low": 0.02,
            "q_high": 0.98,
            "padding_fraction": 0.50,
            "min_width_fraction": 0.02,
            "clip_to_original_bounds": True,
            "merge_overlapping": True,
            "max_boxes": 4,
        },
        "manifold_refocus": {
            "enabled": True,
            "method": "covariance",
            "seed": args.seed + 11,
            "source": "selected_plus_exploration",
            "max_train_points": min(5000, args.exploration_points),
            "min_train_points": 50,
            "top_fraction_for_training": 0.25,
            "sampling": {
                "n_candidates": args.manifold_candidates,
                "inflate": 1.30,
                "diagonal_jitter": 1.0e-6,
                "include_training_points": True,
            },
            "box": {
                "enabled": True,
                "quantile_low": 0.01,
                "quantile_high": 0.99,
                "padding_fraction": 0.50,
                "min_width_fraction": 0.01,
                "max_shrink_factor": 80.0,
                "clip_to_original_bounds": True,
            },
        },
        "ml_focus": {
            "enabled": True,
            "seed": args.seed + 23,
            "model": {
                "type": "extra_trees_regressor",
                "n_estimators": args.ml_estimators,
                "min_samples_leaf": 2,
                "max_features": "sqrt",
            },
            "training": {
                "max_train_points": min(20000, args.exploration_points),
                "min_train_points": 50,
                "require_valid": True,
                "finite_objective_only": True,
                "target_transform": "log10_1p",
            },
            "candidate_generation": {
                "n_candidates": args.ml_candidates,
                "sources": {
                    "selected_box_fraction": 0.50,
                    "elite_local_fraction": 0.30,
                    "global_fraction": 0.20,
                },
            },
            "selection": {
                "n_ml_selected": min(2000, max(100, args.ml_candidates // 10)),
                "include_best_real_points": True,
                "n_best_real_points": min(300, max(50, args.exploration_points // 20)),
                "include_elite_archive": True,
            },
            "focused_box": {
                "enabled": True,
                "quantile_low": 0.02,
                "quantile_high": 0.98,
                "padding_fraction": 0.60,
                "min_width_fraction": 0.02,
                "max_shrink_factor": 80.0,
                "clip_to_original_bounds": True,
            },
            "seeds": {
                "enabled": True,
                "max_seeds": args.ml_seeds,
                "composition": {
                    "best_real_fraction": 0.40,
                    "ml_selected_fraction": 0.40,
                    "local_mutation_fraction": 0.20,
                },
                "local_mutation": {
                    "relative_sigma": 0.05,
                    "log_sigma": 0.20,
                },
            },
        },
        "focused_engine": {
            "name": "adaptive_diver",
            "population_size": args.population_size,
            "max_generations": args.generations,
            "p_best_fraction": 0.20,
            "archive": True,
            "mutation": {
                "adaptive": True,
                "F_min": 0.05,
                "F_max": 0.70,
                "initial_mean": 0.35,
                "learning_rate": 0.10,
            },
            "crossover": {
                "adaptive": True,
                "CR_min": 0.10,
                "CR_max": 0.90,
                "initial_mean": 0.55,
                "learning_rate": 0.10,
            },
            "bounds": {"handling": "reflect"},
            "convergence": {
                "patience": args.patience,
                "population_std_tol": 1.0e-10,
                "min_delta_chi2": 1.0e-10,
            },
            "local_refinement": {
                "enabled": True,
                "method": "Powell",
                "n_elites": 6,
                "maxiter": 800,
            },
            "statistics": {"enabled": True},
            "output": {
                "save_history": True,
                "save_population": True,
                "save_elites": True,
            },
        },
        "output": {
            "save_exploration_points": True,
            "save_selected_points": True,
            "save_clusters": True,
            "save_focused_boxes": True,
        },
    }
    model.statistics.enabled = True
    model.statistics.output_samples = True
    model.statistics.include_observables = True


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rows_from_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def float_or_nan(value: Any) -> float:
    try:
        if value in ("", None):
            return math.nan
        return float(value)
    except Exception:
        return math.nan


def best_so_far(rows: list[dict[str, str]]) -> tuple[list[int], list[float]]:
    xs: list[int] = []
    ys: list[float] = []
    best = math.inf
    for i, row in enumerate(rows, start=1):
        value = float_or_nan(row.get("scanner_target") or row.get("total_nll") or row.get("metric_value"))
        valid = str(row.get("valid", "true")).lower() != "false"
        if math.isfinite(value) and valid:
            best = min(best, value)
        if math.isfinite(best):
            xs.append(i)
            ys.append(best)
    return xs, ys


def output_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    columns = []
    for key in rows[0]:
        if key.startswith("output::"):
            columns.append(key.removeprefix("output::"))
        elif key.startswith("out__"):
            columns.append(key.removeprefix("out__"))
    return columns


def make_plots(run_dir: Path, model_name: str) -> None:
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(exist_ok=True)

    rows = rows_from_csv(run_dir / "points.csv")
    x, y = best_so_far(rows)
    if x:
        plt.figure(figsize=(7, 4.5))
        plt.plot(x, [2.0 * value for value in y], lw=2)
        plt.xlabel("Saved evaluation")
        plt.ylabel("Best chi2 so far")
        plt.title(f"{model_name} convergence")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_dir / "best_chi2_vs_saved_evaluation.png", dpi=180)
        plt.close()

    best_fit = read_json(run_dir / "best_fit.json")
    outputs = best_fit.get("outputs", {})
    finite_outputs = [(name, float_or_nan(value)) for name, value in outputs.items()]
    finite_outputs = [(name, value) for name, value in finite_outputs if math.isfinite(value)]
    if finite_outputs:
        shown = finite_outputs[:12]
        plt.figure(figsize=(max(7, len(shown) * 0.65), 4.5))
        plt.bar([name for name, _ in shown], [value for _, value in shown])
        plt.xticks(rotation=30, ha="right")
        plt.ylabel("Value")
        plt.title(f"Best-fit {model_name} observables")
        plt.tight_layout()
        plt.savefig(plot_dir / "best_fit_observables.png", dpi=180)
        plt.close()

    exploration = rows_from_csv(run_dir / "exploration_points.csv")
    obs = output_columns(exploration)
    if len(obs) >= 2:
        x_name, y_name = obs[0], obs[1]
        x_key, y_key = f"output::{x_name}", f"output::{y_name}"
        xs = [float_or_nan(r.get(x_key) or r.get(f"out__{x_name}")) for r in exploration]
        ys = [float_or_nan(r.get(y_key) or r.get(f"out__{y_name}")) for r in exploration]
        target = [float_or_nan(r.get("scanner_target") or r.get("total_nll")) for r in exploration]
        filtered = [
            (a, b, c)
            for a, b, c in zip(xs, ys, target, strict=False)
            if math.isfinite(a) and math.isfinite(b) and math.isfinite(c)
        ]
        if filtered:
            plt.figure(figsize=(6.5, 5))
            sc = plt.scatter(
                [a for a, _, _ in filtered],
                [b for _, b, _ in filtered],
                c=[min(c, 100.0) for _, _, c in filtered],
                s=8,
                cmap="viridis_r",
                alpha=0.75,
            )
            plt.xlabel(x_name)
            plt.ylabel(y_name)
            plt.title(f"{model_name} exploration")
            plt.colorbar(sc, label="nLL clipped at 100")
            plt.tight_layout()
            plt.savefig(plot_dir / f"exploration_{x_name}_vs_{y_name}.png", dpi=180)
            plt.close()


def first_hit_summary(run_dir: Path, thresholds: tuple[float, ...] = (1.0, 0.1, 1.0e-6)) -> dict[str, Any]:
    hits: dict[str, Any] = {}
    for threshold in thresholds:
        hits[f"first_target_le_{threshold:g}"] = None
    for saved_i, row in enumerate(rows_from_csv(run_dir / "points.csv"), start=1):
        value = float_or_nan(row.get("scanner_target") or row.get("total_nll") or row.get("metric_value"))
        if not math.isfinite(value):
            continue
        for threshold in thresholds:
            key = f"first_target_le_{threshold:g}"
            if hits[key] is None and value <= threshold:
                hits[key] = {
                    "saved_index": saved_i,
                    "evaluation": int(float_or_nan(row.get("evaluation"))),
                    "scanner_target": value,
                }
    return hits


def summarize(run_dir: Path, model_name: str, elapsed_seconds: float) -> dict[str, Any]:
    summary = read_json(run_dir / "summary.json")
    best_fit = read_json(run_dir / "best_fit.json")
    basin_results = read_json(run_dir / "basin_results.json")
    timing = {
        "wall_seconds": elapsed_seconds,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")

    report = {
        "model": model_name,
        "engine": "basin_scan+manifold_refocus+ml_focus",
        "run_dir": str(run_dir),
        "timing": timing,
        "summary": summary,
        "first_hits": first_hit_summary(run_dir),
        "best_fit": best_fit,
        "engine_details": summary.get("engine_details", {}),
        "basin_results": {
            "n_focused_boxes": basin_results.get("n_focused_boxes"),
            "manifold_refocus": basin_results.get("manifold_refocus"),
            "ml_focus": basin_results.get("ml_focus"),
        },
    }
    (run_dir / "scan_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def slug_from_model_path(path: Path) -> str:
    if path.name == "model.yaml":
        return path.parent.name
    return path.stem.replace("_", "-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run basin_scan with manifold_refocus and ml_focus for a model.")
    parser.add_argument("model", type=Path, help="Path to a model.yaml file.")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--exploration-points", type=int, default=15000)
    parser.add_argument("--manifold-candidates", type=int, default=50000)
    parser.add_argument("--ml-candidates", type=int, default=50000)
    parser.add_argument("--ml-estimators", type=int, default=160)
    parser.add_argument("--ml-seeds", type=int, default=400)
    parser.add_argument("--population-size", type=int, default=72)
    parser.add_argument("--generations", type=int, default=240)
    parser.add_argument("--patience", type=int, default=80)
    parser.add_argument("--max-selected-points", type=int, default=2000)
    parser.add_argument("--progress-interval", type=int, default=1000)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    model_path = args.model if args.model.is_absolute() else ROOT / args.model
    model = load_model(model_path)
    model_name = model.metadata.name
    if args.seed is None:
        args.seed = int(getattr(model.scan, "seed", 12345) or 12345)
    if args.run_dir is None:
        args.run_dir = ROOT / "benchmarks" / "runs" / f"{slug_from_model_path(model_path)}_basin_manifold_ml"

    configure_scan(model, args)
    compiled = compile_model(model, build_backend=False)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "campaign_config.json").write_text(
        json.dumps(
            {
                "model_path": str(model_path),
                "model": model_name,
                "seed": args.seed,
                "scan": model.scan.basin_scan,
                "settings": model.scan.settings,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    started = time.perf_counter()
    result = run_scan(
        model,
        compiled,
        run_directory=args.run_dir,
        run_id=f"{slug_from_model_path(model_path)}-basin-manifold-ml",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )
    elapsed = time.perf_counter() - started
    report = summarize(result.run_directory, model_name, elapsed)
    make_plots(result.run_directory, model_name)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
