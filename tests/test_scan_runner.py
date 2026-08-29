import csv
import json
from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model, run_scan
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ModelDefinition, PriorKind
from bsm_scanner.scan import (
    _sample_prior_points,
    build_scan_request,
    evaluate_scan_point,
)

pytest.importorskip("bsm_scanner._core")


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "oneloop_minimal" / "model.yaml"
FIXED_TIMESTAMP = "2026-04-07T00:00:00+00:00"


def make_serial_random_model():
    model = load_model(EXAMPLE)
    model.scan.engine = "serial_random"
    model.scan.save_every = 1
    model.scan.seed = 20260407
    model.scan.settings = {
        "objective": "nll",
        "max_evaluations": 5,
        "invalid_objective": 1.0e30,
        "save_invalid_points": True,
        "verbose": 0,
    }
    return model


def default_point(model):
    return {parameter.name: parameter.default for parameter in model.parameters}


def point_vector(model, request, overrides=None):
    values = default_point(model)
    if overrides:
        values.update(overrides)
    return [float(values[parameter.name]) for parameter in request.scanned_parameters]


def test_scan_request_preserves_parameter_order_and_priors():
    model = make_serial_random_model()
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="scan-order",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert request.parameter_order == [parameter.name for parameter in model.parameters]
    assert [parameter.name for parameter in request.scanned_parameters[:4]] == [
        "Mpsi",
        "MN",
        "Mphi",
        "MA1",
    ]
    assert request.scanned_parameters[0].prior == "log"
    assert request.scanned_parameters[0].lower == pytest.approx(50.0)
    assert request.scanned_parameters[0].upper == pytest.approx(2000.0)


def test_scan_request_supports_signed_log_prior():
    model = make_serial_random_model()
    parameter = model.parameters[0]
    parameter.lower = -3.0
    parameter.upper = 3.0
    parameter.default = 1.0e-5
    parameter.prior = PriorKind.SIGNED_LOG
    parameter.min_abs = 1.0e-8
    compiled = compile_model(model, build_backend=False)

    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="scan-signed-log",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert request.scanned_parameters[0].prior == "signed_log"
    assert request.scanned_parameters[0].min_abs == pytest.approx(1.0e-8)


