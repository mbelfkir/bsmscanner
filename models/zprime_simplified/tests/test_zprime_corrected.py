"""Validation of the corrected Z' simplified DM model (models/zprime_simplified).

References: DM Forum arXiv:1507.00966 Eq. (2.3) (independent re-implementation), Boveia et al.
arXiv:1603.04156 Eqs. (4.1)-(4.3) including their numerical normalisation 6.9e-41 cm^2.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest
from bsm_scanner import compile_model
from bsm_scanner.api import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition

ROOT = Path(__file__).resolve().parents[1]
QUARKS = [0.00216, 0.00470, 0.0935, 1.2730, 4.183, 172.57]
DD = {"SigmaSILimit_cm2", "SigmaSIOverLimit", "lz_si_90cl"}
DATA_PRESENT = (ROOT / "data" / "lz_si_limit.csv").exists()


@pytest.fixture(scope="module")
def free():
    m = load_model_mapping(ROOT / "model.yaml")
    m["theory_checks"], m["likelihoods"] = [], []
    m["observables"] = [x for x in m["observables"] if x["name"] not in DD]
    m["outputs"]["save"] = [x for x in m["outputs"]["save"] if x not in DD]
    model = ModelDefinition.from_mapping(m)
    return model, compile_model(model)


def ev(built, **over):
    model, cm = built
    point = {p.name: p.default for p in model.parameters}
    point.update(over)
    return cm.evaluate(point)["outputs"]


def _vf(m, M):
    return (1 + 2 * m**2 / M**2) * math.sqrt(1 - 4 * m**2 / M**2) if 2 * m < M else 0.0


@pytest.mark.parametrize("M,mchi,gq,gchi", [(3000.0, 500.0, 0.25, 1.0), (250.0, 50.0, 0.1, 1.5),
                                             (1000.0, 600.0, 1.0, 0.3), (120.0, 1.0, 0.01, 0.01)])
def test_width_dm_forum_eq_2_3(free, M, mchi, gq, gchi):
    o = ev(free, MZp=M, mchi=mchi, gq=gq, gchi=gchi)
    g_chi = gchi**2 * M / (12 * math.pi) * _vf(mchi, M)
    g_q = sum(3 * gq**2 * M / (12 * math.pi) * _vf(m, M) for m in QUARKS)
    assert o["WidthFraction"] == pytest.approx((g_chi + g_q) / M, rel=1e-12)
    assert o["InvisibleBR"] == pytest.approx(g_chi / (g_chi + g_q), rel=1e-12, abs=1e-15)


def test_width_top_threshold_regression(free):
    """Upstream proxy 18 g_q^2 M/(12 pi) ignored the top threshold: 17 % too large below 2 m_t."""
    o = ev(free, MZp=300.0, mchi=500.0, gq=0.5, gchi=1.0)
    proxy = 18 * 0.5**2 * 300.0 / (12 * math.pi)
    assert o["WidthFraction"] * 300.0 == pytest.approx(proxy * 15 / 18, rel=2e-3)


@pytest.mark.parametrize("M,mchi,gq,gchi", [(1000.0, 100.0, 0.25, 1.0), (2500.0, 30.0, 0.1, 0.5),
                                             (500.0, 5.0, 1.0, 1.0)])
def test_sigma_si_boveia(free, M, mchi, gq, gchi):
    o = ev(free, MZp=M, mchi=mchi, gq=gq, gchi=gchi)
    mu = 0.939 * mchi / (0.939 + mchi)
    exact = (3 * gq) ** 2 * gchi**2 * mu**2 / (math.pi * M**4) * 3.893794e-28
    assert o["SigmaSI_cm2"] == pytest.approx(exact, rel=1e-12)
    # Boveia et al. Eq. (4.3) numerical form (quoted to 2 digits)
    approx = 6.9e-41 * (gq * gchi / 0.25) ** 2 * (1000.0 / M) ** 4 * mu**2
    assert o["SigmaSI_cm2"] == pytest.approx(approx, rel=0.01)


def _plugin():
    spec = importlib.util.spec_from_file_location("si_limit_under_test", ROOT / "plugins" / "si_limit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_si_plugin_interpolation(tmp_path, monkeypatch):
    mod = _plugin()
    f = tmp_path / "lz.csv"
    f.write_text("mass,sigma\n10,1e-46\n1000,1e-46\n")
    monkeypatch.setattr(mod, "DATA", f)
    mod._CACHE.clear()
    assert mod.sigma_limit_cm2({"m": 100.0}, {}) == pytest.approx(1e-46, rel=1e-12)
    assert mod.sigma_limit_cm2({"m": 2000.0}, {}) == pytest.approx(2e-46, rel=1e-12)  # linear extrapolation
    assert mod.sigma_limit_cm2({"m": 5.0}, {}) == math.inf


def test_si_plugin_fails_loudly(tmp_path, monkeypatch):
    mod = _plugin()
    monkeypatch.setattr(mod, "DATA", tmp_path / "missing.csv")
    mod._CACHE.clear()
    with pytest.raises(FileNotFoundError):
        mod.sigma_limit_cm2({"m": 100.0}, {})


@pytest.mark.skipif(not DATA_PRESENT, reason="LZ SI limit table not provided yet")
def test_full_model_with_lz():
    model = ModelDefinition.from_mapping(load_model_mapping(ROOT / "model_with_direct_detection.yaml"))
    cm = compile_model(model)
    r = cm.evaluate({p.name: p.default for p in model.parameters})
    assert "SigmaSIOverLimit" in r["outputs"] or not r["valid"]
