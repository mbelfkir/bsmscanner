"""Validation of the corrected scotogenic model (models/scotogenic_ma).

Every reference below is computed independently of the model YAML: either in
50-digit mpmath from the published formulas, or by constructing the Yukawa
matrix from a chosen PMNS matrix (Casas-Ibarra) so the expected observables
are known by construction.
"""

from __future__ import annotations

import math
from pathlib import Path

import mpmath as mp
import numpy as np
import pytest
from bsm_scanner import compile_model, load_model
from bsm_scanner.api import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition

mp.mp.dps = 50
MODEL = Path(__file__).resolve().parents[1] / "model_no.yaml"
V = 246.22
FLAVOURS = ("e", "mu", "tau")


@pytest.fixture(scope="module")
def compiled():
    model = load_model(MODEL)
    return model, compile_model(model)


@pytest.fixture(scope="module")
def free():
    """Same model with theory checks and likelihoods stripped.

    The evaluator returns no outputs for points failing a hard cut or a fatal
    theory check, so observable-level reference tests use this build.
    """
    mapping = load_model_mapping(MODEL)
    mapping["theory_checks"] = []
    mapping["likelihoods"] = []
    model = ModelDefinition.from_mapping(mapping)
    return model, compile_model(model)


def evaluate(compiled, **overrides):
    model, cm = compiled
    point = {p.name: p.default for p in model.parameters}
    point.update(overrides)
    return cm.evaluate(point)


def yukawa_overrides(h):
    out = {}
    for a, f in enumerate(FLAVOURS):
        for k in range(3):
            out[f"h{f}{k + 1}_re"] = float(np.real(h[a, k]))
            out[f"h{f}{k + 1}_im"] = float(np.imag(h[a, k]))
    return out


def inert_masses_mp(m_eta_sq, l3, l4, l5):
    v2 = mp.mpf(V) ** 2
    m_eta_sq = mp.mpf(m_eta_sq)
    mc2 = m_eta_sq + mp.mpf(l3) * v2 / 2
    mr2 = m_eta_sq + (mp.mpf(l3) + mp.mpf(l4) + mp.mpf(l5)) * v2 / 2
    mi2 = m_eta_sq + (mp.mpf(l3) + mp.mpf(l4) - mp.mpf(l5)) * v2 / 2
    return mc2, mr2, mi2


def ma_eq11_mp(M, mr2, mi2):
    """Ma hep-ph/0601225 Eq. (11) kernel with its ORIGINAL 1/(16 pi^2) prefactor."""
    M = mp.mpf(M)
    M2 = M**2
    term = lambda m2: m2 / (m2 - M2) * mp.log(m2 / M2)
    return M / (16 * mp.pi**2) * (term(mr2) - term(mi2))


def F2_mp(x):
    x = mp.mpf(x)
    return (1 - 6 * x + 3 * x**2 + 2 * x**3 - 6 * x**2 * mp.log(x)) / (6 * (1 - x) ** 4)


def obliqueF_mp(m1sq, m2sq):
    return (m1sq + m2sq) / 2 - m1sq * m2sq / (m1sq - m2sq) * mp.log(m1sq / m2sq)


def pmns(s12, s13, s23, delta, a21, a31):
    c12, c13, c23 = (math.sqrt(1 - s) for s in (s12, s13, s23))
    s12, s13, s23 = (math.sqrt(s) for s in (s12, s13, s23))
    e = np.exp(-1j * delta)
    V_ = np.array(
        [
            [c12 * c13, s12 * c13, s13 * e],
            [-s12 * c23 - c12 * s23 * s13 / e, c12 * c23 - s12 * s23 * s13 / e, s23 * c13],
            [s12 * s23 - c12 * c23 * s13 / e, -c12 * s23 - s12 * c23 * s13 / e, c23 * c13],
        ]
    )
    return V_ @ np.diag([1.0, np.exp(0.5j * a21), np.exp(0.5j * a31)])


# ---------------------------------------------------------------- loop kernel


