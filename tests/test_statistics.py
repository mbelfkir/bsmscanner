from __future__ import annotations

import csv
import json
from math import exp
from types import SimpleNamespace

import pytest
from bsm_scanner import compile_model, run_scan, run_statistics
from bsm_scanner.model.schema import ModelDefinition, StatisticsSpec
from bsm_scanner.statistics import normalize_shifted_weights, weighted_quantile

pytest.importorskip("bsm_scanner._core")


def test_weighted_quantile_handles_uniform_nonuniform_and_single_point():
    assert weighted_quantile([0.0, 1.0, 2.0], [1.0, 1.0, 1.0], 0.5) == pytest.approx(1.0)
    assert weighted_quantile([0.0, 1.0, 2.0], [0.1, 0.8, 0.1], 0.5) == pytest.approx(1.0)
    assert weighted_quantile([7.5], [1.0], 0.16) == pytest.approx(7.5)


def test_weight_normalization_is_stable_for_large_chi2():
    weights, chi2_min = normalize_shifted_weights([1000.0, 1002.0, 1010.0])

    assert chi2_min == pytest.approx(1000.0)
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] == max(weights)
    assert weights[0] == pytest.approx(1.0 / (1.0 + exp(-1.0) + exp(-5.0)))


def test_statistics_runner_writes_summary_and_intervals(tmp_path):
    run_dir = tmp_path / "scan"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "engine": "de_scipy",
                "objective_mode": "nll",
                "scanned_parameters": [{"name": "x"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    with (run_dir / "points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "evaluation",
                "status",
                "valid",
                "failure_reason",
                "scanner_target",
                "metric_value",
                "total_nll",
                "param::x",
                "output::x_obs",
            ]
        )
        writer.writerow([1, "ok", "true", "", 0.0, 0.0, 0.0, 0.0, 0.0])
        writer.writerow([2, "ok", "true", "", 2.0, 2.0, 2.0, 1.0, 1.0])
        writer.writerow([3, "ok", "true", "", 8.0, 8.0, 8.0, 2.0, 2.0])
        writer.writerow([4, "ok", "false", "bad", 1.0e12, 1.0e12, 1.0e12, 3.0, 3.0])
        writer.writerow([5, "ok", "false", "bad", 3.0, 3.0, 3.0, 4.0, 4.0])

    artifacts = run_statistics(
        run_dir,
        StatisticsSpec(
            enabled=True,
            method="de_weighted",
            credible_levels=[0.68, 0.95],
            output_samples=True,
            include_observables=True,
        ),
    )

    assert artifacts is not None
    assert (run_dir / "statistics" / "de_weighted_samples.csv").exists()
    assert (run_dir / "statistics" / "de_weighted_summary.json").exists()
    assert (run_dir / "statistics" / "de_credible_intervals.json").exists()
    assert (run_dir / "statistics" / "diagnostics.json").exists()

    summary = json.loads((run_dir / "statistics" / "de_weighted_summary.json").read_text(encoding="utf-8"))
    intervals = json.loads((run_dir / "statistics" / "de_credible_intervals.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((run_dir / "statistics" / "diagnostics.json").read_text(encoding="utf-8"))

    x_summary = summary["parameters"]["x"]
    assert x_summary["best_fit"] == pytest.approx(0.0)
    assert x_summary["weighted_mean"] == pytest.approx(
        (0.0 * 1.0 + 1.0 * exp(-1.0) + 2.0 * exp(-4.0)) / (1.0 + exp(-1.0) + exp(-4.0))
    )
    assert x_summary["weighted_median"] == pytest.approx(0.0)
    assert "credible_interval_68" in x_summary
    assert "credible_interval_95" in x_summary
    assert intervals["parameters"]["x"]["68"]["low"] <= intervals["parameters"]["x"]["68"]["high"]
    assert diagnostics["n_total_points"] == 5
    assert diagnostics["n_valid_points"] == 3
    assert diagnostics["n_invalid_points"] == 2
    assert diagnostics["validity_source"] == "valid_column"
    assert diagnostics["chi2_min"] == pytest.approx(0.0)
    assert diagnostics["effective_sample_size"] > 1.0

    sample_rows = list(csv.DictReader((run_dir / "statistics" / "de_weighted_samples.csv").open(newline="")))
    invalid_rows = [row for row in sample_rows if row["valid"] == "false"]
    assert len(invalid_rows) == 2
    assert all(float(row["weight"]) == pytest.approx(0.0) for row in invalid_rows)


def test_statistics_falls_back_for_old_points_without_valid_column(tmp_path):
    run_dir = tmp_path / "old_scan"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps({"engine": "de_scipy", "objective_mode": "nll", "scanned_parameters": [{"name": "x"}]}),
        encoding="utf-8",
    )
    with (run_dir / "points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["evaluation", "status", "failure_reason", "scanner_target", "metric_value", "total_nll", "param::x"])
        writer.writerow([1, "ok", "", 0.0, 0.0, 0.0, 0.0])
        writer.writerow([2, "invalid_point", "bad", 1.0e12, 1.0e12, 1.0e12, 1.0])

    run_statistics(run_dir, StatisticsSpec(enabled=True))

    diagnostics = json.loads((run_dir / "statistics" / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["validity_source"] == "status_fallback"
    assert diagnostics["n_valid_points"] == 1
    assert diagnostics["n_invalid_points"] == 1
    assert any("valid column missing" in warning for warning in diagnostics["warnings"])


def test_statistics_warns_when_valid_row_has_invalid_penalty(tmp_path):
    run_dir = tmp_path / "inconsistent_scan"
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "engine": "de_scipy",
                "objective_mode": "nll",
                "raw_settings": {"invalid_penalty": "1000000000000.0"},
                "scanned_parameters": [{"name": "x"}],
            }
        ),
        encoding="utf-8",
    )
    with (run_dir / "points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["evaluation", "status", "valid", "failure_reason", "scanner_target", "metric_value", "total_nll", "param::x"])
        writer.writerow([1, "ok", "true", "", 0.0, 0.0, 0.0, 0.0])
        writer.writerow([2, "ok", "true", "", 1.0e12, 1.0e12, 1.0e12, 1.0])

    run_statistics(run_dir, StatisticsSpec(enabled=True))

    diagnostics = json.loads((run_dir / "statistics" / "diagnostics.json").read_text(encoding="utf-8"))
    assert any("valid == true but metric_value >= invalid_penalty" in warning for warning in diagnostics["warnings"])


def _make_de_statistics_model() -> ModelDefinition:
    raw = {
        "metadata": {"name": "de-scipy-statistics-toy"},
        "parameters": [
            {
                "name": "x",
                "value_type": "real",
                "scan": True,
                "lower": 0.0,
                "upper": 1.0,
                "default": 0.5,
                "prior": "flat",
            }
        ],
        "observables": [{"name": "x_obs", "expression": "x"}],
        "theory_checks": [
            {
                "name": "x_valid",
                "condition": "x > 0.25",
                "message": "x must stay above 0.25",
            }
        ],
        "likelihoods": [
            {
                "name": "x_term",
                "kind": "gaussian",
                "observable": "x_obs",
                "mean": 0.75,
                "sigma": 0.1,
            }
        ],
        "outputs": {"save": ["x_obs"]},
        "scan": {
            "engine": "de_scipy",
            "save_every": 1,
            "seed": 12345,
            "settings": {
                "objective": "nll",
                "strategy": "rand1bin",
                "maxiter": 3,
                "popsize": 4,
                "tol": 0.01,
                "atol": 0.0,
                "mutation": [0.5, 1.0],
                "recombination": 0.7,
                "init": "latinhypercube",
                "updating": "deferred",
                "workers": 1,
                "polish": False,
                "invalid_penalty": 1.0e12,
                "save_invalid_points": True,
                "verbose": 0,
            },
        },
        "statistics": {
            "enabled": True,
            "method": "de_weighted",
            "credible_levels": [0.68, 0.95],
            "output_samples": True,
            "include_observables": True,
        },
    }
    return ModelDefinition.from_mapping(raw)


def _fake_differential_evolution(func, bounds, **kwargs):
    candidates = [[0.0], [0.9], [0.8], [0.7]]
    best_x = None
    best_fun = None
    nfev = 0
    callback = kwargs.get("callback")
    for index, candidate in enumerate(candidates):
        value = func(candidate)
        nfev += 1
        if best_fun is None or value < best_fun:
            best_fun = value
            best_x = list(candidate)
        if callback is not None and index in {1, 3}:
            callback(best_x, 0.0)
    return SimpleNamespace(
        x=best_x,
        fun=best_fun,
        success=True,
        message="fake scipy convergence",
        nit=2,
        nfev=nfev,
    )


def test_de_scipy_statistics_outputs_are_created(monkeypatch, tmp_path):
    model = _make_de_statistics_model()
    compiled = compile_model(model, build_backend=False)
    monkeypatch.setattr(
        "bsm_scanner.scan._import_scipy_differential_evolution",
        lambda: _fake_differential_evolution,
    )

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "de_scipy_stats",
        run_id="de-scipy-statistics",
        timestamp_utc="2026-04-26T00:00:00+00:00",
    )

    assert results.points_path.exists()
    assert results.summary_path.exists()
    assert results.statistics_directory == results.run_directory / "statistics"
    assert (results.statistics_directory / "de_weighted_samples.csv").exists()
    assert (results.statistics_directory / "de_weighted_summary.json").exists()
    assert (results.statistics_directory / "de_credible_intervals.json").exists()
    assert (results.statistics_directory / "diagnostics.json").exists()

    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    diagnostics = json.loads((results.statistics_directory / "diagnostics.json").read_text(encoding="utf-8"))

    assert summary["valid_points"] == 3
    assert diagnostics["method"] == "de_weighted"
    assert diagnostics["n_total_points"] == 4
    assert diagnostics["n_valid_points"] == 3
