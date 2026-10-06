"""NuFIT two-dimensional 1 sigma / 3 sigma regions with the scan best fit overlaid.

    python plot_nufit_2d.py <nufit_release_file> <best_fit.json> [--label "NuFIT 5.3"] [--points points.csv]

<nufit_release_file> is a NuFIT data release file (e.g. v53.release-SKyes-NO.txt)
containing marginalised Delta chi^2 tables in blocks headed by the variable names.
Contours are drawn at the 2-dof thresholds Delta chi^2 = 2.30 (1 sigma) and
11.83 (3 sigma), the convention NuFIT uses for its 2D projections.

With --points, the scan's valid points within its own Delta chi^2 <= 11.83 of the
scan minimum are overlaid (darker: within 2.30). The scan Delta chi^2 is the
model's total chi^2 profile, not the NuFIT 2D one.
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

LEVELS = {"1σ": 2.30, "3σ": 11.83}
C1, C3 = "#2a78d6", "#eb6834"  # reference categorical slots 1 and 2
INK, INK2, RULE, SURFACE = "#0b0b0b", "#52514e", "#c3c2b7", "#fcfcfb"

# tag: (header in the NuFIT file, x column, y column, x label, y label,
#       best-fit output keys, transform NuFIT x, transform NuFIT y, transform best-fit x, transform best-fit y)
IDENT = lambda v: v
PLANES = {
    "s12_s13": ("sin^2(theta13) sin^2(theta12) Delta_chi^2", 1, 0,
                r"$\sin^2\theta_{12}$", r"$\sin^2\theta_{13}$", ("s12", "s13"), IDENT, IDENT, IDENT, IDENT),
    "s23_dcp": ("sin^2(theta23) Delta_CP/deg Delta_chi^2", 0, 1,
                r"$\sin^2\theta_{23}$", r"$\delta_{CP}$ [deg]", ("s23", "deltaCP_deg_0_360"),
                IDENT, IDENT, IDENT, IDENT),
    # NuFIT tabulates log10(dm21/eV^2) and dm31 in 1e-3 eV^2; plot dm21 in 1e-5 eV^2, dm31 in 1e-3 eV^2.
    "dm21_dm31": ("Log10(Delta_m21^2/[eV^2]) Delta_m31^2/[1e-3_eV^2] Delta_chi^2", 0, 1,
                  r"$\Delta m^2_{21}$ [$10^{-5}$ eV$^2$]", r"$\Delta m^2_{31}$ [$10^{-3}$ eV$^2$]", ("dm21_scaled", "dm3l_scaled"),
                  lambda v: 10.0**v * 1e5, IDENT, lambda v: v * 1e5, lambda v: v * 1e3),
}


def read_block(lines: list[str], header: str) -> np.ndarray:
    start = next(i for i, line in enumerate(lines) if line.strip() == header)
    rows = []
    for line in lines[start + 1:]:
        s = line.strip()
        if not s or s[0].isalpha() or s.startswith("#"):
            break
        rows.append([float(v) for v in s.split()])
    return np.array(rows)


def to_grid(block: np.ndarray, xi: int, yi: int):
    xs, ys = np.unique(block[:, xi]), np.unique(block[:, yi])
    grid = np.full((len(ys), len(xs)), np.nan)
    grid[np.searchsorted(ys, block[:, yi]), np.searchsorted(xs, block[:, xi])] = block[:, 2]
    return xs, ys, grid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("nufit_file", type=Path)
    ap.add_argument("best_fit", type=Path)
    ap.add_argument("--label", default="NuFIT")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--points", type=Path, default=None, help="scan points.csv to overlay")
    args = ap.parse_args()

    scan = None
    if args.points is not None:
        keys = sorted({k for plane in PLANES.values() for k in plane[5]})
        cols = ["valid", "total_nll"] + [f"output::{k}" for k in keys]
        parts = []
        for chunk in pd.read_csv(args.points, usecols=cols, chunksize=500_000):
            chunk = chunk[chunk["valid"].astype(str).str.lower().isin(["true", "1"])]
            parts.append(chunk[np.isfinite(chunk["total_nll"])])
        scan = pd.concat(parts, ignore_index=True)
        scan["dchi2"] = scan["total_nll"] - scan["total_nll"].min()
        scan = scan[scan["dchi2"] <= LEVELS["3σ"]].sort_values("dchi2", ascending=False)

    lines = args.nufit_file.read_text().splitlines()
    best = json.loads(args.best_fit.read_text())
    out_dir = args.out_dir or args.best_fit.parent

    for tag, (header, xi, yi, xlabel, ylabel, (bx, by), fx, fy, gx, gy) in PLANES.items():
        block = read_block(lines, header)
        block[:, xi], block[:, yi] = fx(block[:, xi]), fy(block[:, yi])
        if tag == "s23_dcp":  # NuFIT tabulates delta in [-180, 180]; plot on [0, 360)
            block[:, 1] = np.mod(block[:, 1], 360.0)
            # duplicate the 0 deg row at 360 deg so the contour closes across the seam
            seam = block[np.isclose(block[:, 1], 0.0)].copy()
            seam[:, 1] = 360.0
            block = np.vstack([block, seam])
        xs, ys, grid = to_grid(block, xi, yi)
        grid = grid - np.nanmin(grid)

        fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=150)
        fig.patch.set_facecolor(SURFACE)
        ax.set_facecolor(SURFACE)
        ax.contourf(xs, ys, grid, levels=[0, LEVELS["1σ"]], colors=[C1], alpha=0.30)
        ax.contourf(xs, ys, grid, levels=[LEVELS["1σ"], LEVELS["3σ"]], colors=[C3], alpha=0.18)
        ax.contour(xs, ys, grid, levels=[LEVELS["1σ"]], colors=[C1], linewidths=2, zorder=3)
        ax.contour(xs, ys, grid, levels=[LEVELS["3σ"]], colors=[C3], linewidths=2, zorder=3)
        if scan is not None:
            outer = scan[scan["dchi2"] > LEVELS["1σ"]]
            inner = scan[scan["dchi2"] <= LEVELS["1σ"]]
            for sub, color in ((outer, "#9a9890"), (inner, "#3a3936")):
                ax.scatter(gx(sub[f"output::{bx}"].to_numpy()), gy(sub[f"output::{by}"].to_numpy()),
                           s=3, c=color, alpha=0.55, linewidths=0, rasterized=True, zorder=2)
        iy, ix = np.unravel_index(np.nanargmin(grid), grid.shape)
        ax.plot(xs[ix], ys[iy], marker="+", ms=12, mew=2, color=INK2, ls="none", zorder=4)
        px, py = gx(best["outputs"][bx]), gy(best["outputs"][by])
        ax.plot(px, py, marker="*", ms=15, color=INK, mec=SURFACE, mew=1.5, ls="none", zorder=5)

        handles = [
            Patch(facecolor=C1, alpha=0.5, edgecolor=C1, lw=2, label=f"{args.label} 1σ"),
            Patch(facecolor=C3, alpha=0.35, edgecolor=C3, lw=2, label=f"{args.label} 3σ"),
            Line2D([], [], marker="+", ms=10, mew=2, color=INK2, ls="none", label=f"{args.label} best fit"),
            Line2D([], [], marker="*", ms=12, color=INK, ls="none", label="scotogenic best fit"),
        ]
        if scan is not None:
            handles += [
                Line2D([], [], marker="o", ms=4, color="#3a3936", ls="none", label="scan points, Δχ² ≤ 2.30"),
                Line2D([], [], marker="o", ms=4, color="#9a9890", ls="none", label="scan points, Δχ² ≤ 11.83"),
            ]
        ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, frameon=False,
                  fontsize=8.5, labelcolor=INK, borderaxespad=0.0, handlelength=1.6, columnspacing=1.2)
        # zoom to the 3 sigma region with a margin
        inside = grid <= LEVELS["3σ"] * 1.6
        yy, xx = np.nonzero(inside)
        ax.set_xlim(xs[xx.min()], xs[xx.max()])
        ax.set_ylim(ys[yy.min()], ys[yy.max()])
        if tag == "s23_dcp":
            ax.set_ylim(0, 360)
            ax.set_yticks(range(0, 361, 60))
        ax.set_xlabel(xlabel, color=INK)
        ax.set_ylabel(ylabel, color=INK)
        ax.tick_params(colors=INK2)
        for s in ax.spines.values():
            s.set_color(RULE)
        fig.tight_layout()
        out = out_dir / f"nufit_{tag}.png"
        fig.savefig(out, facecolor=fig.get_facecolor())
        dchi2_best = float(
            grid[np.abs(ys - py).argmin(), np.abs(xs - px).argmin()]
        )
        print(out, f"{args.label} min at ({xs[ix]:.4g}, {ys[iy]:.4g}); scotogenic best fit ({px:.4g}, {py:.4g}) "
              f"sits at {args.label} Delta chi^2 ~ {dchi2_best:.2f} (nearest grid node)")


if __name__ == "__main__":
    main()
