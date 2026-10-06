"""Oblique T parameter vs inert-doublet mass splitting, with the PDG band.

    python plot_oblique.py <run_dir>

T (Barbieri-Hall-Rychkov, observables/electroweak.yaml) against
m_eta+ - m_eta0, m_eta0 = min(m_R, m_I). Horizontal bands: PDG 2024 (U = 0)
T = 0.00 +- 0.06 (Eq. 10.99b) at 1 sigma (+-0.06) and 3 sigma (+-0.18), one
parameter. S is not computed by the model, so no S-T ellipse is drawn.
Points: all valid scan points (faint), and those within the scan's own
Delta chi^2 <= 11.83 / 2.30 of its minimum.
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

T_MEAN, T_SIGMA = 0.00, 0.06
C1, C3 = "#2a78d6", "#eb6834"
INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()

    cols = ["valid", "total_nll", "output::oblique_T", "output::m_eta_charged", "output::m_eta_R", "output::m_eta_I"]
    parts = []
    for chunk in pd.read_csv(args.run_dir / "points.csv", usecols=cols, chunksize=500_000):
        chunk = chunk[chunk["valid"].astype(str).str.lower().isin(["true", "1"])]
        parts.append(chunk[np.isfinite(chunk["total_nll"])])
    d = pd.concat(parts, ignore_index=True)
    d["dchi2"] = d["total_nll"] - d["total_nll"].min()
    d["dm"] = d["output::m_eta_charged"] - np.minimum(d["output::m_eta_R"], d["output::m_eta_I"])
    best = json.loads((args.run_dir / "best_fit.json").read_text())["outputs"]
    bdm = best["m_eta_charged"] - min(best["m_eta_R"], best["m_eta_I"])

    fig, ax = plt.subplots(figsize=(6.4, 5.0), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for lo, hi in ((T_MEAN - 3 * T_SIGMA, T_MEAN - T_SIGMA), (T_MEAN + T_SIGMA, T_MEAN + 3 * T_SIGMA)):
        ax.axhspan(lo, hi, color=C3, alpha=0.15, lw=0, zorder=0)
    ax.axhspan(T_MEAN - T_SIGMA, T_MEAN + T_SIGMA, color=C1, alpha=0.25, lw=0, zorder=0)
    for k, c in ((1, C1), (3, C3)):
        for sgn in (-1, 1):
            ax.axhline(T_MEAN + sgn * k * T_SIGMA, color=c, lw=2, zorder=3)

    outer = d[(d["dchi2"] > 2.30) & (d["dchi2"] <= 11.83)]
    inner = d[d["dchi2"] <= 2.30]
    ax.scatter(d["dm"], d["output::oblique_T"], s=1, c="#d8d6cf", linewidths=0, rasterized=True, zorder=1)
    ax.scatter(outer["dm"], outer["output::oblique_T"], s=3, c="#9a9890", alpha=0.7, linewidths=0,
               rasterized=True, zorder=2)
    ax.scatter(inner["dm"], inner["output::oblique_T"], s=3, c="#3a3936", alpha=0.8, linewidths=0,
               rasterized=True, zorder=2)
    ax.plot(bdm, best["oblique_T"], marker="*", ms=15, color=INK, mec=SURFACE, mew=1.5, ls="none", zorder=5)

    handles = [
        Patch(facecolor=C1, alpha=0.5, edgecolor=C1, lw=2, label="PDG 2024 T, 1σ"),
        Patch(facecolor=C3, alpha=0.35, edgecolor=C3, lw=2, label="PDG 2024 T, 3σ"),
        Line2D([], [], marker="*", ms=12, color=INK, ls="none", label="scotogenic best fit"),
        Line2D([], [], marker="o", ms=4, color="#3a3936", ls="none", label="scan points, Δχ² ≤ 2.30"),
        Line2D([], [], marker="o", ms=4, color="#9a9890", ls="none", label="scan points, Δχ² ≤ 11.83"),
        Line2D([], [], marker="o", ms=4, color="#d8d6cf", ls="none", label="all valid scan points"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False,
              fontsize=8.5, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.2)
    ax.set_xlabel(r"$m_{\eta^\pm} - m_{\eta^0}$ [GeV]", color=INK)
    ax.set_ylabel(r"$T$", color=INK)
    ax.set_ylim(-0.25, max(0.3, float(d["output::oblique_T"].max()) * 1.05))
    ax.tick_params(colors=INK2)
    for s in ax.spines.values():
        s.set_color(RULE)
    fig.tight_layout()
    out = args.run_dir / "oblique_T.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(out, f"best fit: dm = {bdm:.2f} GeV, T = {best['oblique_T']:.4g}; "
          f"valid points with |T| > 3 sigma: {(d['output::oblique_T'].abs() > 3 * T_SIGMA).sum():,}")


if __name__ == "__main__":
    main()
