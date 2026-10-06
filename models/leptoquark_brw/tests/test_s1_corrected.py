"""Validation of the S1 leptoquark tutorial model (models/leptoquark_brw).

References re-implemented independently of the YAML: Angelescu et al. 1808.08179 Eqs. (26)-(27), (12);
Blanke et al. 1811.09603 Eqs. (13), (16)-(17); Dorsner et al. 1603.04993 Table 5 / Sec. 3.2.4;
Belle II 2311.14647 Eq. (1).
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
V, VCS, VCB, VTS, VTB, ALPHA, MT = 246.22, 0.97349, 0.04182, -0.04108, 0.999118, 0.0078153, 172.57
LHC = {"LHCPairMaxRatio", "lhc_pair_production"}


def _build(strip_constraints: bool):
    m = load_model_mapping(ROOT / "model.yaml")
    for sec in ("observables", "likelihoods"):
        m[sec] = [x for x in m[sec] if x["name"] not in LHC]
    m["outputs"]["save"] = [x for x in m["outputs"]["save"] if x not in LHC]
    if strip_constraints:
        m["theory_checks"], m["likelihoods"] = [], []
    model = ModelDefinition.from_mapping(m)
    return model, compile_model(model)


@pytest.fixture(scope="module")
def free():
    return _build(True)


@pytest.fixture(scope="module")
def full():
    return _build(False)


def ev(built, **over):
    model, cm = built
    point = {p.name: p.default for p in model.parameters}
    point.update(over)
    return cm.evaluate(point)


def _ref(M, y33, y23, yr):
    gvl = V**2 * y33 * (VCS * y23 + VCB * y33) / (4 * VCB * M**2)
    gsl_hi = -V**2 * y33 * yr / (4 * VCB * M**2)
    gt_hi = -gsl_hi / 4
    gsl = 1.752 * gsl_hi - 0.287 * gt_hi
    gt = -0.004 * gsl_hi + 0.842 * gt_hi
    rd = 0.296 * ((1 + gvl) ** 2 + 1.54 * (1 + gvl) * gsl + 1.09 * gsl**2 + 1.04 * (1 + gvl) * gt + 0.75 * gt**2)
    rds = 0.254 * ((1 + gvl) ** 2 - 0.13 * (1 + gvl) * gsl + 0.05 * gsl**2 - 5.0 * (1 + gvl) * gt + 16.27 * gt**2)
    csm = ALPHA * VTB * VTS * (-6.35) / math.pi
    cnp = V**2 * y33 * y23 / (2 * M**2)
    rnn = (2 + (1 + cnp / csm) ** 2) / 3
    return dict(gVL_obs=gvl, gSL_mb_obs=gsl, gT_mb_obs=gt, RD=rd, RDst=rds, R_nunu_obs=rnn,
                BR_BKnunu=4.97e-6 * rnn + 0.61e-6)


def test_sm_limit(free):
    o = ev(free, yL33=1e-4, yL23=1e-4, yR23=1e-4)["outputs"]
    assert o["RD"] == pytest.approx(0.296, rel=1e-6)
    assert o["RDst"] == pytest.approx(0.254, rel=1e-6)
    assert o["BR_BKnunu"] == pytest.approx(5.58e-6, rel=1e-6)  # Belle II Eq. (1) SM value


@pytest.mark.parametrize("pt", [dict(MS1=1500.0, yL33=1.0, yL23=0.2, yR23=0.3),
                                dict(MS1=3000.0, yL33=-0.8, yL23=0.05, yR23=1.2),
                                dict(MS1=900.0, yL33=0.3, yL23=-0.4, yR23=-0.1)])
def test_flavour_observables_against_references(free, pt):
    o = ev(free, **pt)["outputs"]
    ref = _ref(pt["MS1"], pt["yL33"], pt["yL23"], pt["yR23"])
    for k, v in ref.items():
        assert o[k] == pytest.approx(v, rel=1e-10, abs=1e-14), k


def test_running_reproduces_angelescu_ratio(free):
    """g_SL = -4 g_T at 1 TeV -> g_SL ~ -8.5 g_T at m_b (Angelescu et al., text below Eq. 10)."""
    o = ev(free, MS1=1000.0, yL33=0.5, yL23=1e-4, yR23=0.5)["outputs"]
    assert o["gSL_mb_obs"] / o["gT_mb_obs"] == pytest.approx(-8.5, abs=0.01)


def test_bnunu_interference_sign(free):
    """c_SM = alpha lambda_t C_L/pi > 0 (lambda_t < 0, C_L < 0): same-sign y33 y23 enhances B -> K nu nu."""
    up = ev(free, MS1=2000.0, yL33=0.5, yL23=0.3, yR23=1e-4)["outputs"]["R_nunu_obs"]
    dn = ev(free, MS1=2000.0, yL33=0.5, yL23=-0.3, yR23=1e-4)["outputs"]["R_nunu_obs"]
    assert up > 1.0 > dn


def test_branching_ratios(free):
    o = ev(free, MS1=5000.0, yL33=0.7, yL23=1e-4, yR23=1e-4)["outputs"]
    total = o["BR_ttau_obs"] + o["BR_bnu_obs"] + o["BR_ctau_obs"] + o["BR_snu_obs"]
    assert total == pytest.approx(1.0, abs=1e-12)
    x = MT**2 / 5000.0**2
    assert o["BR_ttau_obs"] / o["BR_bnu_obs"] == pytest.approx((1 - x) ** 2, rel=1e-10)
    assert o["WidthFraction"] == pytest.approx((0.7**2 * (1 + (1 - x) ** 2) + 3 * 1e-8) / (16 * math.pi), rel=1e-6)


def test_bc_lifetime_cut(full):
    """Gamma/M = 0.13 (passes the width cut) but g_SL(m_b) = 1.49 -> g_P = -1.49 < -1.14 (Eq. 12)."""
    pt = dict(MS1=1000.0, yL33=1.5, yL23=1e-4, yR23=-1.5)
    o = ev(_build(True), **pt)["outputs"]
    assert o["WidthFraction"] < 0.2 and o["gP_mb_obs"] < -1.14
    r = ev(full, **pt)
    assert not r["valid"] and "bc_lifetime" in r["failure_reason"]


def _plugin():
    spec = importlib.util.spec_from_file_location("lhc_pair_under_test", ROOT / "plugins" / "lhc_pair.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_lhc_plugin_synthetic(tmp_path, monkeypatch):
    mod = _plugin()
    d = tmp_path / "lhc_pair"
    d.mkdir()
    (d / "sigma_pair_nnlo.csv").write_text("m,s\n500,1000\n3000,0.01\n")
    (d / "limit_bnu.csv").write_text("m,s\n500,10\n3000,1\n")
    monkeypatch.setattr(mod, "DATA", d)
    mod._CACHE.clear()
    args = dict(M=500.0, BR_ttau=0.5, BR_bnu=0.5, BR_ctau=0.0, BR_snu=0.0)
    assert mod.max_ratio(args, {}) == pytest.approx(1000 * 0.25 / 10, rel=1e-12)
    assert mod.max_ratio(dict(args, M=4000.0), {}) == 0.0


def test_lhc_plugin_fails_loudly(tmp_path, monkeypatch):
    mod = _plugin()
    monkeypatch.setattr(mod, "DATA", tmp_path / "missing")
    mod._CACHE.clear()
    with pytest.raises(FileNotFoundError):
        mod.max_ratio(dict(M=1000.0, BR_ttau=0.5, BR_bnu=0.5, BR_ctau=0.0, BR_snu=0.0), {})
