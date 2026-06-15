from __future__ import annotations

import cmath
import math
from typing import Any

import numpy as np


PI = math.pi
GEV_TO_EV = 1.0e9
V_HIGGS = 246.22
PERTURBATIVITY_BOUND = 4.0 * PI

NUFIT6 = {
    "NO": {
        "s12": (0.308, 0.275, 0.345),
        "s23": (0.470, 0.435, 0.585),
        "s13": (0.02215, 0.02030, 0.02388),
        "delta_deg": (212.0, 124.0, 364.0),
        "dm21": (7.49e-5, 6.92e-5, 8.05e-5),
        "dm3l": (2.513e-3, 2.451e-3, 2.578e-3),
    },
    "IO": {
        "s12": (0.308, 0.275, 0.345),
        "s23": (0.550, 0.440, 0.584),
        "s13": (0.02231, 0.02060, 0.02409),
        "delta_deg": (274.0, 201.0, 335.0),
        "dm21": (7.49e-5, 6.92e-5, 8.05e-5),
        "dm3l": (-2.484e-3, -2.547e-3, -2.421e-3),
    },
}

LFV_LIMITS = {
    "BR_mu_to_e_gamma": 3.1e-13,
    "BR_tau_to_e_gamma": 3.3e-8,
    "BR_tau_to_mu_gamma": 2.2e-8,
    "BR_mu_to_3e": 1.0e-12,
    "BR_tau_to_3e": 2.7e-8,
    "BR_tau_to_3mu": 2.1e-8,
}


class GuidedSamplingError(ValueError):
    pass


