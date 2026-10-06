"""Validation of the corrected Warsaw-basis SMEFT model (models/smeft_wilson).

References independent of the YAML: Han-Skiba hep-ph/0412166 Eq. (16); Brivio-Trott
arXiv:1706.08945 Eqs. (9.7), (9.9), (A.80); LO h -> gamma gamma loop functions; an independent
derivation of the h -> gamma gamma contact matching from the SM width formula.
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
V, LAM, MH, MW, MT = 246.22, 1000.0, 125.25, 80.3692, 172.57
EPS = V**2 / LAM**2
A_MZ, A_0, AS, SW2, IG = 0.0078153, 0.0072973525693, 0.1180, 0.23122, 0.375
SW, CW = math.sqrt(SW2), math.sqrt(1 - SW2)
COEFFS = ("C_Hbox", "C_HD", "C_HWB", "C_HG", "C_HW", "C_HB", "C_uH", "C_dH", "C_eH")


@pytest.fixture(scope="module")
def free():
    m = load_model_mapping(ROOT / "model.yaml")
    m["theory_checks"], m["likelihoods"] = [], []
    model = ModelDefinition.from_mapping(m)
    return model, compile_model(model)


def ev(built, **over):
    model, cm = built
    point = {p.name: 0.0 for p in model.parameters}
    point.update(over)
    return cm.evaluate(point)["outputs"]


def test_sm_limit(free):
    o = ev(free)
    assert o["ObliqueS"] == 0.0 and o["ObliqueT"] == 0.0
    for k in ("KappaV", "KappaT", "KappaB", "KappaTau", "KappaG", "KappaGamma"):
        assert o[k] == pytest.approx(1.0, abs=1e-14)


def test_oblique_han_skiba(free):
    """S = 4 s c v^2 a_WB/alpha, T = -v^2 a_h/(2 alpha), a = C/Lambda^2 (Han-Skiba Eq. 16)."""
    o = ev(free, C_HWB=0.02, C_HD=-0.15)
    assert o["ObliqueS"] == pytest.approx(4 * SW * CW * EPS * 0.02 / A_MZ, rel=1e-12)
    assert o["ObliqueT"] == pytest.approx(-EPS * (-0.15) / (2 * A_MZ), rel=1e-12)
    # B1 regression: upstream S = 4 eps c_WB is low by s c/alpha ~ 54
    assert o["ObliqueS"] / (4 * EPS * 0.02) == pytest.approx(SW * CW / A_MZ, rel=1e-12)
    assert SW * CW / A_MZ == pytest.approx(53.9, abs=0.2)


def test_loop_functions_known_values(free):
    o = ev(free)
    assert o["A_W_sm"] == pytest.approx(-8.33, abs=0.02)
    assert o["A_t_sm"] == pytest.approx(1.84, abs=0.01)
    # heavy-mass limits of the YAML functions, evaluated through the same expressions
    tau = 1e-6
    f = math.asin(math.sqrt(tau)) ** 2
    assert 2 * (tau + (tau - 1) * f) / tau**2 == pytest.approx(4 / 3, rel=1e-3)
    assert -(2 * tau**2 + 3 * tau + 3 * (2 * tau - 1) * f) / tau**2 == pytest.approx(-7.0, rel=1e-3)


def test_yukawa_maps_brivio_trott_9_7(free):
    """Delta kappa_f^2 = 2 eps (C_Hbox - C_HD/4 - C_fH/[Y_f]), [Y_f] = sqrt2 m_f/v (linear order)."""
    c = dict(C_Hbox=0.8, C_HD=0.2, C_uH=1.5, C_dH=0.05, C_eH=0.02)
    o = ev(free, **c)
    norm = EPS * (0.8 - 0.05)
    for key, cf, m in (("KappaT", 1.5, MT), ("KappaB", 0.05, 4.183), ("KappaTau", 0.02, 1.77686)):
        dk2 = 2 * EPS * (0.8 - 0.2 / 4 - cf / (math.sqrt(2) * m / V))
        assert o[key] - 1 == pytest.approx(dk2 / 2, rel=1e-12)
    assert o["KappaV"] - 1 == pytest.approx(norm, rel=1e-12)


def test_gluon_fusion_enhancement_brivio_trott_A80(free):
    """delta kappa_g = 16 pi^2 v^2 C_HG/(g_s^2 I_g Lambda^2) = 4 pi eps C_HG/(alpha_s I_g) ~ 284 eps C_HG."""
    o = ev(free, C_HG=0.01)
    assert o["KappaG"] - 1 == pytest.approx(16 * math.pi**2 * EPS * 0.01 / (4 * math.pi * AS * IG), rel=1e-12)
    assert 4 * math.pi / (AS * IG) == pytest.approx(284.0, abs=0.5)


def test_hgamgam_contact_matching_from_width(free):
    """Independent matching: Gamma = c^2 m_h^3/(4 pi v^2) for L = (c/v) h F F equals
    G_F alpha^2 m_h^3 |A|^2/(128 sqrt2 pi^3) with G_F = 1/(sqrt2 v^2)  =>  c_SM = alpha A/(8 pi)."""
    gf = 1 / (math.sqrt(2) * V**2)
    a_sm = ev(free)["A_gamma_sm"]
    c_sm = math.sqrt(gf * A_0**2 * MH**3 * a_sm**2 / (128 * math.sqrt(2) * math.pi**3) * 4 * math.pi * V**2 / MH**3)
    assert c_sm == pytest.approx(A_0 * abs(a_sm) / (8 * math.pi), rel=1e-12)
    cHB, cHW, cHWB = 0.004, -0.01, 0.003
    o = ev(free, C_HB=cHB, C_HW=cHW, C_HWB=cHWB)
    c_bsm = EPS * (CW**2 * cHB + SW2 * cHW - SW * CW * cHWB)  # coefficient of (1/v) h F F
    expected = 1 + c_bsm / (A_0 * a_sm / (8 * math.pi))
    assert o["KappaGamma"] == pytest.approx(expected, rel=1e-12)
    # same as Brivio-Trott Eq. (9.9) at linear order with I_gamma = A_SM/4
    dk2 = -(16 * math.pi**2 / (4 * math.pi * A_0 * a_sm / 4)) * EPS * (SW * CW * cHWB - SW2 * cHW - CW**2 * cHB)
    assert o["KappaGamma"] - 1 == pytest.approx(dk2 / 2, rel=1e-12)


def test_no_lambda_flat_direction():
    m = load_model_mapping(ROOT / "model.yaml")
    assert "LambdaTeV" not in {p["name"] for p in m["parameters"]}
    assert {p["name"] for p in m["parameters"]} == set(COEFFS)


def test_st_likelihood_correlation():
    m = load_model_mapping(ROOT / "model.yaml")
    st = next(x for x in m["likelihoods"] if x["name"] == "oblique_ST_pdg")
    cov = np.array(st["covariance"])
    assert cov[0, 1] / math.sqrt(cov[0, 0] * cov[1, 1]) == pytest.approx(0.93, abs=1e-3)
    assert math.sqrt(cov[0, 0]) == pytest.approx(0.10) and math.sqrt(cov[1, 1]) == pytest.approx(0.12)
