# Posterior MCMC Refinement

BSMScanner can optionally run a Bayesian posterior-refinement stage after a normal scan has finished.
This stage does not replace `basin_scan`, `adaptive_diver`, `de_scipy`, or random scans. It starts from
the best-fit or elite points found by the global scan, then samples the local posterior with `emcee`.

The posterior convention is:

```text
posterior(theta) proportional to likelihood(theta) * prior(theta)
```

For `objective: nll`, BSMScanner uses:

```text
log_likelihood = -nll
```

For `objective: chi2`, it uses:

```text
log_likelihood = -0.5 * chi2
```

Invalid points return `-inf` log probability. This is intentionally different from optimizer scans,
where invalid points may receive a large finite penalty such as `1.0e12`.

## Minimal YAML

```yaml
scan:
  engine: basin_scan
  settings:
    objective: nll
    invalid_penalty: 1.0e12

  basin_scan:
    ...

  posterior:
    enabled: true
    method: emcee
    run_after: scan

    start_from:
      source: auto
      n_walkers: 64
      initialization: elite_covariance
      elite_fraction: 0.01
      max_elite_points: 1000
      min_elite_points: 20
      jitter_scale: 0.1
      covariance_regularization: 1.0e-10

    mcmc:
      n_steps: 20000
      burn_in: 5000
      thin: 10
      seed: 12345
      progress: true

    objective:
      use: auto
      include_log_prior: true

    priors:
      use_parameter_priors: true
      default_prior: flat
```

Install the optional dependency before enabling this stage:

```bash
python -m pip install 'emcee>=3.1'
```

## Initialization Modes

`best_fit_jitter` initializes all walkers around the single best valid scan point.

`elite_jitter` samples walker centers from the best valid scan points and adds Gaussian jitter.

`elite_covariance` estimates a local covariance matrix from elite scan points and initializes walkers
with multivariate Gaussian perturbations. This is usually the best starting point after `basin_scan`.

With `source: auto`, BSMScanner searches standard artifacts such as `ranked_points.csv`,
`selected_points.csv`, `elite_points.csv`, `final_population.csv`, `exploration_points.csv`,
`points.csv`, and finally `best_fit.json`.

## Output Files

The posterior stage writes files into the same run directory:

```text
mcmc_parameter_order.json
mcmc_initialization.json
mcmc_initial_positions.npy
mcmc_chain.npy
mcmc_logprob.npy
mcmc_samples.csv
mcmc_observables.csv
mcmc_likelihood_terms.csv
mcmc_summary.json
mcmc_acceptance.json
mcmc_diagnostics.json
mcmc_covariance.json
mcmc_correlation.json
mcmc_best_posterior.json
mcmc_best_likelihood.json
mcmc_invalid_reasons.json
mcmc_valid_points_delta_nll.csv
mcmc_valid_points_delta_chi2.csv
mcmc_valid_points_observable_cuts.csv
```

`mcmc_samples.csv` is the main plotting table. It contains:

```text
step, walker, log_prob, nll, chi2, valid, invalid_reason,
<free parameters>, <observables>, like__<likelihood term>
```

`mcmc_summary.json` reports posterior summaries for parameters and observables:

```text
mean, std, median, q16, q84, q025, q975, min, max
```

The 16th, 50th, and 84th percentiles are commonly interpreted as Bayesian credible intervals when
the chain is converged and the posterior mode has been adequately sampled.

## Scientific Caveats

MCMC is a local posterior sampler, not a global optimizer. It does not reliably discover disconnected
basins unless walkers are initialized in those basins. For difficult BSM landscapes, use `basin_scan`
or another global engine first, then use posterior MCMC to quantify uncertainty around the discovered
best-fit regions.

The current `mcmc_valid_points_observable_cuts.csv` file is a placeholder unless observable central
values and uncertainties are available generically from the model metadata. Delta-NLL and delta-chi2
valid-point exports are implemented generically.
