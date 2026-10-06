"""S1 leptoquark scan plots.

    python plot_s1.py <run_dir>

1. rd_rdst.png         R(D) vs R(D*): HFLAV ellipses (1, 3 sigma, 2 dof; exp + SM covariance as in the fit),
                       SM point, scan points coloured by Delta NLL, best fit.
2. coupling_plane.png  (yL33^2/M^2, yL33 yL23/M^2) [TeV^-2]: the two combinations fixed by R(D(*)) via g_VL
                       and by B -> K nu nu.
3. bknunu_vs_mass.png  B(B+ -> K+ nu nu) vs M_S1 with the Belle II band; reference line at the 100 %-BR
                       bb nu nu pair limit 1.81 TeV (35.9 fb^-1, Angelescu et al. 1808.08179 Table 3) --
                       a reference only, not applied in the fit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"
C1, C2, C3, C4 = "#2a78d6", "#eda100", "#eb6834", "#1baf7a"
L1, L3 = 1.15, 5.92
MEAN = np.array([0.342, 0.287])
COV = np.array([[0.000692, -0.00012168], [-0.00012168, 0.000169]])
SM = (0.296, 0.254)


def new_ax():
    fig, ax = plt.subplots(figsize=(6.2, 5.0), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    return fig, ax


def finish(fig, ax, xl, yl, out, handles, ncol=2):
    ax.set_xlabel(xl, color=INK)
    ax.set_ylabel(yl, color=INK)
    ax.tick_params(colors=INK2, which="both")
    for s in ax.spines.values():
        s.set_color(RULE)
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=ncol, frameon=False,
              fontsize=7.4, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    p = pd.read_csv(args.run_dir / "points.csv")
    v = p[p["valid"].astype(str).str.lower().isin(["true", "1"])].copy()
    v["d"] = v["total_nll"] - v["total_nll"].min()
    v["M_TeV"] = v["param::MS1"] / 1000.0
    v["c33"] = v["param::yL33"] ** 2 / v["M_TeV"] ** 2
    v["c3323"] = v["param::yL33"] * v["param::yL23"] / v["M_TeV"] ** 2
    best = json.loads((args.run_dir / "best_fit.json").read_text())
    bp, bo = best["parameters"], best["outputs"]
    groups = [(v[v["d"] > L3], "#c9c7c0", 3, "outside 3σ"), (v[(v["d"] > L1) & (v["d"] <= L3)], C2, 4, "ΔNLL ≤ 5.92 (3σ)"),
              (v[v["d"] <= L1], C1, 4, "ΔNLL ≤ 1.15 (1σ)")]

    def scatter(ax, x, y):
        hs = []
        for sub, color, size, lab in groups:
            ax.scatter(sub[x], sub[y], s=size, c=color, linewidths=0, alpha=0.7, rasterized=True, zorder=2)
            hs.append(Line2D([], [], marker="o", ms=4, color=color, ls="none", label=f"scan, {lab} ({len(sub):,})"))
        return hs

    # 1. R(D) vs R(D*)
    fig, ax = new_ax()
    h = scatter(ax, "output::RD", "output::RDst")
    xx, yy = np.meshgrid(np.linspace(0.20, 0.50, 400), np.linspace(0.22, 0.34, 400))
    inv = np.linalg.inv(COV)
    dx, dy = xx - MEAN[0], yy - MEAN[1]
    chi2 = inv[0, 0] * dx**2 + 2 * inv[0, 1] * dx * dy + inv[1, 1] * dy**2
    ax.contour(xx, yy, chi2, levels=[2.30], colors=[INK], linewidths=1.6, zorder=4)
    ax.contour(xx, yy, chi2, levels=[11.83], colors=[INK], linewidths=1.2, linestyles="--", zorder=4)
    ax.plot(*SM, marker="D", ms=8, color=C3, mec=SURFACE, ls="none", zorder=5)
    ax.plot(bo["RD"], bo["RDst"], marker="*", ms=14, color=INK, mec=SURFACE, mew=1.2, ls="none", zorder=6)
    ax.set_xlim(0.20, 0.50)
    ax.set_ylim(0.22, 0.34)
    h += [Line2D([], [], color=INK, lw=1.6, label="HFLAV 2024, 1σ"), Line2D([], [], color=INK, lw=1.2, ls="--", label="HFLAV 2024, 3σ"),
          Line2D([], [], marker="D", ms=6, color=C3, ls="none", label="SM"),
          Line2D([], [], marker="*", ms=11, color=INK, ls="none", label="S1 best fit")]
    finish(fig, ax, r"$R(D)$", r"$R(D^*)$", args.run_dir / "rd_rdst.png", h)

    # 2. coupling combinations
    fig, ax = new_ax()
    h = scatter(ax, "c33", "c3323")
    mb = bp["MS1"] / 1000.0
    ax.plot(bp["yL33"] ** 2 / mb**2, bp["yL33"] * bp["yL23"] / mb**2, marker="*", ms=14, color=INK, mec=SURFACE,
            mew=1.2, ls="none", zorder=6)
    ax.axhline(0.0, color=RULE, lw=1.0, zorder=1)
    ax.set_xscale("log")
    ax.set_xlim(1e-3, 30)
    ax.set_ylim(-0.3, 0.3)
    h.append(Line2D([], [], marker="*", ms=11, color=INK, ls="none", label="best fit"))
    finish(fig, ax, r"$(y_L^{33})^2/M_{S_1}^2$ [TeV$^{-2}$]  (g$_{VL}$ via V$_{cb}$, R(D$^{(*)}$))",
           r"$y_L^{33}y_L^{23}/M_{S_1}^2$ [TeV$^{-2}$]  (B → Kνν̄)", args.run_dir / "coupling_plane.png", h)

    # 3. B -> K nu nu vs mass
    fig, ax = new_ax()
    ax.axhspan(2.3e-5 - 0.640e-5, 2.3e-5 + 0.707e-5, color=C1, alpha=0.15, lw=0, zorder=0)
    ax.axhline(2.3e-5, color=C1, lw=1.2, zorder=1)
    ax.axhline(5.58e-6, color=C3, lw=1.2, ls="--", zorder=1)
    h = scatter(ax, "param::MS1", "output::BR_BKnunu")
    ax.axvline(1810.0, color=INK2, lw=1.2, ls=":", zorder=1)
    ax.plot(bp["MS1"], bo["BR_BKnunu"], marker="*", ms=14, color=INK, mec=SURFACE, mew=1.2, ls="none", zorder=6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(1e-6, 2e-4)
    h += [Patch(facecolor=C1, alpha=0.35, edgecolor=C1, label="Belle II 2023 (±1σ)"),
          Line2D([], [], color=C3, lw=1.2, ls="--", label="SM 5.58×10⁻⁶"),
          Line2D([], [], color=INK2, lw=1.2, ls=":", label="bb̄νν̄ pair limit, 100 % BR (ref. only)"),
          Line2D([], [], marker="*", ms=11, color=INK, ls="none", label="best fit")]
    finish(fig, ax, r"$M_{S_1}$ [GeV]", r"B$(B^+\to K^+\nu\bar\nu)$", args.run_dir / "bknunu_vs_mass.png", h)


if __name__ == "__main__":
    main()
