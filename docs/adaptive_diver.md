# `adaptive_diver`

`adaptive_diver` is a native Diver-inspired Differential Evolution engine inside
BSMScanner. It is model-agnostic: it only sees scanned parameter names, bounds,
the scalar objective returned by the existing evaluator, validity information,
and scan settings.

It is intended for difficult likelihood scans with correlations, invalid
regions, and disconnected viable islands. It does not contain neutrino, quark,
micrOMEGAs, one-loop, or model-specific logic.

## Algorithm

The first implementation uses a JADE-like current-to-pbest mutation:

```text
v_i = x_i + F_i * (x_pbest - x_i) + F_i * (x_r1 - x_r2)
```

with binomial crossover. `F_i` and `CR_i` are sampled around adaptive running
means `mu_F` and `mu_CR`; successful trials update those means with a
Lehmer-style update for `F` and an arithmetic mean for `CR`.

The objective is minimized. Invalid evaluator results are converted to the
configured invalid objective, and the scan continues.

## Minimal YAML

```yaml
scan:
  engine: adaptive_diver
  seed: 12345
  save_every: 1
  settings:
    objective: nll
    invalid_penalty: 1.0e12
    save_invalid_points: true
    verbose: 1
```

## Exploratory YAML

The engine supports the existing flat `scan.settings` style and a clearer
engine-specific `scan.adaptive_diver` block:

```yaml
scan:
  engine: adaptive_diver
  seed: 12345
  save_every: 1
  settings:
    objective: nll
    invalid_penalty: 1.0e12
    save_invalid_points: true
    verbose: 1

  adaptive_diver:
    population_size: 40
    max_generations: 1000
    max_evaluations: null
    strategy: current_to_pbest
    p_best_fraction: 0.1
    archive: true

    mutation:
      F_min: 0.1
      F_max: 1.0
      initial_mean: 0.5
      learning_rate: 0.1

    crossover:
      CR_min: 0.0
      CR_max: 1.0
      initial_mean: 0.9
      learning_rate: 0.1

    bounds:
      handling: reflect

    convergence:
      patience: 200
      min_delta_chi2: 1.0e-8
      population_std_tol: 0.0

    local_refinement:
      enabled: false
      method: Powell
      n_elites: 5
      maxiter: 2000

    statistics:
      enabled: true
      confidence_levels: [0.68, 0.95]

    output:
      save_history: true
      save_population: true
      save_elites: true
```

`adaptive_de` is accepted as an alias for `adaptive_diver`.

## Outputs

The standard scan artifacts are preserved:

- `points.csv`
- `metadata.json`
- `best_fit.json`
- `summary.json`
- `history.json`

Additional adaptive artifacts may be written:

- `final_population.csv`
- `elite_points.csv`
- `local_refinement.json`, only when local refinement is enabled
- `parameter_summary.json`, only when adaptive population statistics are enabled
- `correlation_matrix.json`, only when adaptive population statistics are enabled

`parameter_summary.json` and `correlation_matrix.json` summarize the final
population. They are not Bayesian posterior samples and should not be cited as
credible intervals from a posterior sampler.

## Progress Logs

With `verbose > 0`, the engine prints lightweight progress to stdout every
`progress_interval` generations:

```text
[adaptive_diver] generation=100 | evaluations=... | valid=... | best_target=... | mean=... | std=... | successes=... | mu_F=... | mu_CR=... | best_parameters={ ... }
```

Set `progress_interval: 0` or `verbose: 0` to disable periodic logs.

## Local Refinement

Local refinement is disabled by default. When enabled, `adaptive_diver` tries to
import `scipy.optimize` and refine the top `n_elites` final-population points
with `Powell` or `L-BFGS-B`, respecting parameter bounds. If SciPy is not
available, the scan does not crash; the skipped refinement is recorded in
`local_refinement.json`.

## Benchmarking Against Other Engines

Use the model-agnostic benchmark runner to compare `adaptive_diver` against
`serial_random`, `de_scipy`, and `adaptive_diver` with local refinement:

```bash
.venv/bin/python benchmarks/engine_benchmark.py \
  --output-dir benchmarks/runs/engine_benchmark_smoke \
  --seeds 101 202 \
  --population-size 12 \
  --generations 12
```

The benchmark uses only toy objectives:

- a simple quadratic
- a narrow correlated valley
- a multimodal Rastrigin-like objective

It writes:

- `engine_benchmark.csv`
- `engine_benchmark.json`
- one scan output directory per objective/engine/seed

These runs are for reproducible comparison only. They should not be interpreted
as proof that one engine is generally superior without larger budgets and
problem-specific validation.
