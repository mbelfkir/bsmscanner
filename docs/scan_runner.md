# Scan Runner

## Gap Addressed

The framework already had model-definition support and a compiled one-point evaluator. The missing layer was the production scan driver that repeatedly calls the native evaluator, maps scanner vectors to named parameters, handles invalid points, and writes complete scan outputs.

That layer now lives in the repository as a native scan subsystem plus a thin Python orchestration API.

## Scan Runner Architecture

Python remains the user-facing layer:

- `bsm_scanner.scan.build_scan_request`
  - reads the existing `scan:` section from the compiled-plan metadata,
  - validates engine/settings,
  - constructs deterministic scanner ordering,
  - prepares a native `ScanConfig` payload.
- `bsm_scanner.scan.run_scan`
  - hands the compiled plan plus validated scan request to the native runner,
  - returns lightweight paths and summary metadata.
- `bsm_scanner.scan.evaluate_scan_point`
  - validates the same mapping used during a full scan and is useful for callback-consistency tests.

C++ owns the hot loop:

- `ScanConfig`
  - immutable run configuration lowered from Python metadata.
- `ParameterMapper`
  - single source of truth for scanner index to parameter-name mapping.
- `CompiledEvaluatorAdapter`
  - turns a scanner vector into evaluator inputs and computes the scalar objective.
- `ResultWriter`
  - writes `points.csv`, `metadata.json`, `best_fit.json`, and `summary.json`.
- `RunController`
  - coordinates evaluation counting, failure counters, best-fit tracking, flushing, and interruption.
- `DiverRunner`
  - wraps the adapter in a Diver-compatible objective callback.
- `SerialRandomRunner`
  - lightweight native fallback for smoke tests and CI when Diver is unavailable.

Python also owns one temporary reference backend:

- `de_scipy`
  - uses `scipy.optimize.differential_evolution`,
  - reuses the same scan request, parameter ordering, invalid-point semantics,
    and artifact layout,
  - exists to validate the DE engine interface before a native implementation is
    added.

Python also owns one native framework DE engine:

- `adaptive_diver`
  - implements a model-agnostic Diver-inspired adaptive Differential Evolution loop,
  - uses the same evaluator, parameter ordering, validity semantics, and artifacts,
  - supports optional SciPy local refinement of elite points,
  - writes final-population and elite artifacts for convergence diagnostics.

Python also owns one orchestration engine:

- `basin_scan`
  - performs broad model-agnostic exploration over the original bounds,
  - clusters promising points in normalized parameter space,
  - constructs focused boxes,
  - launches `adaptive_diver` in each focused box,
  - merges and ranks basin results.

Python also owns the additive statistics/post-processing layer:

- `run_statistics`
  - reads completed scan artifacts,
  - computes machine-readable statistical summaries,
  - writes plot-ready CSV and JSON outputs under `run_directory/statistics`,
  - intentionally does not generate plots.

## Parameter Ordering Rules

Parameter ordering is deterministic and explicit.

1. Parameters are read in the YAML declaration order.
2. Scanned parameters are assigned contiguous scanner indices starting at zero.
3. Fixed parameters remain part of `parameter_order` and are stored in metadata, but they are not passed through the scanner vector.
4. The native `ParameterMapper` validates that:
   - all scanned indices are contiguous,
   - all scanned and fixed parameters appear in the declared order,
   - no duplicate names exist in the declared order,
   - each scanned parameter has valid bounds.

The resulting mapping is written to `metadata.json` under:

- `parameter_order`
- `scanned_parameters`
- `fixed_parameters`

## Invalid-Point Policy

The native evaluator remains the source of truth for point validity.

Scan records carry both:

- `status`
  - technical evaluation status
- `valid`
  - physics/model validity

The scan runner translates outcomes as follows:

- `status == ok` and `valid == true`
  - the point ran and passed model validity checks
  - scanner sees the requested objective value
- `status == ok` and `valid == false`
  - the evaluator ran, but the point failed a physics/model condition such as a
    theory check, non-finite observable, invalid likelihood input, backend
    failure, or explicit invalid-penalty assignment
  - scanner sees `invalid_objective` or the engine-specific invalid penalty
  - failure reason is counted in `summary.json`
- non-`ok` status with `valid == false`
  - technical failure such as missing input, numerical error, or evaluation
    exception
  - scanner sees `invalid_objective`
  - diagnostics remain visible in `points.csv` and `summary.json`
- non-finite `total_nll`, non-finite prior contribution, or non-finite objective
  - translated to an invalid objective
  - recorded with `valid == false`

