"""2HDM scan plots: (cos(beta-alpha), tan beta) and (m_H, m_H+-).

    python plot_2hdm.py <run_dir>

Valid points (top-level exploration + every basin_*/points.csv) coloured by Delta NLL at the 2-dof
thresholds 1.15 (1 sigma) and 5.92 (3 sigma); a random subsample of vetoed exploration points is
drawn behind them, coloured by failure reason.
Reference curves: kappa_V-only 1 sigma edge |c_ba| (interim Higgs likelihood), Type II
kappa_d = s_ba - c_ba tan(beta) contours (incl. the wrong-sign branch kappa_d = -1), the
B -> X_s gamma cut M_H+- = 800 GeV and the diagonal m_H = m_H+-.
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
C1, C2, C3, C4 = "#2a78d6", "#eda100", "#eb6834", "#1baf7a"
DNLL_1S, DNLL_3S = 1.15, 5.92
KV_MEAN, KV_SIG = 1.035, 0.031
FAIL_STYLE = {
    "unbounded": ("vetoed: unbounded from below", "#d8d6cf"),
    "unitarity": ("vetoed: perturbative unitarity", "#b9c7d8"),
    "bsgamma": ("vetoed: B → X_sγ (M_H± < 800 GeV)", "#f2c4b0"),
}


def load(run_dir: Path, cols: list[str]) -> pd.DataFrame:
    want = ["valid", "total_nll", "failure_reason"] + cols
    files = [run_dir / "points.csv", *sorted(run_dir.glob("basin_*/points.csv"))]
    return pd.concat([pd.read_csv(f, usecols=lambda c: c in want) for f in files], ignore_index=True)


def style(fig, ax, xlabel, ylabel, handles, out):
    ax.set_xlabel(xlabel, color=INK)
    ax.set_ylabel(ylabel, color=INK)
    ax.tick_params(colors=INK2, which="both")
    for s in ax.spines.values():
        s.set_color(RULE)
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False,
              fontsize=7.4, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--n-vetoed", type=int, default=30000)
    args = ap.parse_args()

    cols = ["param::tanb", "param::cos_ba", "param::mH", "param::mHp"]
    p = load(args.run_dir, cols)
    valid = p["valid"].astype(str).str.lower().isin(["true", "1"])
    v = p[valid].copy()
    nll_min = v["total_nll"].min()
    v["d"] = v["total_nll"] - nll_min
    bad = p[~valid]
    bad = bad.sample(n=min(args.n_vetoed, len(bad)), random_state=1)
    best = json.loads((args.run_dir / "best_fit.json").read_text())["parameters"]

    def background(ax, x, y):
        handles = []
        for key, (label, color) in FAIL_STYLE.items():
            sub = bad[bad["failure_reason"].fillna("").str.contains(key)]
            ax.scatter(sub[x], sub[y], s=1.5, c=color, linewidths=0, rasterized=True, zorder=1)
            handles.append(Line2D([], [], marker="o", ms=4, color=color, ls="none", label=label))
        return handles

    def foreground(ax, x, y):
        out = v[v["d"] > DNLL_3S]
        mid = v[(v["d"] > DNLL_1S) & (v["d"] <= DNLL_3S)]
        inn = v[v["d"] <= DNLL_1S]
        ax.scatter(out[x], out[y], s=5, c=INK2, linewidths=0, zorder=2)
        ax.scatter(mid[x], mid[y], s=6, c=C2, linewidths=0, zorder=3)
        ax.scatter(inn[x], inn[y], s=4, c=C1, linewidths=0, alpha=0.8, rasterized=True, zorder=4)
        ax.plot(best[x.split("::")[1]], best[y.split("::")[1]], marker="*", ms=14, color=INK, mec=SURFACE,
                mew=1.2, ls="none", zorder=6)
        return [
            Line2D([], [], marker="o", ms=4, color=C1, ls="none", label=f"valid, ΔNLL ≤ 1.15 (1σ) ({len(inn):,})"),
            Line2D([], [], marker="o", ms=4, color=C2, ls="none", label=f"valid, ΔNLL ≤ 5.92 (3σ) ({len(mid):,})"),
            Line2D([], [], marker="o", ms=4, color=INK2, ls="none", label=f"valid, outside 3σ ({len(out):,})"),
            Line2D([], [], marker="*", ms=11, color=INK, ls="none", label="best-fit point (one of the plateau)"),
        ]

    # ---------------- (cos(beta-alpha), tan beta)
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    h = background(ax, "param::cos_ba", "param::tanb") + foreground(ax, "param::cos_ba", "param::tanb")
    s_edge = KV_MEAN - KV_SIG * math.sqrt(2 * (0.5 * ((KV_MEAN - 1) / KV_SIG) ** 2 + DNLL_1S))
    c_edge = math.sqrt(1 - s_edge**2)
    for sgn in (-1, 1):
        ax.axvline(sgn * c_edge, color=C1, lw=1.4, ls="--", zorder=5)
    h.append(Line2D([], [], color=C1, lw=1.4, ls="--", label=f"κ_V-only 1σ: |cos(β−α)| = {c_edge:.3f}"))
    tb = np.logspace(math.log10(0.5), math.log10(60), 400)
    for kd, ls, lab in ((0.9, ":", "κ_d = 0.9, 1.1"), (1.1, ":", None), (-1.0, "-.", "κ_d = −1 (wrong sign)")):
        # kappa_d = sqrt(1-c^2) - c tanb  ->  solve for c on a grid
        cc = np.linspace(-0.3, 0.3, 4001)
        cs = []
        for t in tb:
            f = np.sqrt(1 - cc**2) - cc * t - kd
            idx = np.where(np.sign(f[:-1]) != np.sign(f[1:]))[0]
            cs.append(cc[idx[0]] if len(idx) else np.nan)
        ax.plot(cs, tb, color=C4, lw=1.2, ls=ls, zorder=5)
        if lab:
            h.append(Line2D([], [], color=C4, lw=1.2, ls=ls, label=lab))
    ax.set_yscale("log")
    ax.set_xlim(-0.3, 0.3)
    ax.set_ylim(0.5, 60)
    style(fig, ax, r"$\cos(\beta-\alpha)$", r"$\tan\beta$", h, args.run_dir / "tanb_vs_cosba.png")

    # ---------------- (m_H, m_H+-)
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    h = background(ax, "param::mH", "param::mHp") + foreground(ax, "param::mH", "param::mHp")
    ax.axhline(800.0, color=C3, lw=1.4, zorder=5)
    xx = np.array([130.0, 2000.0])
    ax.plot(xx, xx, color=INK2, lw=1.0, ls="--", zorder=5)
    h += [Line2D([], [], color=C3, lw=1.4, label="B → X_sγ: M_H± = 800 GeV"),
          Line2D([], [], color=INK2, lw=1.0, ls="--", label="m_H = m_H±")]
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(130, 2000)
    ax.set_ylim(130, 2000)
    style(fig, ax, r"$m_H$ [GeV]", r"$m_{H^\pm}$ [GeV]", h, args.run_dir / "mH_vs_mHp.png")


if __name__ == "__main__":
    main()