def test_signed_log_prior_sampling_hits_small_signed_scales():
    model = make_serial_random_model()
    parameter = model.parameters[0]
    parameter.lower = -3.0
    parameter.upper = 3.0
    parameter.default = 1.0e-5
    parameter.prior = PriorKind.SIGNED_LOG
    parameter.min_abs = 1.0e-8
    compiled = compile_model(model, build_backend=False)
    request = build_scan_request(
        model,
        compiled,
        run_directory=Path("unused"),
        run_id="scan-signed-log-sampling",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    samples = _sample_prior_points(
        n_points=2000,
        parameters=[request.scanned_parameters[0]],
        seed=1234,
    )[:, 0]

    assert samples.min() >= -3.0
    assert samples.max() <= 3.0
    assert (samples < 0.0).any()
    assert (samples > 0.0).any()
    assert (abs(samples) < 1.0e-4).mean() > 0.1


def test_incomplete_scan_metadata_raises_clear_error():
    model = make_serial_random_model()
    model.scan.settings = {"objective": "nll"}
    compiled = compile_model(model, build_backend=False)

    with pytest.raises(ModelValidationError, match="max_evaluations"):
        build_scan_request(
            model,
            compiled,
            run_directory=Path("unused"),
            run_id="scan-invalid",
            timestamp_utc=FIXED_TIMESTAMP,
        )


def test_unknown_scan_settings_raise_clear_error():
    model = make_serial_random_model()
    model.scan.settings["dm_target"] = "~chi"
    compiled = compile_model(model, build_backend=False)

    with pytest.raises(ModelValidationError, match="Unsupported scan.settings entries"):
        build_scan_request(
            model,
            compiled,
            run_directory=Path("unused"),
            run_id="scan-unknown-setting",
            timestamp_utc=FIXED_TIMESTAMP,
        )


def test_scan_callback_matches_direct_point_evaluation(tmp_path):
    model = make_serial_random_model()
    compiled = compile_model(model, build_backend=True)
    request = build_scan_request(
        model,
        compiled,
        run_directory=tmp_path / "callback",
        run_id="callback-check",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    point = default_point(model)
    direct = compiled.evaluate(point)
    callback = evaluate_scan_point(
        model,
        compiled,
        point_vector(model, request),
        run_directory=tmp_path / "callback",
    )

    assert direct["status"] == "ok"
    assert callback["valid"] is True
    assert callback["point_result"]["status"] == direct["status"]
    assert callback["point_result"]["total_nll"] == pytest.approx(direct["total_nll"])
    assert callback["point_result"]["outputs"]["HiggsMass"] == pytest.approx(
        direct["outputs"]["HiggsMass"]
    )
    assert callback["point_result"]["outputs"]["mu_to_e_gamma"] == pytest.approx(
        direct["outputs"]["mu_to_e_gamma"]
    )


def test_invalid_points_map_to_scanner_safe_objective(tmp_path):
    model = make_serial_random_model()
    compiled = compile_model(model, build_backend=True)
    request = build_scan_request(
        model,
        compiled,
        run_directory=tmp_path / "invalid",
        run_id="invalid-point",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    callback = evaluate_scan_point(
        model,
        compiled,
        point_vector(model, request, overrides={"Mpsi": 600.0, "Mphi": 300.0}),
        run_directory=tmp_path / "invalid",
    )

    assert callback["valid"] is False
    assert callback["scanner_target"] == pytest.approx(request.invalid_objective)
    assert callback["point_result"]["status"] == "ok"
    assert callback["point_result"]["valid"] is False
    assert "hierarchy" in callback["point_result"]["failure_reason"].lower()


def test_run_scan_writes_deterministic_outputs_and_metadata(tmp_path):
    model = make_serial_random_model()
    compiled = compile_model(model, build_backend=False)

    first = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "run1",
        run_id="deterministic-run",
        timestamp_utc=FIXED_TIMESTAMP,
    )
    second = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "run2",
        run_id="deterministic-run",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert first.points_path.exists()
    assert first.metadata_path.exists()
    assert first.best_fit_path.exists()
    assert first.summary_path.exists()

    assert first.points_path.read_text(encoding="utf-8") == second.points_path.read_text(
        encoding="utf-8"
    )
    assert first.metadata_path.read_text(encoding="utf-8") == second.metadata_path.read_text(
        encoding="utf-8"
    )
    assert first.summary_path.read_text(encoding="utf-8") == second.summary_path.read_text(
        encoding="utf-8"
    )

    metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(first.summary_path.read_text(encoding="utf-8"))

    assert metadata["engine"] == "serial_random"
    assert metadata["parameter_order"][0] == "Mpsi"
    assert summary["evaluations"] == 5
    assert summary["saved_points"] == 5


def test_scan_points_csv_contains_real_valid_column(tmp_path):
    model = ModelDefinition.from_mapping(
        {
            "metadata": {"name": "valid-column-serial"},
            "parameters": [
                {
                    "name": "x",
                    "value_type": "real",
                    "scan": True,
                    "lower": 0.0,
                    "upper": 1.0,
                    "default": 0.5,
                }
            ],
            "observables": [{"name": "x_obs", "expression": "x"}],
            "theory_checks": [
                {
                    "name": "always_invalid",
                    "condition": "x > 2.0",
                    "message": "x deliberately outside allowed region",
                }
            ],
            "likelihoods": [
                {
                    "name": "x_term",
                    "kind": "gaussian",
                    "observable": "x_obs",
                    "mean": 0.5,
                    "sigma": 0.1,
                }
            ],
            "outputs": {"save": ["x_obs"]},
            "scan": {
                "engine": "serial_random",
                "save_every": 1,
                "seed": 12345,
                "settings": {
                    "objective": "nll",
                    "max_evaluations": 3,
                    "invalid_objective": 1.0e12,
                    "save_invalid_points": True,
                    "verbose": 0,
                },
            },
        }
    )
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "valid-column",
        run_id="valid-column",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert "valid" in rows[0]
    assert all(row["status"] == "ok" and row["valid"] == "false" for row in rows)
