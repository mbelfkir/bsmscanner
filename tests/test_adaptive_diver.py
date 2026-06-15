from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from bsm_scanner import compile_model, run_scan
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.scan import build_scan_request


pytest.importorskip("bsm_scanner._core")


FIXED_TIMESTAMP = "2026-05-21T00:00:00+00:00"


def make_quadratic_model(*, invalid_region: bool = False, local_refinement: bool = False) -> ModelDefinition:
    theory_checks = []
    if invalid_region:
        theory_checks.append(
            {
                "name": "x_valid",
                "condition": "x > 0.5",
                "message": "x deliberately invalid below 0.5",
            }
        )
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": "adaptive-diver-quadratic"},
            "parameters": [
                {
                    "name": "x",
                    "value_type": "real",
                    "scan": True,
                    "lower": -5.0,
                    "upper": 5.0,
                    "default": 0.0,
                    "prior": "flat",
                },
                {
                    "name": "y",
                    "value_type": "real",
                    "scan": True,
                    "lower": -5.0,
                    "upper": 5.0,
                    "default": 0.0,
                    "prior": "flat",
                },
            ],
            "observables": [
                {"name": "x_obs", "expression": "x"},
                {"name": "y_obs", "expression": "y"},
            ],
            "theory_checks": theory_checks,
            "likelihoods": [
                {
                    "name": "x_term",
                    "kind": "gaussian",
                    "observable": "x_obs",
                    "mean": 1.0,
                    "sigma": 1.0,
                },
                {
                    "name": "y_term",
                    "kind": "gaussian",
                    "observable": "y_obs",
                    "mean": -2.0,
                    "sigma": 1.0,
                },
            ],
            "outputs": {"save": ["x_obs", "y_obs"]},
            "scan": {
                "engine": "adaptive_diver",
                "save_every": 1,
                "seed": 2468,
                "settings": {
                    "objective": "nll",
                    "invalid_penalty": 1.0e12,
                    "save_invalid_points": True,
                    "verbose": 0,
                },
                "adaptive_diver": {
                    "population_size": 12,
                    "max_generations": 30,
                    "p_best_fraction": 0.25,
                    "archive": True,
                    "mutation": {
                        "F_min": 0.1,
                        "F_max": 1.0,
                        "initial_mean": 0.5,
                        "learning_rate": 0.1,
                    },
                    "crossover": {
                        "CR_min": 0.0,
                        "CR_max": 1.0,
                        "initial_mean": 0.9,
                        "learning_rate": 0.1,
                    },
                    "bounds": {"handling": "reflect"},
                    "convergence": {
                        "patience": 0,
                        "population_std_tol": 0.0,
                    },
                    "local_refinement": {
                        "enabled": local_refinement,
                        "method": "Powell",
                        "n_elites": 2,
                        "maxiter": 80,
                    },
                    "statistics": {"enabled": True},
                    "output": {
                        "save_history": True,
                        "save_population": True,
                        "save_elites": True,
                    },
                },
            },
        }
    )


def make_tight_bounds_model(*, local_method: str) -> ModelDefinition:
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": f"adaptive-diver-tight-bounds-{local_method}"},
            "parameters": [
                {
                    "name": "x",
                    "value_type": "real",
                    "scan": True,
                    "lower": 0.0,
                    "upper": 0.1,
                    "default": 0.05,
                    "prior": "flat",
                },
                {
                    "name": "y",
                    "value_type": "real",
                    "scan": True,
                    "lower": -0.1,
                    "upper": 0.0,
                    "default": -0.05,
                    "prior": "flat",
                },
            ],
            "observables": [
                {"name": "x_obs", "expression": "x"},
                {"name": "y_obs", "expression": "y"},
            ],
            "likelihoods": [
                {
                    "name": "x_term",
                    "kind": "gaussian",
                    "observable": "x_obs",
                    "mean": 1.0,
                    "sigma": 1.0,
                },
                {
                    "name": "y_term",
                    "kind": "gaussian",
                    "observable": "y_obs",
                    "mean": -2.0,
                    "sigma": 1.0,
                },
            ],
            "outputs": {"save": ["x_obs", "y_obs"]},
            "scan": {
                "engine": "adaptive_diver",
                "save_every": 1,
                "seed": 13579,
                "settings": {
                    "objective": "nll",
                    "invalid_penalty": 1.0e12,
                    "save_invalid_points": True,
                    "verbose": 0,
                },
                "adaptive_diver": {
                    "population_size": 8,
                    "max_generations": 5,
                    "p_best_fraction": 0.25,
                    "archive": True,
                    "bounds": {"handling": "reflect"},
                    "convergence": {"patience": 0, "population_std_tol": 0.0},
                    "local_refinement": {
                        "enabled": True,
                        "method": local_method,
                        "n_elites": 3,
                        "maxiter": 80,
                    },
                    "statistics": {"enabled": True},
                    "output": {
                        "save_history": True,
                        "save_population": True,
                        "save_elites": True,
                    },
                },
            },
        }
    )