def test_loop_prefactor_is_half_of_ma_eq11(free):
    """B3: Lambda_k = Ma Eq. (11) / 2 (Merle & Platscher 1507.06314)."""
    r = evaluate(free)
    model, _ = free
    d = {p.name: p.default for p in model.parameters}
    _, mr2, mi2 = inert_masses_mp(d["m_eta_sq"], d["lambda3"], d["lambda4"], d["lambda5"])
    for k in (1, 2, 3):
        ref = ma_eq11_mp(d[f"MN{k}"], mr2, mi2) / 2
        got = r["outputs"][f"loop_N{k}"]
        assert got == pytest.approx(float(ref), rel=1e-6)


@pytest.mark.parametrize("lam5", [1e-4, 1e-8, 1e-12])
def test_loop_small_lambda5_cancellation(free, lam5):
    """Numerics: m_R - m_I cancellation vs 50-digit reference.

    Expected double-precision round-off ~ 1e-16 * m^2/(lambda5 v^2) relative.
    """
    r = evaluate(free, lambda5=lam5)
    model, _ = free
    d = {p.name: p.default for p in model.parameters}
    _, mr2, mi2 = inert_masses_mp(d["m_eta_sq"], d["lambda3"], d["lambda4"], lam5)
    ref = float(ma_eq11_mp(d["MN1"], mr2, mi2) / 2)
    bound = max(1e-9, 50 * 2.2e-16 * float(mr2) / (lam5 * V**2))
    assert r["outputs"]["loop_N1"] == pytest.approx(ref, rel=bound)


@pytest.mark.parametrize("offset", [0.0, 1e-9, -1e-9, 1e-5, -1e-5])
def test_loop_removable_singularity_at_mR_equal_MN(free, offset):
    model, _ = free
    d = {p.name: p.default for p in model.parameters}
    _, mr2, mi2 = inert_masses_mp(d["m_eta_sq"], d["lambda3"], d["lambda4"], d["lambda5"])
    MN = float(mp.sqrt(mr2)) * (1 + offset)
    r = evaluate(free, MN1=MN)
    assert r["valid"], r["failure_reason"]
    Mmp = mp.mpf(MN) if offset else mp.sqrt(mr2) * (1 + mp.mpf("1e-30"))
    ref = float(ma_eq11_mp(Mmp, mr2, mi2) / 2)
    assert r["outputs"]["loop_N1"] == pytest.approx(ref, rel=1e-6)


# ---------------------------------------------------- Casas-Ibarra reference


CI_POINT = dict(m_eta_sq=4.0e5, lambda3=0.3, lambda4=-0.2, lambda5=2.0e-4, MN1=800.0, MN2=1500.0, MN3=3000.0)


