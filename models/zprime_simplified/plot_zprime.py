"""Z' simplified DM model plots (curves through the production evaluator + scan points).

    python plot_zprime.py <run_dir>

1. sigmaSI_vs_mchi.png   sigma_SI vs m_chi: DM Forum benchmark (g_q = 0.25, g_chi = 1) at several M_Z',
                         plus valid scan points (colour = M_Z'). No LZ curve until data/lz_si_limit.csv exists.
2. width_vs_mzp.png      Gamma/M vs M_Z' at the benchmark couplings for several m_chi, vs the upstream proxy.
3. br_inv_plane.png      BR(Z' -> chi chi) in the (M_Z', m_chi) plane at the benchmark couplings.
4. gq_vs_gchi.png        valid / width-vetoed scan points in (g_q, g_chi) with the Gamma/M = 0.3 boundary
                         (massless limit, M_Z' >> 2 m_t, m_chi -> 0).
5. allowed_mzp_mchi.png  allowed region in (M_Z', m_chi): scan points and iso-sigma_SI contours at the benchmark.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bsm_scanner import compile_model
from bsm_scanner.api import load_model_mapping
from bsm_scanner.model.schema import ModelDefinition
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
DD = {"SigmaSILimit_cm2", "SigmaSIOverLimit", "lz_si_90cl"}
GQ, GCHI = 0.25, 1.0


def evaluator():
    m = load_model_mapping(ROOT / "model.yaml")
    m["theory_checks"], m["likelihoods"] = [], []
    m["observables"] = [x for x in m["observables"] if x["name"] not in DD]
    m["outputs"]["save"] = [x for x in m["outputs"]["save"] if x not in DD]
    return compile_model(ModelDefinition.from_mapping(m))


def new_ax(w=6.2, h=4.9):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    return fig, ax


def finish(fig, ax, xl, yl, out, handles=None, ncol=2):
    ax.set_xlabel(xl, color=INK)
    ax.set_ylabel(yl, color=INK)
    ax.tick_params(colors=INK2, which="both")
    for s in ax.spines.values():
        s.set_color(RULE)
    if handles:
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=ncol, frameon=False,
                  fontsize=7.6, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    cm = evaluator()
    ev = lambda **kw: cm.evaluate(kw)["outputs"]
    p = pd.read_csv(args.run_dir / "points.csv")
    valid = p["valid"].astype(str).str.lower().isin(["true", "1"])
    v = p[valid]

    # 1. sigma_SI vs m_chi
    fig, ax = new_ax()
    sc = ax.scatter(v["param::mchi"], v["output::SigmaSI_cm2"], c=v["param::MZp"], cmap="cividis", norm=LogNorm(100, 1e4),
                    s=6, linewidths=0, alpha=0.8, zorder=1)
    mm = np.logspace(0, math.log10(5000), 200)
    h = []
    for color, M in zip(SERIES, (500.0, 1000.0, 2000.0, 5000.0)):
        ss = [ev(MZp=M, mchi=x, gq=GQ, gchi=GCHI)["SigmaSI_cm2"] for x in mm]
        ax.plot(mm, ss, color=color, lw=1.8, zorder=3)
        h.append(Line2D([], [], color=color, lw=1.8, label=f"M_Z′ = {M/1000:g} TeV, g_q = 0.25, g_χ = 1"))
    ax.set_xscale("log")
    ax.set_yscale("log")
    cb = fig.colorbar(sc, ax=ax, pad=0.02)
    cb.set_label("scan points: M_Z′ [GeV]", color=INK2)
    cb.ax.tick_params(colors=INK2)
    h.append(Line2D([], [], marker="o", ms=4, color=INK2, ls="none", label=f"valid scan points ({len(v):,})"))
    finish(fig, ax, r"$m_\chi$ [GeV]", r"$\sigma_{\rm SI}$ (DM–nucleon) [cm$^2$]", args.run_dir / "sigmaSI_vs_mchi.png", h)

    # 2. width vs M_Z'
    fig, ax = new_ax()
    MM = np.logspace(2, 4, 300)
    h = []
    for color, mx in zip(SERIES, (1.0, 200.0, 1000.0)):
        ww = [ev(MZp=x, mchi=mx, gq=GQ, gchi=GCHI)["WidthFraction"] for x in MM]
        ax.plot(MM, ww, color=color, lw=1.8)
        h.append(Line2D([], [], color=color, lw=1.8, label=f"Eq. (2.3), m_χ = {mx:g} GeV"))
    proxy = (18 * GQ**2 + GCHI**2) / (12 * math.pi) * np.ones_like(MM)
    ax.plot(MM, proxy, color=INK, lw=1.2, ls=":")
    ax.axvline(2 * 172.57, color=RULE, lw=1.0, ls="--")
    ax.text(2 * 172.57 * 1.05, 0.0255, "2m_t", color=INK2, fontsize=8)
    h.append(Line2D([], [], color=INK, lw=1.2, ls=":", label="upstream proxy (no thresholds), m_χ → 0"))
    ax.set_xscale("log")
    finish(fig, ax, r"$M_{Z'}$ [GeV]", r"$\Gamma_{Z'}/M_{Z'}$  (g_q = 0.25, g_χ = 1)", args.run_dir / "width_vs_mzp.png", h)

    # 3. BR(Z' -> chi chi) plane
    fig, ax = new_ax(6.2, 5.0)
    mz = np.logspace(2, 4, 120)
    mx = np.logspace(0, math.log10(5000), 120)
    Z = np.array([[ev(MZp=a, mchi=b, gq=GQ, gchi=GCHI)["InvisibleBR"] for a in mz] for b in mx])
    pc = ax.pcolormesh(mz, mx, Z, cmap="Blues", vmin=0, vmax=max(Z.max(), 1e-9), shading="auto", rasterized=True)
    ax.plot(mz, mz / 2, color=SERIES[1], lw=1.6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    cb = fig.colorbar(pc, ax=ax, pad=0.02)
    cb.set_label(r"BR$(Z'\to\chi\bar\chi)$  (g_q = 0.25, g_χ = 1)", color=INK2)
    cb.ax.tick_params(colors=INK2)
    finish(fig, ax, r"$M_{Z'}$ [GeV]", r"$m_\chi$ [GeV]", args.run_dir / "br_inv_plane.png",
           [Line2D([], [], color=SERIES[1], lw=1.6, label="M_Z′ = 2 m_χ (invisible threshold)")], ncol=1)

    # 4. (g_q, g_chi) with the width boundary
    fig, ax = new_ax()
    bad = p[~valid & p["failure_reason"].fillna("").str.contains("width")]
    ax.scatter(v["param::gq"], v["param::gchi"], s=6, c=SERIES[0], linewidths=0, alpha=0.7, zorder=2)
    ax.scatter(bad["param::gq"], bad["param::gchi"], s=14, c=SERIES[1], marker="x", linewidths=0.9, zorder=3)
    gc = np.logspace(-3, math.log10(2), 300)
    gq_b = np.sqrt(np.clip(0.3 * 12 * math.pi - gc**2, 0, None) / 18)
    ax.plot(gq_b, gc, color=INK, lw=1.6, zorder=4)
    ax.set_xscale("log")
    ax.set_yscale("log")
    finish(fig, ax, r"$g_q$", r"$g_\chi$", args.run_dir / "gq_vs_gchi.png", [
        Line2D([], [], marker="o", ms=4, color=SERIES[0], ls="none", label=f"valid ({len(v):,})"),
        Line2D([], [], marker="x", ms=5, color=SERIES[1], ls="none", label=f"vetoed: Γ/M > 0.3 ({len(bad):,})"),
        Line2D([], [], color=INK, lw=1.6, label="Γ/M = 0.3 (M_Z′ ≫ 2m_t, m_χ → 0)"),
    ])

    # 5. allowed region in (M_Z', m_chi)
    plot_mass_plane(args.run_dir)


def plot_mass_plane(run_dir: Path) -> None:
    """Allowed region in (M_Z', m_chi): valid / vetoed scan points and iso-sigma_SI contours at the
    DM Forum benchmark couplings. With only the width cut active the allowed region is the full plane."""
    cm = evaluator()
    p = pd.read_csv(run_dir / "points.csv")
    valid = p["valid"].astype(str).str.lower().isin(["true", "1"])
    v, bad = p[valid], p[~valid]
    fig, ax = new_ax(6.4, 5.2)
    ax.scatter(v["param::MZp"], v["param::mchi"], s=7, c=SERIES[0], linewidths=0, alpha=0.75, zorder=2)
    ax.scatter(bad["param::MZp"], bad["param::mchi"], s=16, c=SERIES[1], marker="x", linewidths=0.9, zorder=3)
    mz = np.logspace(2, 4, 150)
    mx = np.logspace(0, math.log10(5000), 150)
    S = np.array([[cm.evaluate({"MZp": a, "mchi": b, "gq": GQ, "gchi": GCHI})["outputs"]["SigmaSI_cm2"] for a in mz]
                  for b in mx])
    levels = [-44, -42, -40, -38]
    cs = ax.contour(mz, mx, np.log10(S), levels=levels, colors=[INK2], linewidths=1.0, linestyles="--", zorder=4)
    ax.clabel(cs, fmt=lambda x: f"10$^{{{int(x)}}}$ cm$^2$", fontsize=7, colors=INK2)
    ax.plot(mz, mz / 2, color=SERIES[2], lw=1.6, zorder=4)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(100, 1e4)
    ax.set_ylim(1, 5000)
    finish(fig, ax, r"$M_{Z'}$ [GeV]", r"$m_\chi$ [GeV]", run_dir / "allowed_mzp_mchi.png", [
        Line2D([], [], marker="o", ms=4, color=SERIES[0], ls="none", label=f"allowed (width cut only) ({len(v):,})"),
        Line2D([], [], marker="x", ms=5, color=SERIES[1], ls="none", label=f"vetoed: Γ/M > 0.3 ({len(bad):,})"),
        Line2D([], [], color=INK2, lw=1.0, ls="--", label="σ_SI at g_q = 0.25, g_χ = 1"),
        Line2D([], [], color=SERIES[2], lw=1.6, label="M_Z′ = 2 m_χ"),
    ])


if __name__ == "__main__":
    main()
