# Model Schema

## Philosophy

The common case does not require users to write C++. A new model is defined through structured YAML with typed sections.

That YAML can be either:

- a single-file model definition
- a top-level manifest that imports smaller YAML fragments

## Top-Level Sections

```yaml
metadata:
imports:
parameters:
constants:
functions:
derived_scalars:
derived_complex:
matrices:
diagonalizations:
mixing_matrices:
observables:
theory_checks:
likelihoods:
outputs:
scan:
statistics:
```

`imports:` is optional. When present, it is a string or list of strings pointing to additional YAML fragments. Imported fragments are resolved relative to the file that declares them.

Example:

```yaml
metadata:
  name: oneloop_full_normal

imports:
  - parameters.yaml
  - constants.yaml
  - observables/neutrino.yaml
  - constraints/likelihoods.yaml
```

Fragments may themselves contain `imports:` for nested composition.

## Merge Rules

Imported fragments merge in listed order, then the current file contributes its own sections.

- named list sections concatenate:
  - `parameters`, `constants`, `functions`, `derived_scalars`, `derived_complex`
  - `matrices`, `diagonalizations`, `observables`, `theory_checks`, `likelihoods`
  - `mixing_matrices`
- mapping sections merge by key:
  - `metadata`, `outputs`, `scan`, `statistics`
- `outputs.save` concatenates

Duplicate named entries across concatenated sections are rejected at load time with a clear error. Conflicting scalar keys inside merged mappings are also rejected.

This same import mechanism is how models consume reusable framework-owned YAML
blocks. A model may, for example, import
`core/neutrino/normal.yaml` for generic
ordering-aware neutrino observables while keeping its own likelihood blocks
under the model directory.

## Parameters

```yaml
parameters:
  - name: Mpsi
    value_type: real
    scan: true
    lower: 100.0
    upper: 2000.0
    default: 300.0
    prior: log
```

Supported options:

- `scan`: whether the parameter is scanned or fixed.
- `prior`: `flat`, `log`, or `fixed`.
- `value_type`: `real` or `complex`.

Complex parameters are typically expressed as paired real parameters for scanner friendliness, with a derived complex node reconstructing the analytic object.

## Statistics Block

The optional `statistics:` block enables additive post-processing after a scan:

```yaml
statistics:
  enabled: true
  method: de_weighted
  credible_levels: [0.68, 0.95]
  output_samples: true
  include_observables: true
```

This block does not change point evaluation or scan-engine behavior. It controls
machine-readable post-processing outputs under `run_directory/statistics`.

For new scan outputs, statistics use the explicit `valid` column written to
`points.csv`. `status` reports technical evaluation status; `valid` reports
physics/model validity. Invalid rows can remain in CSV outputs for debugging,
but they are excluded from likelihood-weighted summaries.

## Constants

```yaml
constants:
  - name: vev
    value: 246.22
```

## Reusable Analytic Functions

```yaml
functions:
  - name: I3
    args: [mphi, mphip, mpsi]
    expression: >
      -(
        (mphi**2 * log((mpsi**2)/(mphi**2))) /
        ((mphi**2 - mphip**2) * (mphi**2 - mpsi**2))
        +
        (mphip**2 * log((mpsi**2)/(mphip**2))) /
        ((mphip**2 - mphi**2) * (mphip**2 - mpsi**2))
      ) / ((4*pi)*(4*pi))
```

These are compile-time expanded into dependent expressions before lowering.

## Derived Nodes

```yaml
derived_scalars:
  - name: mphi_sq
    expression: Mphi**2 - 0.5*k1*vev**2

derived_complex:
  - name: ye
    expression: Reye + 1j*Imgye
```

## Matrices

```yaml
matrices:
  - name: neutrino_mass_matrix
    value_type: complex_matrix
    type: majorana_mass
    role: neutrino
    diagonalize: true
    rows:
      - ["2*Ye*ye*norm", "Ye*ymu*norm"]
      - ["Ye*ymu*norm", "2*Ymu*ymu*norm"]
```

Supported metadata:

- `type` or `matrix_type`
  - `complex_general`
  - `complex_symmetric`
  - `dirac_mass`
  - `majorana_mass`
  - `hermitian`
  - `real_symmetric`
- `role`
  - a model-defined label such as `neutrino` or `charged_lepton`
