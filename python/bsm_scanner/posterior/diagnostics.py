from __future__ import annotations

from typing import Any

import numpy as np


def build_diagnostics(
    *,
    sampler: Any,
    chain: np.ndarray,
    flat_logprob: np.ndarray,
    rows: list[dict[str, Any]],
    n_walkers: int,
    ndim: int,
    n_steps: int,
    burn_in: int,
    thin: int,
) -> dict[str, Any]:
    acceptance = np.asarray(getattr(sampler, "acceptance_fraction", []), dtype=float)
    warnings: list[str] = []
    autocorr: list[float] | None = None
    try:
        tau = sampler.get_autocorr_time(tol=0)
        autocorr = [float(item) for item in tau]
        if np.any(n_steps < 50.0 * tau):
            warnings.append("Chain length is shorter than 50 autocorrelation times for at least one parameter.")
    except Exception as exc:
        warnings.append(f"Autocorrelation time unavailable: {exc}")

    if acceptance.size:
        mean_acceptance = float(np.mean(acceptance))
        if mean_acceptance < 0.1:
            warnings.append("Mean acceptance fraction is low (<0.1).")
        if mean_acceptance > 0.8:
            warnings.append("Mean acceptance fraction is high (>0.8).")
    else:
        mean_acceptance = None

    valid_count = sum(1 for row in rows if row.get("valid") is True)
    invalid_count = len(rows) - valid_count
    finite_logprob = flat_logprob[np.isfinite(flat_logprob)]
    best_logprob = float(np.max(finite_logprob)) if finite_logprob.size else None
    valid_nll = [float(row["nll"]) for row in rows if row.get("valid") is True and row.get("nll") not in {"", None}]
    valid_chi2 = [float(row["chi2"]) for row in rows if row.get("valid") is True and row.get("chi2") not in {"", None}]
    ess = None
    if autocorr:
        tau_max = max(autocorr)
        if tau_max > 0:
            ess = float(chain.shape[0] * chain.shape[1] / tau_max)

    return {
        "n_walkers": n_walkers,
        "ndim": ndim,
        "n_steps": n_steps,
        "burn_in": burn_in,
        "thin": thin,
        "total_raw_samples": int(chain.shape[0] * chain.shape[1]),
        "total_flat_samples": int(len(rows)),
        "number_valid_samples": int(valid_count),
        "number_invalid_samples": int(invalid_count),
        "mean_acceptance_fraction": mean_acceptance,
        "min_acceptance_fraction": float(np.min(acceptance)) if acceptance.size else None,
        "max_acceptance_fraction": float(np.max(acceptance)) if acceptance.size else None,
        "acceptance_fraction_per_walker": [float(item) for item in acceptance],
        "autocorrelation_time": autocorr,
        "effective_sample_size_estimate": ess,
        "warnings": warnings,
        "best_log_prob": best_logprob,
        "best_nll": min(valid_nll) if valid_nll else None,
        "best_chi2": min(valid_chi2) if valid_chi2 else None,
    }
