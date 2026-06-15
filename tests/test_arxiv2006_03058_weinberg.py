from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from bsm_scanner import compile_model, load_model, run_scan
from bsm_scanner.model.graph import build_model_graph


pytest.importorskip("bsm_scanner._core")


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "arxiv2006_03058_weinberg"
MODEL_NO = MODEL_DIR / "model_no.yaml"
MODEL_IO = MODEL_DIR / "model_io.yaml"
FIXED_TIMESTAMP = "2026-05-20T00:00:00+00:00"

NO_POINT = {
    "Retau": 0.029725,
    "Imtau": 1.1181,
    "a2t": 1.7303,
    "a3t": -2.7706,
    "g2t": 2.716,
    "g3t": -0.35786,
}

IO_POINT = {
    "Retau": 0.027941,
    "Imtau": 1.5921,
    "a2t": 1.7266,
    "a3t": -2.17,
    "g2t": 0.4705,
    "g3t": -1.2442,
}

NO_PDG_TAKAGI_REFERENCE = {
    "me_over_mu": 0.0049421699542366885,
    "mu_over_tau": 0.05648917752606122,
    "s12_sq": 0.3106117814891357,
    "s13_sq": 0.023025321071515073,
    "s23_sq": 0.5449913235569374,
    "deltaCP_over_pi": 1.2211397402641864,
    "r": 0.02912708311826326,
    "dm21": 7.356079868874301e-05,
    "dm3l": 0.002525512025700195,
    "m1": 0.00738634326918084,
    "m2": 0.011318960446035498,
    "m3": 0.05079439036537764,
    "J": -0.021869203480762246,
    "Jmax": 0.03416108683507457,
    "sum_m": 0.06949969408059398,
    "mbeta": 0.011620307257393356,
    "nscale": 0.07660247267356302,
}

IO_PDG_TAKAGI_REFERENCE = {
    "me_over_mu": 0.004830619795663459,
    "mu_over_tau": 0.05647840159968499,
    "s12_sq": 0.32473541164847686,
    "s13_sq": 0.022670206560072816,
    "s23_sq": 0.5507678913576258,
    "deltaCP_over_pi": 0.7237206490387276,
    "r": -0.029315798940845687,
    "dm21": 7.348953808347119e-05,
    "dm3l": -0.0025068236493148498,
    "m1": 0.052920922289185414,
    "m2": 0.05361075968517395,
    "m3": 0.019164809018266362,
    "J": 0.026152948924326284,
    "Jmax": 0.03427602029688437,
    "sum_m": 0.12569649099262573,
    "mbeta": 0.05261923096872907,
    "nscale": 0.23580302931711378,
}


def _evaluate(path: Path, point: dict[str, float], extra_outputs: list[str] | None = None):
    model = load_model(path)
    if extra_outputs:
        model.outputs.save.extend(extra_outputs)
    return model, compile_model(model, build_backend=True).evaluate(point)


def _assert_reference_subset(outputs: dict, reference: dict[str, float]) -> None:
    tight = {
        "me_over_mu",
        "mu_over_tau",
        "s12_sq",
        "s13_sq",
        "s23_sq",
        "deltaCP_over_pi",
        "r",
        "J",
        "Jmax",
    }
    for name, expected in reference.items():
        value = float(outputs[name])
        if name in tight:
            assert value == pytest.approx(expected, rel=2.0e-8, abs=1.0e-10)
        else:
            # The model supplies rounded paper-point inputs while the reusable
            # core applies the PDG/Takagi convention and profile-based mass scale.
            assert value == pytest.approx(expected, rel=8.0e-3, abs=1.0e-8)


def test_no_and_io_models_load_without_duplicate_symbols():
    no = load_model(MODEL_NO)
    io = load_model(MODEL_IO)

    assert no.metadata.ordering == "normal"
    assert io.metadata.ordering == "inverted"
    assert [parameter.name for parameter in no.parameters if parameter.scan] == [
        "Retau",
        "Imtau",
        "a2t",
        "a3t",
        "g2t",
        "g3t",
    ]
    assert all(parameter.name != "n_scale" for parameter in no.parameters)
    assert {constant.name for constant in no.constants} >= {"n_scale"}


