from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .config import PosteriorConfig
from .diagnostics import build_diagnostics
from .initialization import initialize_walkers
from .io import write_json, write_rows_csv
from .log_probability import LogProbabilityContext, log_probability, metadata_for_theta, objective_mode_for_posterior
from .priors import ParameterInfo, parameter_order
from .summaries import build_summary


def _import_emcee():
    try:
        import emcee  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "The posterior MCMC stage requires the optional dependency emcee. "
            "Install it with pip install emcee or disable scan.posterior.enabled."
        ) from exc
    return emcee


def _parameters_from_request(request: Any) -> list[ParameterInfo]:
    return [
        ParameterInfo(
            name=item.name,
            lower=float(item.lower),
            upper=float(item.upper),
            prior=str(item.prior),
            default=item.default,
        )
        for item in request.scanned_parameters
    ]


def _row_from_metadata(step: int, walker: int, theta: np.ndarray, log_prob_value: float, metadata: dict[str, Any], parameters: list[ParameterInfo]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "step": step,
        "walker": walker,
        "log_prob": float(log_prob_value),
        "nll": metadata.get("nll"),
        "chi2": metadata.get("chi2"),
        "valid": bool(metadata.get("valid", False)),
        "invalid_reason": metadata.get("invalid_reason", ""),
    }
    for parameter, value in zip(parameters, theta, strict=True):
        row[parameter.name] = float(value)
    for name, value in metadata.get("outputs", {}).items():
        row[name] = value
    for name, value in metadata.get("likelihood_terms", {}).items():
        row[f"like__{name}"] = value
    return row


def _fieldnames(rows: list[dict[str, Any]], parameters: list[ParameterInfo]) -> tuple[list[str], list[str], list[str]]:
    base = ["step", "walker", "log_prob", "nll", "chi2", "valid", "invalid_reason"]
    params = parameter_order(parameters)
    observable_names = sorted({key for row in rows for key in row if key not in set(base + params) and not key.startswith("like__")})
    likelihood_names = sorted({key for row in rows for key in row if key.startswith("like__")})
    return base + params + observable_names + likelihood_names, observable_names, likelihood_names


def _write_valid_point_cuts(run_dir: Path, rows: list[dict[str, Any]], config: PosteriorConfig) -> None:
    valid = [row for row in rows if row.get("valid") is True]
    if not valid:
        write_rows_csv(run_dir / "mcmc_valid_points_delta_nll.csv", ["cut"], [])
        write_rows_csv(run_dir / "mcmc_valid_points_delta_chi2.csv", ["cut"], [])
        write_rows_csv(run_dir / "mcmc_valid_points_observable_cuts.csv", ["sigma_cut"], [])
        return
    fieldnames = list(rows[0].keys())
    if config.valid_points.delta_nll:
        best_nll = min(float(row["nll"]) for row in valid if row.get("nll") not in {"", None})
        selected = []
        for cut in config.valid_points.delta_nll:
            for row in valid:
                if row.get("nll") not in {"", None} and float(row["nll"]) - best_nll <= float(cut):
                    copied = dict(row)
                    copied["delta_nll_cut"] = cut
                    selected.append(copied)
        write_rows_csv(run_dir / "mcmc_valid_points_delta_nll.csv", ["delta_nll_cut", *fieldnames], selected)
    if config.valid_points.delta_chi2:
        best_chi2 = min(float(row["chi2"]) for row in valid if row.get("chi2") not in {"", None})
        selected = []
        for cut in config.valid_points.delta_chi2:
            for row in valid:
                if row.get("chi2") not in {"", None} and float(row["chi2"]) - best_chi2 <= float(cut):
                    copied = dict(row)
                    copied["delta_chi2_cut"] = cut
                    selected.append(copied)
        write_rows_csv(run_dir / "mcmc_valid_points_delta_chi2.csv", ["delta_chi2_cut", *fieldnames], selected)
    write_rows_csv(run_dir / "mcmc_valid_points_observable_cuts.csv", ["sigma_cut", "note"], [{"sigma_cut": "", "note": "Observable sigma-cut metadata is not available generically yet."}])