@pytest.mark.parametrize(
    "delta_deg,a21_deg,a31_deg",
    [(-130.0, 40.0, 250.0), (60.0, 300.0, 10.0), (-20.0, 0.0, 180.0)],
)
def test_casas_ibarra_reference_point(compiled, free, delta_deg, a21_deg, a31_deg):
    """B1+B2: known PMNS, masses, and phases are recovered through the production path."""
    lam = np.array([evaluate(free, **CI_POINT)["outputs"][f"loop_N{k}"] for k in (1, 2, 3)])
    assert np.all(lam > 0)  # lambda5 > 0 => m_R > m_I => Lambda_k > 0
    m_eV = np.array([0.004, math.sqrt(0.004**2 + 7.4e-5), math.sqrt(0.004**2 + 2.51e-3)])
    s12, s13, s23 = 0.307, 0.0222, 0.47
    U = pmns(s12, s13, s23, math.radians(delta_deg), math.radians(a21_deg), math.radians(a31_deg))
    th = 0.3 + 0.2j  # complex orthogonal O = R_12(th): non-trivial Yukawa texture
    O = np.array([[np.cos(th), np.sin(th), 0], [-np.sin(th), np.cos(th), 0], [0, 0, 1]])
    # M_nu = h diag(Lambda) h^T = U* diag(m) U^dagger  (U^T M U = diag(m))
    h = np.conj(U) @ np.diag(np.sqrt(m_eV * 1e-9)) @ O @ np.diag(1 / np.sqrt(lam))
    r = evaluate(compiled, **CI_POINT, **yukawa_overrides(h))
    assert r["valid"], r["failure_reason"]
    o = r["outputs"]
    # Model prediction (GeV singular values of M_nu) is the absolute input spectrum.
    np.testing.assert_allclose([o["m1_raw"], o["m2_raw"], o["m3_raw"]], m_eV * 1e-9, rtol=1e-9)
    # Core observables_common: m_i = scale * m_i_raw, scale anchored to NuFIT bf_dm21/bf_dm3l.
    bf21, bf3l = 7.49e-05, 0.002513
    dm21_raw = (m_eV[1] ** 2 - m_eV[0] ** 2) * 1e-18
    dm3l_raw = (m_eV[2] ** 2 - m_eV[0] ** 2) * 1e-18
    scale = math.sqrt((bf21 / dm21_raw + bf3l / dm3l_raw) / 2)
    assert o["scale"] == pytest.approx(scale, rel=1e-9)
    m_core = scale * m_eV * 1e-9
    np.testing.assert_allclose([o["m1"], o["m2"], o["m3"]], m_core, rtol=1e-9)
    assert o["s12"] == pytest.approx(s12, abs=1e-10)
    assert o["s13"] == pytest.approx(s13, abs=1e-10)
    assert o["s23"] == pytest.approx(s23, abs=1e-10)
    wrap = lambda a: (a + 180.0) % 360.0 - 180.0
    assert o["deltaCP_deg_m180_180"] == pytest.approx(delta_deg, abs=1e-6)
    assert o["deltaCP_deg_0_360"] == pytest.approx(delta_deg % 360.0, abs=1e-6)
    assert o["deltaCP_deg"] == o["deltaCP_deg_0_360"]
    assert wrap(o["alpha21_deg"] - a21_deg) == pytest.approx(0.0, abs=1e-6)
    assert wrap(o["alpha31_deg"] - a31_deg) == pytest.approx(0.0, abs=1e-6)
    mbb = abs(np.sum(U[0, :] ** 2 * m_core))
    assert o["mbetabeta"] == pytest.approx(mbb, rel=1e-9)
    # B1: the table term is finite for every delta (no 1e6 out-of-range penalty).
    assert r["likelihood_terms"]["delta_cp_nufit"] < 50.0


# --------------------------------------------------------------------- LFV


def br_lfv_mp(h, mc2, MN, a, b, br_nu):
    alpha = mp.mpf("0.0072973525693")
    GF = mp.mpf("1.1663788e-5")
    AD = 0
    for k in range(3):
        hb = mp.mpc(h[b, k].real, h[b, k].imag)
        ha = mp.mpc(h[a, k].real, h[a, k].imag)
        AD += mp.conj(hb) * ha * F2_mp(mp.mpf(MN[k]) ** 2 / mc2)
    AD /= 2 * (4 * mp.pi) ** 2 * mc2
    return 3 * (4 * mp.pi) ** 3 * alpha / (4 * GF**2) * abs(AD) ** 2 * br_nu


@pytest.mark.parametrize("MN1", [30.0, 325.672, 326.0, 331.0, 5.0e4])
def test_lfv_against_toma_vicente(free, MN1):
    """M2: BR(l_a -> l_b gamma), Toma & Vicente Eqs. (13)-(14), incl. F2 near xi = 1."""
    r = evaluate(free, MN1=MN1)
    model, _ = free
    d = {p.name: p.default for p in model.parameters}
    d["MN1"] = MN1
    h = np.array([[d[f"h{f}{k}_re"] + 1j * d[f"h{f}{k}_im"] for k in (1, 2, 3)] for f in FLAVOURS])
    mc2, _, _ = inert_masses_mp(d["m_eta_sq"], d["lambda3"], d["lambda4"], d["lambda5"])
    MN = [d["MN1"], d["MN2"], d["MN3"]]
    o = r["outputs"]
    assert o["br_mu_e_gamma"] == pytest.approx(float(br_lfv_mp(h, mc2, MN, 1, 0, 1)), rel=1e-8)
    assert o["br_tau_e_gamma"] == pytest.approx(float(br_lfv_mp(h, mc2, MN, 2, 0, 0.1782)), rel=1e-8)
    assert o["br_tau_mu_gamma"] == pytest.approx(float(br_lfv_mp(h, mc2, MN, 2, 1, 0.1739)), rel=1e-8)