- `diagonalize`
  - when `true`, the loader automatically creates a diagonalization node using
    the appropriate method for the matrix type
- `diagonalization_name` (optional)
  - override the generated node name
- `diagonalization_method` (optional)
  - override the inferred method explicitly

Current method inference:

- `complex_general` -> `svd`
- `complex_symmetric` -> `takagi`
- `hermitian` -> `hermitian_eigh`
- `dirac_mass` -> `svd_complex`
- complex `majorana_mass` -> `takagi`
- `real_symmetric` -> `self_adjoint_eigen`

If `diagonalize: true` and no explicit name is given, the framework generates:

- `diag__<role>` when `role` is present
- `diag__<matrix_name>` otherwise

This keeps the core generic: no matrix names such as `Mnu` or `Me` are
hardcoded into the evaluator.

## Diagonalization Nodes

```yaml
diagonalizations:
  - name: neutrino_takagi
    input: neutrino_mass_matrix
    method: takagi
```

Supported methods in the skeleton:

- `svd_real`
- `svd_complex`
- `svd`
- `takagi`
- `hermitian_eigh`
- `self_adjoint_eigen`
- `self_adjoint_eigen_complex`

Explicit `diagonalizations:` are still supported. Automatic diagonalization is
meant to remove duplicated boilerplate, not to remove manual control.

New models can name diagonalization outputs directly:

```yaml
matrices:
  - name: Ml
    value_type: complex_matrix
    type: complex_general
    role: charged_lepton_mass
    diagonalize:
      method: svd
      output:
        masses: charged_lepton_masses
        left_unitary: U_l_L
        right_unitary: U_l_R
    rows:
      - ["0.000511", "0.0", "0.0"]
      - ["0.0", "0.10566", "0.0"]
      - ["0.0", "0.0", "1.77686"]
```

The generated aliases are graph nodes and can be saved or used by downstream
observables and mixing matrices.

## Mixing Matrices

Mixing matrices are first-class graph nodes constructed from rotation matrices:

```yaml
mixing_matrices:
  - name: PMNS
    type: left_mismatch
    convention: U_left_dagger_U_right
    left: U_l_L
    right: U_nu
    output: U_PMNS

  - name: CKM
    type: left_mismatch
    convention: U_left_dagger_U_right
    left: U_u_L
    right: U_d_L
    output: V_CKM
```

`U_left_dagger_U_right` means:

```text
output = dagger(left) @ right
```

So the standard flavor conventions are:

```text
U_PMNS = U_l_L^\dagger U_nu
V_CKM  = U_u_L^\dagger U_d_L
```

The alternate convention is `U_left_U_right_dagger`.

Optional-sector behavior:

- PMNS requires a neutrino rotation.
- PMNS can use an identity charged-lepton fallback for neutrino-only models.
- CKM requires both up- and down-sector rotations.
- undefined rotations raise validation errors naming the missing object.

See `docs/matrix_diagonalization.md` for the full convention reference.

Reusable CKM scalar observables live in:

```text
core/quark/ckm_observables.yaml
```

The block assumes a matrix node named `V_CKM` and provides absolute CKM
elements, quark mixing angles, `deltaCKM`, `J_CKM`, and prefixed Wolfenstein
parameters. See `docs/ckm_observables.md`.

When CKM is built directly from SVD rotations, import
`core/quark/ckm_from_left_rotations_descending_svd.yaml` to construct the raw
`V_CKM_descending` matrix, then import
`core/quark/ckm_observables_from_descending_svd.yaml` to reorder
`(t,c,u) x (b,s,d)` into physical `(u,c,t) x (d,s,b)` before extracting scalar
CKM observables.

Reusable quark mass-ratio observables live in:

```text
core/quark/quark_mass_ratios.yaml
```

That block assumes ordered SVD aliases named `up_quark_masses` and
`down_quark_masses` and provides CSV-safe outputs such as `mu_over_mc`,
`mc_over_mt`, `md_over_ms`, and `ms_over_mb`.

## Reusable Core Blocks

The framework may ship declarative YAML under
`core` for calculations that are genuinely
model-independent.

Example:

