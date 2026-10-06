"""SMEFT scan plots: (C_HD, C_HWB) and (C_HD, C_Hbox), with analytic profile-likelihood contours.

    python plot_smeft.py <run_dir>

Points: valid scan points coloured by Delta NLL (2-dof thresholds 1.15 = 1 sigma, 5.92 = 3 sigma).
Contours: exact profile NLL of the model's likelihood (it is quadratic in these coefficients):
  (C_HD, C_HWB):  C_Hbox profiled (fits kappa_V exactly)  -> 1/2 d^T Sigma^-1 d,  d = (S - S0, T - T0)
  (C_HD, C_Hbox): C_HWB profiled (fits S given T)          -> 1/2 (T - T0)^2/sigma_T^2 + kappa_V term
with S = 4 s c eps C_HWB/alpha, T = -eps C_HD/(2 alpha), kappa_V = 1 + eps (C_Hbox - C_HD/4).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"
C1, C2, C3 = "#2a78d6", "#eda100", "#eb6834"
EPS, ALPHA = 246.22**2 / 1.0e6, 0.0078153
SC = math.sqrt(0.23122 * (1 - 0.23122))
S0, T0, SS, ST, RHO = -0.04, 0.01, 0.10, 0.12, 0.93
KV0, KVS = 1.035, 0.031
L1, L3 = 2.30 / 2, 11.83 / 2


def s_of(c_hwb):
    return 4 * SC * EPS * c_hwb / ALPHA


def t_of(c_hd):
    return -EPS * c_hd / (2 * ALPHA)


def nll_st(s, t):
    ds, dt = s - S0, t - T0
    det = 1 - RHO**2
    return 0.5 * (ds**2 / SS**2 + dt**2 / ST**2 - 2 * RHO * ds * dt / (SS * ST)) / det


def style(fig, ax, xlabel, ylabel, handles, out, legend_y=1.01):
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.tick_params(colors=INK2)
    for s in ax.spines.values():
        s.set_color(RULE)
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, legend_y), ncol=2, frameon=False,
              fontsize=7.6, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
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
    p["d"] = p["total_nll"] - p["total_nll"].min()
    best = json.loads((args.run_dir / "best_fit.json").read_text())["parameters"]

    def scatter(ax, x, y):
        out = p[p["d"] > L3]
        mid = p[(p["d"] > L1) & (p["d"] <= L3)]
        inn = p[p["d"] <= L1]
        ax.scatter(out[x], out[y], s=3, c="#c9c7c0", linewidths=0, rasterized=True, zorder=1)
        ax.scatter(mid[x], mid[y], s=4, c=C2, linewidths=0, rasterized=True, zorder=2)
        ax.scatter(inn[x], inn[y], s=4, c=C1, linewidths=0, alpha=0.7, rasterized=True, zorder=3)
        ax.plot(best[x.split("::")[1]], best[y.split("::")[1]], marker="*", ms=14, color=INK, mec=SURFACE,
                mew=1.2, ls="none", zorder=6)
        return [
            Line2D([], [], marker="o", ms=4, color=C1, ls="none", label=f"scan, ΔNLL ≤ 1.15 (1σ) ({len(inn):,})"),
            Line2D([], [], marker="o", ms=4, color=C2, ls="none", label=f"scan, ΔNLL ≤ 5.92 (3σ) ({len(mid):,})"),
            Line2D([], [], marker="o", ms=4, color="#c9c7c0", ls="none", label=f"scan, outside 3σ ({len(out):,})"),
            Line2D([], [], marker="*", ms=11, color=INK, ls="none", label="best fit (NLL = 2×10⁻¹²)"),
            Line2D([], [], color=INK, lw=1.6, label="analytic profile 1σ"),
            Line2D([], [], color=INK, lw=1.2, ls="--", label="analytic profile 3σ"),
        ]

    # ---- (C_HD, C_HWB): S-T ellipse
    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    h = scatter(ax, "param::C_HD", "param::C_HWB")
    xx = np.linspace(-0.1, 0.1, 500)
    yy = np.linspace(-0.035, 0.035, 500)
    X, Y = np.meshgrid(xx, yy)
    Z = nll_st(s_of(Y), t_of(X))
    ax.contour(X, Y, Z - Z.min(), levels=[L1], colors=[INK], linewidths=1.6, zorder=5)
    ax.contour(X, Y, Z - Z.min(), levels=[L3], colors=[INK], linewidths=1.2, linestyles="--", zorder=5)
    ax.set_xlim(-0.1, 0.1)
    ax.set_ylim(-0.035, 0.035)
    sec = ax.secondary_xaxis("top", functions=(t_of, lambda t: -2 * ALPHA * t / EPS))
    sec.set_xlabel("T", color=INK2)
    sec.tick_params(colors=INK2)
    secy = ax.secondary_yaxis("right", functions=(s_of, lambda s: s * ALPHA / (4 * SC * EPS)))
    secy.set_ylabel("S", color=INK2)
    secy.tick_params(colors=INK2)
    style(fig, ax, r"$C_{HD}$  ($\Lambda$ = 1 TeV)", r"$C_{HWB}$  ($\Lambda$ = 1 TeV)", h,
          args.run_dir / "C_HWB_vs_C_HD.png", legend_y=1.14)

    # ---- (C_HD, C_Hbox): T marginal + kappa_V
    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    h = scatter(ax, "param::C_HD", "param::C_Hbox")
    yy = np.linspace(-5, 5, 600)
    X, Y = np.meshgrid(xx, yy)
    kv = 1 + EPS * (Y - X / 4)
    Z = 0.5 * ((t_of(X) - T0) / ST) ** 2 + 0.5 * ((kv - KV0) / KVS) ** 2
    ax.contour(X, Y, Z - Z.min(), levels=[L1], colors=[INK], linewidths=1.6, zorder=5)
    ax.contour(X, Y, Z - Z.min(), levels=[L3], colors=[INK], linewidths=1.2, linestyles="--", zorder=5)
    ax.set_xlim(-0.1, 0.1)
    ax.set_ylim(-2.0, 3.0)
    style(fig, ax, r"$C_{HD}$  ($\Lambda$ = 1 TeV)", "$C_{H}$□  ($\\Lambda$ = 1 TeV)", h,
          args.run_dir / "C_Hbox_vs_C_HD.png")


if __name__ == "__main__":
    main()
