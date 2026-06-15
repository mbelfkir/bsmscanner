from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from bsm_scanner import compile_model, run_scan
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.scan import (
    _AdaptiveDiverObjective,
    _PythonScanArtifactsWriter,
    _apply_initial_population_seeds,
    _build_staged_evaluation_context,
    _evaluate_basin_points,
    _ml_focus_box_from_points,
    _ml_focus_transform_values,
    _select_basin_points,
    build_scan_request,
)


pytest.importorskip("bsm_scanner._core")


FIXED_TIMESTAMP = "2026-05-21T00:00:00+00:00"


def make_narrow_basin_model(*, invalid_region: bool = False, scan_config: dict | None = None) -> ModelDefinition:
    theory_checks = []
    if invalid_region:
        theory_checks.append(
            {
                "name": "x_valid",
                "condition": "x > -4.0",
                "message": "deliberately invalid exploration region",
            }
        )
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": "basin-scan-narrow"},
            "parameters": [
                {"name": "x", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
                {"name": "y", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
            ],
            "observables": [
                {"name": "x_obs", "expression": "x"},
                {"name": "y_obs", "expression": "y"},
            ],
            "theory_checks": theory_checks,
            "likelihoods": [
                {"name": "x_term", "kind": "gaussian", "observable": "x_obs", "mean": 3.0, "sigma": 0.08},
                {"name": "y_term", "kind": "gaussian", "observable": "y_obs", "mean": -4.0, "sigma": 0.08},
            ],
            "outputs": {"save": ["x_obs", "y_obs"]},
            "scan": scan_config or basin_scan_config(n_points=220, max_clusters=2),
        }
    )


def make_two_basin_model() -> ModelDefinition:
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": "basin-scan-two-basins"},
            "parameters": [
                {"name": "x", "value_type": "real", "scan": True, "lower": -5.0, "upper": 5.0, "default": 0.0},
                {"name": "y", "value_type": "real", "scan": True, "lower": -5.0, "upper": 5.0, "default": 0.0},
            ],
            "observables": [
                {
                    "name": "basin_distance",
                    "expression": "if_else(x < 0, (x + 3.0)**2 + y**2, (x - 3.0)**2 + y**2)",
                }
            ],
            "likelihoods": [
                {"name": "basin_term", "kind": "gaussian", "observable": "basin_distance", "mean": 0.0, "sigma": 0.1}
            ],
            "outputs": {"save": ["basin_distance"]},
            "scan": basin_scan_config(n_points=360, top_fraction=0.25, eps_fraction=0.18, max_clusters=4),
        }
    )