def make_ab_gaussian_model() -> ModelDefinition:
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": "adaptive-diver-ab-gaussian"},
            "parameters": [
                {
                    "name": "a",
                    "value_type": "real",
                    "scan": True,
                    "lower": -3.0,
                    "upper": 3.0,
                    "default": 0.0,
                    "prior": "flat",
                },
                {
                    "name": "b",
                    "value_type": "real",
                    "scan": True,
                    "lower": -3.0,
                    "upper": 3.0,
                    "default": 0.0,
                    "prior": "flat",
                },
            ],
            "observables": [
                {"name": "a_obs", "expression": "a"},
                {"name": "b_obs", "expression": "b"},
            ],
            "likelihoods": [
                {
                    "name": "a_gaussian",
                    "kind": "gaussian",
                    "observable": "a_obs",
                    "mean": 1.2,
                    "sigma": 0.25,
                },
                {
                    "name": "b_gaussian",
                    "kind": "gaussian",
                    "observable": "b_obs",
                    "mean": -0.8,
                    "sigma": 0.4,
                },
            ],
            "outputs": {"save": ["a_obs", "b_obs"]},
            "scan": {
                "engine": "adaptive_diver",
                "save_every": 1,
                "seed": 9876,
                "settings": {
                    "objective": "nll",
                    "invalid_penalty": 1.0e12,
                    "save_invalid_points": True,
                    "verbose": 0,
                },
                "adaptive_diver": {
                    "population_size": 16,
                    "max_generations": 50,
                    "p_best_fraction": 0.25,
                    "archive": True,
                    "bounds": {"handling": "reflect"},
                    "convergence": {"patience": 0, "population_std_tol": 0.0},
                    "local_refinement": {"enabled": False},
                    "statistics": {"enabled": True},
                    "output": {
                        "save_history": True,
                        "save_population": True,
                        "save_elites": True,
                    },
                },
            },
        }
    )


def assert_tight_bounds_row(row: dict[str, str]) -> None:
    assert 0.0 <= float(row["param::x"]) <= 0.1
    assert -0.1 <= float(row["param::y"]) <= 0.0


def test_adaptive_diver_registered_and_parses_nested_settings():
    model = make_quadratic_model()
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="adaptive-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert request.engine == "adaptive_diver"
    assert request.engine_options["strategy"] == "current_to_pbest"
    assert request.engine_options["population_size"] == 12
    assert request.engine_options["max_generations"] == 30
    assert request.engine_options["bounds_handling"] == "reflect"
    assert request.engine_options["adaptive_statistics"] is True


def test_adaptive_de_alias_selects_adaptive_diver():
    model = make_quadratic_model()
    model.scan.engine = "adaptive_de"
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="adaptive-alias",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert request.engine == "adaptive_diver"


def test_adaptive_diver_quadratic_improves_and_writes_outputs(tmp_path):
    model = make_quadratic_model()
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "adaptive",
        run_id="adaptive-quadratic",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))

    assert best_fit["has_best_point"] is True
    assert best_fit["best_metric_value"] < 1.0e-3
    assert best_fit["parameters"]["x"] == pytest.approx(1.0, abs=0.08)
    assert best_fit["parameters"]["y"] == pytest.approx(-2.0, abs=0.08)
    assert summary["engine_details"]["native_backend"] == "adaptive_diver"
    assert summary["engine_details"]["stop_reason"] == "max_generations"
    assert (results.run_directory / "history.json").exists()
    assert (results.run_directory / "final_population.csv").exists()
    assert (results.run_directory / "elite_points.csv").exists()
    assert (results.run_directory / "parameter_summary.json").exists()
    assert (results.run_directory / "correlation_matrix.json").exists()

    with results.points_path.open(newline="") as handle:
        point_rows = list(csv.DictReader(handle))
    with (results.run_directory / "history.json").open() as handle:
        history = json.load(handle)
    metadata = json.loads(results.metadata_path.read_text(encoding="utf-8"))

    assert point_rows
    assert {"evaluation", "status", "valid", "metric_value", "param::x", "param::y"} <= set(point_rows[0])
    assert history
    assert {"generation", "best_scanner_target", "mu_F", "mu_CR", "evaluations"} <= set(history[0])
    assert metadata["engine"] == "adaptive_diver"
    assert metadata["engine_options"]["population_size"] == 12


