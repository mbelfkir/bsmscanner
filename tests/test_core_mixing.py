from __future__ import annotations

import math

import numpy as np
import pytest
from bsm_scanner import delta_deg_signed, pmns_observables_from_matrix, wrap_2pi


def _build_pmns_pdg(
    s12_sq: float,
    s13_sq: float,
    s23_sq: float,
    delta: float,
) -> np.ndarray:
    s12, c12 = math.sqrt(s12_sq), math.sqrt(1.0 - s12_sq)
    s13, c13 = math.sqrt(s13_sq), math.sqrt(1.0 - s13_sq)
    s23, c23 = math.sqrt(s23_sq), math.sqrt(1.0 - s23_sq)
    positive_phase = np.exp(1j * delta)
    negative_phase = np.exp(-1j * delta)
    return np.array(
        [
            [c12 * c13, s12 * c13, s13 * negative_phase],
            [
                -s12 * c23 - c12 * s23 * s13 * positive_phase,
                c12 * c23 - s12 * s23 * s13 * positive_phase,
                s23 * c13,
            ],
            [
                s12 * s23 - c12 * c23 * s13 * positive_phase,
                -c12 * s23 - s12 * c23 * s13 * positive_phase,
                c23 * c13,
            ],
        ],
        dtype=np.complex128,
    )


def test_pmns_observables_from_matrix_recovers_pdg_parameters():
    matrix = _build_pmns_pdg(0.308, 0.02215, 0.470, math.radians(212.0))

    observables = pmns_observables_from_matrix(matrix)

    assert observables["s12"] == pytest.approx(0.308, abs=1.0e-12)
    assert observables["s13"] == pytest.approx(0.02215, abs=1.0e-12)
    assert observables["s23"] == pytest.approx(0.470, abs=1.0e-12)
    assert observables["delta_cp_deg"] == pytest.approx(212.0, abs=1.0e-10)
    assert observables["theta12_rad"] == pytest.approx(math.asin(math.sqrt(0.308)))
    assert observables["theta13_rad"] == pytest.approx(math.asin(math.sqrt(0.02215)))
    assert observables["theta23_rad"] == pytest.approx(math.asin(math.sqrt(0.470)))


def test_pmns_observables_are_invariant_under_row_and_column_rephasing():
    matrix = _build_pmns_pdg(0.308, 0.02215, 0.470, math.radians(212.0))
    row_phases = np.diag(np.exp(1j * np.array([0.2, -1.1, 2.0])))
    column_phases = np.diag(np.exp(1j * np.array([0.7, -0.4, 1.3])))

    observables = pmns_observables_from_matrix(row_phases @ matrix @ column_phases)

    assert observables["s12"] == pytest.approx(0.308, abs=1.0e-12)
    assert observables["s13"] == pytest.approx(0.02215, abs=1.0e-12)
    assert observables["s23"] == pytest.approx(0.470, abs=1.0e-12)
    assert observables["delta_cp_deg"] == pytest.approx(212.0, abs=1.0e-10)


def test_pmns_observables_report_undefined_phase_when_s13_is_zero():
    matrix = _build_pmns_pdg(0.308, 0.0, 0.470, 0.0)

    observables = pmns_observables_from_matrix(matrix)

    assert observables["s13"] == 0.0
    assert math.isnan(observables["sin_delta_cp"])
    assert math.isnan(observables["cos_delta_cp"])
    assert math.isnan(observables["delta_cp_rad"])
    assert math.isnan(observables["delta_cp_deg"])


def test_pmns_observable_helpers_validate_and_convert_values():
    assert wrap_2pi(-math.pi / 2.0) == pytest.approx(1.5 * math.pi)
    assert delta_deg_signed(212.0) == pytest.approx(-148.0)
    with pytest.raises(ValueError, match="shape"):
        pmns_observables_from_matrix(np.eye(2))
    bad_matrix = np.eye(3, dtype=np.complex128)
    bad_matrix[0, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        pmns_observables_from_matrix(bad_matrix)