This keeps the scanner robust while preserving diagnostics for post-run analysis.

`points.csv` includes the validity flag near the front:

```text
evaluation,status,valid,failure_reason,scanner_target,metric_value,total_nll,...
```

Downstream statistics must use `valid`, not `status == ok`, for new scan
outputs. This distinction is important because a point can run successfully but
still fail model validity checks.

## Objective Convention

The current runner supports:

- `objective: nll`
- `objective: posterior_nll`

The scanner always receives a scalar target to minimize.

- If `maximize: false`, the scanner target is the metric value directly.
- If `maximize: true`, the scanner target is `-metric_value`.

For `posterior_nll`, the native adapter adds the declared parameter priors to the evaluator's `total_nll`.

## Supported Scan Metadata

The scan runner consumes the existing `scan:` block from the model definition:

```yaml
scan:
  engine: diver
  save_every: 250
  seed: 12345
  settings:
    objective: nll
    maxgen: 2000
    NP: 48
    convthresh: 1.0e-3
    convsteps: 20
    invalid_objective: 1.0e300
    save_invalid_points: false
    verbose: 1
```

Supported keys in `settings`:

- `objective`
- `maximize`
- `max_evaluations`
- `max_generations` or `maxgen`
- `population_size` or `NP`
- `convergence_threshold` or `convthresh`
- `convergence_steps` or `convsteps`
- `invalid_objective`
- `max_init_attempts`
- `save_invalid_points`
- `verbose`
- `progress_interval` / `progress_every` / `log_every`

`de_scipy` accepts a focused SciPy-style subset in the same `settings` block:

- `strategy`
- `maxiter`
- `popsize`
- `tol`
- `atol`
- `mutation`
- `recombination`
- `init`
- `updating`
- `workers`
- `polish`
- `invalid_penalty`
- `x0`
- `seed` (optional override of top-level `scan.seed`)
- `progress_interval` (print DE progress every N generations when `verbose > 0`)

Example:

```yaml
scan:
  engine: de_scipy
  seed: 12345
  save_every: 1
  settings:
    objective: nll
    strategy: rand1bin
    maxiter: 50
    popsize: 15
    tol: 1.0e-2
    atol: 0.0
    mutation: [0.5, 1.0]
    recombination: 0.7
    init: latinhypercube
    updating: deferred
    workers: 1
    polish: false
    progress_interval: 100
    invalid_penalty: 1.0e12
```

With `de_scipy`, `verbose > 0` prints lightweight progress logs to stdout:

```text
[de_scipy] generation=100 | evaluations=... | valid=... | saved=... | best_target=... | best_metric=... | convergence=... | best_parameters={ ... }
```

Set `progress_interval: 0` or `verbose: 0` to disable periodic stdout updates.

`adaptive_diver` accepts the same shared scan settings and may additionally use
an engine-specific block:

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
    p_best_fraction: 0.1
    archive: true
    bounds:
      handling: reflect
    convergence:
      patience: 200
      min_delta_chi2: 1.0e-8
      population_std_tol: 0.0
    local_refinement:
      enabled: false
    statistics:
      enabled: true
```

See `docs/adaptive_diver.md` for the full option list. `adaptive_de` is accepted
as an alias for `adaptive_diver`.

`basin_scan` accepts shared scan settings plus a top-level `scan.basin_scan`
block. It is an orchestration wrapper around exploration plus focused
`adaptive_diver` runs:

```yaml
scan:
  engine: basin_scan
  seed: 12345
  settings:
    objective: nll
    invalid_penalty: 1.0e12
    verbose: 1

  basin_scan:
    exploration:
      method: latin_hypercube
      n_points: 50000
    selection:
      mode: top_fraction
      top_fraction: 0.02
      max_points: 2000
    clustering:
      method: dbscan
      eps_fraction: 0.08
      min_samples: 10
      max_clusters: 8
    boxes:
      construction: quantile
      padding_fraction: 0.25
      min_width_fraction: 0.02
    focused_engine:
      name: adaptive_diver
      population_size: 60
      max_generations: 1500
