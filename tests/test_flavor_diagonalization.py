from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from bsm_scanner import compile_model, load_model, run_scan
from bsm_scanner.exceptions import ModelValidationError
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parents[1]


def _evaluate(raw: dict):
    pytest.importorskip("bsm_scanner._core")
    return compile_model(ModelDefinition.from_mapping(raw), build_backend=True).evaluate({})


def _complex_matrix(rows: list[list[complex]]) -> list[list[str]]:
    return [[repr(value).replace("(", "").replace(")", "") for value in row] for row in rows]


def _rotation_12(theta: float) -> np.ndarray:
    c = np.cos(theta)
    s = np.sin(theta)
    return np.array(
        [
            [c, s, 0.0],
            [-s, c, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=complex,
    )


def _unitary_close(matrix: np.ndarray, *, atol: float = 1.0e-10) -> None:
    assert matrix.conj().T @ matrix == pytest.approx(np.eye(matrix.shape[1]), abs=atol)


def _standard_ckm(theta12: float = 0.226, theta13: float = 0.0037, theta23: float = 0.041, delta: float = 1.19) -> np.ndarray:
    s12 = np.sin(theta12)
    s13 = np.sin(theta13)
    s23 = np.sin(theta23)
    c12 = np.cos(theta12)
    c13 = np.cos(theta13)
    c23 = np.cos(theta23)
    phase = np.exp(1j * delta)
    return np.array(
        [
            [c12 * c13, s12 * c13, s13 * np.exp(-1j * delta)],
            [
                -s12 * c23 - c12 * s23 * s13 * phase,
                c12 * c23 - s12 * s23 * s13 * phase,
                s23 * c13,
            ],
            [
                s12 * s23 - c12 * c23 * s13 * phase,
                -c12 * s23 - s12 * c23 * s13 * phase,
                c23 * c13,
            ],
        ],
        dtype=complex,
    )


def _core_ckm_model(tmp_path: Path, outputs: list[str], *, likelihoods: str = "") -> Path:
    matrix_rows = _complex_matrix(_standard_ckm().tolist())
    model_path = tmp_path / "model.yaml"
    model_path.write_text(
        "metadata:\n"
        "  name: ckm-core-test\n"
        "imports:\n"
        f"  - {ROOT / 'core' / 'quark' / 'ckm_observables.yaml'}\n"
        "matrices:\n"
        "  V_CKM:\n"
        "    value_type: complex_matrix\n"
        "    rows:\n"
        + "\n".join(
            "      - [" + ", ".join(f'"{cell}"' for cell in row) + "]"
            for row in matrix_rows
        )
        + "\n"
        + likelihoods
        + "outputs:\n"
        + "  save:\n"
        + "".join(f"    - {name}\n" for name in outputs),
        encoding="utf-8",
    )
    return model_path


def test_dirac_svd_outputs_biunitary_factors():
    matrix = np.array(
        [
            [1.0 + 0.2j, 0.3 - 0.1j, 0.0],
            [0.0 + 0.4j, 2.0, 0.2j],
            [0.1, -0.2j, 3.0 + 0.3j],
        ],
        dtype=complex,
    )
    result = _evaluate(
        {
            "metadata": {"name": "dirac-svd"},
            "matrices": {
                "M": {
                    "value_type": "complex_matrix",
                    "type": "complex_general",
                    "diagonalize": {
                        "method": "svd",
                        "output": {
                            "masses": "masses",
                            "left_unitary": "U_L",
                            "right_unitary": "U_R",
                        },
                    },
                    "rows": _complex_matrix(matrix.tolist()),
                }
            },
            "outputs": {"save": ["masses", "U_L", "U_R"]},
        }
    )

    masses = np.asarray(result["outputs"]["masses"])
    u_left = np.asarray(result["outputs"]["U_L"])
    u_right = np.asarray(result["outputs"]["U_R"])

    assert np.all(masses >= -1.0e-12)
    _unitary_close(u_left)
    _unitary_close(u_right)
    assert u_left.conj().T @ matrix @ u_right == pytest.approx(np.diag(masses), abs=1.0e-10)


def test_majorana_takagi_outputs_symmetric_mass_factorization():
    matrix = np.array(
        [
            [1.0 + 0.2j, 0.3 - 0.4j, 0.1j],
            [0.3 - 0.4j, 2.0 + 0.1j, -0.2],
            [0.1j, -0.2, 0.7 - 0.3j],
        ],
        dtype=complex,
    )
    result = _evaluate(
        {
            "metadata": {"name": "takagi"},
            "matrices": {
                "Mnu": {
                    "value_type": "complex_matrix",
                    "type": "complex_symmetric",
                    "role": "neutrino_mass",
                    "diagonalize": {
                        "method": "takagi",
                        "output": {"masses": "neutrino_masses", "unitary": "U_nu"},
                    },
                    "rows": _complex_matrix(matrix.tolist()),
                }
            },
            "outputs": {"save": ["neutrino_masses", "U_nu"]},
        }
    )

    masses = np.asarray(result["outputs"]["neutrino_masses"])
    unitary = np.asarray(result["outputs"]["U_nu"])

    assert np.all(masses >= -1.0e-12)
    _unitary_close(unitary)
    assert unitary.T @ matrix @ unitary == pytest.approx(np.diag(masses), abs=1.0e-9)


def test_hermitian_eigh_outputs_unitary_eigendecomposition():
    matrix = np.array(
        [
            [2.0, 0.3 + 0.4j, 0.0],
            [0.3 - 0.4j, 3.0, -0.2j],
            [0.0, 0.2j, 4.0],
        ],
        dtype=complex,
    )
    result = _evaluate(
        {
            "metadata": {"name": "hermitian"},
            "matrices": {
                "H": {
                    "value_type": "complex_matrix",
                    "type": "hermitian",
                    "diagonalize": {
                        "method": "hermitian_eigh",
                        "output": {"eigenvalues": "evals", "unitary": "U_H"},
                    },
                    "rows": _complex_matrix(matrix.tolist()),
                }
            },
            "outputs": {"save": ["evals", "U_H"]},
        }
    )

    eigenvalues = np.asarray(result["outputs"]["evals"])
    unitary = np.asarray(result["outputs"]["U_H"])

    _unitary_close(unitary)
    assert unitary.conj().T @ matrix @ unitary == pytest.approx(np.diag(eigenvalues), abs=1.0e-10)


def test_pmns_left_mismatch_convention_is_generic():
    charged_lepton = _rotation_12(0.2)
    neutrino = _rotation_12(-0.5)
    result = _evaluate(
        {
            "metadata": {"name": "pmns-mismatch"},
            "matrices": {
                "U_l_L": {"value_type": "complex_matrix", "rows": _complex_matrix(charged_lepton.tolist())},
                "U_nu": {"value_type": "complex_matrix", "rows": _complex_matrix(neutrino.tolist())},
            },
            "mixing_matrices": {
                "PMNS": {
                    "type": "left_mismatch",
                    "convention": "U_left_dagger_U_right",
                    "left": "U_l_L",
                    "right": "U_nu",
                    "output": "U_PMNS",
                }
            },
            "outputs": {"save": ["U_PMNS"]},
        }
    )

    assert np.asarray(result["outputs"]["U_PMNS"]) == pytest.approx(
        charged_lepton.conj().T @ neutrino,
        abs=1.0e-12,
    )


def test_ckm_left_mismatch_convention_is_generic_and_quark_only():
    up_left = _rotation_12(0.01)
    down_left = _rotation_12(0.23)
    result = _evaluate(
        {
            "metadata": {"name": "ckm-mismatch"},
            "matrices": {
                "U_u_L": {"value_type": "complex_matrix", "rows": _complex_matrix(up_left.tolist())},
                "U_d_L": {"value_type": "complex_matrix", "rows": _complex_matrix(down_left.tolist())},
            },
            "mixing_matrices": {
                "CKM": {
                    "type": "ckm",
                    "up": "U_u_L",
                    "down": "U_d_L",
                    "output": "V_CKM",
                }
            },
            "outputs": {"save": ["V_CKM"]},
        }
    )

    ckm = np.asarray(result["outputs"]["V_CKM"])
    assert ckm == pytest.approx(up_left.conj().T @ down_left, abs=1.0e-12)
    _unitary_close(ckm)


def test_ckm_core_observables_extract_absolute_values(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    ckm = _standard_ckm()
    names = ["Vud", "Vus", "Vub", "Vcd", "Vcs", "Vcb", "Vtd", "Vts", "Vtb"]
    result = compile_model(load_model(_core_ckm_model(tmp_path, names)), build_backend=True).evaluate({})

    assert result["status"] == "ok"
    for name, expected in zip(names, np.abs(ckm).reshape(-1), strict=True):
        assert result["outputs"][name] == pytest.approx(expected)


def test_ckm_core_observables_recover_standard_angles_and_phase(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    theta12 = 0.226
    theta13 = 0.0037
    theta23 = 0.041
    delta = 1.19
    outputs = [
        "theta12_q",
        "theta13_q",
        "theta23_q",
        "theta12_q_deg",
        "theta13_q_deg",
        "theta23_q_deg",
        "deltaCKM",
        "deltaCKM_deg",
        "deltaCKM_over_pi",
    ]
    result = compile_model(load_model(_core_ckm_model(tmp_path, outputs)), build_backend=True).evaluate({})

    assert result["status"] == "ok"
    assert result["outputs"]["theta12_q"] == pytest.approx(theta12)
    assert result["outputs"]["theta13_q"] == pytest.approx(theta13)
    assert result["outputs"]["theta23_q"] == pytest.approx(theta23)
    assert result["outputs"]["theta12_q_deg"] == pytest.approx(theta12 * 180 / np.pi)
    assert result["outputs"]["theta13_q_deg"] == pytest.approx(theta13 * 180 / np.pi)
    assert result["outputs"]["theta23_q_deg"] == pytest.approx(theta23 * 180 / np.pi)
    assert result["outputs"]["deltaCKM"] == pytest.approx(delta)
    assert result["outputs"]["deltaCKM_deg"] == pytest.approx(delta * 180 / np.pi)
    assert result["outputs"]["deltaCKM_over_pi"] == pytest.approx(delta / np.pi)


def test_ckm_core_observables_compute_jarlskog_and_wolfenstein(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    ckm = _standard_ckm()
    outputs = [
        "J_CKM",
        "J_CKM_abs",
        "J_CKM_standard",
        "wolfenstein_lambda",
        "wolfenstein_A",
        "wolfenstein_rhobar",
        "wolfenstein_etabar",
    ]
    result = compile_model(load_model(_core_ckm_model(tmp_path, outputs)), build_backend=True).evaluate({})
    out = result["outputs"]

    direct_j = np.imag(ckm[0, 0] * ckm[1, 1] * np.conj(ckm[0, 1]) * np.conj(ckm[1, 0]))
    lambda_expected = abs(ckm[0, 1]) / np.sqrt(abs(ckm[0, 0]) ** 2 + abs(ckm[0, 1]) ** 2)
    a_expected = (1 / lambda_expected) * abs(ckm[1, 2] / ckm[0, 1])
    ratio = -ckm[0, 0] * np.conj(ckm[0, 2]) / (ckm[1, 0] * np.conj(ckm[1, 2]))

    assert result["status"] == "ok"
    assert out["J_CKM"] == pytest.approx(direct_j)
    assert out["J_CKM_abs"] == pytest.approx(abs(direct_j))
    assert out["J_CKM_standard"] == pytest.approx(direct_j)
    assert out["wolfenstein_lambda"] == pytest.approx(lambda_expected)
    assert out["wolfenstein_A"] == pytest.approx(a_expected)
    assert out["wolfenstein_rhobar"] == pytest.approx(np.real(ratio))
    assert out["wolfenstein_etabar"] == pytest.approx(np.imag(ratio))


def test_ckm_toy_likelihoods_evaluate_from_core_observables(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    likelihoods = (
        "likelihoods:\n"
        "  - name: ckm_like_Vus\n"
        "    kind: gaussian\n"
        "    observable: Vus\n"
        "    mean: 0.22\n"
        "    sigma: 0.1\n"
        "  - name: ckm_like_delta\n"
        "    kind: gaussian\n"
        "    observable: deltaCKM_deg\n"
        "    mean: 70.0\n"
        "    sigma: 100.0\n"
    )
    result = compile_model(
        load_model(_core_ckm_model(tmp_path, ["Vus", "deltaCKM_deg"], likelihoods=likelihoods)),
        build_backend=True,
    ).evaluate({})

    assert result["status"] == "ok"
    assert set(result["likelihood_terms"]) == {"ckm_like_Vus", "ckm_like_delta"}
    assert result["likelihood_terms"]["ckm_like_Vus"] >= 0.0
    assert result["likelihood_terms"]["ckm_like_delta"] >= 0.0


def test_quark_only_scan_writes_ckm_scalar_observables_and_likelihoods(tmp_path):
    pytest.importorskip("bsm_scanner._core")

    ckm = _standard_ckm()
    down_matrix = ckm @ np.diag([4.18, 0.096, 0.0047])
    down_rows = _complex_matrix(down_matrix.tolist())
    model_path = tmp_path / "quark_only_model.yaml"
    model_path.write_text(
        "metadata:\n"
        "  name: quark-only-ckm-scan\n"
        "imports:\n"
        f"  - {ROOT / 'core' / 'quark' / 'ckm_observables.yaml'}\n"
        "parameters:\n"
        "  - name: dummy\n"
        "    scan: true\n"
        "    lower: 0.0\n"
        "    upper: 1.0\n"
        "    default: 0.5\n"
        "matrices:\n"
        "  Mu:\n"
        "    value_type: complex_matrix\n"
        "    type: complex_general\n"
        "    diagonalize:\n"
        "      method: svd\n"
        "      output:\n"
        "        masses: up_quark_masses\n"
        "        left_unitary: U_u_L\n"
        "        right_unitary: U_u_R\n"
        "    rows:\n"
        "      - [\"173.0\", \"0.0\", \"0.0\"]\n"
        "      - [\"0.0\", \"1.27\", \"0.0\"]\n"
        "      - [\"0.0\", \"0.0\", \"0.0022\"]\n"
        "  Md:\n"
        "    value_type: complex_matrix\n"
        "    type: complex_general\n"
        "    diagonalize:\n"
        "      method: svd\n"
        "      output:\n"
        "        masses: down_quark_masses\n"
        "        left_unitary: U_d_L\n"
        "        right_unitary: U_d_R\n"
        "    rows:\n"
        + "\n".join(
            "      - [" + ", ".join(f'"{cell}"' for cell in row) + "]"
            for row in down_rows
        )
        + "\n"
        "mixing_matrices:\n"
        "  CKM:\n"
        "    type: ckm\n"
        "    up: U_u_L\n"
        "    down: U_d_L\n"
        "    output: V_CKM\n"
        "likelihoods:\n"
        "  - name: ckm_scan_Vus\n"
        "    kind: gaussian\n"
        "    observable: Vus\n"
        "    mean: 0.22\n"
        "    sigma: 0.1\n"
        "outputs:\n"
        "  save:\n"
        "    - Vus\n"
        "    - Vcb\n"
        "    - Vub\n"
        "    - deltaCKM\n"
        "    - J_CKM\n"
        "    - wolfenstein_lambda\n"
        "scan:\n"
        "  engine: serial_random\n"
        "  save_every: 1\n"
        "  seed: 12345\n"
        "  settings:\n"
        "    objective: nll\n"
        "    max_evaluations: 2\n"
        "    invalid_objective: 1.0e12\n"
        "    verbose: 0\n",
        encoding="utf-8",
    )
    model = load_model(model_path)

    compiled = compile_model(model, build_backend=False)
    results = run_scan(
        model,
        compiled,
        run_directory=tmp_path / "ckm-scan",
        run_id="ckm-scan",
        timestamp_utc="2026-05-20T00:00:00Z",
    )

    with results.points_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert "output::Vus" in rows[0]
    assert "output::deltaCKM" in rows[0]
    assert "output::J_CKM" in rows[0]
    assert "output::wolfenstein_lambda" in rows[0]
    assert "likelihood::ckm_scan_Vus" in rows[0]
    assert all(row["status"] == "ok" and row["valid"] == "true" for row in rows)


def test_pmns_identity_fallback_preserves_neutrino_only_models():
    result = _evaluate(
        {
            "metadata": {"name": "neutrino-only"},
            "matrices": {
                "Mnu": {
                    "value_type": "complex_matrix",
                    "type": "complex_symmetric",
                    "diagonalize": {
                        "method": "takagi",
                        "output": {"masses": "neutrino_masses", "unitary": "U_nu"},
                    },
                    "rows": [["1.0", "0.0"], ["0.0", "2.0"]],
                }
            },
            "mixing_matrices": {
                "PMNS": {
                    "type": "pmns",
                    "neutrino": "U_nu",
                    "output": "U_PMNS",
                }
            },
            "outputs": {"save": ["U_nu", "U_PMNS"]},
        }
    )

    assert np.asarray(result["outputs"]["U_PMNS"]) == pytest.approx(
        np.asarray(result["outputs"]["U_nu"]),
        abs=1.0e-12,
    )


def test_full_flavor_toy_model_loads_lowers_and_evaluates():
    pytest.importorskip("bsm_scanner._core")

    model = load_model(ROOT / "models" / "flavor_toy" / "model.yaml")
    result = compile_model(model, build_backend=True).evaluate({})

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert "U_PMNS" in result["outputs"]
    assert "V_CKM" in result["outputs"]
    assert "Vus" in result["outputs"]
    assert "deltaCKM" in result["outputs"]
    assert "J_CKM" in result["outputs"]
    assert "wolfenstein_lambda" in result["outputs"]
    assert "ckm_toy_Vus" in result["likelihood_terms"]
    _unitary_close(np.asarray(result["outputs"]["U_PMNS"]), atol=1.0e-9)
    _unitary_close(np.asarray(result["outputs"]["V_CKM"]), atol=1.0e-9)


def test_invalid_ckm_request_reports_missing_rotation():
    with pytest.raises(ModelValidationError, match="down"):
        ModelDefinition.from_mapping(
            {
                "metadata": {"name": "bad-ckm"},
                "matrices": {
                    "U_u_L": {"value_type": "complex_matrix", "rows": [["1.0"]]},
                },
                "mixing_matrices": {
                    "CKM": {"type": "ckm", "up": "U_u_L", "output": "V_CKM"}
                },
                "outputs": {"save": ["V_CKM"]},
            }
        )


def test_invalid_pmns_request_reports_missing_neutrino_rotation():
    with pytest.raises(ModelValidationError, match="neutrino rotation"):
        ModelDefinition.from_mapping(
            {
                "metadata": {"name": "bad-pmns"},
                "mixing_matrices": {"PMNS": {"type": "pmns", "output": "U_PMNS"}},
                "outputs": {"save": ["U_PMNS"]},
            }
        )


def test_pmns_without_charged_lepton_fallback_can_be_rejected():
    with pytest.raises(ModelValidationError, match="identity fallback is disabled"):
        ModelDefinition.from_mapping(
            {
                "metadata": {"name": "no-fallback"},
                "matrices": {
                    "U_nu": {"value_type": "complex_matrix", "rows": [["1.0"]]},
                },
                "mixing_matrices": {
                    "PMNS": {
                        "type": "pmns",
                        "neutrino": "U_nu",
                        "charged_lepton_identity_fallback": False,
                        "output": "U_PMNS",
                    }
                },
                "outputs": {"save": ["U_PMNS"]},
            }
        )
