from __future__ import annotations

import csv
import json

import numpy as np
import pytest

pytest.importorskip("bsm_scanner._core")
pytest.importorskip("emcee")

from bsm_scanner import compile_model, run_scan
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.posterior.config import StartFromConfig
from bsm_scanner.posterior.initialization import initialize_walkers
from bsm_scanner.posterior.log_probability import LogProbabilityContext, log_probability
from bsm_scanner.posterior.priors import ParameterInfo
from bsm_scanner.scan import build_scan_request


FIXED_TIMESTAMP = "2026-05-21T00:00:00+00:00"


def make_gaussian_model(*, posterior_enabled: bool = True, objective: str = "nll") -> ModelDefinition:
    posterior = {
        "enabled": posterior_enabled,
        "method": "emcee",
        "start_from": {
            "n_walkers": 12,
            "initialization": "elite_covariance",
            "elite_fraction": 0.5,
            "min_elite_points": 4,
            "max_elite_points": 30,
            "jitter_scale": 0.03,
        },
        "mcmc": {
            "n_steps": 80,
            "burn_in": 20,
            "thin": 2,
            "seed": 2468,
            "progress": False,
        },
        "valid_points": {
            "enabled": True,
            "delta_nll": [0.5],
            "delta_chi2": [1.0],
            "observable_sigma_cuts": [1],
        },
    }
    return ModelDefinition.from_mapping(
        {
            "metadata": {"name": "posterior-gaussian"},
            "parameters": [
                {
                    "name": "x",
                    "value_type": "real",
                    "scan": True,
                    "lower": -4.0,
                    "upper": 4.0,
                    "default": 0.0,
                    "prior": "flat",
                },
                {
                    "name": "y",
                    "value_type": "real",
                    "scan": True,
                    "lower": -4.0,
                    "upper": 4.0,
                    "default": 0.0,
                    "prior": "flat",
                },
            ],
            "observables": [
                {"name": "x_obs", "expression": "x"},
                {"name": "y_obs", "expression": "y"},
            ],
            "likelihoods": [
                {"name": "x_term", "kind": "gaussian", "observable": "x_obs", "mean": 1.0, "sigma": 0.5},
                {"name": "y_term", "kind": "gaussian", "observable": "y_obs", "mean": -1.0, "sigma": 0.5},
            ],
            "outputs": {"save": ["x_obs", "y_obs"]},
            "scan": {
                "engine": "serial_random",
                "save_every": 1,
                "seed": 13579,
                "settings": {
                    "objective": objective,
                    "max_evaluations": 120,
                    "invalid_penalty": 1.0e12,
                    "save_invalid_points": True,
                    "verbose": 0,
                },
                "posterior": posterior,
            },
        }
    )


def test_log_probability_objective_conventions(tmp_path):
    model = make_gaussian_model(posterior_enabled=False, objective="nll")
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled, run_directory=tmp_path / "lp")
    parameters = [
        ParameterInfo(item.name, item.lower, item.upper, item.prior, item.default)
        for item in request.scanned_parameters
    ]
    context = LogProbabilityContext(
        compiled=compiled,
        request=request,
        parameters=parameters,
        objective_mode="nll",
        default_prior="flat",
        use_parameter_priors=True,
        include_log_prior=True,
    )
    assert log_probability(np.array([1.0, -1.0]), context) == pytest.approx(0.0, abs=1.0e-12)
    assert log_probability(np.array([20.0, -1.0]), context) == float("-inf")

    context.objective_mode = "chi2"
    assert log_probability(np.array([1.5, -1.0]), context) == pytest.approx(-0.5, abs=1.0e-12)