def basin_scan_config(
    *,
    n_points: int,
    top_fraction: float = 0.12,
    eps_fraction: float = 0.18,
    max_clusters: int = 3,
) -> dict:
    return {
        "engine": "basin_scan",
        "save_every": 1,
        "seed": 24680,
        "settings": {
            "objective": "nll",
            "invalid_penalty": 1.0e12,
            "save_invalid_points": True,
            "verbose": 0,
        },
        "basin_scan": {
            "seed": 24680,
            "exploration": {
                "method": "latin_hypercube",
                "n_points": n_points,
                "keep_fraction": top_fraction,
            },
            "selection": {
                "mode": "top_fraction",
                "top_fraction": top_fraction,
                "max_points": 90,
            },
            "clustering": {
                "method": "dbscan",
                "enabled": True,
                "eps_fraction": eps_fraction,
                "min_samples": 3,
                "max_clusters": max_clusters,
            },
            "boxes": {
                "construction": "quantile",
                "q_low": 0.05,
                "q_high": 0.95,
                "padding_fraction": 0.4,
                "min_width_fraction": 0.08,
                "clip_to_original_bounds": True,
            },
            "focused_engine": {
                "name": "adaptive_diver",
                "population_size": 14,
                "max_generations": 30,
                "p_best_fraction": 0.3,
                "archive": True,
                "bounds": {"handling": "reflect"},
                "convergence": {"patience": 0, "population_std_tol": 0.0},
                "local_refinement": {
                    "enabled": True,
                    "method": "Powell",
                    "n_elites": 3,
                    "maxiter": 120,
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
                "save_clusters": True,
                "save_focused_boxes": True,
            },
        },
    }


def progressive_basin_scan_config() -> dict:
    config = basin_scan_config(n_points=80, top_fraction=0.25, eps_fraction=0.22, max_clusters=3)
    basin = config["basin_scan"]
    basin["progressive_exploration"] = {
        "enabled": True,
        "n_rounds": 2,
        "points_per_round": [90, 60],
        "selection": {
            "mode": "top_fraction",
            "top_fraction": 0.25,
            "max_points": 40,
        },
        "elite_preservation": {
            "enabled": True,
            "always_keep_global_best": True,
            "archive_size": 40,
            "elite_fraction": 0.5,
            "min_elite_points": 4,
            "max_elite_points": 12,
        },
        "elite_boxes": {
            "enabled": True,
            "construction": "quantile",
            "q_low": 0.05,
            "q_high": 0.95,
            "padding_fraction": 0.25,
            "min_width_fraction": 0.04,
            "max_boxes": 2,
        },
        "best_centered_box": {
            "enabled": True,
            "width_fraction": 0.25,
            "shrink_per_round": 0.7,
            "min_width_fraction": 0.03,
        },
        "boxes": {
            "construction": "quantile",
            "q_low": 0.05,
            "q_high": 0.95,
            "padding_fraction": 0.35,
            "min_width_fraction": 0.05,
            "clip_to_original_bounds": True,
            "merge_overlapping": True,
            "max_boxes": 3,
        },
        "sampling": {
            "method": "latin_hypercube",
            "allocate_points": "mixed",
            "fractions": {
                "elite_boxes": 0.45,
                "selected_boxes": 0.35,
                "global": 0.20,
            },
            "min_points_per_box": 10,
        },
        "output": {
            "save_round_points": True,
            "save_round_selected": True,
            "save_round_boxes": True,
        },
    }
    basin["focused_engine"]["population_size"] = 8
    basin["focused_engine"]["max_generations"] = 5
    basin["focused_engine"]["local_refinement"]["enabled"] = False
    return config


def progressive_balanced_basin_scan_config() -> dict:
    config = progressive_basin_scan_config()
    balanced_selection = {
        "mode": "balanced_terms",
        "total_top_fraction": 0.50,
        "term_quantile_cut": 0.70,
        "top_fraction": 0.25,
        "max_points": 40,
        "min_points": 2,
        "terms": "auto",
        "fallback_mode": "top_fraction",
    }
    config["basin_scan"]["selection"] = dict(balanced_selection)
    config["basin_scan"]["progressive_exploration"]["selection"] = dict(balanced_selection)
    return config


def ml_focus_basin_scan_config() -> dict:
    config = basin_scan_config(n_points=60, top_fraction=0.4, eps_fraction=0.25, max_clusters=1)
    config["basin_scan"]["focused_engine"]["population_size"] = 6
    config["basin_scan"]["focused_engine"]["max_generations"] = 2
    config["basin_scan"]["focused_engine"]["local_refinement"]["enabled"] = False
    config["basin_scan"]["ml_focus"] = {
        "enabled": True,
        "seed": 13579,
        "model": {
            "type": "extra_trees_regressor",
            "n_estimators": 8,
            "min_samples_leaf": 1,
            "max_features": "sqrt",
        },
        "training": {
            "max_train_points": 200,
            "min_train_points": 10,
            "require_valid": True,
            "finite_objective_only": True,
            "target_transform": "log10_1p",
        },
        "candidate_generation": {
            "n_candidates": 200,
            "sources": {
                "selected_box_fraction": 0.4,
                "elite_local_fraction": 0.4,
                "global_fraction": 0.2,
            },
        },
        "selection": {
            "n_ml_selected": 40,
            "include_best_real_points": True,
            "n_best_real_points": 20,
            "include_elite_archive": True,
        },
        "focused_box": {
            "enabled": True,
            "quantile_low": 0.05,
            "quantile_high": 0.95,
            "padding_fraction": 0.5,
            "min_width_fraction": 0.05,
            "max_shrink_factor": 20.0,
            "clip_to_original_bounds": True,
        },
        "seeds": {
            "enabled": True,
            "max_seeds": 20,
            "composition": {
                "best_real_fraction": 0.4,
                "ml_selected_fraction": 0.4,
                "local_mutation_fraction": 0.2,
            },
            "local_mutation": {
                "relative_sigma": 0.04,
                "log_sigma": 0.2,
            },
        },
    }
    return config


def manifold_refocus_basin_scan_config(*, with_ml_focus: bool = False) -> dict:
    config = basin_scan_config(n_points=90, top_fraction=0.35, eps_fraction=0.3, max_clusters=1)
    config["basin_scan"]["selection"]["max_points"] = 40
    config["basin_scan"]["focused_engine"]["population_size"] = 6
    config["basin_scan"]["focused_engine"]["max_generations"] = 2
    config["basin_scan"]["focused_engine"]["local_refinement"]["enabled"] = False
    config["basin_scan"]["manifold_refocus"] = {
        "enabled": True,
        "method": "covariance",
        "seed": 97531,
        "source": "selected",
        "max_train_points": 30,
        "min_train_points": 5,
        "top_fraction_for_training": 1.0,
        "sampling": {
            "n_candidates": 200,
            "inflate": 0.5,
            "diagonal_jitter": 1.0e-6,
            "include_training_points": True,
        },
        "box": {
            "enabled": True,
            "quantile_low": 0.10,
            "quantile_high": 0.90,
            "padding_fraction": 0.2,
            "min_width_fraction": 0.02,
            "max_shrink_factor": 50.0,
            "clip_to_original_bounds": True,
        },
    }
    if with_ml_focus:
        config["basin_scan"]["ml_focus"] = ml_focus_basin_scan_config()["basin_scan"]["ml_focus"]
        config["basin_scan"]["ml_focus"]["model"]["n_estimators"] = 6
        config["basin_scan"]["ml_focus"]["candidate_generation"]["n_candidates"] = 80
        config["basin_scan"]["ml_focus"]["selection"]["n_ml_selected"] = 20
        config["basin_scan"]["ml_focus"]["selection"]["n_best_real_points"] = 10
        config["basin_scan"]["ml_focus"]["seeds"]["max_seeds"] = 10
    return config


def test_basin_scan_registered_and_parses_nested_settings():
    model = make_narrow_basin_model()
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="basin-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert request.engine == "basin_scan"
    assert request.engine_options["exploration"]["method"] == "latin_hypercube"
    assert request.engine_options["progressive_exploration"]["enabled"] is False
    assert request.engine_options["ml_focus"]["enabled"] is False
    assert request.engine_options["manifold_refocus"]["enabled"] is False
    assert request.engine_options["focused_engine"]["name"] == "adaptive_diver"
    assert request.engine_options["focused_engine"]["options"]["population_size"] == 14


def test_basin_scan_manifold_refocus_parses_nested_settings():
    model = make_narrow_basin_model(scan_config=manifold_refocus_basin_scan_config())
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="basin-manifold-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    manifold = request.engine_options["manifold_refocus"]
    assert manifold["enabled"] is True
    assert manifold["method"] == "covariance"
    assert manifold["source"] == "selected"
    assert manifold["n_candidates"] == 200
    assert manifold["box"]["quantile_low"] == pytest.approx(0.10)
    assert manifold["box"]["max_shrink_factor"] == pytest.approx(50.0)


def test_basin_scan_ml_focus_parses_nested_settings():
    model = make_narrow_basin_model(scan_config=ml_focus_basin_scan_config())
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="basin-ml-focus-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    ml_focus = request.engine_options["ml_focus"]
    assert ml_focus["enabled"] is True
    assert ml_focus["model"]["type"] == "extra_trees_regressor"
    assert ml_focus["model"]["n_estimators"] == 8
    assert ml_focus["training"]["target_transform"] == "log10_1p"
    assert ml_focus["candidate_generation"]["n_candidates"] == 200
    assert ml_focus["selection"]["n_ml_selected"] == 40
    assert ml_focus["seeds"]["max_seeds"] == 20


def test_ml_focus_feature_transform_respects_prior_bounds():
    model = ModelDefinition.from_mapping(
        {
            "metadata": {"name": "ml-focus-transform"},
            "parameters": [
                {"name": "flat", "value_type": "real", "scan": True, "lower": -2.0, "upper": 2.0, "default": 0.0},
                {"name": "logp", "value_type": "real", "scan": True, "lower": 1.0e-3, "upper": 1.0e3, "default": 1.0, "prior": "log"},
                {"name": "signed", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.1, "prior": "signed_log", "min_abs": 1.0e-6},
            ],
            "observables": [{"name": "objective", "expression": "flat**2 + logp"}],
            "likelihoods": [{"name": "term", "kind": "gaussian", "observable": "objective", "mean": 0.0, "sigma": 1.0}],
            "scan": basin_scan_config(n_points=10),
        }
    )
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled)
    points = np.asarray([[-2.0, 1.0e-3, -10.0], [0.0, 1.0, 0.0], [2.0, 1.0e3, 10.0]])

    transformed = _ml_focus_transform_values(points, request.scanned_parameters)

    assert transformed.shape == points.shape
    assert np.all(transformed >= 0.0)
    assert np.all(transformed <= 1.0)
    assert transformed[0, 0] == pytest.approx(0.0)
    assert transformed[-1, 0] == pytest.approx(1.0)
    assert transformed[0, 1] == pytest.approx(0.0)
    assert transformed[-1, 1] == pytest.approx(1.0)


