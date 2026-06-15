from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StartFromConfig:
    source: str = "auto"
    n_walkers: int = 64
    initialization: str = "elite_covariance"
    elite_fraction: float = 0.01
    max_elite_points: int = 1000
    min_elite_points: int = 20
    jitter_scale: float = 0.1
    covariance_regularization: float = 1.0e-10
    max_initialization_attempts: int = 10000


@dataclass(slots=True)
class MCMCConfig:
    n_steps: int = 20000
    burn_in: int = 5000
    thin: int = 10
    seed: int = 12345
    vectorize: bool = False
    progress: bool = True
    resume: bool = False
    n_workers: int = 1


@dataclass(slots=True)
class ObjectiveConfig:
    use: str = "auto"
    invalid_logprob: float = float("-inf")
    include_log_prior: bool = True


@dataclass(slots=True)
class PriorsConfig:
    use_parameter_priors: bool = True
    default_prior: str = "flat"


@dataclass(slots=True)
class ValidPointsConfig:
    enabled: bool = True
    delta_nll: list[float] = field(default_factory=lambda: [0.5, 2.0, 4.5])
    delta_chi2: list[float] = field(default_factory=lambda: [1.0, 4.0, 9.0])
    observable_sigma_cuts: list[float] = field(default_factory=lambda: [1.0, 2.0, 3.0])


@dataclass(slots=True)
class OutputsConfig:
    save_chain: bool = True
    save_flat_samples: bool = True
    save_observables: bool = True
    save_likelihood_terms: bool = True
    save_summary: bool = True
    save_covariance: bool = True
    save_diagnostics: bool = True
    save_valid_points: bool = True


@dataclass(slots=True)
class PosteriorConfig:
    enabled: bool = False
    method: str = "emcee"
    run_after: str = "scan"
    start_from: StartFromConfig = field(default_factory=StartFromConfig)
    mcmc: MCMCConfig = field(default_factory=MCMCConfig)
    objective: ObjectiveConfig = field(default_factory=ObjectiveConfig)
    priors: PriorsConfig = field(default_factory=PriorsConfig)
    valid_points: ValidPointsConfig = field(default_factory=ValidPointsConfig)
    outputs: OutputsConfig = field(default_factory=OutputsConfig)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "PosteriorConfig":
        payload = dict(raw or {})
        return cls(
            enabled=bool(payload.get("enabled", False)),
            method=str(payload.get("method", "emcee")),
            run_after=str(payload.get("run_after", "scan")),
            start_from=StartFromConfig(**dict(payload.get("start_from", {}))),
            mcmc=MCMCConfig(**dict(payload.get("mcmc", {}))),
            objective=ObjectiveConfig(**dict(payload.get("objective", {}))),
            priors=PriorsConfig(**dict(payload.get("priors", {}))),
            valid_points=ValidPointsConfig(**dict(payload.get("valid_points", {}))),
            outputs=OutputsConfig(**dict(payload.get("outputs", {}))),
        )

    def validate(self, *, ndim: int) -> None:
        if self.method != "emcee":
            raise ValueError("scan.posterior.method currently supports only 'emcee'.")
        if self.run_after != "scan":
            raise ValueError("scan.posterior.run_after currently supports only 'scan'.")
        if self.start_from.initialization not in {"best_fit_jitter", "elite_jitter", "elite_covariance"}:
            raise ValueError(
                "scan.posterior.start_from.initialization must be one of "
                "'best_fit_jitter', 'elite_jitter', or 'elite_covariance'."
            )
        if self.start_from.n_walkers < max(2, 2 * ndim):
            raise ValueError("scan.posterior.start_from.n_walkers must be at least 2 * ndim for emcee.")
        if self.mcmc.n_steps <= 0:
            raise ValueError("scan.posterior.mcmc.n_steps must be > 0.")
        if self.mcmc.burn_in < 0:
            raise ValueError("scan.posterior.mcmc.burn_in must be >= 0.")
        if self.mcmc.thin <= 0:
            raise ValueError("scan.posterior.mcmc.thin must be > 0.")
        if self.objective.use not in {"auto", "nll", "chi2"}:
            raise ValueError("scan.posterior.objective.use must be 'auto', 'nll', or 'chi2'.")
        if self.priors.default_prior not in {"flat", "log", "signed_log"}:
            raise ValueError("scan.posterior.priors.default_prior must be 'flat', 'log', or 'signed_log'.")