def test_log_probability_invalid_evaluator_returns_negative_infinity(tmp_path):
    model = make_gaussian_model(posterior_enabled=False)
    model.theory_checks.append(
        ModelDefinition.from_mapping(
            {
                "metadata": {"name": "tmp"},
                "parameters": [{"name": "z", "scan": False, "default": 1.0}],
                "theory_checks": [{"name": "unused", "condition": "z > 0"}],
            }
        ).theory_checks[0]
    )
    model.theory_checks[-1].condition = "x < 0.0"
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(model, compiled, run_directory=tmp_path / "invalid")
    parameters = [
        ParameterInfo(item.name, item.lower, item.upper, item.prior, item.default)
        for item in request.scanned_parameters
    ]
    context = LogProbabilityContext(
        compiled=compiled,
        request=request,
        parameters=parameters,
        objective_mode="nll",
        default_prior="flat",
        use_parameter_priors=True,
        include_log_prior=True,
    )
    assert log_probability(np.array([1.0, -1.0]), context) == float("-inf")


def test_initialization_best_fit_and_elite_covariance(tmp_path):
    run_dir = tmp_path / "init"
    run_dir.mkdir()
    with (run_dir / "points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["valid", "total_nll", "param::x", "param::y"])
        writer.writerow(["true", "0.1", "1.0", "-1.0"])
        writer.writerow(["true", "0.2", "1.1", "-0.9"])
        writer.writerow(["true", "0.3", "0.9", "-1.1"])
    parameters = [
        ParameterInfo("x", -4.0, 4.0, "flat"),
        ParameterInfo("y", -4.0, 4.0, "flat"),
    ]
    rng = np.random.default_rng(123)
    positions, diagnostics, covariance = initialize_walkers(
        run_dir,
        parameters,
        StartFromConfig(n_walkers=8, initialization="elite_covariance", min_elite_points=2, max_elite_points=3),
        rng=rng,
    )
    assert positions.shape == (8, 2)
    assert np.all(np.isfinite(positions))
    assert np.all(positions >= -4.0)
    assert np.all(positions <= 4.0)
    assert covariance.shape == (2, 2)
    assert diagnostics["number_of_elite_points_used"] >= 2


def test_posterior_enabled_writes_outputs_and_recovers_gaussian_center(tmp_path):
    model = make_gaussian_model(posterior_enabled=True)
    compiled = compile_model(model, build_backend=False)
    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "posterior-run",
        run_id="posterior-run",
        timestamp_utc=FIXED_TIMESTAMP,
    )
    expected = [
        "mcmc_chain.npy",
        "mcmc_logprob.npy",
        "mcmc_initial_positions.npy",
        "mcmc_samples.csv",
        "mcmc_observables.csv",
        "mcmc_likelihood_terms.csv",
        "mcmc_summary.json",
        "mcmc_acceptance.json",
        "mcmc_diagnostics.json",
        "mcmc_covariance.json",
        "mcmc_correlation.json",
        "mcmc_best_posterior.json",
        "mcmc_best_likelihood.json",
        "mcmc_invalid_reasons.json",
        "mcmc_valid_points_delta_nll.csv",
        "mcmc_valid_points_delta_chi2.csv",
        "mcmc_valid_points_observable_cuts.csv",
    ]
    for filename in expected:
        assert (results.run_directory / filename).exists(), filename

    with (results.run_directory / "mcmc_samples.csv").open(newline="") as handle:
        first = next(csv.DictReader(handle))
    for column in ["step", "walker", "log_prob", "nll", "chi2", "valid", "invalid_reason", "x", "y", "x_obs", "y_obs", "like__x_term", "like__y_term"]:
        assert column in first

    summary = json.loads((results.run_directory / "mcmc_summary.json").read_text(encoding="utf-8"))
    assert summary["parameters"]["x"]["mean"] == pytest.approx(1.0, abs=0.7)
    assert summary["parameters"]["y"]["mean"] == pytest.approx(-1.0, abs=0.7)
    assert results.summary["posterior"]["valid_samples"] > 0


def test_posterior_disabled_leaves_scan_without_mcmc_outputs(tmp_path):
    model = make_gaussian_model(posterior_enabled=False)
    compiled = compile_model(model, build_backend=False)
    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "posterior-disabled",
        run_id="posterior-disabled",
        timestamp_utc=FIXED_TIMESTAMP,
    )
    assert not (results.run_directory / "mcmc_samples.csv").exists()
    assert "posterior" not in results.summary
