"""Validation of the corrected Type II 2HDM (models/two_higgs_doublet).

References are independent of the YAML: mass matrices rebuilt from the quartics and
diagonalised, brute-force positivity of the quartic potential, Branco et al. Eq. (388)
re-implemented in numpy, exact Type II coupling identities.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from bsm_scanner import compile_model
from bsm_scanner.api import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parents[1]
V, MH, MZ, MW, SW2 = 246.22, 125.25, 91.1876, 80.3692, 0.23122


@pytest.fixture(scope="module")
def free():
    m = load_model_mapping(ROOT / "model.yaml")
    m["theory_checks"], m["likelihoods"] = [], []
    model = ModelDefinition.from_mapping(m)
    return model, compile_model(model)


@pytest.fixture(scope="module")
def full():
    model = ModelDefinition.from_mapping(load_model_mapping(ROOT / "model.yaml"))
    return model, compile_model(model)


def ev(built, **over):
    """Overrides may give m12sq (upstream variable); it is converted to delta_soft."""
    model, cm = built
    point = {p.name: p.default for p in model.parameters}
    m12sq = over.pop("m12sq", None)
    point.update(over)
    if m12sq is not None:
        b = math.atan(point["tanb"])
        M2 = m12sq / (math.sin(b) * math.cos(b))
        point["delta_soft"] = (point["mH"] ** 2 - M2) * point["tanb"] ** 2 / V**2
    return cm.evaluate(point)


POINTS = [
    dict(mH=600.0, mA=620.0, mHp=650.0, tanb=2.0, cos_ba=0.02, m12sq=1.2e5),
    dict(mH=900.0, mA=950.0, mHp=1000.0, tanb=10.0, cos_ba=-0.05, m12sq=7.0e4),
    dict(mH=400.0, mA=300.0, mHp=850.0, tanb=0.8, cos_ba=0.25, m12sq=2.0e4),
    dict(mH=1500.0, mA=1450.0, mHp=1480.0, tanb=35.0, cos_ba=0.003, m12sq=6.3e4),
]


@pytest.mark.parametrize("pt", POINTS)
def test_quartics_reproduce_physical_spectrum(free, pt):
    """B1: rebuild the CP-even, CP-odd and charged mass matrices from lambda_i and m12^2."""
    o = ev(free, **pt)["outputs"]
    l1, l2, l3, l4, l5 = (o[f"lambda{i}"] for i in range(1, 6))
    b = math.atan(pt["tanb"])
    sb, cb = math.sin(b), math.cos(b)
    M2 = pt["m12sq"] / (sb * cb)
    l345 = l3 + l4 + l5
    mat = np.array([[l1 * V**2 * cb**2 + M2 * sb**2, (l345 * V**2 - M2) * sb * cb],
                    [(l345 * V**2 - M2) * sb * cb, l2 * V**2 * sb**2 + M2 * cb**2]])
    w, vec = np.linalg.eigh(mat)
    np.testing.assert_allclose(np.sqrt(w), [MH, pt["mH"]], rtol=1e-9)
    # h = -s_a rho1 + c_a rho2: the light eigenvector fixes alpha up to an overall sign
    s_a, c_a = math.sin(o["alpha"]), math.cos(o["alpha"])
    assert abs(abs(np.dot(vec[:, 0], [-s_a, c_a])) - 1.0) < 1e-9
    assert math.sqrt(M2 - l5 * V**2) == pytest.approx(pt["mA"], rel=1e-9)
    assert math.sqrt(M2 - 0.5 * (l4 + l5) * V**2) == pytest.approx(pt["mHp"], rel=1e-9)


def test_upstream_proxy_regression(free):
    """At the upstream default point the upstream lambda1 proxy (1.25) is off by >3x."""
    o = ev(free, mH=600.0, tanb=2.0, cos_ba=0.02, m12sq=1.2e5)["outputs"]
    M2 = 1.2e5 / (math.sin(math.atan(2.0)) * math.cos(math.atan(2.0)))
    proxy = (MH**2 + 600.0**2 - M2) / V**2
    assert proxy == pytest.approx(1.25, abs=0.01)
    assert o["lambda1"] > 3 * proxy


def _quartic_min(l1, l2, l3, l4, l5, n=40000, seed=1):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n, 8))
    p1 = z[:, 0:2] + 1j * z[:, 2:4]
    p2 = z[:, 4:6] + 1j * z[:, 6:8]
    a = np.sum(np.abs(p1) ** 2, axis=1)
    c = np.sum(np.abs(p2) ** 2, axis=1)
    x = np.sum(np.conj(p1) * p2, axis=1)
    v4 = 0.5 * l1 * a**2 + 0.5 * l2 * c**2 + l3 * a * c + l4 * np.abs(x) ** 2 + l5 * np.real(x**2)
    return np.min(v4 / (a + c) ** 2)


@pytest.mark.parametrize("lams,ok", [
    ((1.0, 1.0, 0.5, 0.2, 0.1), True),
    ((1.0, 1.0, -1.2, 0.0, 0.0), False),      # l3 < -sqrt(l1 l2)
    ((2.0, 0.5, -0.5, -0.6, 0.4), False),     # l3 + l4 - |l5| = -1.5 < -1
    ((2.0, 0.5, -0.5, -0.3, 0.1), True),      # -0.9 > -1
])
def test_bfb_condition_matches_brute_force(lams, ok):
    """B2: Branco Eq. (176) vs the minimum of V4/|phi|^4 over random field directions."""
    l1, l2, l3, l4, l5 = lams
    eq176 = l1 > 0 and l2 > 0 and l3 > -math.sqrt(l1 * l2) and l3 + l4 - abs(l5) > -math.sqrt(l1 * l2)
    assert eq176 == ok
    assert (_quartic_min(*lams) > 0) == ok


def test_bfb_check_rejects_unbounded_point(full):
    r = ev(full, mHp=900.0, mA=880.0, mH=860.0, m12sq=3.0e5)  # lambda1 < 0
    assert not r["valid"] and "unbounded" in r["failure_reason"]


def test_unitarity_single_doublet_limit(free):
    """l1 = l2 = L, others 0 -> largest eigenvalue 3L (SM: 3 lambda < 8 pi)."""
    # alignment, tanb = 1, mH = mA = mHp = M: l1 = l2 = mh^2/v^2, l3 = mh^2/v^2, l4 = l5 = 0
    M = 700.0
    o = ev(free, mH=M, mA=M, mHp=M, tanb=1.0, cos_ba=0.0, m12sq=M**2 / 2)["outputs"]
    L = MH**2 / V**2
    np.testing.assert_allclose([o["lambda1"], o["lambda2"], o["lambda3"], o["lambda4"], o["lambda5"]],
                               [L, L, L, 0.0, 0.0], atol=1e-10)
    # with l3 = L: a+ = 3L + 2L = 5L is the largest
    assert o["UnitarityMaxEigenvalue"] == pytest.approx(5 * L, rel=1e-10)


def _F(x, y):
    return 0.0 if x == y else 0.5 * (x + y) - x * y / (x - y) * math.log(x / y)


def _T(mH_, mA, mHp, cba):
    s2, c2 = 1 - cba**2, cba**2
    t = (_F(mHp**2, mA**2) + s2 * _F(mHp**2, mH_**2) + c2 * _F(mHp**2, MH**2)
         - s2 * _F(mH_**2, mA**2) - c2 * _F(MH**2, mA**2)
         + 3 * c2 * (_F(MZ**2, mH_**2) - _F(MW**2, mH_**2) - _F(MZ**2, MH**2) + _F(MW**2, MH**2)))
    return t / (16 * math.pi * SW2 * MW**2)


@pytest.mark.parametrize("pt", POINTS)
def test_oblique_T_against_branco_388(free, pt):
    o = ev(free, **pt)["outputs"]
    assert o["ObliqueT"] == pytest.approx(_T(pt["mH"], pt["mA"], pt["mHp"], pt["cos_ba"]), rel=1e-9, abs=1e-12)


def test_oblique_T_custodial_limit(free):
    """Alignment and m_H+- = m_A: T = 0 exactly (Branco Eq. 388)."""
    o = ev(free, mH=500.0, mA=800.0, mHp=800.0, cos_ba=0.0, tanb=1.5, m12sq=1.0e5)["outputs"]
    assert abs(o["ObliqueT"]) < 1e-12


def test_oblique_T_small_splitting_approximation(free):
    """Alignment, small splittings: T ~ (m+ - mA)(m+ - mH)/(12 pi^2 alpha v^2) with
    16 pi s_W^2 m_W^2 used in place of 16 pi^2 alpha v^2 (equal at tree level)."""
    mH_, mA, mHp = 800.0, 805.0, 830.0
    o = ev(free, mH=mH_, mA=mA, mHp=mHp, cos_ba=0.0, tanb=2.0, m12sq=2.5e5)["outputs"]
    approx = 4.0 / 3.0 * (mHp - mA) * (mHp - mH_) / (16 * math.pi * SW2 * MW**2)
    assert o["ObliqueT"] == pytest.approx(approx, rel=0.05)
    old_proxy = (mHp - mA) * (mHp - mH_) / (1600 * math.pi * V)
    assert o["ObliqueT"] > 10 * old_proxy  # B3 regression


@pytest.mark.parametrize("pt", POINTS)
def test_type2_kappa_identities(free, pt):
    """Exact identities: k_u = s_ba + c_ba/tanb, k_d = k_l = s_ba - c_ba tanb, k_V = s_ba."""
    o = ev(free, **pt)["outputs"]
    sba = math.sqrt(1 - pt["cos_ba"] ** 2)
    assert o["KappaV"] == pytest.approx(sba, rel=1e-12)
    assert o["KappaU"] == pytest.approx(sba + pt["cos_ba"] / pt["tanb"], rel=1e-10)
    assert o["KappaD"] == pytest.approx(sba - pt["cos_ba"] * pt["tanb"], rel=1e-10, abs=1e-12)
    assert o["KappaL"] == o["KappaD"]


def test_alignment_limit_all_kappas_one(free):
    o = ev(free, cos_ba=0.0, tanb=7.0)["outputs"]
    for k in ("KappaV", "KappaU", "KappaD", "KappaL"):
        assert o[k] == pytest.approx(1.0, abs=1e-12)


def test_bsgamma_cut(full):
    # bounded and unitary point (M = mH = mA = 700 GeV, alignment) with m_H+- = 750 GeV < 800 GeV
    pt = dict(mH=700.0, mA=700.0, mHp=750.0, cos_ba=0.0, tanb=3.0, m12sq=700.0**2 * 0.3)
    r = ev(full, **pt)
    assert not r["valid"] and "bsgamma" in r["failure_reason"]
    pt["mHp"] = 820.0  # same point above the bound: passes the cut
    r = ev(full, **pt)
    assert "bsgamma" not in r["failure_reason"]