```yaml
metadata:
  name: leptontest_normal

imports:
  - parameters.yaml
  - functions.yaml
  - derived.yaml
  - matrices.yaml
  - ../../core/neutrino/normal.yaml
  - constraints/likelihood.yaml
  - outputs.yaml
  - scan.yaml
```

This split is intentional:

- the core owns reusable calculations
- the model owns parameter choices, matrices, datasets, and likelihood terms
- the user can still swap or edit model-side likelihood blocks without touching
  the framework

## Observable Nodes

An observable can be expression-based:

```yaml
observables:
  - name: dm21
    expression: m2**2 - m1**2
```

or plugin-backed:

```yaml
observables:
  - name: Omega
    value_type: real
    plugin_call:
      plugin: oneloop_micromegas
      function: omega
      bindings:
        Mchi: Mpsi
        Mh: mh_ref
        dm_target_name: dm_target_name
```

or projected from a diagonalization node:

```yaml
observables:
  - name: m1
    projection:
      from: neutrino_svd
      quantity: singular_values
      index: 0
```

`plugin_call` is also available on `derived_scalars` and `derived_complex`.
Each plugin call must declare:

- `plugin`: runtime plugin name
- `function`: named output/function inside that plugin
- `bindings`: mapping from plugin argument name to source node name
- `options` (optional): mapping of scalar literal options passed directly to the plugin
- `output` (optional): output selector for plugins that multiplex several result channels

`plugin_call` is also available on `derived_scalars`, `derived_complex`,
`observables`, and `theory_checks`.

## Theory Checks

```yaml
theory_checks:
  - name: positive_mphi
    condition: mphi_sq > 0
    fatal: true
    message: mphi_sq must remain positive
```

Theory checks may also be plugin-backed:

```yaml
theory_checks:
  - name: backend_consistency
    plugin_call:
      plugin: toy_backend
      function: passes_check
      bindings:
        x: mass_like_observable
      options:
        threshold: 10.0
    fatal: true
    message: backend consistency check failed
```

Theory checks are evaluated separately from likelihoods and can invalidate a point before constraint evaluation.

## Likelihood Controls

`table_lookup` supports optional interpolation and source-parity controls:

```yaml
likelihoods:
  - name: theta12_term
    kind: table_lookup
    observable: Theta12
    interpolation: cubic_spline
    in_range_offset: -6.1
    table_file: data/Inverted/Theta12.csv
    out_of_range_penalty_scale: 4.0e4
    out_of_range_penalty_cap: 1.0e6
```

- `interpolation`: `linear` or `cubic_spline`
- `in_range_offset`: additive shift applied only to the interpolated in-range table value

`multivariate_gaussian` also supports an explicit quadratic prefactor:

```yaml
likelihoods:
  - name: Oblique_term
    kind: multivariate_gaussian
    quadratic_form_prefactor: 1.0
```

The default `quadratic_form_prefactor` is `0.5`, corresponding to the common `0.5 * Δᵀ C⁻¹ Δ` convention. Set it to `1.0` when a source implementation defines the full quadratic form directly.

## Likelihoods

Supported likelihood kinds:

- `gaussian`
- `asymmetric_gaussian`
- `upper_limit`
- `lower_limit`
- `interval`
- `hard_cut`
- `table_lookup`
- `multivariate_gaussian`
- `custom`

Examples:

```yaml
likelihoods:
  - name: higgs_mass
    kind: gaussian
    observable: HiggsMass
    mean: 125.10
    sigma: 0.14

  - name: mu_to_e_gamma
    kind: upper_limit
    observable: mu_to_e_gamma
    upper: 4.2e-13
    sigma: 1.0e-13

  - name: dm21_term
    kind: table_lookup
    observable: log10_dm21
    table_file: data/Normal/dm21.csv
    out_of_range_penalty_scale: 4.0e4
    out_of_range_penalty_cap: 1.0e6

  - name: backend_term
    kind: custom
    plugin_call:
      plugin: toy_backend
      function: nll
      bindings:
        x: HiggsMass
      options:
        scale: 2.0
      output: nll
```

Custom likelihoods may use either the legacy `plugin` callback name or the
preferred `plugin_call` contract. `plugin_call` is the generic path for
backend-driven likelihood terms because it supports structured bindings and
literal options without extending the framework core for each model.