def test_lfv_hard_cut_rejects_large_yukawas(compiled, free):
    big = {f"h{f}{k}_{c}": 0.5 for f in FLAVOURS for k in (1, 2, 3) for c in ("re", "im")}
    assert evaluate(free, **big)["outputs"]["br_mu_e_gamma"] > 1.5e-13
    r = evaluate(compiled, **big)
    assert not r["valid"]


# --------------------------------------------------------------- oblique T


def T_mp(m_eta_sq, l3, l4, l5):
    mc2, mr2, mi2 = inert_masses_mp(m_eta_sq, l3, l4, l5)
    alpha = mp.mpf("0.0078153")
    return (obliqueF_mp(mc2, mr2) + obliqueF_mp(mc2, mi2) - obliqueF_mp(mr2, mi2)) / (
        16 * mp.pi**2 * alpha * mp.mpf(V) ** 2
    )


@pytest.mark.parametrize("l4,l5", [(-0.5, 1e-3), (0.4, 1e-6), (-2.0, 1e-9), (1.0, 0.3)])
def test_oblique_T_against_reference(free, l4, l5):
    r = evaluate(free, lambda4=l4, lambda5=l5)
    ref = float(T_mp(1.0e5, 0.2, l4, l5))
    assert r["outputs"]["oblique_T"] == pytest.approx(ref, rel=1e-6, abs=1e-12)


def test_oblique_T_custodial_limit(free):
    """lambda4 = lambda5 -> 0: degenerate doublet, T -> 0."""
    r = evaluate(free, lambda4=0.0, lambda5=1e-12)
    assert abs(r["outputs"]["oblique_T"]) < 1e-10


def test_oblique_T_small_splitting_matches_bhr_approximation(free):
    r = evaluate(free, lambda4=-0.05, lambda5=1e-6)
    o = r["outputs"]
    approx = (o["m_eta_charged"] - o["m_eta_R"]) * (o["m_eta_charged"] - o["m_eta_I"]) / (
        12 * math.pi**2 * 0.0078153 * V**2
    )
    assert o["oblique_T"] == pytest.approx(approx, rel=2e-2)


# ------------------------------------------------------ Z2 relic and LEP


def test_charged_lightest_z2_odd_is_vetoed(compiled):
    # lambda4 > 0 lifts eta_R, eta_I above eta+; heavy N => eta+ is the lightest Z2-odd state.
    r = evaluate(compiled, lambda4=1.0, MN1=5e3, MN2=6e3, MN3=7e3)
    assert not r["valid"]
    assert "stable charged relic" in r["failure_reason"]


def test_lep2_neutral_region_flagged(compiled, free):
    """m_R ~ 65 GeV, m_I ~ 85 GeV (Lundstrom et al. excluded box); m_eta+ ~ 89.6 GeV."""
    v2 = V**2
    m_eta_sq, l3 = 5000.0, 0.1
    l5 = (65.0**2 - 85.0**2) / v2
    l4 = (65.0**2 + 85.0**2 - 2 * m_eta_sq) / v2 - l3
    pt = dict(m_eta_sq=m_eta_sq, lambda3=l3, lambda4=l4, lambda5=l5, MN1=5e3, MN2=6e3, MN3=7e3)
    o = evaluate(free, **pt)["outputs"]
    assert o["m_eta_R"] == pytest.approx(65.0, rel=1e-9)
    assert o["m_eta_I"] == pytest.approx(85.0, rel=1e-9)
    assert o["lep2_neutral_excluded"] == 1.0
    r = evaluate(compiled, **pt)
    assert not r["valid"] and "lep2_neutral_scalars" in r["failure_reason"]
    assert evaluate(free)["outputs"]["lep2_neutral_excluded"] == 0.0