def test_mass_matrices_evaluate_and_neutrino_matrix_is_symmetric():
    for path, point in [(MODEL_NO, NO_POINT), (MODEL_IO, IO_POINT)]:
        _, result = _evaluate(path, point, extra_outputs=["Me", "Mn"])
        me = np.asarray(result["outputs"]["Me"])
        mn = np.asarray(result["outputs"]["Mn"])

        assert result["status"] == "ok"
        assert result["valid"] is True
        assert me.shape == (3, 3)
        assert mn.shape == (3, 3)
        assert np.max(np.abs(me - np.diag(np.diag(me)))) > 1.0e-6
        assert mn == pytest.approx(mn.T, abs=1.0e-10)


def test_core_pmns_observables_depend_on_charged_lepton_diagonalization():
    model = load_model(MODEL_NO)
    graph = build_model_graph(model)

    assert "diag__charged_lepton" in graph.nodes
    assert "diag__neutrino" in graph.nodes
    assert graph.nodes["charged_lepton_u_00"].dependencies == {"diag__charged_lepton"}
    assert "charged_lepton_u_02" in graph.nodes["Ue1"].dependencies
    assert "neutrino_u_02" in graph.nodes["Ue1"].dependencies


def test_no_reference_point_matches_pdg_takagi_regression():
    _, result = _evaluate(MODEL_NO, NO_POINT)

    assert result["status"] == "ok"
    assert result["valid"] is True
    _assert_reference_subset(result["outputs"], NO_PDG_TAKAGI_REFERENCE)
    assert math.isfinite(float(result["outputs"]["eta1"]))
    assert math.isfinite(float(result["outputs"]["eta2"]))
    assert math.isfinite(float(result["outputs"]["mbetabeta"]))


def test_io_reference_point_matches_pdg_takagi_regression():
    _, result = _evaluate(MODEL_IO, IO_POINT)

    assert result["status"] == "ok"
    assert result["valid"] is True
    _assert_reference_subset(result["outputs"], IO_PDG_TAKAGI_REFERENCE)
    assert math.isfinite(float(result["outputs"]["eta1"]))
    assert math.isfinite(float(result["outputs"]["eta2"]))
    assert math.isfinite(float(result["outputs"]["mbetabeta"]))


def test_likelihood_terms_match_flavorpy_fitted_observable_list():
    model = load_model(MODEL_NO)
    names = {term.name for term in model.likelihoods}
    observables = {term.observable for term in model.likelihoods}

    assert names == {
        "me_over_mu_term",
        "mu_over_tau_term",
        "s12_sq_term",
        "s13_sq_term",
        "s23_sq_term",
        "dm21_term",
        "dm3l_term",
    }
    assert observables == {
        "me_over_mu",
        "mu_over_tau",
        "s12_sq",
        "s13_sq",
        "s23_sq",
        "dm21",
        "dm3l",
    }
    assert "deltaCP_over_pi" not in observables
    assert "deltaCP" not in observables


def test_scan_config_scans_six_parameters_and_keeps_n_scale_fixed():
    model = load_model(MODEL_NO)

    assert model.scan.engine == "de_scipy"
    assert [parameter.name for parameter in model.parameters if parameter.scan] == [
        "Retau",
        "Imtau",
        "a2t",
        "a3t",
        "g2t",
        "g3t",
    ]
    assert all(parameter.name != "n_scale" for parameter in model.parameters)
    assert any(constant.name == "n_scale" and constant.value == 1.0 for constant in model.constants)


def test_tiny_de_scipy_scan_writes_outputs_and_statistics(tmp_path):
    model = load_model(MODEL_NO)
    model.scan.settings["maxiter"] = 1
    model.scan.settings["popsize"] = 2
    model.scan.settings["polish"] = False
    model.scan.settings["verbose"] = 0
    compiled = compile_model(model, build_backend=False)

    result = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "weinberg-no-smoke",
        run_id="weinberg-no-smoke",
        timestamp_utc=FIXED_TIMESTAMP,
    )

    with result.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert "valid" in rows[0]
    assert "output::s12_sq" in rows[0]
    assert "output::mu_over_tau" in rows[0]
    assert "likelihood::dm3l_term" in rows[0]
    assert (result.run_directory / "statistics" / "diagnostics.json").exists()
