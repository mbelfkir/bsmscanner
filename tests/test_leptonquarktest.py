from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest
from bsm_scanner import compile_model, load_model, run_scan

pytest.importorskip("bsm_scanner._core")


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "leptonquarktest" / "model.yaml"
ADAPTIVE_MODEL_PATH = ROOT / "models" / "leptonquarktest" / "model_adaptive_diver.yaml"
FIXED_TIMESTAMP = "2026-05-20T00:00:00+00:00"

LEPTON_OUTPUTS = [
    "s12",
    "s13",
    "s23",
    "deltaCP",
    "d_over_pi",
    "deltaCP_deg",
    "eta1",
    "eta2",
    "m1",
    "m2",
    "m3",
    "dm21",
    "dm3l",
    "r",
    "sum_m",
    "J",
    "Jmax",
    "mbeta",
    "mbetabeta",
    "m_b",
    "m_bb",
    "scale",
]

CKM_OUTPUTS = [
    "Vud",
    "Vus",
    "Vub",
    "Vcd",
    "Vcs",
    "Vcb",
    "Vtd",
    "Vts",
    "Vtb",
    "theta12_q",
    "theta13_q",
    "theta23_q",
    "theta12_q_deg",
    "theta13_q_deg",
    "theta23_q_deg",
    "deltaCKM",
    "deltaCKM_deg",
    "J_CKM",
    "wolfenstein_lambda",
    "wolfenstein_A",
    "wolfenstein_rhobar",
    "wolfenstein_etabar",
]

QUARK_RATIO_OUTPUTS = [
    "mu_over_mc",
    "mc_over_mt",
    "md_over_ms",
    "ms_over_mb",
]


def _reference_result():
    model = load_model(MODEL_PATH)
    compiled = compile_model(model, build_backend=True)
    return model, compiled.evaluate({})


def test_leptonquarktest_model_loads_and_validates():
    model = load_model(MODEL_PATH)

    assert model.metadata.name == "leptonquarktest"
    assert model.metadata.ordering == "inverted"
    assert [parameter.name for parameter in model.parameters] == [
        "Retau",
        "Imtau",
        "n_scale",
        "alpha",
        "beta",
        "gamma",
    ]
    assert [parameter.name for parameter in model.parameters if parameter.scan] == [
        "Retau",
        "Imtau",
        "alpha",
        "beta",
        "gamma",
    ]
    assert [matrix.name for matrix in model.matrices[:4]] == ["Mnu", "Ml", "Mu", "Md"]
    assert "V_CKM" in {matrix.name for matrix in model.matrices}
    assert {mixing.name for mixing in model.mixing_matrices} == {"CKM"}
    assert "V_CKM_descending" in {mixing.output for mixing in model.mixing_matrices}


def test_leptonquarktest_reference_point_evaluates_valid():
    _, result = _reference_result()

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert result["failure_reason"] == ""


def test_leptonquarktest_lepton_observables_are_finite():
    _, result = _reference_result()

    for name in LEPTON_OUTPUTS:
        assert name in result["outputs"]
        assert math.isfinite(float(result["outputs"][name]))


def test_leptonquarktest_ckm_and_quark_observables_are_finite():
    _, result = _reference_result()

    for name in CKM_OUTPUTS + QUARK_RATIO_OUTPUTS:
        assert name in result["outputs"]
        assert math.isfinite(float(result["outputs"][name]))

    assert result["outputs"]["dq"] == pytest.approx(result["outputs"]["deltaCKM_deg"])
    assert result["outputs"]["t12"] == pytest.approx(result["outputs"]["theta12_q_deg"])
    assert result["outputs"]["t13"] == pytest.approx(result["outputs"]["theta13_q_deg"])
    assert result["outputs"]["t23"] == pytest.approx(result["outputs"]["theta23_q_deg"])


