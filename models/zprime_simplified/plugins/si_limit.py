"""Spin-independent DM-nucleon limit lookup (90 % CL) for the Z' simplified model.

Required input: ../data/lz_si_limit.csv, two columns: m_chi [GeV], sigma_SI 90 % CL upper limit [cm^2]
(LZ, 4.2 tonne-year exposure, arXiv:2410.17036, official data release / HEPData).

Registered plugin function: si_limit.sigma_limit_cm2(m) -- log-log interpolation of the limit.
Above the tabulated mass range the limit is extrapolated linearly in m (sigma_lim ~ m_chi for
m_chi >> m_N, the standard large-mass scaling of an exposure-limited search); below it the
function returns +inf (no constraint), which the YAML documents.
"""

from __future__ import annotations

import math
from pathlib import Path

import bsm_scanner
import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data" / "lz_si_limit.csv"
_CACHE: dict[str, np.ndarray] = {}


def _table() -> tuple[np.ndarray, np.ndarray]:
    if "t" not in _CACHE:
        if not DATA.exists():
            raise FileNotFoundError(
                f"Direct-detection limit '{DATA}' is missing. Provide the LZ (arXiv:2410.17036) SI "
                "90 % CL limit as a two-column CSV (m_chi [GeV], sigma [cm^2])."
            )
        rows = []
        for line in DATA.read_text().splitlines():
            parts = line.strip().replace(",", " ").split()
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except (ValueError, IndexError):
                continue
        arr = np.array(sorted(rows))
        if len(arr) < 2 or np.any(arr <= 0):
            raise ValueError(f"'{DATA}' must contain >= 2 rows of positive (mass, sigma) pairs.")
        _CACHE["t"] = arr
    arr = _CACHE["t"]
    return arr[:, 0], arr[:, 1]


def sigma_limit_cm2(args, options):
    m = float(args["m"])
    ms, ss = _table()
    if m < ms[0]:
        return math.inf
    if m > ms[-1]:
        return float(ss[-1] * m / ms[-1])
    return float(np.exp(np.interp(np.log(m), np.log(ms), np.log(ss))))


bsm_scanner.register_plugin_function("si_limit", "sigma_limit_cm2", sigma_limit_cm2)
