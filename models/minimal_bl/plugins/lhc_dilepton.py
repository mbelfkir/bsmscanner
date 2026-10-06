"""LHC dilepton Z' limit for the minimal B-L model, by rescaling the ATLAS Z'_SSM result.

Source: ATLAS, "Search for high-mass dilepton resonances using 139 fb^-1 of pp collision
data at sqrt(s) = 13 TeV", Phys. Lett. B 796 (2019) 68, arXiv:1903.06248 (HEPData record).

Required input files in ../data/atlas_dilepton_139/ (two columns: mass [GeV], value [fb]):
    ssm_theory.csv      sigma x B(Z'_SSM -> l l), single lepton flavour, ATLAS theory curve
    observed_limit.csv  observed 95 % CL upper limit on sigma x B(l l), spin-1 / SSM signal

Registered plugin function: lhc_dilepton.ssm_sigma_over_limit(M)
    returns sigma(pp -> Z'_SSM)(M) / [sigmaB_limit](M) = sigmaB_SSM_theory / (BR_SSM(ll) sigmaB_limit),
    i.e. the SSM production cross section in units of the observed limit on sigma x B.
    Outside the tabulated mass range it returns 0.0 (no constraint), which the YAML documents.

The B-L prediction is then (see constraints/lhc_dilepton.yaml)
    sigmaB_BL / sigmaB_limit = r_prod(g') * BR_BL(ll) * ssm_sigma_over_limit(M),
with the LO narrow-width production ratio r_prod computed in YAML.
"""

from __future__ import annotations

import math
from pathlib import Path

import bsm_scanner
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "atlas_dilepton_139"
SIN2W = 0.23122
M_TOP = 172.57


def _load(name: str) -> tuple[np.ndarray, np.ndarray]:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"LHC dilepton input '{path}' is missing. Provide the ATLAS arXiv:1903.06248 HEPData "
            "tables (see plugins/lhc_dilepton.py docstring) or remove constraints/lhc_dilepton.yaml "
            "from model.yaml imports."
        )
    rows = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.replace(",", " ").split()
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except (ValueError, IndexError):
            continue  # header line
    arr = np.array(sorted(rows))
    if len(arr) < 2 or np.any(arr[:, 1] <= 0):
        raise ValueError(f"'{path}' must contain >= 2 rows of positive (mass, value) pairs.")
    return arr[:, 0], arr[:, 1]


_CACHE: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _table(name: str) -> tuple[np.ndarray, np.ndarray]:
    if name not in _CACHE:
        _CACHE[name] = _load(name)
    return _CACHE[name]


def _loginterp(x: float, xs: np.ndarray, ys: np.ndarray) -> float:
    return float(np.exp(np.interp(x, xs, np.log(ys))))


def br_ssm_ll(mass: float) -> float:
    """BR(Z'_SSM -> e e) at tree level with Z couplings, top threshold included."""
    def width(t3: float, q: float, nc: int, m: float) -> float:
        v, a = t3 - 2.0 * q * SIN2W, t3
        r = (m / mass) ** 2
        if 4.0 * r >= 1.0:
            return 0.0
        beta = math.sqrt(1.0 - 4.0 * r)
        return nc * (v * v * (1.0 + 2.0 * r) * beta + a * a * beta**3)

    up = width(0.5, 2 / 3, 3, 0.0) * 2 + width(0.5, 2 / 3, 3, M_TOP)
    down = width(-0.5, -1 / 3, 3, 0.0) * 3
    lep = width(-0.5, -1.0, 1, 0.0)
    nu = width(0.5, 0.0, 1, 0.0)
    return lep / (up + down + 3 * lep + 3 * nu)


def ssm_sigma_over_limit(args, options):
    mass = float(args["M"])
    m_th, s_th = _table("ssm_theory.csv")
    m_lim, s_lim = _table("observed_limit.csv")
    lo, hi = max(m_th[0], m_lim[0]), min(m_th[-1], m_lim[-1])
    if not (lo <= mass <= hi):
        return 0.0
    sigma_b_ssm = _loginterp(mass, m_th, s_th)
    sigma_b_lim = _loginterp(mass, m_lim, s_lim)
    return sigma_b_ssm / (br_ssm_ll(mass) * sigma_b_lim)


bsm_scanner.register_plugin_function("lhc_dilepton", "ssm_sigma_over_limit", ssm_sigma_over_limit)
