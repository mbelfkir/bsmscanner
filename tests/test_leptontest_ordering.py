from pathlib import Path

import pytest

from bsm_scanner import compile_model, load_model
from bsm_scanner.model.schema import ModelDefinition
from bsm_scanner.model.validation import (
    require_likelihood_coverage,
    require_no_dead_scanned_parameters,
)


ROOT = Path(__file__).resolve().parents[1]
LEPTONTEST = ROOT / "models" / "leptontest"


def _load(name: str):
    return load_model(LEPTONTEST / name)


def test_leptontest_variants_compile_with_core_neutrino_imports():
    normal_model = _load("model.yaml")
    inverted_model = _load("model_inverted.yaml")
    normal = compile_model(normal_model, build_backend=False)
    inverted = compile_model(inverted_model, build_backend=False)

    assert normal.model.metadata.ordering == "normal"
    assert inverted.model.metadata.ordering == "inverted"
    assert normal.plan.evaluation_order
    assert inverted.plan.evaluation_order

    assert normal_model.diagonalizations == []
    assert inverted_model.diagonalizations == []

    assert {constant.name for constant in normal_model.constants} == {
        "me_over_mtau",
        "mmu_over_mtau",
        "bf_dm21",
        "bf_dm3l",
    }
    assert {constant.name for constant in inverted_model.constants} == {
        "me_over_mtau",
        "mmu_over_mtau",
        "bf_dm21",
        "bf_dm3l",
    }


def test_leptontest_automatic_diagonalizations_use_role_based_names():
    normal = _load("model.yaml")
    inverted = _load("model_inverted.yaml")

    for model in (normal, inverted):
        resolved = {diag.name: diag for diag in model.resolved_diagonalizations()}
        assert resolved["diag__charged_lepton"].input == "lepton_mass_matrix"
        assert resolved["diag__charged_lepton"].method == "svd_complex"
        assert resolved["diag__neutrino"].input == "neutrino_mass_matrix"
        assert resolved["diag__neutrino"].method == "takagi"

        require_no_dead_scanned_parameters(model)


def test_automatic_diagonalization_is_generic_not_leptontest_specific():
    raw = {
        "metadata": {"name": "auto-diag-generic"},
        "matrices": [
            {
                "name": "demo_matrix",
                "value_type": "real_matrix",
                "type": "real_symmetric",
                "role": "sample_sector",
                "diagonalize": True,
                "rows": [["1.0", "0.0"], ["0.0", "2.0"]],
            }
        ],
        "observables": [
            {
                "name": "light_eval",
                "value_type": "real",
                "projection": {
                    "from": "diag__sample_sector",
                    "quantity": "eigenvalues",
                    "index": 0,
                },
            }
        ],
        "outputs": {"save": ["light_eval"]},
    }

    model = ModelDefinition.from_mapping(raw)
    compiled = compile_model(model, build_backend=True)
    result = compiled.evaluate({})

    assert model.diagonalizations == []
    assert {diag.name for diag in model.resolved_diagonalizations()} == {"diag__sample_sector"}
    assert result["status"] == "ok"
    assert result["outputs"]["light_eval"] == pytest.approx(1.0)