def _bounds(context: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    return dict(context.get("lower", {})), dict(context.get("upper", {}))


def _in_bounds(name: str, value: float, context: dict[str, Any]) -> bool:
    lower, upper = _bounds(context)
    lo = float(lower.get(name, -math.inf))
    hi = float(upper.get(name, math.inf))
    return math.isfinite(value) and lo <= value <= hi


def _set_if_in_bounds(out: dict[str, float], name: str, value: float, context: dict[str, Any]) -> bool:
    value = float(value)
    if not _in_bounds(name, value, context):
        return False
    out[name] = value
    return True


def _uniform_in_bounds(
    point: dict[str, float],
    name: str,
    lo: float,
    hi: float,
    *,
    rng: np.random.Generator,
    context: dict[str, Any],
    log: bool = False,
) -> float | None:
    lower, upper = _bounds(context)
    if name not in point:
        return None
    lo = max(float(lo), float(lower.get(name, -math.inf)))
    hi = min(float(hi), float(upper.get(name, math.inf)))
    if hi <= lo:
        return None
    if log:
        lo = max(lo, 1.0e-30)
        return float(10.0 ** rng.uniform(math.log10(lo), math.log10(hi)))
    return float(rng.uniform(lo, hi))


def _infer_target_dm(point: dict[str, float], options: dict[str, Any]) -> str:
    configured = str(options.get("target_dm", "auto"))
    if configured.lower() != "auto":
        return configured
    return "H01" if "gap_chi" in point else "chi"


def _hierarchy(options: dict[str, Any]) -> str:
    raw = options.get("hierarchy", "NO")
    if isinstance(raw, bool):
        return "NO" if raw is False else "IO"
    hierarchy = str(raw).upper()
    if hierarchy in {"NORMAL", "NO"}:
        return "NO"
    if hierarchy in {"INVERTED", "IO"}:
        return "IO"
    raise GuidedSamplingError(f"Unsupported hierarchy '{hierarchy}'. Use NO or IO.")


def _i3(m_phi: float, m_phip: float, m_psi: float) -> float:
    a = m_phi * m_phi
    b = m_phip * m_phip
    c = m_psi * m_psi
    if min(abs(a - b), abs(a - c), abs(b - c)) < 1.0e-8 * max(a, b, c, 1.0):
        raise GuidedSamplingError("near-singular I3 loop masses")
    term_a = a * math.log(c / a) / ((a - b) * (a - c))
    term_b = b * math.log(c / b) / ((b - a) * (b - c))
    return -(term_a + term_b) / ((4.0 * PI) ** 2)


def _materialize(point: dict[str, float], target_dm: str) -> dict[str, float]:
    p = dict(point)
    if target_dm == "H01":
        p["MH01"] = float(p["Mdm"])
        p["Mchi"] = float(p["Mdm"]) + float(p.get("gap_chi", p.get("gap_H01", 0.0)))
        p["mphich"] = float(p["Mdm"]) + float(p["gap_charged"])
        p["MH02"] = float(p["Mdm"]) + float(p["gap_H02"])
        p["MA01"] = float(p["Mdm"]) + float(p["gap_A01"])
    else:
        p["Mchi"] = float(p["Mdm"])
        p["mphich"] = float(p["Mdm"]) + float(p["gap_charged"])
        p["MH01"] = float(p["Mdm"]) + float(p["gap_H01"])
        p["MH02"] = p["MH01"] + float(p["gap_H02"])
        p["MA01"] = float(p["Mdm"]) + float(p["gap_A01"])
    p["Mpsi"] = p["Mchi"]
    p["Mphi"] = p["mphich"]
    p["MH1"] = p["MH01"]
    p["MH2"] = p["MH02"]
    p["MA1"] = p["MA01"]
    return p


def _derive_scalars(p: dict[str, float]) -> dict[str, float]:
    sh = float(p["sh"])
    if not (0.0 < sh < 1.0):
        raise GuidedSamplingError("sh outside (0, 1)")
    ch = 1.0 - sh
    s_h = math.sqrt(sh)
    c_h = math.sqrt(ch)
    mphi_sq = float(p["Mphi"]) ** 2 - 0.5 * float(p["k1"]) * V_HIGGS**2
    mphip_sq = sh * float(p["MH1"]) ** 2 + ch * float(p["MH2"]) ** 2 - 0.5 * float(p["k4"]) * V_HIGGS**2
    if mphi_sq <= 0.0 or mphip_sq <= 0.0:
        raise GuidedSamplingError("non-positive scalar squared mass")
    mphi = math.sqrt(mphi_sq)
    mphip = math.sqrt(mphip_sq)
    m_ha22 = ch * float(p["MH2"]) ** 2 + sh * float(p["MH1"]) ** 2
    m_ha12 = c_h * s_h * (float(p["MH1"]) ** 2 - float(p["MH2"]) ** 2)
    denom = m_ha22 - float(p["MA1"]) ** 2
    if abs(denom) < 1.0e-12 * max(abs(m_ha22), float(p["MA1"]) ** 2, 1.0):
        raise GuidedSamplingError("near-singular pseudoscalar sector")
    ma2_sq = m_ha22 + m_ha12 * m_ha12 / denom
    if ma2_sq <= 0.0:
        raise GuidedSamplingError("non-positive MA2 squared")
    ca = 1.0 - min(max((ma2_sq - (sh * float(p["MH1"]) ** 2 + ch * float(p["MH2"]) ** 2)) / (ma2_sq - float(p["MA1"]) ** 2), 0.0), 1.0)
    k2 = (
        ch * float(p["MH1"]) ** 2
        + sh * float(p["MH2"]) ** 2
        + ca * float(p["MA1"]) ** 2
        + (1.0 - ca) * ma2_sq
        - 2.0 * float(p["Mphi"]) ** 2
    ) / V_HIGGS**2
    k3 = (
        (ch * float(p["MH1"]) ** 2 + sh * float(p["MH2"]) ** 2)
        - (ca * float(p["MA1"]) ** 2 + (1.0 - ca) * ma2_sq)
    ) / V_HIGGS**2
    return {
        "sH": s_h,
        "cH": c_h,
        "mp": mphi,
        "mpp": mphip,
        "muphi": math.sqrt(2.0 * sh * ch) * (float(p["MH1"]) ** 2 - float(p["MH2"]) ** 2) / V_HIGGS,
        "k2": k2,
        "k3": k3,
    }


def _pmns_matrix(s12: float, s13: float, s23: float, delta: float, alpha21: float, alpha31: float) -> np.ndarray:
    c12, c13, c23 = math.sqrt(1.0 - s12), math.sqrt(1.0 - s13), math.sqrt(1.0 - s23)
    s12r, s13r, s23r = math.sqrt(s12), math.sqrt(s13), math.sqrt(s23)
    eid = cmath.exp(1j * delta)
    emid = cmath.exp(-1j * delta)
    v = np.array(
        [
            [c12 * c13, s12r * c13, s13r * emid],
            [-s12r * c23 - c12 * s23r * s13r * eid, c12 * c23 - s12r * s23r * s13r * eid, s23r * c13],
            [s12r * s23r - c12 * c23 * s13r * eid, -c12 * s23r - s12r * c23 * s13r * eid, c23 * c13],
        ],
        dtype=np.complex128,
    )
    return v @ np.diag([1.0 + 0.0j, cmath.exp(0.5j * alpha21), cmath.exp(0.5j * alpha31)])


def _sample_range(
    name: str,
    default: tuple[float, float, float],
    *,
    rng: np.random.Generator,
    options: dict[str, Any],
) -> float:
    targets = options.get("targets", {})
    if isinstance(targets, dict) and name in targets:
        payload = targets[name]
        if isinstance(payload, dict):
            if "value" in payload:
                return float(payload["value"])
            lo = float(payload.get("lower", payload.get("min", default[1])))
            hi = float(payload.get("upper", payload.get("max", default[2])))
        else:
            lo, hi = float(payload[0]), float(payload[1])
    else:
        lo, hi = float(default[1]), float(default[2])
    if name == "delta_deg" and lo > hi:
        width = (hi + 360.0) - lo
        return float((lo + rng.uniform(0.0, width)) % 360.0)
    return float(rng.uniform(lo, hi))


def _sample_phase(
    name: str,
    *,
    rng: np.random.Generator,
    options: dict[str, Any],
) -> float:
    targets = options.get("targets", {})
    if isinstance(targets, dict) and name in targets:
        payload = targets[name]
        if isinstance(payload, dict):
            if "value" in payload:
                return float(payload["value"])
            lo = float(payload.get("lower", payload.get("min", 0.0)))
            hi = float(payload.get("upper", payload.get("max", 2.0 * PI)))
        else:
            lo, hi = float(payload[0]), float(payload[1])
        return float(rng.uniform(lo, hi))
    return float(rng.uniform(0.0, 2.0 * PI))


def _construct_yukawas(point: dict[str, float], target: dict[str, float], hierarchy: str, target_dm: str) -> dict[str, float]:
    p = _materialize(point, target_dm)
    scalars = _derive_scalars(p)
    s12 = float(target["s12"])
    s13 = float(target["s13"])
    s23 = float(target["s23"])
    delta = -math.radians(float(target["delta_deg"]) % 360.0)
    alpha21 = float(target["alpha21"])
    alpha31 = float(target["alpha31"])
    dm21 = float(target["dm21"])
    dm3l = float(target["dm3l"])
    yprime_abs = float(target["yprime_abs"])
    balance = float(target["yukawa_balance"])

    if hierarchy == "NO":
        masses_ev = np.array([0.0, math.sqrt(dm21), math.sqrt(dm3l)], dtype=float)
        nonzero = [1, 2]
    else:
        m2 = math.sqrt(abs(dm3l))
        m1 = math.sqrt(max(m2 * m2 - dm21, 0.0))
        masses_ev = np.array([m1, m2, 0.0], dtype=float)
        nonzero = [0, 1]

    base = -(
        float(scalars["muphi"])
        * V_HIGGS**2
        * float(p["Mchi"])
        * _i3(float(scalars["mp"]), float(scalars["mpp"]), float(p["Mchi"]))
        / float(p["MN"])
    )
    if base == 0.0 or not math.isfinite(base):
        raise GuidedSamplingError("zero loop normalization")
    yprime = yprime_abs if base > 0.0 else -yprime_abs
    lam = abs(base * yprime)
    if lam <= 0.0 or not math.isfinite(lam):
        raise GuidedSamplingError("invalid loop normalization")

    u = _pmns_matrix(s12, s13, s23, delta, alpha21, alpha31)
    e_a = np.conj(u[:, nonzero[0]])
    e_b = np.conj(u[:, nonzero[1]])
    m_a = masses_ev[nonzero[0]] / GEV_TO_EV
    m_b = masses_ev[nonzero[1]] / GEV_TO_EV
    a = math.sqrt(m_a / (2.0 * lam))
    b = math.sqrt(m_b / (2.0 * lam))
    y = balance * (a * e_a + 1j * b * e_b)
    y_n = (a * e_a - 1j * b * e_b) / balance

    out = dict(point)
    for i in range(3):
        out[f"ynr{i + 1}"] = float(np.real(y[i]))
        out[f"yni{i + 1}"] = float(np.imag(y[i]))
        out[f"Y1r{i + 1}"] = float(np.real(y_n[i]))
        out[f"Y1i{i + 1}"] = float(np.imag(y_n[i]))
    out["ypr11"] = float(np.real(yprime))
    out["ypi11"] = float(np.imag(yprime))
    return out


def _target_from_options(
    *,
    rng: np.random.Generator,
    options: dict[str, Any],
    hierarchy: str,
    yprime_abs_range: tuple[float, float],
    balance_range: tuple[float, float],
) -> dict[str, float]:
    ranges = NUFIT6[hierarchy]
    return {
        "s12": _sample_range("s12", ranges["s12"], rng=rng, options=options),
        "s13": _sample_range("s13", ranges["s13"], rng=rng, options=options),
        "s23": _sample_range("s23", ranges["s23"], rng=rng, options=options),
        "dm21": _sample_range("dm21", ranges["dm21"], rng=rng, options=options),
        "dm3l": _sample_range("dm3l", ranges["dm3l"], rng=rng, options=options),
        "delta_deg": _sample_range("delta_deg", ranges["delta_deg"], rng=rng, options=options),
        "alpha21": _sample_phase("alpha21", rng=rng, options=options),
        "alpha31": _sample_phase("alpha31", rng=rng, options=options),
        "yprime_abs": float(10.0 ** rng.uniform(math.log10(yprime_abs_range[0]), math.log10(yprime_abs_range[1]))),
        "yukawa_balance": float(10.0 ** rng.uniform(math.log10(balance_range[0]), math.log10(balance_range[1]))),
    }


def construct_yukawas_from_neutrino_targets(
    point: dict[str, float],
    *,
    rng: np.random.Generator | None = None,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    rng = np.random.default_rng() if rng is None else rng
    options = {} if options is None else dict(options)
    context = {} if context is None else dict(context)
    hierarchy = _hierarchy(options)
    target_dm = _infer_target_dm(point, options)
    yprime_range = (
        max(float(options.get("yprime_abs_min", 1.0e-7)), 1.0e-30),
        max(float(options.get("yprime_abs_max", 3.0)), 1.0e-30),
    )
    balance_range = (
        max(float(options.get("balance_min", 1.0e-3)), 1.0e-30),
        max(float(options.get("balance_max", 1.0e3)), 1.0e-30),
    )
    try:
        out = _construct_yukawas(
            point,
            _target_from_options(
                rng=rng,
                options=options,
                hierarchy=hierarchy,
                yprime_abs_range=yprime_range,
                balance_range=balance_range,
            ),
            hierarchy,
            target_dm,
        )
    except (GuidedSamplingError, FloatingPointError, ValueError, np.linalg.LinAlgError):
        return None
    for name in ("ypr11", "ypi11", "Y1r1", "Y1i1", "Y1r2", "Y1i2", "Y1r3", "Y1i3", "ynr1", "yni1", "ynr2", "yni2", "ynr3", "yni3"):
        if name in out and not _in_bounds(name, float(out[name]), context):
            return None
    return out


def rescale_yprime_to_neutrino_sum(
    point: dict[str, float],
    *,
    rng: np.random.Generator | None = None,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    rng = np.random.default_rng() if rng is None else rng
    options = {} if options is None else dict(options)
    context = {} if context is None else dict(context)
    target_min = max(float(options.get("target_sum_min_eV", 0.045)), 1.0e-30)
    target_max = max(target_min, float(options.get("target_sum_max_eV", 0.119)))
    target_sum = 10.0 ** rng.uniform(math.log10(target_min), math.log10(target_max))
    target_dm = _infer_target_dm(point, options)
    hierarchy = _hierarchy(options)
    try:
        p = _materialize(point, target_dm)
        scalars = _derive_scalars(p)
        yprime = complex(float(point["ypr11"]), float(point["ypi11"]))
        if abs(yprime) <= 0.0:
            return None
        y = np.array([complex(point[f"ynr{i}"], point[f"yni{i}"]) for i in range(1, 4)])
        y_n = np.array([complex(point[f"Y1r{i}"], point[f"Y1i{i}"]) for i in range(1, 4)])
        norm = -(
            float(scalars["muphi"])
            * V_HIGGS**2
            * float(p["Mchi"])
            * _i3(float(scalars["mp"]), float(scalars["mpp"]), float(p["Mchi"]))
            / float(p["MN"])
        ) * yprime
        matrix = norm * (np.outer(y_n, y) + np.outer(y, y_n))
        masses = np.linalg.svd(matrix, compute_uv=False)
        perm = [2, 1, 0] if hierarchy == "NO" else [1, 0, 2]
        raw_sum = float(np.sum(masses[perm]) * GEV_TO_EV)
        if raw_sum <= 0.0 or not math.isfinite(raw_sum):
            return None
        yprime *= target_sum / raw_sum
    except (GuidedSamplingError, FloatingPointError, ValueError, np.linalg.LinAlgError, KeyError):
        return None
    out = dict(point)
    if not _set_if_in_bounds(out, "ypr11", yprime.real, context):
        return None
    if not _set_if_in_bounds(out, "ypi11", yprime.imag, context):
        return None
    return out


def h01_scalar_dm_corridor(
    point: dict[str, float],
    *,
    rng: np.random.Generator | None = None,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    rng = np.random.default_rng() if rng is None else rng
    options = {} if options is None else dict(options)
    context = {} if context is None else dict(context)
    if _infer_target_dm(point, options) != "H01":
        return None

    out = dict(point)
    mode_roll = rng.random()
    if mode_roll < float(options.get("higgs_funnel_fraction", 0.25)):
        mdm = _uniform_in_bounds(point, "Mdm", float(options.get("funnel_mass_min", 62.8)), float(options.get("funnel_mass_max", 75.0)), rng=rng, context=context)
        sh = _uniform_in_bounds(point, "sh", 0.03, 0.997, rng=rng, context=context)
    elif mode_roll < float(options.get("higgs_funnel_fraction", 0.25)) + float(options.get("high_mass_fraction", 0.55)):
        mdm = _uniform_in_bounds(point, "Mdm", float(options.get("high_mass_min", 500.0)), float(options.get("high_mass_max", 1500.0)), rng=rng, context=context, log=True)
        sh = _uniform_in_bounds(point, "sh", 1.0e-3, 0.20, rng=rng, context=context, log=True)
    else:
        mdm = _uniform_in_bounds(point, "Mdm", float(options.get("mid_mass_min", 75.0)), float(options.get("mid_mass_max", 500.0)), rng=rng, context=context, log=True)
        sh = _uniform_in_bounds(point, "sh", 0.01, 0.80, rng=rng, context=context, log=True)
    if mdm is not None:
        out["Mdm"] = mdm
    if sh is not None:
        out["sh"] = sh
    for name, lo, hi in [
        ("gap_charged", float(options.get("gap_charged_min", 1.0)), float(options.get("gap_charged_max", 35.0))),
        ("gap_H02", float(options.get("gap_H02_min", 1.0)), float(options.get("gap_H02_max", 45.0))),
        ("gap_A01", float(options.get("gap_A01_min", 1.0)), float(options.get("gap_A01_max", 45.0))),
        ("gap_chi", float(options.get("gap_chi_min", 5.0)), float(options.get("gap_chi_max", 180.0))),
    ]:
        value = _uniform_in_bounds(point, name, lo, hi, rng=rng, context=context)
        if value is not None:
            out[name] = value
    for name, lo, hi, log in [("l2", 1.0e-3, 0.6, True), ("l3", 1.0e-3, 0.6, True), ("k5", 0.0, 0.5, False)]:
        value = _uniform_in_bounds(point, name, lo, hi, rng=rng, context=context, log=log)
        if value is not None:
            out[name] = value
    return out


def visible_si_corridor(
    point: dict[str, float],
    *,
    rng: np.random.Generator | None = None,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    rng = np.random.default_rng() if rng is None else rng
    options = {} if options is None else dict(options)
    context = {} if context is None else dict(context)
    if _infer_target_dm(point, options) != "chi":
        return None

    work = dict(point)
    gap = _uniform_in_bounds(point, "gap_charged", float(options.get("gap_charged_min", 5.0)), float(options.get("gap_charged_max", 60.0)), rng=rng, context=context)
    if gap is not None:
        work["gap_charged"] = gap
    k1_abs = _uniform_in_bounds(point, "k1", float(options.get("k1_abs_min", 1.5)), float(options.get("k1_abs_max", 7.5)), rng=rng, context=context)
    if k1_abs is not None:
        work["k1"] = -k1_abs if rng.random() < float(options.get("negative_k1_fraction", 0.25)) else k1_abs

    attempts = max(1, int(options.get("attempts", 8)))
    best: dict[str, float] | None = None
    best_score = -math.inf
    for _ in range(attempts):
        candidate = construct_yukawas_from_neutrino_targets(work, rng=rng, options=options, context=context)
        if candidate is None:
            continue
        yn_norm = math.sqrt(sum(candidate[f"ynr{i}"] ** 2 + candidate[f"yni{i}"] ** 2 for i in range(1, 4)))
        score = math.log10(max(abs(float(candidate.get("k1", work.get("k1", 0.0)))) * yn_norm * yn_norm, 1.0e-300))
        if score > best_score:
            best_score = score
            best = candidate
    return best
