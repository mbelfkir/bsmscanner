from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bsm_scanner import compile_model, run_scan
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.scan import build_scan_request


pytest.importorskip("bsm_scanner._core")

ROOT = Path(__file__).resolve().parents[1]
LEPTONTEST_DE_MODEL = ROOT / "examples" / "leptontest" / "model_de_scipy.yaml"


def make_de_model() -> ModelDefinition:
    raw = {
        "metadata": {"name": "de-scipy-toy"},
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
    }
    return ModelDefinition.from_mapping(raw)


def fake_differential_evolution_factory(captured: dict):
    def fake_differential_evolution(func, bounds, **kwargs):
        captured["bounds"] = bounds
        captured["kwargs"] = kwargs
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

    return fake_differential_evolution


def test_de_scipy_engine_is_registered_and_parses_settings():
    model = make_de_model()
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="de-scipy-request",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    assert request.engine == "de_scipy"
    assert request.engine_options["strategy"] == "rand1bin"
    assert request.engine_options["maxiter"] == 3
    assert request.engine_options["popsize"] == 4
    assert request.engine_options["mutation"] == (0.5, 1.0)
    assert request.engine_options["polish"] is False
    assert request.engine_options["progress_interval"] == 100
    assert request.invalid_objective == pytest.approx(1.0e12)


def test_leptontest_de_scipy_manifest_loads_with_reference_engine():
    from bsm_scanner import load_model

    model = load_model(LEPTONTEST_DE_MODEL)
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="leptontest-de-scipy",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    assert model.metadata.name == "leptontest_de_scipy"
    assert request.engine == "de_scipy"
    assert request.engine_options["strategy"] == "rand1bin"
    assert request.engine_options["polish"] is False
    assert model.statistics.enabled is True
    assert model.statistics.method == "de_weighted"


def test_de_scipy_rejects_invalid_x0_shape():
    model = make_de_model()
    model.scan.settings["x0"] = [0.1, 0.2]
    compiled = compile_model(model, build_backend=False)

    with pytest.raises(Exception, match="x0"):
        build_scan_request(
            model,
            compiled,
            run_directory=Path("unused"),
            run_id="de-scipy-bad-x0",
            timestamp_utc="2026-04-24T00:00:00+00:00",
        )


def test_de_scipy_runs_and_writes_artifacts(monkeypatch, tmp_path):
    model = make_de_model()
    compiled = compile_model(model, build_backend=False)
    captured: dict = {}
    monkeypatch.setattr(
        "bsm_scanner.scan._import_scipy_differential_evolution",
        lambda: fake_differential_evolution_factory(captured),
    )

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "de_scipy_run",
        run_id="de-scipy-run",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    assert results.points_path.exists()
    assert results.metadata_path.exists()
    assert results.best_fit_path.exists()
    assert results.summary_path.exists()
    assert (results.run_directory / "history.json").exists()

    metadata = json.loads(results.metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))

    assert metadata["engine"] == "de_scipy"
    assert metadata["engine_options"]["strategy"] == "rand1bin"
    assert captured["kwargs"]["strategy"] == "rand1bin"
    assert captured["kwargs"]["popsize"] == 4
    assert captured["kwargs"]["polish"] is False
    assert summary["evaluations"] == 4
    assert summary["valid_points"] == 3
    assert summary["failure_counters"]["invalid_point"] == 1
    assert summary["engine_details"]["success"] is True
    assert best_fit["has_best_point"] is True
    assert best_fit["parameters"]["x"] == pytest.approx(0.8)

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert "valid" in rows[0]
    assert any(row["status"] == "ok" and row["valid"] == "false" for row in rows)
    assert all(
        row["valid"] == "false"
        for row in rows
        if float(row["metric_value"]) == pytest.approx(model.scan.settings["invalid_penalty"])
    )


def test_de_scipy_progress_logging_reports_periodic_best_fit(monkeypatch, tmp_path, capsys):
    model = make_de_model()
    model.scan.settings["verbose"] = 1
    model.scan.settings["progress_interval"] = 2
    compiled = compile_model(model, build_backend=False)

    monkeypatch.setattr(
        "bsm_scanner.scan._import_scipy_differential_evolution",
        lambda: fake_differential_evolution_factory({}),
    )

    run_scan(
        model,
        compiled,
        run_directory=tmp_path / "progress",
        run_id="de-scipy-progress",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    output = capsys.readouterr().out
    assert "[de_scipy] start" in output
    assert "[de_scipy] generation=2" in output
    assert "evaluations=4" in output
    assert "best_metric=" in output
    assert "best_parameters={ x=0.8 }" in output
    assert "[de_scipy] final" in output


def test_de_scipy_invalid_points_map_to_penalty(monkeypatch, tmp_path):
    model = make_de_model()
    compiled = compile_model(model, build_backend=False)

    def all_invalid(func, bounds, **kwargs):
        first = func([0.0])
        second = func([0.1])
        return SimpleNamespace(
            x=[0.0],
            fun=min(first, second),
            success=False,
            message="all invalid",
            nit=1,
            nfev=2,
        )

    monkeypatch.setattr(
        "bsm_scanner.scan._import_scipy_differential_evolution",
        lambda: all_invalid,
    )

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "all_invalid",
        run_id="de-scipy-invalid",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))
    best_fit = json.loads(results.best_fit_path.read_text(encoding="utf-8"))

    assert summary["valid_points"] == 0
    assert summary["failure_counters"]["invalid_point"] == 2
    assert best_fit["has_best_point"] is False

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert all(row["status"] == "ok" and row["valid"] == "false" for row in rows)


def test_de_scipy_is_deterministic_under_fixed_seed(monkeypatch, tmp_path):
    model = make_de_model()
    compiled = compile_model(model, build_backend=False)

    monkeypatch.setattr(
        "bsm_scanner.scan._import_scipy_differential_evolution",
        lambda: fake_differential_evolution_factory({}),
    )

    first = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "first",
        run_id="de-scipy-seeded",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )
    second = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "second",
        run_id="de-scipy-seeded",
        timestamp_utc="2026-04-24T00:00:00+00:00",
    )

    assert first.points_path.read_text(encoding="utf-8") == second.points_path.read_text(encoding="utf-8")
    assert first.metadata_path.read_text(encoding="utf-8") == second.metadata_path.read_text(encoding="utf-8")
    assert first.summary_path.read_text(encoding="utf-8") == second.summary_path.read_text(encoding="utf-8")