def test_leptontest_ordering_blocks_keep_flavorpy_permutation_convention():
    normal = _load("model.yaml")
    inverted = _load("model_inverted.yaml")

    normal_obs = {obs.name: obs for obs in normal.observables}
    inverted_obs = {obs.name: obs for obs in inverted.observables}
    normal_matrices = {matrix.name: matrix for matrix in normal.matrices}
    inverted_matrices = {matrix.name: matrix for matrix in inverted.matrices}

    expected_lepton_matrix = [
        ["me_over_mtau", "0.0", "0.0"],
        ["0.0", "mmu_over_mtau", "0.0"],
        ["0.0", "0.0", "1.0"],
    ]
    assert normal_matrices["lepton_mass_matrix"].rows == expected_lepton_matrix
    assert inverted_matrices["lepton_mass_matrix"].rows == expected_lepton_matrix

    assert normal_obs["m1_raw"].projection.index == 2
    assert normal_obs["m2_raw"].projection.index == 1
    assert normal_obs["m3_raw"].projection.index == 0
    assert "conj(charged_lepton_u_02) * neutrino_u_02" in normal_obs["Ue1"].expression
    assert "conj(charged_lepton_u_02) * neutrino_u_01" in normal_obs["Ue2"].expression
    assert "conj(charged_lepton_u_02) * neutrino_u_00" in normal_obs["Ue3"].expression

    assert inverted_obs["m1_raw"].projection.index == 1
    assert inverted_obs["m2_raw"].projection.index == 0
    assert inverted_obs["m3_raw"].projection.index == 2
    assert "conj(charged_lepton_u_02) * neutrino_u_01" in inverted_obs["Ue1"].expression
    assert "conj(charged_lepton_u_02) * neutrino_u_00" in inverted_obs["Ue2"].expression
    assert "conj(charged_lepton_u_02) * neutrino_u_02" in inverted_obs["Ue3"].expression


def test_leptontest_model_side_likelihood_blocks_remain_imported_and_active():
    require_likelihood_coverage(
        _load("model.yaml"),
        {"s12_term", "s13_term", "s23_term", "deltaCP_term", "m12_term", "m3l_term", "sumOfMass"},
    )
    require_likelihood_coverage(
        _load("model_inverted.yaml"),
        {"s12_term", "s13_term", "s23_term", "deltaCP_term", "m12_term", "m3l_term", "sumOfMass"},
    )


def test_leptontest_numeric_regression_survives_core_refactor():
    pytest.importorskip("bsm_scanner._core")

    point = {"Retau": -0.011631, "Imtau": 0.994666}

    normal = compile_model(_load("model.yaml"), build_backend=True)
    normal_result = normal.evaluate(point)
    assert normal_result["status"] == "ok"
    assert normal_result["outputs"]["s12"] == pytest.approx(0.9369456913352766)
    assert normal_result["outputs"]["s13"] == pytest.approx(0.29134348124547244)
    assert normal_result["outputs"]["s23"] == pytest.approx(0.6640628746819647)
    assert normal_result["outputs"]["deltaCP"] == pytest.approx(4.763494228972019)
    assert normal_result["outputs"]["dm21"] == pytest.approx(0.0012565963680999863)
    assert normal_result["outputs"]["dm3l"] == pytest.approx(0.001295097436888022)
    assert normal_result["outputs"]["mbeta"] == pytest.approx(0.03481313336516685)
    assert normal_result["outputs"]["mbetabeta"] == pytest.approx(0.03238367383790771)
    assert normal_result["total_nll"] == pytest.approx(308362.20608253597)

    inverted = compile_model(_load("model_inverted.yaml"), build_backend=True)
    inverted_result = inverted.evaluate(point)
    assert inverted_result["status"] == "ok"
    assert inverted_result["outputs"]["s12"] == pytest.approx(0.3049707474234188)
    assert inverted_result["outputs"]["s13"] == pytest.approx(0.04468384687081638)
    assert inverted_result["outputs"]["s23"] == pytest.approx(0.3488737876539934)
    assert inverted_result["outputs"]["deltaCP"] == pytest.approx(4.568673101162382)
    assert inverted_result["outputs"]["dm21"] == pytest.approx(7.437257128517098e-05)
    assert inverted_result["outputs"]["dm3l"] == pytest.approx(-0.0025017416263552793)
    assert inverted_result["outputs"]["mbeta"] == pytest.approx(0.0483852644806731)
    assert inverted_result["outputs"]["mbetabeta"] == pytest.approx(0.04500866403110994)
    assert inverted_result["total_nll"] == pytest.approx(844.4951708967392)
