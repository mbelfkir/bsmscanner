"""Validation of the corrected minimal B-L model (models/minimal_bl).

References are independent of the YAML: Basso-Moretti-Pruna (arXiv:1106.4462) equations
re-implemented in numpy, analytic limits, and the paper's quoted Z' branching ratios.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest
from bsm_scanner import compile_model
from bsm_scanner.api import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "model.yaml"
V, MH1 = 246.22, 125.25
DILEPTON = {"dilepton_prod_ratio", "dilepton_ssm_sigma_over_limit", "dilepton_signal_over_limit",
            "atlas_dilepton_139", "dilepton_g_z", "dilepton_c_u", "dilepton_c_d", "dilepton_r_ud"}
DATA_PRESENT = (ROOT / "data" / "atlas_dilepton_139" / "observed_limit.csv").exists()


def _build(strip_dilepton: bool, strip_constraints: bool):
    m = load_model_mapping(MODEL if strip_dilepton else ROOT / "model_with_lhc_dilepton.yaml")
    if strip_dilepton:
        for sec in ("constants", "derived_scalars", "observables", "likelihoods"):
            m[sec] = [x for x in m.get(sec, []) if x["name"] not in DILEPTON]
        m["outputs"]["save"] = [x for x in m["outputs"]["save"] if x not in DILEPTON]
    if strip_constraints:
        m["theory_checks"], m["likelihoods"] = [], []
    model = ModelDefinition.from_mapping(m)
    return model, compile_model(model)


@pytest.fixture(scope="module")
def free():
    return _build(strip_dilepton=True, strip_constraints=True)


@pytest.fixture(scope="module")
def full_no_dilepton():
    return _build(strip_dilepton=True, strip_constraints=False)


def evaluate(built, **over):
    model, cm = built
    point = {p.name: p.default for p in model.parameters}
    point.update(over)
    return cm.evaluate(point)


# ------------------------------------------------------------- masses, scalars


def test_masses_eq_2_25_and_2_35(free):
    o = evaluate(free, gBL=0.2, vBL=12000.0, yN1=0.01, yN2=0.1, yN3=1.0)["outputs"]
    assert o["MZprime"] == pytest.approx(2 * 0.2 * 12000.0, rel=1e-14)
    for k, y in zip((1, 2, 3), (0.01, 0.1, 1.0)):
        assert o[f"HeavyNeutrino{k}Mass"] == pytest.approx(math.sqrt(2) * y * 12000.0, rel=1e-14)


@pytest.mark.parametrize("sa,mh2,x", [(0.05, 800.0, 7.0e4), (-0.3, 300.0, 4.0e3), (0.2, 4000.0, 2.0e4)])
def test_scalar_couplings_reproduce_physical_spectrum(free, sa, mh2, x):
    """Eqs. (2.26)-(2.30) applied to the YAML lambdas give back (m_h1, m_h2, alpha)."""
    o = evaluate(free, sin_alpha=sa, mH2=mh2, vBL=x)["outputs"]
    l1, l2, l3 = o["lambdaH"], o["lambdaS"], o["lambdaHS"]
    root = math.sqrt((l1 * V**2 - l2 * x**2) ** 2 + (l3 * x * V) ** 2)
    m1sq, m2sq = l1 * V**2 + l2 * x**2 - root, l1 * V**2 + l2 * x**2 + root
    assert math.sqrt(m1sq) == pytest.approx(MH1, rel=1e-9)
    assert math.sqrt(m2sq) == pytest.approx(mh2, rel=1e-9)
    assert l3 * x * V / root == pytest.approx(2 * sa * math.sqrt(1 - sa**2), rel=1e-9, abs=1e-12)
    assert 4 * l1 * l2 - l3**2 == pytest.approx(m1sq * m2sq / (V**2 * x**2), rel=1e-9)


# ------------------------------------------------------------------ Z' width


def test_zprime_width_massless_limit_without_heavy_n(free):
    """Eq. (3.7) summed, N closed (M_N > M_Z'/2): Gamma/M = 13 g'^2/(24 pi), BR(ee) = 1/6.5."""
    g = 0.3
    o = evaluate(free, gBL=g, vBL=5.0e4, yN1=1.0, yN2=1.0, yN3=1.0)["outputs"]  # M_N = 70.7 TeV > M_Z' = 30 TeV
    r_top = (172.57 / 3.0e4) ** 2  # residual top-mass correction ~ 6 r^2
    assert o["ZprimeWidthOverMass"] == pytest.approx(13 * g**2 / (24 * math.pi), rel=1e-3)
    assert o["BRZprimeToEE"] == pytest.approx(1 / 6.5, rel=1e-3)
    assert o["BRZprimeToNN"] == 0.0
    assert r_top < 1e-4


def test_zprime_width_massless_limit_with_light_heavy_n(free):
    """Three open, light Majorana N: Gamma/M = 8 g'^2/(12 pi), BR(ee) = 1/8 (paper: 12.5 %)."""
    g = 0.3
    o = evaluate(free, gBL=g, vBL=5.0e4, yN1=1e-6, yN2=1e-6, yN3=1e-6)["outputs"]
    assert o["ZprimeWidthOverMass"] == pytest.approx(8 * g**2 / (12 * math.pi), rel=1e-3)
    assert o["BRZprimeToEE"] == pytest.approx(1 / 8, rel=1e-3)
    assert o["BRZprimeToNN"] == pytest.approx(1.5 / 8, rel=1e-3)


def test_zprime_width_against_independent_sum(free):
    """Generic point with top and N thresholds vs an independent implementation of Eq. (3.7)."""
    g, x, ys = 0.15, 1200.0, (0.05, 0.12, 0.3)
    o = evaluate(free, gBL=g, vBL=x, yN1=ys[0], yN2=ys[1], yN3=ys[2])["outputs"]
    M = 2 * g * x  # 360 GeV: top open, N3 closed
    dirac = lambda m: (1 + 2 * m**2 / M**2) * math.sqrt(1 - 4 * m**2 / M**2) if 2 * m < M else 0.0
    maj = lambda m: (1 - 4 * m**2 / M**2) ** 1.5 if 2 * m < M else 0.0
    quarks = [0.00216, 0.00470, 0.0935, 1.2730, 4.183, 172.57]
    leptons = [0.00051099895, 0.1056583755, 1.77686]
    s = sum(dirac(m) for m in quarks) / 3 + sum(dirac(m) for m in leptons) + 1.5
    s += 0.5 * sum(maj(math.sqrt(2) * y * x) for y in ys)
    assert o["ZprimeWidthOverMass"] == pytest.approx(g**2 / (12 * math.pi) * s, rel=1e-12)
    assert o["ZprimeWidth"] == pytest.approx(g**2 / (12 * math.pi) * s * M, rel=1e-12)


def test_narrow_width_cut_now_bites_below_g_1(full_no_dilepton):
    """B1 regression: upstream proxy g^2/(12 pi) allowed g' = 0.9; full width gives Gamma/M > 0.1."""
    r = evaluate(full_no_dilepton, gBL=0.9, vBL=5.0e4, sin_alpha=0.0)
    assert not r["valid"] and "zprime_narrow_width" in r["failure_reason"]
    assert 0.9**2 / (12 * math.pi) < 0.1  # what the upstream proxy would have accepted


# ------------------------------------------------------------------ Higgs


def test_signal_strength_decoupling_limit(free):
    o = evaluate(free, sin_alpha=0.0)["outputs"]
    assert o["HiggsSignalStrength"] == 1.0 and o["HiggsExoticBR"] == 0.0


def test_signal_strength_with_exotic_decays(free):
    sa, g, x, ys = 0.3, 0.003, 3600.0, (0.005, 0.008, 0.5)
    o = evaluate(free, sin_alpha=sa, gBL=g, vBL=x, yN1=ys[0], yN2=ys[1], yN3=ys[2])["outputs"]
    mzp = 2 * g * x  # 21.6 GeV < m_h/2
    def nn(mn):
        if 2 * mn >= MH1:
            return 0.0
        return sa**2 * mn**2 * MH1 * (1 - 4 * mn**2 / MH1**2) ** 1.5 / (16 * math.pi * x**2)
    r = mzp**2 / MH1**2
    zz = sa**2 * MH1**3 / (32 * math.pi * x**2) * (1 - 4 * r + 12 * r**2) * math.sqrt(1 - 4 * r)
    exotic = sum(nn(math.sqrt(2) * y * x) for y in ys) + zz
    ca2 = 1 - sa**2
    mu = ca2 * ca2 * 4.088e-3 / (ca2 * 4.088e-3 + exotic)
    assert o["HiggsExoticBR"] == pytest.approx(exotic / (ca2 * 4.088e-3 + exotic), rel=1e-12)
    assert o["HiggsSignalStrength"] == pytest.approx(mu, rel=1e-12)
    assert o["HiggsExoticBR"] > 0.01  # non-negligible: h1 -> Z'Z' at small x


# --------------------------------------------------------- LHC dilepton (plugin)


def _plugin():
    spec = importlib.util.spec_from_file_location("lhc_dilepton_under_test", ROOT / "plugins" / "lhc_dilepton.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_production_ratio_insensitive_to_ud_luminosity_ratio():
    cu, cd = 0.28675, 0.36961
    f = lambda r: (r + 1) / (cu * r + cd)
    vals = [f(r) for r in np.linspace(2.0, 5.0, 31)]
    assert (max(vals) - min(vals)) / f(3.0) < 0.05
    assert abs(f(2.0) / f(3.0) - 1) < 0.025 and abs(f(5.0) / f(3.0) - 1) < 0.025


def test_ssm_couplings_and_branching_ratio():
    s2 = 0.23122
    assert (0.5 - 4 / 3 * s2) ** 2 + 0.25 == pytest.approx(0.28675, abs=5e-5)
    assert (-0.5 + 2 / 3 * s2) ** 2 + 0.25 == pytest.approx(0.36961, abs=5e-5)
    br = _plugin().br_ssm_ll(4000.0)
    assert br == pytest.approx(0.0308, abs=0.0005)  # ATLAS quotes ~3 % for Z'_SSM -> ee


def test_plugin_ratio_with_synthetic_tables(tmp_path, monkeypatch):
    mod = _plugin()
    d = tmp_path / "atlas_dilepton_139"
    d.mkdir()
    (d / "ssm_theory.csv").write_text("mass,sigmaB\n250,100\n6000,0.001\n")
    (d / "observed_limit.csv").write_text("mass,limit\n250,10\n6000,0.01\n")
    monkeypatch.setattr(mod, "DATA_DIR", d)
    mod._CACHE.clear()
    m = 3125.0  # arithmetic midpoint: log(sigma) is interpolated linearly in M
    th, lim = math.sqrt(100 * 0.001), math.sqrt(10 * 0.01)
    assert mod.ssm_sigma_over_limit({"M": m}, {}) == pytest.approx(th / (mod.br_ssm_ll(m) * lim), rel=1e-9)
    assert mod.ssm_sigma_over_limit({"M": 100.0}, {}) == 0.0
    assert mod.ssm_sigma_over_limit({"M": 7000.0}, {}) == 0.0


def test_plugin_fails_loudly_without_data(tmp_path, monkeypatch):
    mod = _plugin()
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "missing")
    mod._CACHE.clear()
    with pytest.raises(FileNotFoundError):
        mod.ssm_sigma_over_limit({"M": 1000.0}, {})


@pytest.mark.skipif(not DATA_PRESENT, reason="ATLAS arXiv:1903.06248 tables not provided yet")
def test_full_model_with_dilepton_limit_evaluates():
    model, cm = _build(strip_dilepton=False, strip_constraints=True)
    point = {p.name: p.default for p in model.parameters}
    o = cm.evaluate(point)["outputs"]
    assert math.isfinite(o["dilepton_signal_over_limit"]) and o["dilepton_signal_over_limit"] >= 0.0
