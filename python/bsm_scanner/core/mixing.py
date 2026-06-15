"""Model-independent mixing-matrix observable extraction."""

from __future__ import annotations

import math
from typing import TypedDict

import numpy as np
from numpy.typing import ArrayLike


_EPSILON = 1.0e-16


class PMNSObservables(TypedDict):
    s12: float
    s13: float
    s23: float
    theta12_rad: float
    theta13_rad: float
    theta23_rad: float
    theta12_deg: float
    theta13_deg: float
    theta23_deg: float
    delta_cp_rad: float
    delta_cp_deg: float
    sin_delta_cp: float
    cos_delta_cp: float
    jarlskog: float


def _clip01(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _clip11(value: float) -> float:
    return min(max(float(value), -1.0), 1.0)


def wrap_2pi(value: float) -> float:
    """Wrap an angle in radians to the interval [0, 2*pi)."""

    wrapped = math.fmod(float(value), 2.0 * math.pi)
    return wrapped + 2.0 * math.pi if wrapped < 0.0 else wrapped


def delta_deg_signed(delta_deg: float) -> float:
    """Convert a phase from [0, 360) degrees to [-180, 180)."""

    return ((float(delta_deg) + 180.0) % 360.0) - 180.0


def pmns_observables_from_matrix(matrix: ArrayLike) -> PMNSObservables:
    """Extract PDG mixing observables from a 3x3 complex PMNS matrix.

    The input is interpreted as ``U_PMNS = U_e_L^dagger U_nu``, with flavor
    rows and ordered neutrino-mass columns. Squared mixing sines are extracted
    from matrix-element magnitudes, while the Dirac phase is reconstructed
    from the Jarlskog invariant and an ``atan2`` quadrant determination.
    """

    unitary = np.asarray(matrix, dtype=np.complex128)
    if unitary.shape != (3, 3):
        raise ValueError(f"PMNS matrix must have shape (3, 3), got {unitary.shape}")
    if not np.all(np.isfinite(unitary)):
        raise ValueError("PMNS matrix contains non-finite entries")

    ue1, ue2, ue3 = unitary[0, 0], unitary[0, 1], unitary[0, 2]
    um1, um2, um3 = unitary[1, 0], unitary[1, 1], unitary[1, 2]

    s13_sq = _clip01(abs(ue3) ** 2)
    c13_sq = max(1.0 - s13_sq, _EPSILON)
    s12_sq = _clip01(abs(ue2) ** 2 / c13_sq)
    s23_sq = _clip01(abs(um3) ** 2 / c13_sq)

    c12_sq = max(1.0 - s12_sq, 0.0)
    c23_sq = max(1.0 - s23_sq, 0.0)
    s12, c12 = math.sqrt(s12_sq), math.sqrt(c12_sq)
    s13, c13 = math.sqrt(s13_sq), math.sqrt(c13_sq)
    s23, c23 = math.sqrt(s23_sq), math.sqrt(c23_sq)

    theta12 = math.asin(s12)
    theta13 = math.asin(s13)
    theta23 = math.asin(s23)

    jarlskog = float(np.imag(ue1 * um2 * np.conj(ue2) * np.conj(um1)))
    sin_denominator = s12 * c12 * s23 * c23 * s13 * c13 * c13
    if sin_denominator <= _EPSILON:
        sin_delta = math.nan
        cos_delta = math.nan
        delta = math.nan
    else:
        sin_delta = _clip11(jarlskog / sin_denominator)
        cos_denominator = max(2.0 * s12 * c12 * s23 * c23 * s13, _EPSILON)
        cos_delta = _clip11(
            (
                abs(um1) ** 2
                - s12_sq * c23_sq
                - c12_sq * s23_sq * s13_sq
            )
            / cos_denominator
        )
        delta = wrap_2pi(math.atan2(sin_delta, cos_delta))

    return {
        "s12": float(s12_sq),
        "s13": float(s13_sq),
        "s23": float(s23_sq),
        "theta12_rad": float(theta12),
        "theta13_rad": float(theta13),
        "theta23_rad": float(theta23),
        "theta12_deg": float(math.degrees(theta12)),
        "theta13_deg": float(math.degrees(theta13)),
        "theta23_deg": float(math.degrees(theta23)),
        "delta_cp_rad": float(delta),
        "delta_cp_deg": float(math.degrees(delta)) if math.isfinite(delta) else math.nan,
        "sin_delta_cp": float(sin_delta),
        "cos_delta_cp": float(cos_delta),
        "jarlskog": float(jarlskog),
    }
