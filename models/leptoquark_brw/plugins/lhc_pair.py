"""LHC S1 pair-production limits, channel by channel, for the leptoquark tutorial.

Required inputs in ../data/lhc_pair/ (two columns, mass [GeV], cross section [fb]):
    sigma_pair_nnlo.csv   theory sigma(pp -> S1 S1*) at 13 TeV (NNLO+NNLL, coupling independent)
    limit_ttau.csv        observed 95 % CL limit on sigma x BR^2 for S1 S1* -> t tau t tau
    limit_bnu.csv         ... -> b nu b nu
    limit_ctau.csv        ... -> c tau c tau (a jet + tau search)
    limit_snu.csv         ... -> s nu s nu (light-jet + MET search)
Each limit is the published 100 %-BR cross-section limit for that final state (HEPData).

Registered plugin function: lhc_pair.max_ratio(M, BR_ttau, BR_bnu, BR_ctau, BR_snu)
    returns max_c [sigma_pair(M) BR_c^2 / sigma_lim,c(M)] over the channels whose tables exist,
    0 for a channel outside its tabulated mass range. Mixed channels (e.g. t tau + b nu) are not
    used (conservative: weaker than the full combination).
"""

from __future__ import annotations

from pathlib import Path

import bsm_scanner
import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data" / "lhc_pair"
CHANNELS = ("ttau", "bnu", "ctau", "snu")
_CACHE: dict[str, tuple[np.ndarray, np.ndarray] | None] = {}


def _read(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = []
    for line in path.read_text().splitlines():
        parts = line.strip().replace(",", " ").split()
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except (ValueError, IndexError):
            continue
    arr = np.array(sorted(rows))
    if len(arr) < 2 or np.any(arr <= 0):
        raise ValueError(f"'{path}' must contain >= 2 rows of positive (mass, value) pairs.")
    return arr[:, 0], arr[:, 1]


def _table(name: str, required: bool) -> tuple[np.ndarray, np.ndarray] | None:
    if name not in _CACHE:
        path = DATA / f"{name}.csv"
        if not path.exists():
            if required:
                raise FileNotFoundError(
                    f"LHC pair-production input '{path}' is missing (see plugins/lhc_pair.py docstring)."
                )
            _CACHE[name] = None
        else:
            _CACHE[name] = _read(path)
    return _CACHE[name]


def _interp(m: float, table: tuple[np.ndarray, np.ndarray]) -> float | None:
    xs, ys = table
    if not (xs[0] <= m <= xs[-1]):
        return None
    return float(np.exp(np.interp(m, xs, np.log(ys))))


def max_ratio(args, options):
    m = float(args["M"])
    sigma = _interp(m, _table("sigma_pair_nnlo", required=True))
    if sigma is None:
        return 0.0
    tables = {c: _table(f"limit_{c}", required=False) for c in CHANNELS}
    if all(t is None for t in tables.values()):
        raise FileNotFoundError(f"No channel limit tables found in '{DATA}'.")
    worst = 0.0
    for c, t in tables.items():
        if t is None:
            continue
        lim = _interp(m, t)
        if lim is None:
            continue
        worst = max(worst, sigma * float(args[f"BR_{c}"]) ** 2 / lim)
    return worst


bsm_scanner.register_plugin_function("lhc_pair", "max_ratio", max_ratio)
