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

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from bsm_scanner import compile_model, load_model, run_scan  # noqa: E402

MODEL = ROOT / "models" / "minimal_bl" / "model.yaml"


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
            "max_points": min(2000, max(100, args.exploration_points // 5)),
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
        "progressive_exploration": {
            "enabled": args.progressive,
            "n_rounds": 2,
            "points_per_round": [args.exploration_points, max(1000, args.exploration_points // 2)],
            "combine_with_previous_selected": True,
            "selection": {
                "mode": "balanced_terms",
                "total_top_fraction": 0.20,
                "term_quantile_cut": 0.50,
                "top_fraction": 0.10,
                "max_points": min(2000, max(100, args.exploration_points // 5)),
                "min_points": 50,
                "terms": "auto",
                "fallback_mode": "top_fraction",
            },
            "elite_preservation": {
                "enabled": True,
                "always_keep_global_best": True,
                "archive_size": 500,
                "elite_fraction": 0.05,
                "min_elite_points": 20,
                "max_elite_points": 200,
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
            "sampling": {
                "method": "latin_hypercube",
                "allocate_points": "mixed",
                "fractions": {"elite_boxes": 0.50, "selected_boxes": 0.30, "global": 0.20},
                "min_points_per_box": 500,
            },
            "output": {
                "save_round_points": True,
                "save_round_selected": True,
                "save_round_boxes": True,
            },
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
                "patience": 80,
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


def make_plots(run_dir: Path) -> None:
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(exist_ok=True)

    rows = rows_from_csv(run_dir / "points.csv")
    x, y = best_so_far(rows)
    if x:
        plt.figure(figsize=(7, 4.5))
        plt.plot(x, [2.0 * value for value in y], lw=2)
        plt.xlabel("Saved evaluation")
        plt.ylabel("Best chi2 so far")
        plt.title("Minimal B-L basin+manifold+ML convergence")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_dir / "best_chi2_vs_saved_evaluation.png", dpi=180)
        plt.close()

    best_fit = read_json(run_dir / "best_fit.json")
    outputs = best_fit.get("outputs", {})
    obs_names = ["MZprime", "contact_scale", "HiggsSignalStrength", "ZprimeWidthFractionProxy"]
    obs_values = [float_or_nan(outputs.get(name)) for name in obs_names]
    if any(math.isfinite(v) for v in obs_values):
        plt.figure(figsize=(7, 4.5))
        plt.bar(obs_names, obs_values)
        plt.xticks(rotation=25, ha="right")
        plt.ylabel("Value")
        plt.title("Best-fit Minimal B-L observables")
        plt.tight_layout()
        plt.savefig(plot_dir / "best_fit_observables.png", dpi=180)
        plt.close()

    points = rows_from_csv(run_dir / "exploration_points.csv")
    if points:
        mzp = [float_or_nan(r.get("output::MZprime") or r.get("out__MZprime")) for r in points]
        contact = [float_or_nan(r.get("output::contact_scale") or r.get("out__contact_scale")) for r in points]
        target = [float_or_nan(r.get("scanner_target") or r.get("total_nll")) for r in points]
        filtered = [(a, b, c) for a, b, c in zip(mzp, contact, target, strict=False) if math.isfinite(a) and math.isfinite(b) and math.isfinite(c)]
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
            plt.axhline(7000.0, color="crimson", lw=1.5, ls="--", label="LEP proxy")
            plt.xlabel("MZprime [GeV]")
            plt.ylabel("MZprime / gBL [GeV]")
            plt.title("Exploration points")
            plt.colorbar(sc, label="nLL clipped at 100")
            plt.legend()
            plt.tight_layout()
            plt.savefig(plot_dir / "exploration_mzprime_contact.png", dpi=180)
            plt.close()


def summarize(run_dir: Path, elapsed_seconds: float) -> dict[str, Any]:
    summary = read_json(run_dir / "summary.json")
    best_fit = read_json(run_dir / "best_fit.json")
    basin_results = read_json(run_dir / "basin_results.json")
    timing = {
        "wall_seconds": elapsed_seconds,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")

    report = {
        "model": "minimal_bl_gauge",
        "engine": "basin_scan+manifold_refocus+ml_focus",
        "run_dir": str(run_dir),
        "timing": timing,
        "summary": summary,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Minimal B-L basin_scan with manifold_refocus and ml_focus.")
    parser.add_argument("--run-dir", type=Path, default=ROOT / "benchmarks" / "runs" / "minimal_bl_basin_manifold_ml")
    parser.add_argument("--seed", type=int, default=11064462)
    parser.add_argument("--exploration-points", type=int, default=15000)
    parser.add_argument("--manifold-candidates", type=int, default=50000)
    parser.add_argument("--ml-candidates", type=int, default=50000)
    parser.add_argument("--ml-estimators", type=int, default=160)
    parser.add_argument("--ml-seeds", type=int, default=400)
    parser.add_argument("--population-size", type=int, default=72)
    parser.add_argument("--generations", type=int, default=240)
    parser.add_argument("--progressive", action="store_true")
    parser.add_argument("--progress-interval", type=int, default=1000)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    model = load_model(MODEL)
    configure_scan(model, args)
    compiled = compile_model(model, build_backend=False)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "campaign_config.json").write_text(
        json.dumps(
            {
                "model_path": str(MODEL),
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
        run_id="minimal-bl-basin-manifold-ml",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )
    elapsed = time.perf_counter() - started
    report = summarize(result.run_directory, elapsed)
    make_plots(result.run_directory)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