def test_adaptive_diver_two_parameter_gaussian_fit_recovers_a_b(tmp_path):
    model = make_ab_gaussian_model()
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "ab-gaussian",
        run_id="adaptive-ab-gaussian",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))

    assert best_fit["has_best_point"] is True
    assert best_fit["best_metric_value"] < 1.0e-8
    assert best_fit["parameters"]["a"] == pytest.approx(1.2, abs=1.0e-4)
    assert best_fit["parameters"]["b"] == pytest.approx(-0.8, abs=1.0e-4)
    assert best_fit["outputs"]["a_obs"] == pytest.approx(1.2, abs=1.0e-4)
    assert best_fit["outputs"]["b_obs"] == pytest.approx(-0.8, abs=1.0e-4)
    assert best_fit["likelihood_terms"]["a_gaussian"] < 1.0e-8
    assert best_fit["likelihood_terms"]["b_gaussian"] < 1.0e-8
    assert (results.run_directory / "final_population.csv").exists()
    assert (results.run_directory / "elite_points.csv").exists()


def test_adaptive_diver_respects_bounds_in_final_population(tmp_path):
    model = make_quadratic_model()
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "bounds",
        run_id="adaptive-bounds",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    with (results.run_directory / "final_population.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    for row in rows:
        assert -5.0 <= float(row["param::x"]) <= 5.0
        assert -5.0 <= float(row["param::y"]) <= 5.0


def test_adaptive_diver_invalid_points_do_not_crash(tmp_path):
    model = make_quadratic_model(invalid_region=True)
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "invalid",
        run_id="adaptive-invalid",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    assert summary["evaluations"] > 0
    assert summary["valid_points"] > 0
    assert summary["failure_counters"]["invalid_point"] > 0

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["status"] == "ok" and row["valid"] == "false" for row in rows)


def test_adaptive_diver_optional_local_refinement_writes_artifact(tmp_path):
    pytest.importorskip("scipy.optimize")
    model = make_quadratic_model(local_refinement=True)
    model.scan.adaptive_diver["max_generations"] = 2
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "local",
        run_id="adaptive-local",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert (results.run_directory / "local_refinement.json").exists()
    payload = json.loads((results.run_directory / "local_refinement.json").read_text(encoding="utf-8"))
    assert payload["enabled"] is True
    assert payload["results"]


@pytest.mark.parametrize("local_method", ["Powell", "L-BFGS-B"])
def test_adaptive_diver_aggressive_bounds_and_local_refinement_outputs(local_method, tmp_path):
    pytest.importorskip("scipy.optimize")
    model = make_tight_bounds_model(local_method=local_method)
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / f"tight-{local_method}",
        run_id=f"adaptive-tight-{local_method}",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))
    assert 0.0 <= float(best_fit["parameters"]["x"]) <= 0.1
    assert -0.1 <= float(best_fit["parameters"]["y"]) <= 0.0

    for filename in ["points.csv", "final_population.csv", "elite_points.csv"]:
        with (results.run_directory / filename).open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        for row in rows:
            assert_tight_bounds_row(row)

    local_payload = json.loads((results.run_directory / "local_refinement.json").read_text(encoding="utf-8"))
    assert local_payload["enabled"] is True
    for item in local_payload["results"]:
        parameters = item.get("parameters")
        if not parameters:
            continue
        assert 0.0 <= float(parameters["x"]) <= 0.1
        assert -0.1 <= float(parameters["y"]) <= 0.0


def test_existing_engines_still_available():
    de_model = make_quadratic_model()
    de_model.scan.engine = "de_scipy"
    de_model.scan.adaptive_diver = {}
    de_model.scan.settings.update(
        {
            "strategy": "rand1bin",
            "maxiter": 1,
            "popsize": 4,
            "tol": 0.01,
            "atol": 0.0,
            "mutation": [0.5, 1.0],
            "recombination": 0.7,
            "init": "latinhypercube",
            "updating": "deferred",
            "workers": 1,
            "polish": False,
        }
    )
    serial_model = make_quadratic_model()
    serial_model.scan.engine = "serial_random"
    serial_model.scan.adaptive_diver = {}
    serial_model.scan.settings["max_evaluations"] = 2

    de_request = build_scan_request(
        de_model,
        compile_model(de_model, build_backend=False),
        run_directory=Path("unused"),
        run_id="de-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )
    serial_request = build_scan_request(
        serial_model,
        compile_model(serial_model, build_backend=False),
        run_directory=Path("unused"),
        run_id="serial-request",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert de_request.engine == "de_scipy"
    assert serial_request.engine == "serial_random"