def test_leptonquarktest_flavorpy_ckm_reference_angles():
    model = load_model(MODEL_PATH)
    compiled = compile_model(model, build_backend=True)
    result = compiled.evaluate({"Retau": -0.5, "Imtau": 1.027139})

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert result["outputs"]["t12"] == pytest.approx(14.256250, abs=1.0e-5)
    assert result["outputs"]["t13"] == pytest.approx(82.076160, abs=1.0e-5)
    assert result["outputs"]["t23"] == pytest.approx(59.363982, abs=5.0e-5)
    assert result["outputs"]["mu_over_mc"] == pytest.approx(0.538355, abs=1.0e-6)
    assert result["outputs"]["mc_over_mt"] == pytest.approx(0.822271, abs=1.0e-6)
    assert result["outputs"]["md_over_ms"] == pytest.approx(0.351797, abs=1.0e-6)
    assert result["outputs"]["ms_over_mb"] == pytest.approx(0.703595, abs=1.0e-6)


def test_leptonquarktest_likelihoods_include_lepton_and_quark_sectors():
    _, result = _reference_result()
    terms = result["likelihood_terms"]

    assert "lepton_s12_term" in terms
    assert "lepton_m3l_term" in terms
    assert "quark_t12_term" in terms
    assert "quark_ms_over_mb_term" in terms
    assert any(name.startswith("lepton_") for name in terms)
    assert any(name.startswith("quark_") for name in terms)
    assert result["total_nll"] == pytest.approx(sum(float(value) for value in terms.values()))


def test_leptonquarktest_scan_writes_lepton_quark_outputs_and_likelihoods(tmp_path):
    model = load_model(MODEL_PATH)
    model.scan.settings["max_evaluations"] = 3
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "leptonquarktest-scan",
        run_id="leptonquarktest-scan",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    header = set(rows[0])
    assert "valid" in header
    assert "output::s12" in header
    assert "output::deltaCP" in header
    assert "output::Vus" in header
    assert "output::Vcb" in header
    assert "output::deltaCKM_deg" in header
    assert "output::mu_over_mc" in header
    assert "output::ms_over_mb" in header
    assert "likelihood::lepton_s12_term" in header
    assert "likelihood::quark_t12_term" in header
    assert all(row["status"] == "ok" for row in rows)


def test_leptonquarktest_adaptive_diver_manifest_runs_smoke_scan(tmp_path):
    model = load_model(ADAPTIVE_MODEL_PATH)
    assert model.scan.engine == "adaptive_diver"
    assert model.metadata.name == "leptonquarktest_adaptive_diver"

    model.scan.settings["verbose"] = 0
    model.scan.adaptive_diver["population_size"] = 6
    model.scan.adaptive_diver["max_generations"] = 2
    model.scan.adaptive_diver["local_refinement"]["enabled"] = False
    model.scan.adaptive_diver["statistics"]["enabled"] = True
    compiled = compile_model(model, build_backend=False)

    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "leptonquarktest-adaptive",
        run_id="leptonquarktest-adaptive",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    assert results.points_path.exists()
    assert (results.run_directory / "history.json").exists()
    assert (results.run_directory / "final_population.csv").exists()
    assert (results.run_directory / "elite_points.csv").exists()
    assert (results.run_directory / "parameter_summary.json").exists()
    assert (results.run_directory / "correlation_matrix.json").exists()

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    header = set(rows[0])
    assert "valid" in header
    assert "output::s12" in header
    assert "output::Vus" in header
    assert "likelihood::lepton_s12_term" in header
    assert "likelihood::quark_t12_term" in header


def test_leptonquarktest_model_does_not_define_physical_observables_locally():
    model_dir = MODEL_PATH.parent
    local_yaml = list(model_dir.rglob("*.yaml"))

    assert local_yaml
    for path in local_yaml:
        text = path.read_text(encoding="utf-8")
        assert "\nobservables:" not in f"\n{text}"
        if path.name == "matrices.yaml":
            assert "\nmixing_matrices:" not in f"\n{text}"

    manifest = MODEL_PATH.read_text(encoding="utf-8")
    assert "../../core/neutrino/inverted.yaml" in manifest
    assert "../../core/quark/ckm_from_left_rotations_descending_svd.yaml" in manifest
    assert "../../core/quark/ckm_observables_from_descending_svd.yaml" in manifest
    assert "../../core/quark/quark_mass_ratios.yaml" in manifest
