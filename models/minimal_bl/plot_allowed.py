"""Allowed-region plots for the minimal B-L scan: (M_Z', g') and (m_h2, sin alpha).

    python plot_allowed.py <run_dir>

Points: valid scan points with Delta NLL <= 1.15 (1 sigma, 2 dof) and <= 5.92 (3 sigma, 2 dof),
other valid points, and points vetoed by the LEP contact bound or the Z' narrow-width cut.
Lines: analytic boundaries of the LEP bound (M_Z' >= 7 TeV g'), the narrow-width cut
(Gamma/M < 0.1 with the full Eq. 3.7 width: g' < 0.686 with three light N, 0.760 with none),
the scan domain (x = vBL in [1, 100] TeV), and the mu_h 1 sigma (2 dof) value of |sin alpha|.
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

INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"
C1, C3, CX, CV = "#2a78d6", "#eb6834", "#c3c2b7", "#9a9890"
DNLL_1S, DNLL_3S = 2.30 / 2, 11.83 / 2  # NLL objective: Delta NLL = Delta chi^2 / 2
MU_MEAN, MU_SIGMA = 1.025, 0.06


def sin_alpha_edge(dnll: float, nll_min: float) -> float:
    """|sin alpha| where NLL(mu = 1 - s^2) - NLL_min = dnll (exotic decays neglected)."""
    s2 = MU_SIGMA * math.sqrt(2 * (nll_min + dnll)) - (MU_MEAN - 1.0)
    return math.sqrt(max(s2, 0.0))


def style(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.tick_params(colors=INK2, which="both")
    for s in ax.spines.values():
        s.set_color(RULE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()

    p = pd.read_csv(args.run_dir / "points.csv")
    valid = p["valid"].astype(str).str.lower().isin(["true", "1"])
    reason = p["failure_reason"].fillna("")
    p["MZp"] = 2.0 * p["param::gBL"] * p["param::vBL"]
    nll_min = p.loc[valid, "total_nll"].min()
    p["dnll"] = np.where(valid, p["total_nll"] - nll_min, np.inf)
    best = json.loads((args.run_dir / "best_fit.json").read_text())["parameters"]

    groups = [
        ("vetoed: LEP contact bound", ~valid & reason.str.contains("lep_contact"), CX, "x", 14),
        ("vetoed: Z′ narrow width", ~valid & reason.str.contains("narrow_width"), C3, "x", 14),
        ("valid, outside 3σ", valid & (p["dnll"] > DNLL_3S), CV, "o", 4),
        ("valid, ΔNLL ≤ 5.92 (3σ)", valid & (p["dnll"] <= DNLL_3S) & (p["dnll"] > DNLL_1S), "#eda100", "o", 7),
        ("valid, ΔNLL ≤ 1.15 (1σ)", valid & (p["dnll"] <= DNLL_1S), C1, "o", 4),
    ]

    # ---------------- (M_Z', g')
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for label, sel, color, marker, size in groups:
        sub = p[sel]
        ax.scatter(sub["MZp"], sub["param::gBL"], s=size, c=color, marker=marker, linewidths=0.8 if marker == "x" else 0,
                   alpha=0.8, rasterized=True, label=f"{label} ({len(sub):,})", zorder=2)
    g = np.logspace(-3, 0, 200)
    ax.plot(7000.0 * g, g, color=INK, lw=1.6, zorder=3, label="LEP: M_Z′ = 7 TeV · g′")
    for gmax, ls, lab in ((0.686, "--", "Γ/M = 0.1, three light N"), (0.760, ":", "Γ/M = 0.1, no N")):
        ax.axhline(gmax, color=C3, lw=1.6, ls=ls, zorder=3, label=lab)
    for i, x in enumerate((1.0e3, 1.0e5)):
        ax.plot(2 * g * x, g, color=INK2, lw=0.8, ls="-.", zorder=1,
                label="scan domain edges, x = 1 and 100 TeV" if i == 0 else None)
    ax.plot(2 * best["gBL"] * best["vBL"], best["gBL"], marker="*", ms=14, color=INK, mec=SURFACE, mew=1.2,
            ls="none", zorder=5, label="best-fit point (one of the flat minimum)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1.0, 3.0e5)
    ax.set_ylim(8e-4, 1.2)
    style(ax, r"$M_{Z'}$ [GeV]", r"$g'_1$")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False, fontsize=7.2,
              labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    out1 = args.run_dir / "allowed_MZp_gBL.png"
    fig.savefig(out1, facecolor=fig.get_facecolor())

    # ---------------- (m_h2, sin alpha)
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for label, sel, color, marker, size in groups[2:]:
        sub = p[sel]
        ax.scatter(sub["param::sin_alpha"], sub["param::mH2"], s=size, c=color, linewidths=0, alpha=0.8,
                   rasterized=True, label=f"{label} ({len(sub):,})", zorder=2)
    s1 = sin_alpha_edge(DNLL_1S, nll_min)
    for sgn in (-1, 1):
        ax.axvline(sgn * s1, color=C1, lw=1.8, zorder=3)
    ax.plot([], [], color=C1, lw=1.8, label=f"μ_h 1σ (2 dof): |sin α| = {s1:.3f}")
    ax.plot(best["sin_alpha"], best["mH2"], marker="*", ms=14, color=INK, mec=SURFACE, mew=1.2, ls="none",
            zorder=5, label="best-fit point (one of the flat minimum)")
    ax.set_yscale("log")
    ax.set_xlim(-0.36, 0.36)
    style(ax, r"$\sin\alpha$", r"$m_{h_2}$ [GeV]")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False, fontsize=7.2,
              labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    out2 = args.run_dir / "allowed_mH2_sinalpha.png"
    fig.savefig(out2, facecolor=fig.get_facecolor())
    print(out1, out2, f"NLL_min={nll_min:.5f}", f"|sin a| 1sigma(2dof)={s1:.4f}",
          f"3sigma(2dof)={sin_alpha_edge(DNLL_3S, nll_min):.4f}")


if __name__ == "__main__":
    main()