def test_ml_focus_box_is_conservative_and_contains_known_minimum():
    model = make_narrow_basin_model(scan_config=ml_focus_basin_scan_config())
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled)
    lower = np.asarray([item.lower for item in request.scanned_parameters], dtype=float)
    upper = np.asarray([item.upper for item in request.scanned_parameters], dtype=float)
    options = request.engine_options
    candidate_cloud = np.asarray(
        [
            [2.8, -4.2],
            [3.0, -4.0],
            [3.1, -3.9],
            [3.2, -4.1],
            [2.9, -3.8],
        ],
        dtype=float,
    )

    box = _ml_focus_box_from_points(
        points=candidate_cloud,
        best_objective=0.0,
        lower=lower,
        upper=upper,
        request=request,
        options=options,
    )

    assert box is not None
    assert box["box_type"] == "ml_focus"
    assert box["lower"]["x"] <= 3.0 <= box["upper"]["x"]
    assert box["lower"]["y"] <= -4.0 <= box["upper"]["y"]
    assert -10.0 <= box["lower"]["x"] <= box["upper"]["x"] <= 10.0
    assert -10.0 <= box["lower"]["y"] <= box["upper"]["y"] <= 10.0
    assert 0.0 < box["relative_box_volume"] < 1.0


def test_basin_scan_ml_focus_writes_artifacts_when_sklearn_available(tmp_path):
    pytest.importorskip("sklearn")

    model = make_narrow_basin_model(scan_config=ml_focus_basin_scan_config())
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "ml-focus",
        run_id="basin-ml-focus",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    for filename in [
        "ml_focus_training.csv",
        "ml_focus_candidates.csv",
        "ml_focus_selected.csv",
        "ml_focus_box.json",
        "ml_focus_seeds.csv",
        "ml_focus_diagnostics.json",
    ]:
        assert (results.run_directory / filename).exists()
    diagnostics = json.loads((results.run_directory / "ml_focus_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["enabled"] is True
    assert diagnostics["focused_box_created"] is True
    box = json.loads((results.run_directory / "ml_focus_box.json").read_text(encoding="utf-8"))["box"]
    assert -10.0 <= box["lower"]["x"] <= box["upper"]["x"] <= 10.0
    assert -10.0 <= box["lower"]["y"] <= box["upper"]["y"] <= 10.0


def test_basin_scan_ml_focus_clear_error_without_sklearn(tmp_path):
    try:
        import sklearn  # noqa: F401
    except Exception:
        model = make_narrow_basin_model(scan_config=ml_focus_basin_scan_config())
        with pytest.raises(ModelValidationError, match="scikit-learn"):
            run_scan(
                model,
                compile_model(model, build_backend=False),
                run_directory=tmp_path / "ml-focus-no-sklearn",
                run_id="basin-ml-focus-no-sklearn",
                timestamp_utc=FIXED_TIMESTAMP,
            )
    else:
        pytest.skip("scikit-learn is installed; missing dependency path is not active")


def test_basin_scan_manifold_refocus_writes_artifacts_and_shrinks_box(tmp_path):
    model = make_narrow_basin_model(scan_config=manifold_refocus_basin_scan_config())
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "manifold-refocus",
        run_id="basin-manifold-refocus",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    for filename in [
        "manifold_refocus_training.csv",
        "manifold_refocus_candidates.csv",
        "manifold_refocus_box.json",
        "manifold_refocus_diagnostics.json",
    ]:
        assert (results.run_directory / filename).exists()
    diagnostics = json.loads((results.run_directory / "manifold_refocus_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["enabled"] is True
    assert diagnostics["box_created"] is True
    box = json.loads((results.run_directory / "manifold_refocus_box.json").read_text(encoding="utf-8"))["box"]
    assert box["box_type"] == "manifold_refocus"
    assert -10.0 <= box["lower"]["x"] < box["upper"]["x"] <= 10.0
    assert -10.0 <= box["lower"]["y"] < box["upper"]["y"] <= 10.0
    assert 0.0 < box["relative_box_volume"] < 1.0
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    assert summary["engine_details"]["manifold_refocus_enabled"] is True
    assert summary["engine_details"]["manifold_refocus_box_created"] is True


def test_basin_scan_manifold_refocus_feeds_ml_focus_when_both_enabled(tmp_path):
    pytest.importorskip("sklearn")

    model = make_narrow_basin_model(scan_config=manifold_refocus_basin_scan_config(with_ml_focus=True))
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "manifold-ml-focus",
        run_id="basin-manifold-ml-focus",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert (results.run_directory / "manifold_refocus_box.json").exists()
    assert (results.run_directory / "ml_focus_box.json").exists()
    basin_results = json.loads((results.run_directory / "basin_results.json").read_text(encoding="utf-8"))
    assert basin_results["manifold_refocus"]["box_created"] is True
    assert basin_results["ml_focus"]["focused_box_created"] is True
    ml_box = json.loads((results.run_directory / "ml_focus_box.json").read_text(encoding="utf-8"))["box"]
    assert -10.0 <= ml_box["lower"]["x"] < ml_box["upper"]["x"] <= 10.0
    assert -10.0 <= ml_box["lower"]["y"] < ml_box["upper"]["y"] <= 10.0


def test_basin_scan_discovers_narrow_basin_from_wide_box(tmp_path):
    model = make_narrow_basin_model()
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "narrow",
        run_id="basin-narrow",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))

    assert best_fit["has_best_point"] is True
    assert best_fit["best_metric_value"] < 1.0e-4
    assert best_fit["parameters"]["x"] == pytest.approx(3.0, abs=2.0e-2)
    assert best_fit["parameters"]["y"] == pytest.approx(-4.0, abs=2.0e-2)
    assert summary["engine_details"]["orchestrator"] == "basin_scan"
    assert summary["engine_details"]["focused_boxes"] >= 1

    for filename in [
        "points.csv",
        "exploration_points.csv",
        "selected_points.csv",
        "clusters.csv",
        "focused_boxes.json",
        "basin_results.json",
        "best_fit.json",
        "summary.json",
    ]:
        assert (results.run_directory / filename).exists()

    boxes = json.loads((results.run_directory / "focused_boxes.json").read_text(encoding="utf-8"))["boxes"]
    assert boxes
    for box in boxes:
        assert 0.0 < box["relative_box_volume"] <= 1.0
        assert -10.0 <= box["lower"]["x"] <= box["upper"]["x"] <= 10.0
        assert -10.0 <= box["lower"]["y"] <= box["upper"]["y"] <= 10.0
    assert not (results.run_directory / "progressive_exploration_summary.json").exists()


def test_basin_scan_writes_generic_likelihood_component_columns(tmp_path):
    model = make_narrow_basin_model()
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "like-components",
        run_id="basin-like-components",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    for filename in ["points.csv", "exploration_points.csv", "selected_points.csv"]:
        with (results.run_directory / filename).open(newline="") as handle:
            fieldnames = csv.DictReader(handle).fieldnames or []
        assert "like__x_term" in fieldnames
        assert "like__y_term" in fieldnames

    metadata = json.loads(results.metadata_path.read_text(encoding="utf-8"))
    assert metadata["likelihood_terms"] == ["x_term", "y_term"]
    assert metadata["point_component_columns"] == ["like__x_term", "like__y_term"]


def test_basin_scan_balanced_terms_selection_rejects_catastrophic_term():
    points = np.asarray([[0.0], [1.0], [2.0], [3.0]], dtype=float)
    totals = [10.0, 12.0, 20.0, 15.0]
    terms = [
        {"term_a": 9.0, "term_b": 30.0},
        {"term_a": 3.0, "term_b": 6.0},
        {"term_a": 8.0, "term_b": 31.0},
        {"term_a": 7.0, "term_b": 8.0},
    ]
    records = [
        {
            "valid": True,
            "scanner_target": total,
            "metric_value": total,
            "point_result": {"status": "ok", "total_nll": total, "likelihood_terms": term_payload},
        }
        for total, term_payload in zip(totals, terms, strict=True)
    ]
    selected_points, selected_records, selected_indices, diagnostics = _select_basin_points(
        points=points,
        records=records,
        invalid_objective=1.0e12,
        options={
            "selection": {
                "mode": "balanced_terms",
                "top_fraction": 1.0,
                "total_top_fraction": 1.0,
                    "term_quantile_cut": 0.50,
                "max_points": 4,
                "min_points": 1,
                "terms": "auto",
                "exclude_terms": [],
                "combine_with_top_fraction": True,
                "fallback_mode": "top_fraction",
                "chi2_window": 0.0,
            }
        },
        return_diagnostics=True,
    )

    assert 0 not in selected_indices.tolist()
    assert 1 in selected_indices.tolist()
    assert selected_points[0].tolist() == [1.0]
    assert selected_records[0]["point_result"]["likelihood_terms"] == {"term_a": 3.0, "term_b": 6.0}
    assert diagnostics["fallback_used"] is False
    assert diagnostics["likelihood_terms_used"] == ["term_a", "term_b"]
    assert diagnostics["thresholds"]["term_b"] < 30.0


def test_basin_scan_balanced_terms_falls_back_without_terms():
    points = np.asarray([[0.0], [1.0], [2.0]], dtype=float)
    records = [
        {
            "valid": True,
            "scanner_target": total,
            "metric_value": total,
            "point_result": {"status": "ok", "total_nll": total, "likelihood_terms": {}},
        }
        for total in [3.0, 1.0, 2.0]
    ]
    _, _, selected_indices, diagnostics = _select_basin_points(
        points=points,
        records=records,
        invalid_objective=1.0e12,
        options={
            "selection": {
                "mode": "balanced_terms",
                "top_fraction": 1.0 / 3.0,
                "total_top_fraction": 1.0,
                "term_quantile_cut": 0.30,
                "max_points": 2,
                "min_points": 1,
                "terms": "auto",
                "exclude_terms": [],
                "combine_with_top_fraction": True,
                "fallback_mode": "top_fraction",
                "chi2_window": 0.0,
            }
        },
        return_diagnostics=True,
    )

    assert selected_indices.tolist() == [1]
    assert diagnostics["fallback_used"] is True
    assert diagnostics["fallback_reason"] == "no_likelihood_terms_available"


def test_basin_scan_can_rank_two_disconnected_basins(tmp_path):
    model = make_two_basin_model()
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "two-basins",
        run_id="basin-two",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    payload = json.loads((results.run_directory / "basin_results.json").read_text(encoding="utf-8"))
    assert payload["n_focused_boxes"] >= 2
    best = payload["ranked_results"][0]["parameters"]
    assert abs(abs(best["x"]) - 3.0) < 5.0e-2
    assert abs(best["y"]) < 5.0e-2


def test_basin_scan_handles_invalid_exploration_regions(tmp_path):
    model = make_narrow_basin_model(invalid_region=True)
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "invalid",
        run_id="basin-invalid",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))

    assert summary["failure_counters"]["invalid_point"] > 0
    assert best_fit["has_best_point"] is True
    assert best_fit["parameters"]["x"] > -4.0

    with (results.run_directory / "exploration_points.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["status"] == "ok" and row["valid"] == "false" for row in rows)


def test_basin_scan_progressive_exploration_writes_round_artifacts(tmp_path):
    model = make_narrow_basin_model(scan_config=progressive_basin_scan_config())
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "progressive",
        run_id="basin-progressive",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    summary_path = results.run_directory / "progressive_exploration_summary.json"
    round_dir = results.run_directory / "progressive_exploration"
    assert summary_path.exists()
    assert (round_dir / "round_00_points.csv").exists()
    assert (round_dir / "round_00_selected.csv").exists()
    assert (round_dir / "round_00_boxes.json").exists()
    assert (round_dir / "round_01_points.csv").exists()
    assert (round_dir / "round_01_selected.csv").exists()
    assert (round_dir / "round_01_boxes.json").exists()
    assert (results.run_directory / "selected_points.csv").exists()
    assert (results.run_directory / "best_fit.json").exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["enabled"] is True
    assert summary["n_rounds"] == 2
    assert summary["final_selected_count"] > 0
    assert "global_best_objective" in summary
    round_best = [round_info["global_best_objective_after_round"] for round_info in summary["rounds"]]
    assert round_best == sorted(round_best, reverse=True)
    scan_summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    assert scan_summary["engine_details"]["progressive_exploration_enabled"] is True

    with (round_dir / "round_01_points.csv").open(newline="") as handle:
        source_types = {row["source_type"] for row in csv.DictReader(handle)}
    assert "global" in source_types
    assert {"selected_cloud", "elite", "best_centered"} & source_types


def test_basin_scan_progressive_balanced_terms_writes_selection_summaries(tmp_path):
    model = make_narrow_basin_model(scan_config=progressive_balanced_basin_scan_config())
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "progressive-balanced",
        run_id="basin-progressive-balanced",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    round_dir = results.run_directory / "progressive_exploration"
    round_summary_path = round_dir / "round_00_selection_summary.json"
    assert round_summary_path.exists()
    summary = json.loads(round_summary_path.read_text(encoding="utf-8"))
    assert summary["mode"] == "balanced_terms"
    assert summary["likelihood_terms_used"] == ["x_term", "y_term"]
    assert summary["thresholds"]

    progressive_summary = json.loads(
        (results.run_directory / "progressive_exploration_summary.json").read_text(encoding="utf-8")
    )
    assert progressive_summary["rounds"][0]["selection_summary"]["mode"] == "balanced_terms"

    with (round_dir / "round_00_points.csv").open(newline="") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    assert "like__x_term" in fieldnames
    assert "like__y_term" in fieldnames


def test_basin_scan_applies_final_selection_after_progressive_exploration(tmp_path):
    config = progressive_basin_scan_config()
    config["basin_scan"]["progressive_exploration"]["selection"] = {
        "mode": "top_fraction",
        "top_fraction": 0.80,
        "max_points": 80,
    }
    config["basin_scan"]["selection"] = {
        "mode": "top_fraction",
        "top_fraction": 0.80,
        "max_points": 5,
    }
    model = make_narrow_basin_model(scan_config=config)
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "progressive-final-selection",
        run_id="basin-progressive-final-selection",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    summary = json.loads((results.run_directory / "selection_summary.json").read_text(encoding="utf-8"))
    assert summary["source"] == "post_progressive_final_selection"
    assert summary["progressive_final_selected_count_before_final_selection"] > summary["final_selected_count"]
    assert summary["final_selected_count"] == 5

    with (results.run_directory / "selected_points.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5


def test_basin_scan_progressive_boxes_are_nonzero_and_inside_bounds(tmp_path):
    model = make_narrow_basin_model(scan_config=progressive_basin_scan_config())
    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "progressive-bounds",
        run_id="basin-progressive-bounds",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    round_dir = results.run_directory / "progressive_exploration"
    volumes_by_round = []
    for round_index in [0, 1]:
        payload = json.loads((round_dir / f"round_{round_index:02d}_boxes.json").read_text(encoding="utf-8"))
        volumes = [box["relative_box_volume"] for box in payload["boxes"]]
        assert volumes
        box_types = {box["box_type"] for box in payload["boxes"]}
        assert "selected_cloud" in box_types
        assert "best_centered" in box_types
        volumes_by_round.append(volumes)
        for box in payload["boxes"]:
            assert 0.0 < box["relative_box_volume"] <= 1.0
            assert -10.0 <= box["lower"]["x"] <= box["upper"]["x"] <= 10.0
            assert -10.0 <= box["lower"]["y"] <= box["upper"]["y"] <= 10.0
            if box["box_type"] == "best_centered":
                assert box["contains_global_best"] is True

    assert min(volumes_by_round[-1]) <= max(volumes_by_round[0])

    for points_file in sorted(round_dir.glob("round_*_points.csv")):
        with points_file.open(newline="") as handle:
            for row in csv.DictReader(handle):
                assert -10.0 <= float(row["param::x"]) <= 10.0
                assert -10.0 <= float(row["param::y"]) <= 10.0


def test_basin_scan_proposal_layer_writes_diagnostics_and_respects_bounds(tmp_path):
    config = basin_scan_config(n_points=40, top_fraction=0.3, max_clusters=1)
    config["basin_scan"]["proposals"] = {
        "enabled": True,
        "stages": [
            {
                "name": "targeted_prior",
                "type": "prior_profile",
                "probability": 1.0,
                "parameters": [
                    {"name": "x", "mean": 3.0, "sigma": 0.02},
                    {"name": "y", "mean": -4.0, "sigma": 0.02},
                ],
            }
        ],
    }
    model = make_narrow_basin_model(scan_config=config)

    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "proposal",
        run_id="basin-proposal",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    proposal_summary = json.loads(
        (results.run_directory / "proposal_summary.json").read_text(encoding="utf-8")
    )
    assert proposal_summary["enabled"] is True
    assert proposal_summary["applications"]["targeted_prior"] == 40
    with (results.run_directory / "exploration_points.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["proposal_used"] == "targeted_prior" for row in rows)
    assert all(-10.0 <= float(row["param::x"]) <= 10.0 for row in rows)
    assert all(-10.0 <= float(row["param::y"]) <= 10.0 for row in rows)


def test_basin_scan_guided_sampling_point_function_from_model_block(tmp_path):
    hook_path = tmp_path / "guided_hook.py"
    hook_path.write_text(
        "\n".join(
            [
                "def move_point(point, rng=None, options=None, context=None):",
                "    point['x'] = options.get('x_target', 1.25)",
                "    point['y'] = options.get('y_target', -2.5)",
                "    return point",
            ]
        ),
        encoding="utf-8",
    )
    config = basin_scan_config(n_points=16, top_fraction=0.5, max_clusters=1)
    model = ModelDefinition.from_mapping(
        {
            "metadata": {"name": "guided-sampling-hook"},
            "parameters": [
                {"name": "x", "value_type": "real", "scan": True, "lower": -5.0, "upper": 5.0, "default": 0.0},
                {"name": "y", "value_type": "real", "scan": True, "lower": -5.0, "upper": 5.0, "default": 0.0},
            ],
            "observables": [
                {"name": "x_obs", "expression": "x"},
                {"name": "y_obs", "expression": "y"},
            ],
            "likelihoods": [
                {"name": "x_term", "kind": "gaussian", "observable": "x_obs", "mean": 1.25, "sigma": 0.1},
                {"name": "y_term", "kind": "gaussian", "observable": "y_obs", "mean": -2.5, "sigma": 0.1},
            ],
            "outputs": {"save": ["x_obs", "y_obs"]},
            "guided_sampling": {
                "enabled": True,
                "apply_to": ["exploration"],
                "stages": [
                    {
                        "name": "toy_hook",
                        "type": "point_function",
                        "probability": 1.0,
                        "function": f"{hook_path}:move_point",
                        "options": {"x_target": 1.25, "y_target": -2.5},
                    }
                ],
            },
            "scan": config,
        }
    )

    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "guided-hook",
        run_id="guided-hook",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    proposal_summary = json.loads(
        (results.run_directory / "proposal_summary.json").read_text(encoding="utf-8")
    )
    assert proposal_summary["enabled"] is True
    assert proposal_summary["applications"]["toy_hook"] == 16
    with (results.run_directory / "exploration_points.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {row["proposal_used"] for row in rows} == {"toy_hook"}
    assert all(float(row["param::x"]) == pytest.approx(1.25) for row in rows)
    assert all(float(row["param::y"]) == pytest.approx(-2.5) for row in rows)


def test_basin_scan_guided_sampling_complex_vector_norm_is_complex_norm(tmp_path):
    config = basin_scan_config(n_points=12, top_fraction=0.5, max_clusters=1)
    model = ModelDefinition.from_mapping(
        {
            "metadata": {"name": "guided-complex-vector"},
            "parameters": [
                {"name": "ar1", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
                {"name": "ai1", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
                {"name": "ar2", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
                {"name": "ai2", "value_type": "real", "scan": True, "lower": -10.0, "upper": 10.0, "default": 0.0},
            ],
            "observables": [
                {"name": "norm_obs", "expression": "ar1**2 + ai1**2 + ar2**2 + ai2**2"},
            ],
            "likelihoods": [
                {"name": "norm_term", "kind": "gaussian", "observable": "norm_obs", "mean": 4.0, "sigma": 0.5},
            ],
            "outputs": {"save": ["norm_obs"]},
            "guided_sampling": {
                "enabled": True,
                "stages": [
                    {
                        "name": "complex_norm",
                        "type": "complex_vector_norm",
                        "probability": 1.0,
                        "vectors": [
                            {
                                "components": {"real": ["ar1", "ar2"], "imag": ["ai1", "ai2"]},
                                "norm_range": [2.0, 2.0],
                            }
                        ],
                    }
                ],
            },
            "scan": config,
        }
    )

    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "guided-complex",
        run_id="guided-complex",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    with (results.run_directory / "exploration_points.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        norm = sum(
            float(row[f"param::{name}"]) ** 2
            for name in ("ar1", "ai1", "ar2", "ai2")
        )
        assert norm == pytest.approx(4.0)


def test_basin_scan_staged_policy_and_refinement_write_artifacts(tmp_path):
    config = basin_scan_config(n_points=30, top_fraction=0.3, max_clusters=1)
    config["basin_scan"]["staged_evaluation"] = {
        "enabled": True,
        "cheap_stage": {"include_terms": ["x_term"]},
        "expensive_stage": {"include_terms": ["y_term"]},
        "full_eval_policy": {
            "max_cheap_objective": 1000000.0,
            "require_no_hard_failures": True,
        },
    }
    config["basin_scan"]["refinement"] = {
        "enabled": True,
        "n_rounds": 1,
        "points_per_seed": 2,
        "max_seeds": 3,
        "jitter_fraction": 0.02,
        "apply_proposals": False,
    }
    model = make_narrow_basin_model(scan_config=config)

    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "staged-refinement",
        run_id="basin-staged-refinement",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    staged = json.loads(
        (results.run_directory / "staged_evaluation_summary.json").read_text(encoding="utf-8")
    )
    assert staged["enabled"] is True
    assert staged["cheap_terms"] == ["x_term"]
    assert staged["full_candidates"] + staged["cheap_rejections"] == 30
    assert (results.run_directory / "refinement_points.csv").exists()
    refinement = json.loads(
        (results.run_directory / "refinement_summary.json").read_text(encoding="utf-8")
    )
    assert refinement["enabled"] is True
    assert refinement["evaluated_points"] == 6
    with (results.run_directory / "refinement_points.csv").open(newline="") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    assert "objective_cheap" in fieldnames
    assert "objective_full" in fieldnames
    assert "stage_reached" in fieldnames


def test_basin_scan_staged_evaluation_skips_excluded_expensive_plugin(tmp_path):
    config = basin_scan_config(n_points=2, top_fraction=0.5, max_clusters=1)
    config["basin_scan"]["staged_evaluation"] = {
        "enabled": True,
        "cheap_stage": {
            "include_terms": ["cheap_term"],
            "exclude_outputs": ["expensive_obs"],
        },
        "expensive_stage": {"include_terms": ["expensive_term"]},
        "full_eval_policy": {
            "max_cheap_objective": 0.0,
            "require_no_hard_failures": True,
        },
        "save_rejected_cheap_points": False,
    }
    model = ModelDefinition.from_mapping(
        {
            "metadata": {"name": "basin-scan-staged-skip-expensive"},
            "parameters": [
                {"name": "x", "value_type": "real", "scan": True, "lower": -1.0, "upper": 1.0, "default": 0.0},
            ],
            "observables": [
                {"name": "cheap_obs", "expression": "x"},
                {
                    "name": "expensive_obs",
                    "value_type": "real",
                    "plugin_call": {
                        "plugin": "definitely_missing_plugin",
                        "function": "expensive",
                        "bindings": {"x": "x"},
                    },
                },
            ],
            "likelihoods": [
                {"name": "cheap_term", "kind": "gaussian", "observable": "cheap_obs", "mean": 1.0, "sigma": 0.1},
                {"name": "expensive_term", "kind": "gaussian", "observable": "expensive_obs", "mean": 0.0, "sigma": 1.0},
            ],
            "outputs": {"save": ["cheap_obs", "expensive_obs"]},
            "scan": config,
        }
    )
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(
        model,
        compiled,
        run_directory=tmp_path / "staged-skip-expensive",
        run_id="staged-skip-expensive",
        timestamp_utc=FIXED_TIMESTAMP,
    )
    writer = _PythonScanArtifactsWriter(request)
    try:
        objective = _AdaptiveDiverObjective(compiled, request, writer)
        context = _build_staged_evaluation_context(model, request, request.engine_options)
        records = _evaluate_basin_points(
            objective=objective,
            points=np.asarray([[0.0]], dtype=float),
            request=request,
            options=request.engine_options,
            label="test",
            staged_context=context,
        )
    finally:
        writer.close()

    assert records[0]["stage_reached"] == "cheap_rejected"
    assert records[0]["point_result"]["status"] == "ok"
    assert "expensive_term" not in records[0]["point_result"]["likelihood_terms"]
    assert objective.evaluations == 1
    assert objective.valid_points == 0
    assert objective.best_record is None


def test_adaptive_diver_initial_population_seeds_replace_random_rows():
    population = np.zeros((3, 2), dtype=float)
    seeds = [[2.0, -2.0], [10.0, -10.0]]
    seeded, count = _apply_initial_population_seeds(
        population,
        seeds=seeds,
        lower=np.asarray([-5.0, -5.0]),
        upper=np.asarray([5.0, 5.0]),
    )

    assert count == 2
    assert seeded[0].tolist() == [2.0, -2.0]
    assert seeded[1].tolist() == [5.0, -5.0]
    assert seeded[2].tolist() == [0.0, 0.0]


def test_basin_scan_near_miss_keeps_likelihood_term_champions():
    points = np.asarray([[0.0], [1.0], [2.0]], dtype=float)
    records = [
        {
            "valid": True,
            "scanner_target": total,
            "metric_value": total,
            "hard_failures": 0,
            "fit_failures": 1,
            "stage_reached": "full",
            "point_result": {
                "status": "ok",
                "total_nll": total,
                "likelihood_terms": terms,
            },
        }
        for total, terms in [
            (1.0, {"term_a": 0.9, "term_b": 0.1}),
            (2.0, {"term_a": 0.01, "term_b": 1.99}),
            (3.0, {"term_a": 1.5, "term_b": 1.5}),
        ]
    ]

    _, _, selected_indices, diagnostics = _select_basin_points(
        points=points,
        records=records,
        invalid_objective=1.0e12,
        options={
            "selection": {
                "mode": "top_fraction",
                "top_fraction": 1.0 / 3.0,
                "total_top_fraction": 1.0 / 3.0,
                "term_quantile_cut": 0.3,
                "max_points": 3,
                "min_points": 1,
                "terms": "auto",
                "exclude_terms": [],
                "combine_with_top_fraction": True,
                "fallback_mode": "top_fraction",
                "chi2_window": 0.0,
                "near_miss": {
                    "enabled": True,
                    "max_hard_failures": 0,
                    "max_fit_failures": 3,
                    "objective_cap": 10.0,
                    "include_full_eval_points": True,
                },
            }
        },
        return_diagnostics=True,
    )

    assert 0 in selected_indices
    assert 1 in selected_indices
    assert diagnostics["near_miss_enabled"] is True
    assert diagnostics["near_miss_added"] >= 1


def test_basin_scan_near_miss_can_keep_invalid_diagnostic_rows():
    points = np.asarray([[0.0], [1.0]], dtype=float)
    records = [
        {
            "valid": False,
            "scanner_target": 9.0,
            "metric_value": 9.0,
            "hard_failures": 1,
            "fit_failures": 0,
            "stage_reached": "cheap_rejected",
            "point_result": {
                "status": "ok",
                "failure_reason": "near_theory_boundary",
                "total_nll": 9.0,
                "likelihood_terms": {"term_a": 0.1, "term_b": 8.9},
            },
        },
        {
            "valid": False,
            "scanner_target": 12.0,
            "metric_value": 12.0,
            "hard_failures": 1,
            "fit_failures": 0,
            "stage_reached": "cheap_rejected",
            "point_result": {
                "status": "ok",
                "failure_reason": "near_fit_boundary",
                "total_nll": 12.0,
                "likelihood_terms": {"term_a": 10.0, "term_b": 2.0},
            },
        },
    ]

    _, selected_records, selected_indices, diagnostics = _select_basin_points(
        points=points,
        records=records,
        invalid_objective=1.0e12,
        options={
            "selection": {
                "mode": "top_fraction",
                "top_fraction": 0.5,
                "total_top_fraction": 0.5,
                "term_quantile_cut": 0.3,
                "max_points": 2,
                "min_points": 1,
                "terms": "auto",
                "exclude_terms": [],
                "combine_with_top_fraction": True,
                "fallback_mode": "top_fraction",
                "chi2_window": 0.0,
                "near_miss": {
                    "enabled": True,
                    "include_invalid": True,
                    "max_hard_failures": 1,
                    "max_fit_failures": 0,
                    "objective_cap": 20.0,
                    "include_full_eval_points": False,
                    "keep_accepted": True,
                    "keep_per_term_best": True,
                    "max_accepted_points": 10,
                    "max_near_miss_points": 10,
                },
            }
        },
        return_diagnostics=True,
    )

    assert set(selected_indices.tolist()) == {0, 1}
    assert all(not record["valid"] for record in selected_records)
    assert diagnostics["near_miss_include_invalid"] is True
    assert diagnostics["near_miss_candidate_count"] == 2
    assert diagnostics["near_miss_added"] == 2


def test_basin_scan_writes_accepted_and_near_miss_artifacts(tmp_path):
    config = basin_scan_config(n_points=50, top_fraction=0.2, max_clusters=1)
    config["basin_scan"]["selection"]["near_miss"] = {
        "enabled": True,
        "keep_accepted": True,
        "keep_per_term_best": True,
        "max_hard_failures": 0,
        "max_fit_failures": 3,
        "objective_cap": 1.0e6,
        "include_full_eval_points": True,
    }
    model = make_narrow_basin_model(scan_config=config)

    results = run_scan(
        model,
        compile_model(model, build_backend=False),
        run_directory=tmp_path / "near-miss-artifacts",
        run_id="near-miss-artifacts",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert (results.run_directory / "accepted_points.csv").exists()
    assert (results.run_directory / "near_miss_points.csv").exists()
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    assert summary["engine_details"]["accepted_points_path"] == "accepted_points.csv"
    assert summary["engine_details"]["near_miss_points_path"] == "near_miss_points.csv"
    selection_summary = json.loads(
        (results.run_directory / "selection_summary.json").read_text(encoding="utf-8")
    )
    assert selection_summary["near_miss_enabled"] is True
