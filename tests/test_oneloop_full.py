import json
from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model, run_scan
from bsm_scanner.scan import build_scan_request, evaluate_scan_point

pytest.importorskip("bsm_scanner._core")


FULL_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "oneloop_full" / "model.yaml"
FIXED_TIMESTAMP = "2026-04-09T00:00:00+00:00"


def make_full_model():
    return load_model(FULL_EXAMPLE)


def make_full_serial_random_model():
    model = make_full_model()
    model.scan.engine = "serial_random"
    model.scan.save_every = 1
    model.scan.seed = 20260409
    model.scan.settings = {
        "objective": "nll",
        "max_evaluations": 2,
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


def test_full_oneloop_model_loads_with_all_core_sectors():
    model = make_full_model()

    assert model.metadata.name == "oneloop_full_normal"
    assert len(model.parameters) == 27
    assert len(model.diagonalizations) == 7
    assert len(model.matrices) == 7
    assert len(model.theory_checks) >= 15
    assert len(model.likelihoods) >= 16

    names = {observable.name for observable in model.observables}
    for required in (
        "Theta12",
        "Theta13",
        "Theta23",
        "deltaCP",
        "dm21",
        "dm3l",
        "HiggsRgg",
        "mu_to_e_gamma",
        "tau_to_mumumu",
        "ObliqueS",
        "ObliqueT",
    ):
        assert required in names

    theta12_term = next(item for item in model.likelihoods if item.name == "theta12_term")
    dm3l_term = next(item for item in model.likelihoods if item.name == "dm3l_term")
    assert theta12_term.kind.value == "table_lookup"
    assert dm3l_term.kind.value == "table_lookup"
    assert len(theta12_term.table) > 100
    assert len(dm3l_term.table) > 100


def test_full_oneloop_default_point_evaluates_and_exposes_key_outputs():
    model = make_full_model()
    compiled = compile_model(model, build_backend=True)

    result = compiled.evaluate(default_point(model))

    assert result["status"] == "ok"
    assert result["total_nll"] > 0
    for required in (
        "MA2",
        "Theta12",
        "Theta13",
        "Theta23",
        "deltaCP",
        "dm21",
        "dm3l",
        "HiggsMass",
        "HiggsRgg",
        "mu_to_e_gamma",
        "tau_to_mumumu",
        "ObliqueS",
        "ObliqueT",
    ):
        assert required in result["outputs"]


def test_full_oneloop_oscillation_table_terms_are_nonzero_in_range_when_disfavored():
    model = make_full_model()
    disabled = {
        "higgs_mass_term",
        "higgs_rgg_term",
        "mu_to_e_gamma_limit",
        "tau_to_e_gamma_limit",
        "tau_to_mu_gamma_limit",
        "mu_to_eee_limit",
        "tau_to_eee_limit",
        "tau_to_mumumu_limit",
        "oblique_ST_term",
    }
    model.likelihoods = [term for term in model.likelihoods if term.name not in disabled]
    compiled = compile_model(model, build_backend=True)

    point = {
        "Mpsi": 13.3516,
        "MN": 1052.48,
        "Mphi": 976.922,
        "MA1": 265.292,
        "MH1": 264.357,
        "MH2": 1030.25,
        "sh": 0.983422,
        "k1": 0.0453352,
        "k4": -0.376188,
        "Reye": 0.12944,
        "Imgye": -0.0546125,
        "Reymu": 0.0371844,
        "Imgymu": -0.161442,
        "Reytau": -0.179725,
        "Imgytau": -0.21988,
        "ReYe": 0.11896,
        "ImgYe": -0.0371501,
        "ReYmu": -0.25688,
        "ImgYmu": 0.206539,
        "ReYtau": -0.260302,
        "ImgYtau": 0.0833255,
        "Reyp": 0.046421,
        "Imgyp": 0.223811,
        "lambda1": 0.22451,
        "lambda2": 0.227105,
        "lambda3": 0.256559,
        "k5": 0.296305,
    }
    result = compiled.evaluate(point)

    assert result["status"] == "ok"
    assert result["likelihood_terms"]["theta12_term"] > 0.0
    assert result["likelihood_terms"]["theta13_term"] > 0.0
    assert result["likelihood_terms"]["theta23_term"] > 0.0
    assert result["likelihood_terms"]["deltaCP_term"] > 0.0
    assert result["likelihood_terms"]["dm21_term"] > 0.0
    assert result["likelihood_terms"]["dm3l_term"] > 0.0
    assert result["total_nll"] > 1000.0


def test_full_oneloop_scan_callback_matches_direct_point_evaluation(tmp_path):
    model = make_full_serial_random_model()
    compiled = compile_model(model, build_backend=True)
    request = build_scan_request(
        model,
        compiled,
        run_directory=tmp_path / "callback",
        run_id="oneloop-full-callback",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    direct = compiled.evaluate(default_point(model))
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
    assert callback["point_result"]["outputs"]["dm21"] == pytest.approx(direct["outputs"]["dm21"])
    assert callback["point_result"]["outputs"]["ObliqueT"] == pytest.approx(
        direct["outputs"]["ObliqueT"]
    )


def test_full_oneloop_serial_random_smoke_scan_writes_outputs(tmp_path):
    model = make_full_serial_random_model()
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "scan",
        run_id="oneloop-full-smoke",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert results.points_path.exists()
    assert results.metadata_path.exists()
    assert results.best_fit_path.exists()
    assert results.summary_path.exists()

    metadata = json.loads(results.metadata_path.read_text(encoding="utf-8"))
    summary = json.loads(results.summary_path.read_text(encoding="utf-8"))

    assert metadata["model_name"] == "oneloop_full_normal"
    assert metadata["parameter_order"][0] == "Mpsi"
    assert summary["evaluations"] == 2
    assert "Theta12" in metadata["selected_outputs"]
