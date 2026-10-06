"""Additional physics plots for the minimal B-L scan (valid points only).

    python plot_more.py <run_dir>

1. zp_width_vs_g.png        Gamma_Z'/M_Z' vs g'_1: full Eq. (3.7) width vs the upstream proxy g'^2/(12 pi)
2. br_ee_vs_mn_ratio.png    BR(Z' -> e e) vs M_N1/M_Z' (heavy-neutrino channel opening)
3. mn_vs_mzp.png            M_N1 vs M_Z', colour = BR(Z' -> N N), threshold M_N = M_Z'/2
4. mu_vs_sinalpha.png       mu_h vs sin(alpha) with the LHC Run-2 measurement band
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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"
C1, C2, C3 = "#2a78d6", "#1baf7a", "#eb6834"


def new_ax():
    fig, ax = plt.subplots(figsize=(6.0, 4.8), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    return fig, ax


def finish(fig, ax, xlabel, ylabel, out, handles=None, ncol=2):
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.tick_params(colors=INK2, which="both")
    for s in ax.spines.values():
        s.set_color(RULE)
    if handles:
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=ncol, frameon=False,
                  fontsize=7.8, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    p = pd.read_csv(args.run_dir / "points.csv")
    p = p[p["valid"].astype(str).str.lower().isin(["true", "1"])].copy()
    g = p["param::gBL"].to_numpy()
    mzp = p["output::MZprime"].to_numpy()
    mn1 = p["output::HeavyNeutrino1Mass"].to_numpy()
    dot = dict(s=4, linewidths=0, alpha=0.75, rasterized=True)

    # 1. Z' width
    fig, ax = new_ax()
    ax.scatter(g, p["output::ZprimeWidthOverMass"], c=C1, **dot, zorder=2)
    gg = np.logspace(-3, 0, 200)
    ax.plot(gg, 13 * gg**2 / (24 * math.pi), color=INK, lw=1.4, zorder=3)
    ax.plot(gg, 8 * gg**2 / (12 * math.pi), color=INK, lw=1.4, ls="--", zorder=3)
    ax.plot(gg, gg**2 / (12 * math.pi), color=C3, lw=1.6, ls=":", zorder=3)
    ax.axhline(0.1, color=C3, lw=1.2, zorder=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    finish(fig, ax, r"$g'_1$", r"$\Gamma_{Z'}/M_{Z'}$", args.run_dir / "zp_width_vs_g.png", [
        Line2D([], [], marker="o", ms=4, color=C1, ls="none", label="scan points (full Eq. 3.7 width)"),
        Line2D([], [], color=INK, lw=1.4, label=r"$13g'^2/24\pi$ (no heavy N)"),
        Line2D([], [], color=INK, lw=1.4, ls="--", label=r"$8g'^2/12\pi$ (three light N)"),
        Line2D([], [], color=C3, lw=1.6, ls=":", label=r"upstream proxy $g'^2/12\pi$"),
        Line2D([], [], color=C3, lw=1.2, label="narrow-width cut Γ/M = 0.1"),
    ])

    # 2. BR(Z' -> ee) vs M_N1 / M_Z'
    fig, ax = new_ax()
    ax.scatter(mn1 / mzp, p["output::BRZprimeToEE"], c=C1, **dot, zorder=2)
    ax.axhline(1 / 6.5, color=INK, lw=1.2, ls="--", zorder=1)
    ax.axhline(1 / 8, color=INK, lw=1.2, ls=":", zorder=1)
    ax.axvline(0.5, color=C3, lw=1.2, zorder=1)
    ax.set_xscale("log")
    finish(fig, ax, r"$M_{N_1}/M_{Z'}$", r"BR$(Z'\to e^+e^-)$", args.run_dir / "br_ee_vs_mn_ratio.png", [
        Line2D([], [], marker="o", ms=4, color=C1, ls="none", label="scan points"),
        Line2D([], [], color=INK, lw=1.2, ls="--", label="1/6.5 = 15.4 % (all N closed)"),
        Line2D([], [], color=INK, lw=1.2, ls=":", label="1/8 = 12.5 % (all N light)"),
        Line2D([], [], color=C3, lw=1.2, label=r"$Z'\to N_1N_1$ threshold"),
    ])

    # 3. M_N1 vs M_Z', colour = BR(Z' -> NN)
    fig, ax = new_ax()
    sc = ax.scatter(mzp, mn1, c=p["output::BRZprimeToNN"], cmap="Blues", vmin=0, vmax=0.1875, s=5,
                    linewidths=0, rasterized=True, zorder=2)
    xx = np.logspace(0, 6, 50)
    ax.plot(xx, xx / 2, color=C3, lw=1.4, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(mzp.min() / 1.5, mzp.max() * 1.5)
    ax.set_ylim(mn1.min() / 1.5, mn1.max() * 1.5)
    cb = fig.colorbar(sc, ax=ax, pad=0.02)
    cb.set_label(r"BR$(Z'\to NN)$, summed over $N_{1,2,3}$", color=INK2)
    cb.ax.tick_params(colors=INK2)
    finish(fig, ax, r"$M_{Z'}$ [GeV]", r"$M_{N_1}$ [GeV]", args.run_dir / "mn_vs_mzp.png", [
        Line2D([], [], color=C3, lw=1.4, label=r"$M_{N_1} = M_{Z'}/2$ (decay threshold)"),
    ], ncol=1)

    # 4. mu_h vs sin(alpha)
    fig, ax = new_ax()
    mean, sig = 1.025, 0.06
    ax.axhspan(mean - sig, mean + sig, color=C1, alpha=0.18, lw=0, zorder=0)
    ax.axhline(mean, color=C1, lw=1.2, zorder=1)
    sa = p["param::sin_alpha"].to_numpy()
    exotic = p["output::HiggsExoticBR"].to_numpy() > 1e-4
    ax.scatter(sa[~exotic], p["output::HiggsSignalStrength"].to_numpy()[~exotic], c=INK2, **dot, zorder=2)
    ax.scatter(sa[exotic], p["output::HiggsSignalStrength"].to_numpy()[exotic], c=C3, s=10, linewidths=0, zorder=3)
    ss = np.linspace(-0.35, 0.35, 200)
    ax.plot(ss, 1 - ss**2, color=INK, lw=1.2, ls="--", zorder=2)
    finish(fig, ax, r"$\sin\alpha$", r"$\mu_{h_1}$", args.run_dir / "mu_vs_sinalpha.png", [
        Patch(facecolor=C1, alpha=0.35, edgecolor=C1, label="LHC Run 2: 1.025 ± 0.06"),
        Line2D([], [], color=INK, lw=1.2, ls="--", label=r"$\cos^2\alpha$ (no exotic decays)"),
        Line2D([], [], marker="o", ms=4, color=INK2, ls="none", label="scan points"),
        Line2D([], [], marker="o", ms=5, color=C3, ls="none",
               label=f"BR(h₁→NN, Z′Z′) > 10⁻⁴ ({int(exotic.sum())})"),
    ])


if __name__ == "__main__":
    main()