Likelihood composition remains model-side by design. The framework core
provides reusable kernels such as `gaussian`, `hard_cut`, `table_lookup`, and
`multivariate_gaussian`, but it does not own model datasets or decide which
terms are active in a given scan.

For `table_lookup`, the framework accepts either:

- `table`: inline `[[x, nll], ...]` rows
- `table_file`: a relative path to a two-column CSV or whitespace-separated file

When `table_file` is used through [load_model](../python/bsm_scanner/api.py), the file is resolved relative to the fragment that contains it and loaded into the compiled constraint payload before graph construction.

Optional table-lookup controls:

- `out_of_range_penalty_scale`
- `out_of_range_penalty_cap`

These reproduce the reference `oneloop` behavior where values outside the tabulated domain receive a quadratic penalty instead of silently clamping to the table edge.

## Outputs

```yaml
outputs:
  save:
    - Mpsi
    - mphi
    - dm21
    - mu_to_e_gamma
```

## Scan Section

```yaml
scan:
  engine: diver
  seed: 12345
  save_every: 1000
  settings:
    objective: nll
    maxgen: 4000
    NP: 48
    convthresh: 1.0e-3
    convsteps: 20
    invalid_objective: 1.0e300
    save_invalid_points: false
    verbose: 1
```

Supported scan metadata:

- `engine`: currently `diver`, `serial_random`, `de_scipy`, or `adaptive_diver`.
- `seed`: deterministic seed forwarded to the native runner.
- `save_every`: native flush cadence for scan output files.
- `settings.objective`: `nll` or `posterior_nll`.
- `settings.max_evaluations`: required for `serial_random`, optional for `diver`.
- `settings.max_generations` or `settings.maxgen`: required for `diver` unless `max_evaluations` is given.
- `settings.population_size` or `settings.NP`: Diver population size.
- `settings.convergence_threshold` or `settings.convthresh`
- `settings.convergence_steps` or `settings.convsteps`
- `settings.invalid_objective`
- `settings.max_init_attempts`
- `settings.save_invalid_points`
- `settings.verbose`

`de_scipy` also accepts:

- `settings.strategy`
- `settings.maxiter`
- `settings.popsize`
- `settings.tol`
- `settings.atol`
- `settings.mutation`
- `settings.recombination`
- `settings.init`
- `settings.updating`
- `settings.workers`
- `settings.polish`
- `settings.invalid_penalty`
- `settings.x0`
- `settings.seed`

`adaptive_diver` also accepts an engine-specific `scan.adaptive_diver` mapping
for population size, generations, adaptive mutation/crossover, bound handling,
convergence, optional local refinement, and final-population summaries. See
`docs/adaptive_diver.md` for the full schema.

The runner uses parameter declaration order as the deterministic parameter-order source, and this ordering is written to scan metadata for downstream reproducibility.

## Statistics Section

```yaml
statistics:
  enabled: true
  method: de_weighted
  credible_levels: [0.68, 0.95]
  output_samples: true
  include_observables: true
```

Supported metadata:

- `enabled`
  - enable additive post-processing under `run_directory/statistics`
- `method`
  - `de_weighted` is implemented
  - `de_mcmc`, `profile_likelihood`, and `nested_sampling` are reserved and currently raise a clear `NotImplementedError`
- `credible_levels`
  - central weighted credible intervals to compute
- `output_samples`
  - whether to write `statistics/de_weighted_samples.csv`
- `include_observables`
  - whether to keep `output::...` columns in the statistics sample table

The statistics layer is intentionally plot-free. It only writes machine-readable
CSV and JSON artifacts for later notebook or script-based visualization.

## Recommended Large-Model Layout

For large models, prefer a manifest plus sector files:

```text
models/example/
  model.yaml
  parameters.yaml
  constants.yaml
  functions.yaml
  derived.yaml
  matrices.yaml
  diagonalizations.yaml
  observables/
  constraints/
  outputs.yaml
  scan.yaml
  data/
```

For models that reuse framework-owned neutrino calculations, the layout can be
even slimmer:

```text
models/example/
  model.yaml
  parameters.yaml
  functions.yaml
  derived.yaml
  matrices.yaml
  constraints/
  outputs.yaml
  scan.yaml
```

with `model.yaml` importing a core block such as
`../../core/neutrino/normal.yaml` or `../../core/neutrino/inverted.yaml`.