```

See `docs/basin_scan.md` for the full option list and artifact descriptions.
`basin_scan.progressive_exploration.enabled` is available as an opt-in staged
exploration mode. It is disabled by default and preserves the original one-shot
exploration behavior unless explicitly enabled.

Validation rules:

- `serial_random` requires `max_evaluations`.
- `diver` requires `max_generations` or `max_evaluations`.
- `de_scipy` currently requires `workers = 1` in the reference implementation.
- `adaptive_diver` requires at least four population members and never passes
  permanently out-of-bounds points to the evaluator.
- `basin_scan` requires at least one exploration point and currently supports
  `adaptive_diver` as its focused engine.
- log priors require strictly positive lower bounds.
- scanned parameters must currently be real scalars.

For `de_scipy`, invalid points and evaluator exceptions are translated into the
configured `invalid_penalty`, so the optimizer can continue without crashing.
Those rows are written with `valid == false`.

## Statistics Metadata

The optional top-level `statistics:` block controls additive post-processing:

```yaml
statistics:
  enabled: true
  method: de_weighted
  credible_levels: [0.68, 0.95]
  output_samples: true
  include_observables: true
```

Current method support:

- `de_weighted`
  - implemented
- `de_mcmc`
  - reserved placeholder
- `profile_likelihood`
  - reserved placeholder
- `nested_sampling`
  - reserved placeholder

`de_weighted` is intentionally conservative in scope:

- it treats the scan points as evaluated DE points, not as true posterior samples
- it uses `metric_value` as the chi2-like quantity to weight
- it uses `valid == true` rows for likelihood-weighted summaries
- it computes numerically stable shifted likelihood weights from
  `delta_chi2 = chi2 - chi2_min`
- it writes only machine-readable outputs for later plotting

This keeps the architecture clean:

`engine -> raw scan/statistical outputs -> external plotting`

## Output Files

Each scan directory contains:

- `points.csv`
  - one row per saved evaluation,
  - scanner target, metric value, total nLL,
  - scanned parameters,
  - selected outputs,
  - per-likelihood terms.
- `metadata.json`
  - model name/version,
  - framework version,
  - engine and objective mode,
  - seed and timestamp,
  - parameter ordering,
  - priors, bounds, fixed parameters,
  - raw scanner settings.
- `best_fit.json`
  - best valid point found during the run,
  - scanned parameter values,
  - outputs,
  - per-likelihood terms.
- `summary.json`
  - total evaluations,
  - saved/valid counts,
  - interruption flag,
  - failure counters,
  - failure reasons.
- `history.json` for `de_scipy` and `adaptive_diver`
  - per-generation best-target snapshots and convergence metadata when available.
- `final_population.csv` for `adaptive_diver`
  - final population, objective values, status/valid flags, and scanned parameters.
- `elite_points.csv` for `adaptive_diver`
  - top final-population points sorted by objective value.
- `parameter_summary.json` and `correlation_matrix.json` for `adaptive_diver`
  - optional final-population summaries; these are not posterior samples.
- `exploration_points.csv`, `selected_points.csv`, `clusters.csv`,
  `focused_boxes.json`, and `basin_results.json` for `basin_scan`
  - basin-discovery artifacts plus ranked focused-run summaries.

When `statistics.enabled: true`, the run directory also contains:

- `statistics/de_weighted_samples.csv`
  - one row per saved scan point with derived `chi2`, `delta_chi2`, `loglike`,
    `shifted_loglike`, and normalized likelihood weights
- `statistics/de_weighted_summary.json`
  - weighted summaries and credible intervals per scanned parameter
- `statistics/de_credible_intervals.json`
  - compact parameter-to-interval map
- `statistics/diagnostics.json`
  - counts, ESS, chi2 range, weight diagnostics, and warnings

The JSON writers sort unordered content before writing so metadata and summaries are deterministic for reproducibility tests.

## Build With Diver

The Diver bridge is optional and is disabled by default.

Build with Diver support through `scikit-build-core`:

```bash
CMAKE_ARGS="-DBSM_SCANNER_BUILD_DIVER=ON -DBSM_SCANNER_DIVER_ROOT=/path/to/Diver" \
python -m pip install -e .[dev]
```

You can also pass explicit paths instead of a prefix:

```bash
CMAKE_ARGS="-DBSM_SCANNER_BUILD_DIVER=ON \
  -DBSM_SCANNER_DIVER_INCLUDE_DIR=/path/to/Diver/include \
  -DBSM_SCANNER_DIVER_LIBRARY=/path/to/libdiver.so" \
python -m pip install -e .[dev]
```

## Build With SciPy DE

The `de_scipy` engine is optional and lives entirely on the Python side.

Install the reference backend dependency with:

```bash
python -m pip install -e '.[de]'
```

## Launch Example

Compile and run the example scan:

```bash
python examples/oneloop_minimal/run_scan.py --run-dir examples/oneloop_minimal/runs/example_scan
```

If the example model uses `engine: diver`, make sure the native extension was built with Diver support. For a quick smoke test in CI or on a laptop, change `scan.engine` to `serial_random` and set `settings.max_evaluations`.
