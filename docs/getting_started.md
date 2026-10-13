# Getting started

This page takes you from installation to a first scan, then shows how a real model is laid out.
For the complete schema see [Writing a model](authoring_models.md); for worked physics examples
see the [Tutorials](tutorials/index.md).

## 1. Install

```bash
pip install bsm-scanner
bsm-scanner --version
```

The optional extras add plotting and analysis helpers (`pip install "bsm-scanner[analysis]"`)
and the SciPy-based engines and local refinement (`pip install "bsm-scanner[de]"`).

## 2. Create and run a starter model

```bash
bsm-scanner new-model mymodel
bsm-scanner run --model mymodel/model.yaml --run-dir mymodel/runs/first
```

`new-model` writes a small, complete model to `mymodel/model.yaml`, so you always start from a
working baseline. The run directory then contains:

| File | Content |
|---|---|
| `points.csv` | every evaluated point: parameters, requested outputs, each likelihood term, validity and failure reason |
| `best_fit.json` | the best point: parameters, outputs and the contribution of every likelihood term |
| `summary.json` | evaluations, valid points, failure counts by reason, engine diagnostics and stop reason |
| `metadata.json` | seed, fully resolved configuration and framework version — enough to reproduce the run |

## 3. Anatomy of a model

A model is a manifest that imports YAML fragments. A typical layout:

```text
mymodel/
  model.yaml          # metadata + imports only
  parameters.yaml     # free parameters, ranges and priors
  constants.yaml      # fixed numbers
  functions.yaml      # reusable analytic functions (expanded at load time)
  derived.yaml        # derived scalar / complex quantities
  matrices.yaml       # mass matrices and how to diagonalise them
  observables.yaml    # named physical quantities
  likelihoods.yaml    # the terms summed into the objective
  outputs.yaml        # what to write to points.csv
  scan.yaml           # engine and its settings
```

The manifest can also import reusable blocks shipped with the package by name:

```yaml
metadata:
  name: my_neutrino_model
  ordering: normal
imports:
  - parameters.yaml
  - matrices.yaml
  - core:neutrino/normal.yaml        # PMNS, angles, delta_CP, masses, m_beta, m_betabeta
  - likelihoods.yaml
  - outputs.yaml
  - scan.yaml
```

List the available blocks and inspect what one defines before importing it:

```bash
bsm-scanner core list
bsm-scanner core show core:neutrino/observables_common.yaml
```

### Parameters

```yaml
parameters:
  - {name: MN1, value_type: real, scan: true, lower: 10.0, upper: 1.0e5, default: 900.0, prior: log}
  - {name: lambda5, value_type: real, scan: true, lower: -0.01, upper: 0.01, default: 1.0e-8,
     prior: signed_log, min_abs: 1.0e-12}
```

Priors are `flat`, `log`, `signed_log` (sign sampled independently, magnitude log-uniform above
`min_abs`) and `fixed`.

### Matrices

Declare a matrix entry by entry; its `type` selects the diagonalisation:

```yaml
matrices:
  - name: neutrino_mass_matrix
    value_type: complex_matrix
    type: majorana_mass      # -> Takagi factorisation, U^T M U = diag(m), m >= 0
    role: neutrino           # -> node diag__neutrino, read by core:neutrino/*
    diagonalize: true
    rows:
      - ["m11", "m12", "m13"]
      - ["m12", "m22", "m23"]
      - ["m13", "m23", "m33"]
```

### Observables, theory checks and likelihoods

```yaml
observables:
  - {name: dm21_meV2, value_type: real, expression: "dm21_scaled*1.0e6"}

theory_checks:
  - {name: perturbative, condition: "abs(lambda5) < 4*pi", fatal: true,
     message: lambda5 is non-perturbative}

likelihoods:
  - {name: s12_nufit, kind: table_lookup, observable: s12,
     table_file: core:data/nufit/Normal/Theta12.csv, interpolation: cubic_spline}
  - {name: higgs_mu, kind: gaussian, observable: mu_h, mean: 1.025, sigma: 0.06}
  - {name: meg_limit, kind: hard_cut, observable: br_mu_e_gamma, lower: 0.0, upper: 1.5e-13}
```

Theory checks decide whether a point is a sensible theory at all; likelihood terms decide how
well it fits. A failed fatal check or hard cut invalidates the point and its reason is recorded.
Nine likelihood kinds are available: `gaussian`, `asymmetric_gaussian`, `upper_limit`,
`lower_limit`, `interval`, `hard_cut`, `table_lookup`, `multivariate_gaussian` and `custom`
(plugin-backed).

!!! note "Neutrino mass scale"
    The `core:neutrino` blocks expose both the raw singular values of the mass matrix
    (`m1`, `m2`, `m3`, in the matrix's own units) and `*_scaled` masses normalised to the NuFIT
    best-fit splittings. A model that predicts the absolute neutrino mass scale should fit the
    raw quantities; a texture that predicts only mass ratios uses the `*_scaled` ones. See the
    [changelog](changelog.md) for the 0.2.0 naming.

## 4. Choose an engine

The engine is one block of `scan.yaml`:

```yaml
scan:
  engine: adaptive_diver        # serial_random | de_scipy | adaptive_diver | basin_scan
  seed: 12345
  settings: {objective: nll, invalid_penalty: 1.0e12, save_invalid_points: true}
  adaptive_diver:
    population_size: 128
    max_generations: 400
    convergence: {patience: 100}
```

| Engine | Use it when |
|---|---|
| `serial_random` | the likelihood has nothing to optimise (pure exclusion) or you need an unbiased baseline |
| `de_scipy` | you want an independent cross-check with SciPy's differential evolution |
| `adaptive_diver` | the default for a graded likelihood: self-adapting differential evolution with optional local refinement |
| `basin_scan` | the valid region is a tiny or disconnected fraction of the prior: explore, cluster, then run `adaptive_diver` in focused boxes |

A build compiled with the external Diver library also accepts `engine: diver`.
See [adaptive_diver](adaptive_diver.md) and [basin_scan](basin_scan.md) for every option.

## 5. From Python

```python
from bsm_scanner import load_model, compile_model, run_scan, load_results

model = load_model("mymodel/model.yaml")
compiled = compile_model(model)

point = {p.name: p.default for p in model.parameters}
print(compiled.evaluate(point)["outputs"])        # one point through the compiled evaluator

result = run_scan(model, compiled, run_directory="mymodel/runs/python")
print(result.summary["best_metric_value"])
```

## Next steps

- [Tutorials](tutorials/index.md): seven complete models, each with the specification, a live
  scan, the reference best fit and its figures.
- [Writing a model](authoring_models.md): the full schema.
- [Statistics](statistics.md) and [Posterior sampling](posterior_mcmc.md): from a scan to
  intervals.