def run_posterior_stage(model: Any, compiled: Any, request: Any, run_directory: str | Path, raw_config: dict[str, Any]) -> dict[str, Any] | None:
    config = PosteriorConfig.from_mapping(raw_config)
    if not config.enabled:
        return None
    emcee = _import_emcee()
    run_dir = Path(run_directory)
    parameters = _parameters_from_request(request)
    config.validate(ndim=len(parameters))
    objective_mode = objective_mode_for_posterior(config.objective.use, request.objective_mode)
    rng = np.random.default_rng(config.mcmc.seed)

    write_json(run_dir / "mcmc_parameter_order.json", {"parameter_order": parameter_order(parameters), "ndim": len(parameters)})
    initial_positions, initialization_diagnostics, covariance = initialize_walkers(
        run_dir,
        parameters,
        config.start_from,
        rng=rng,
    )
    np.save(run_dir / "mcmc_initial_positions.npy", initial_positions)
    write_json(run_dir / "mcmc_initialization.json", initialization_diagnostics)
    write_json(run_dir / "mcmc_covariance.json", {"parameters": parameter_order(parameters), "matrix": covariance})
    std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    denom = np.outer(std, std)
    correlation = np.divide(covariance, denom, out=np.zeros_like(covariance), where=denom > 0)
    write_json(run_dir / "mcmc_correlation.json", {"parameters": parameter_order(parameters), "matrix": correlation})

    context = LogProbabilityContext(
        compiled=compiled,
        request=request,
        parameters=parameters,
        objective_mode=objective_mode,
        default_prior=config.priors.default_prior,
        use_parameter_priors=config.priors.use_parameter_priors,
        include_log_prior=config.objective.include_log_prior,
    )
    sampler = emcee.EnsembleSampler(
        config.start_from.n_walkers,
        len(parameters),
        lambda theta: log_probability(theta, context),
        vectorize=config.mcmc.vectorize,
    )
    sampler.run_mcmc(initial_positions, config.mcmc.n_steps, progress=config.mcmc.progress)

    chain = sampler.get_chain()
    logprob = sampler.get_log_prob()
    if config.outputs.save_chain:
        np.save(run_dir / "mcmc_chain.npy", chain)
        np.save(run_dir / "mcmc_logprob.npy", logprob)

    flat_chain = sampler.get_chain(discard=config.mcmc.burn_in, thin=config.mcmc.thin, flat=False)
    flat_logprob_by_walker = sampler.get_log_prob(discard=config.mcmc.burn_in, thin=config.mcmc.thin, flat=False)
    rows: list[dict[str, Any]] = []
    for step in range(flat_chain.shape[0]):
        for walker in range(flat_chain.shape[1]):
            theta = flat_chain[step, walker, :]
            lp = float(flat_logprob_by_walker[step, walker])
            metadata = metadata_for_theta(theta, context, lp)
            rows.append(_row_from_metadata(step, walker, theta, lp, metadata, parameters))

    fieldnames, observable_names, likelihood_names = _fieldnames(rows, parameters)
    if config.outputs.save_flat_samples:
        write_rows_csv(run_dir / "mcmc_samples.csv", fieldnames, rows)
    if config.outputs.save_observables:
        write_rows_csv(run_dir / "mcmc_observables.csv", ["step", "walker", *observable_names], rows)
    if config.outputs.save_likelihood_terms:
        write_rows_csv(run_dir / "mcmc_likelihood_terms.csv", ["step", "walker", *likelihood_names], rows)
    if config.outputs.save_summary:
        write_json(run_dir / "mcmc_summary.json", build_summary(rows, parameter_order(parameters), observable_names))

    flat_logprob = sampler.get_log_prob(discard=config.mcmc.burn_in, thin=config.mcmc.thin, flat=True)
    diagnostics = build_diagnostics(
        sampler=sampler,
        chain=chain,
        flat_logprob=flat_logprob,
        rows=rows,
        n_walkers=config.start_from.n_walkers,
        ndim=len(parameters),
        n_steps=config.mcmc.n_steps,
        burn_in=config.mcmc.burn_in,
        thin=config.mcmc.thin,
    )
    diagnostics["log_probability_evaluations"] = context.evaluations
    if config.outputs.save_diagnostics:
        write_json(run_dir / "mcmc_diagnostics.json", diagnostics)
        write_json(
            run_dir / "mcmc_acceptance.json",
            {
                "acceptance_fraction_per_walker": diagnostics["acceptance_fraction_per_walker"],
                "mean_acceptance_fraction": diagnostics["mean_acceptance_fraction"],
            },
        )
        write_json(run_dir / "mcmc_invalid_reasons.json", dict(context.invalid_reasons))

    valid_rows = [row for row in rows if row.get("valid") is True]
    if valid_rows:
        best_posterior = max(valid_rows, key=lambda row: float(row["log_prob"]))
        best_likelihood = min(valid_rows, key=lambda row: float(row["nll"]) if row.get("nll") not in {"", None} else float("inf"))
        write_json(run_dir / "mcmc_best_posterior.json", best_posterior)
        write_json(run_dir / "mcmc_best_likelihood.json", best_likelihood)
    else:
        write_json(run_dir / "mcmc_best_posterior.json", {"has_best_point": False})
        write_json(run_dir / "mcmc_best_likelihood.json", {"has_best_point": False})

    if config.valid_points.enabled and config.outputs.save_valid_points:
        _write_valid_point_cuts(run_dir, rows, config)

    return {
        "enabled": True,
        "method": config.method,
        "n_walkers": config.start_from.n_walkers,
        "n_steps": config.mcmc.n_steps,
        "burn_in": config.mcmc.burn_in,
        "thin": config.mcmc.thin,
        "objective_mode": objective_mode,
        "valid_samples": diagnostics["number_valid_samples"],
        "invalid_samples": diagnostics["number_invalid_samples"],
        "mean_acceptance_fraction": diagnostics["mean_acceptance_fraction"],
        "summary_path": "mcmc_summary.json",
        "diagnostics_path": "mcmc_diagnostics.json",
        "samples_path": "mcmc_samples.csv",
    }
