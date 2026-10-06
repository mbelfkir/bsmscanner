"""2D profile-likelihood contours from a BSMScanner run.

    python plot_profile_2d.py <run_dir> [--x s12] [--y s13] [--bins 120]

For each (x, y) bin the minimum chi^2 over all valid evaluated points is taken
(profiling over every other parameter), and Delta chi^2 = chi^2 - chi^2_min.
Contours at the 2-dof thresholds 2.30 (1 sigma) and 11.83 (3 sigma).

Caveat: the points are an optimizer's trajectory, not a uniform sample, so the
profile is reliable only where the scan actually explored; empty bins are
shown blank, not as excluded.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LABELS = {"s12": r"$\sin^2\theta_{12}$", "s13": r"$\sin^2\theta_{13}$", "s23": r"$\sin^2\theta_{23}$",
          "deltaCP_deg_m180_180": r"$\delta_{CP}$ [deg]", "deltaCP_deg_0_360": r"$\delta_{CP}$ [deg]"}
LEVELS = {"1σ": 2.30, "3σ": 11.83}  # Delta chi^2, 2 dof (68.27 %, 99.73 %)
C1, C3 = "#2a78d6", "#eb6834"      # reference categorical slots 1 and 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--x", default="s12")
    ap.add_argument("--y", default="s13")
    ap.add_argument("--bins", type=int, default=120)
    ap.add_argument("--window", type=float, default=30.0, help="max Delta chi^2 kept for the plot")
    args = ap.parse_args()

    cols = ["valid", "total_nll", f"output::{args.x}", f"output::{args.y}"]
    chunks = []
    for chunk in pd.read_csv(args.run_dir / "points.csv", usecols=cols, chunksize=500_000):
        chunk = chunk[chunk["valid"].astype(str).str.lower().isin(["true", "1"])]
        chunks.append(chunk[np.isfinite(chunk["total_nll"])])
    df = pd.concat(chunks, ignore_index=True)
    chi2_min = df["total_nll"].min()
    df["dchi2"] = df["total_nll"] - chi2_min
    near = df[df["dchi2"] <= args.window]
    best = df.loc[df["total_nll"].idxmin()]
    x, y = near[f"output::{args.x}"].to_numpy(), near[f"output::{args.y}"].to_numpy()

    # Profile on a grid: min Delta chi^2 per bin.
    pad_x, pad_y = 0.05 * np.ptp(x), 0.05 * np.ptp(y)
    xe = np.linspace(x.min() - pad_x, x.max() + pad_x, args.bins + 1)
    ye = np.linspace(y.min() - pad_y, y.max() + pad_y, args.bins + 1)
    ix = np.clip(np.digitize(x, xe) - 1, 0, args.bins - 1)
    iy = np.clip(np.digitize(y, ye) - 1, 0, args.bins - 1)
    grid = np.full((args.bins, args.bins), np.inf)
    np.minimum.at(grid, (iy, ix), near["dchi2"].to_numpy())
    xc, yc = 0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1])

    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    shown = np.where(np.isfinite(grid), grid, np.nan)
    pc = ax.pcolormesh(xe, ye, np.ma.masked_invalid(shown), cmap="Greys_r", vmin=0, vmax=args.window,
                       shading="flat", alpha=0.55, rasterized=True)
    filled = np.where(np.isfinite(grid), grid, args.window * 10)
    ax.contourf(xc, yc, filled, levels=[0, LEVELS["1σ"]], colors=[C1], alpha=0.25)
    ax.contourf(xc, yc, filled, levels=[LEVELS["1σ"], LEVELS["3σ"]], colors=[C3], alpha=0.15)
    ax.contour(xc, yc, filled, levels=[LEVELS["1σ"]], colors=[C1], linewidths=2)
    ax.contour(xc, yc, filled, levels=[LEVELS["3σ"]], colors=[C3], linewidths=2)
    ax.plot(best[f"output::{args.x}"], best[f"output::{args.y}"], marker="*", ms=14, color="#0b0b0b",
            mec="#fcfcfb", mew=1.5, ls="none")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], color=C1, lw=2, label=r"1$\sigma$ ($\Delta\chi^2$ = 2.30)"),
        Line2D([], [], color=C3, lw=2, label=r"3$\sigma$ ($\Delta\chi^2$ = 11.83)"),
        Line2D([], [], marker="*", ms=12, color="#0b0b0b", ls="none",
               label=f"best fit ($\\chi^2_{{min}}$ = {chi2_min:.2f})"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=3, frameon=False,
              fontsize=8.5, labelcolor="#0b0b0b", borderaxespad=0.0, handlelength=1.6, columnspacing=1.2)
    cb = fig.colorbar(pc, ax=ax, pad=0.02)
    cb.set_label(r"profile $\Delta\chi^2$", color="#52514e")
    cb.ax.tick_params(colors="#52514e")
    ax.set_xlabel(LABELS.get(args.x, args.x), color="#0b0b0b")
    ax.set_ylabel(LABELS.get(args.y, args.y), color="#0b0b0b")
    ax.tick_params(colors="#52514e")
    for s in ax.spines.values():
        s.set_color("#c3c2b7")
    fig.tight_layout()
    out = args.run_dir / f"profile_{args.x}_{args.y}.png"
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(out, f"chi2_min={chi2_min:.4f}", f"best {args.x}={best[f'output::{args.x}']:.5f}",
          f"{args.y}={best[f'output::{args.y}']:.5f}", f"points within window={len(near):,}")
    for name, lev in LEVELS.items():
        sel = near[near["dchi2"] <= lev]
        print(f"{name}: {args.x} in [{sel[f'output::{args.x}'].min():.4f}, {sel[f'output::{args.x}'].max():.4f}], "
              f"{args.y} in [{sel[f'output::{args.y}'].min():.5f}, {sel[f'output::{args.y}'].max():.5f}]  (n={len(sel):,})")


if __name__ == "__main__":
    main()
