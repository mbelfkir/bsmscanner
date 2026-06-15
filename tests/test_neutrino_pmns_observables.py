from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from bsm_scanner import compile_model, load_model, pmns_observables_from_matrix


pytest.importorskip("bsm_scanner._core")

ROOT = Path(__file__).resolve().parents[1]


def _format_complex(value: complex) -> str:
    return repr(complex(value)).replace("(", "").replace(")", "")


def _matrix_rows(matrix: np.ndarray) -> str:
    return "\n".join(
        "      - [" + ", ".join(f'"{_format_complex(cell)}"' for cell in row) + "]"
        for row in matrix
    )


def _pdg_pmns(
    *,
    s12_sq: float,
    s13_sq: float,
    s23_sq: float,
    delta: float,
    alpha21: float = 0.0,
    alpha31: float = 0.0,
) -> np.ndarray:
    s12 = math.sqrt(s12_sq)
    s13 = math.sqrt(s13_sq)
    s23 = math.sqrt(s23_sq)
    c12 = math.sqrt(1.0 - s12_sq)
    c13 = math.sqrt(1.0 - s13_sq)
    c23 = math.sqrt(1.0 - s23_sq)
    phase = np.exp(1j * delta)
    dirac = np.array(
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
    majorana = np.diag([1.0, np.exp(0.5j * alpha21), np.exp(0.5j * alpha31)])
    return dirac @ majorana


def _majorana_matrix(unitary: np.ndarray, masses: np.ndarray) -> np.ndarray:
    return unitary.conj() @ np.diag(masses) @ unitary.conj().T


def _dirac_matrix_from_left(left_unitary_physical: np.ndarray) -> np.ndarray:
    masses_descending = np.diag([1.0, 0.059, 0.0028])
    # The reusable core labels charged-lepton mass columns as tau, mu, e = 0, 1, 2.
    left_unitary_svd_order = left_unitary_physical[:, [2, 1, 0]]
    return left_unitary_svd_order @ masses_descending


def _write_model(
    tmp_path: Path,
    *,
    ordering: str,
    pmns: np.ndarray,
    masses_physical_order: np.ndarray,
    charged_left: np.ndarray | None = None,
) -> Path:
    charged_left = np.eye(3, dtype=complex) if charged_left is None else charged_left
    neutrino_left = charged_left @ pmns
    me = _dirac_matrix_from_left(charged_left)
    mnu = _majorana_matrix(neutrino_left, masses_physical_order)
    constants = "constants_normal.yaml" if ordering == "normal" else "constants_inverted.yaml"
    observables = "observables_normal.yaml" if ordering == "normal" else "observables_inverted.yaml"
    model_path = tmp_path / f"pmns_{ordering}.yaml"
    model_path.write_text(
        "metadata:\n"
        f"  name: pmns-{ordering}-regression\n"
        "matrices:\n"
        "  Me:\n"
        "    value_type: complex_matrix\n"
        "    type: dirac_mass\n"
        "    role: charged_lepton\n"
        "    diagonalize: true\n"
        "    rows:\n"
        f"{_matrix_rows(me)}\n"
        "  Mnu:\n"
        "    value_type: complex_matrix\n"
        "    type: majorana_mass\n"
        "    role: neutrino\n"
        "    diagonalize: true\n"
        "    rows:\n"
        f"{_matrix_rows(mnu)}\n"
        "imports:\n"
        f"  - {ROOT / 'core' / 'constants' / 'physics_constants.yaml'}\n"
        f"  - {ROOT / 'core' / 'neutrino' / constants}\n"
        f"  - {ROOT / 'core' / 'neutrino' / 'observables_common.yaml'}\n"
        f"  - {ROOT / 'core' / 'neutrino' / observables}\n"
        "outputs:\n"
        "  save:\n"
        "    - s12\n"
        "    - s13\n"
        "    - s23\n"
        "    - theta12_angle\n"
        "    - theta13_angle\n"
        "    - theta23_angle\n"
        "    - deltaCP\n"
        "    - deltaCP_deg\n"
        "    - J\n"
        "    - Jmax\n"
        "    - Ue1\n"
        "    - Ue2\n"
        "    - Ue3\n"
        "    - Umu1\n"
        "    - Umu2\n"
        "    - Umu3\n"
        "    - Utau1\n"
        "    - Utau2\n"
        "    - Utau3\n"
        "    - alpha21\n"
        "    - alpha31\n"
        "    - m1\n"
        "    - m2\n"
        "    - m3\n"
        "    - dm21\n"
        "    - dm3l\n"
        "    - mbeta\n"
        "    - mbetabeta\n",
        encoding="utf-8",
    )
    return model_path


def _evaluate_model(path: Path) -> dict:
    return compile_model(load_model(path), build_backend=True).evaluate({})


def _expected_mbeta(pmns: np.ndarray, masses: np.ndarray) -> float:
    return float(math.sqrt(sum(abs(pmns[0, idx]) ** 2 * masses[idx] ** 2 for idx in range(3))))


def _expected_mbetabeta(pmns: np.ndarray, masses: np.ndarray) -> float:
    return float(abs(sum(pmns[0, idx] ** 2 * masses[idx] for idx in range(3))))


@pytest.mark.parametrize("delta_deg", [60.0, 240.0])
def test_core_pmns_pdg_extraction_preserves_delta_quadrant(tmp_path: Path, delta_deg: float):
    masses = np.array([0.011, 0.014, 0.052])
    pmns = _pdg_pmns(
        s12_sq=0.308,
        s13_sq=0.02215,
        s23_sq=0.470,
        delta=math.radians(delta_deg),
        alpha21=0.7,
        alpha31=2.1,
    )
    result = _evaluate_model(
        _write_model(tmp_path, ordering="normal", pmns=pmns, masses_physical_order=masses)
    )
    out = result["outputs"]

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert out["s12"] == pytest.approx(0.308, abs=2.0e-10)
    assert out["s13"] == pytest.approx(0.02215, abs=2.0e-10)
    assert out["s23"] == pytest.approx(0.470, abs=2.0e-10)
    assert out["deltaCP_deg"] == pytest.approx(delta_deg, abs=2.0e-7)
    assert out["alpha21"] == pytest.approx(0.7, abs=2.0e-10)
    assert out["alpha31"] == pytest.approx(2.1, abs=2.0e-10)
    extracted = pmns_observables_from_matrix(
        np.array(
            [
                [out["Ue1"], out["Ue2"], out["Ue3"]],
                [out["Umu1"], out["Umu2"], out["Umu3"]],
                [out["Utau1"], out["Utau2"], out["Utau3"]],
            ]
        )
    )
    assert extracted["s12"] == pytest.approx(out["s12"], abs=1.0e-12)
    assert extracted["s13"] == pytest.approx(out["s13"], abs=1.0e-12)
    assert extracted["s23"] == pytest.approx(out["s23"], abs=1.0e-12)
    assert extracted["delta_cp_rad"] == pytest.approx(out["deltaCP"], abs=1.0e-12)
    assert extracted["jarlskog"] == pytest.approx(out["J"], abs=1.0e-12)
    scaled_masses = np.array([out["m1"], out["m2"], out["m3"]])
    assert out["mbeta"] == pytest.approx(_expected_mbeta(pmns, scaled_masses), rel=1.0e-10)
    assert out["mbetabeta"] == pytest.approx(
        _expected_mbetabeta(pmns, scaled_masses),
        rel=1.0e-10,
    )


def test_core_pmns_uses_charged_lepton_left_mismatch(tmp_path: Path):
    theta = 0.37
    charged_left = np.array(
        [
            [math.cos(theta), math.sin(theta), 0.0],
            [-math.sin(theta), math.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=complex,
    )
    masses = np.array([0.010, 0.013, 0.050])
    pmns = _pdg_pmns(
        s12_sq=0.308,
        s13_sq=0.02215,
        s23_sq=0.470,
        delta=math.radians(212.0),
        alpha21=0.7,
        alpha31=2.1,
    )
    result = _evaluate_model(
        _write_model(
            tmp_path,
            ordering="normal",
            pmns=pmns,
            masses_physical_order=masses,
            charged_left=charged_left,
        )
    )
    out = result["outputs"]

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert out["s12"] == pytest.approx(0.308, abs=2.0e-10)
    assert out["s13"] == pytest.approx(0.02215, abs=2.0e-10)
    assert out["s23"] == pytest.approx(0.470, abs=2.0e-10)
    assert out["deltaCP_deg"] == pytest.approx(212.0, abs=2.0e-7)


def test_core_pmns_inverted_ordering_keeps_dm3l_negative(tmp_path: Path):
    m3 = 0.012
    dm21 = 7.4e-5
    dm3l_abs = 2.50e-3
    m1 = math.sqrt(m3**2 + dm3l_abs - dm21)
    m2 = math.sqrt(m1**2 + dm21)
    masses = np.array([m1, m2, m3])
    pmns = _pdg_pmns(
        s12_sq=0.308,
        s13_sq=0.02215,
        s23_sq=0.470,
        delta=math.radians(212.0),
        alpha21=0.2,
        alpha31=1.3,
    )
    result = _evaluate_model(
        _write_model(tmp_path, ordering="inverted", pmns=pmns, masses_physical_order=masses)
    )
    out = result["outputs"]

    assert result["status"] == "ok"
    assert result["valid"] is True
    assert out["s12"] == pytest.approx(0.308, abs=2.0e-10)
    assert out["s13"] == pytest.approx(0.02215, abs=2.0e-10)
    assert out["s23"] == pytest.approx(0.470, abs=2.0e-10)
    assert out["deltaCP_deg"] == pytest.approx(212.0, abs=2.0e-7)
    assert out["dm21"] > 0
    assert out["dm3l"] < 0


def test_core_pmns_marks_undefined_dirac_phase_invalid(tmp_path: Path):
    masses = np.array([0.011, 0.014, 0.052])
    pmns = _pdg_pmns(
        s12_sq=0.308,
        s13_sq=0.0,
        s23_sq=0.470,
        delta=0.0,
    )
    result = _evaluate_model(
        _write_model(tmp_path, ordering="normal", pmns=pmns, masses_physical_order=masses)
    )

    assert result["status"] == "ok"
    assert result["valid"] is False
    assert result["failure_reason"] == "non_finite_node: deltaCP"
