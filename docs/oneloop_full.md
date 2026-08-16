# Full Oneloop Example

The full migrated normal-ordering oneloop model now lives in modular form at:

- `models/oneloop/model.yaml`

The old example path remains as a compatibility wrapper:

- `examples/oneloop_full/model.yaml`

The modular layout is:

```text
models/oneloop/
  model.yaml
  parameters.yaml
  constants.yaml
  functions.yaml
  derived.yaml
  matrices.yaml
  diagonalizations.yaml
  observables/
    neutrino.yaml
    higgs.yaml
    lfv.yaml
    ew.yaml
    scalar_sector.yaml
    dm.yaml
  constraints/
    theory_checks.yaml
    likelihoods.yaml
  outputs.yaml
  scan.yaml
  data/
```

## What Is Active

### Parameters

All parameters from the `config_nr.yaml` scan parameterization are active in the example:

- `Mpsi`, `MN`, `Mphi`, `MA1`, `MH1`, `MH2`
- `sh`, `k1`, `k4`, `k5`, `lambda1`, `lambda2`, `lambda3`
- all real and imaginary Yukawa components for `y`, `Y`, and `y'`

### Observables

The example currently computes:

- Neutrino sector:
  - `Theta12`, `Theta13`, `Theta23`, `deltaCP`
  - `dm21`, `dm3l`
  - `m1`, `m2`, `m3`, `sum_m`
  - `eta1`, `eta2`, `scale`, `mbeta`, `mbetabeta`
- LFV:
  - `mu_to_e_gamma`, `tau_to_e_gamma`, `tau_to_mu_gamma`
  - `mu_to_eee`, `tau_to_eee`, `tau_to_mumumu`
- Higgs:
  - `HiggsMass`, `HiggsRgg`
- Electroweak precision:
  - `ObliqueS`, `ObliqueT`

### Theory Checks

The example currently enforces:

- positivity / non-tachyon conditions for derived squared masses
- validity of the dependent `MA2` relation
- dark-matter identity as an analytic lightest-state check
- non-singular `I3` mass splittings
- the original I3 mass-ordering condition
- quartic/vacuum bounds
- perturbative unitarity from the six scalar scattering matrices
- finite-value checks for neutrino, LFV, and precision sectors

### Likelihood Terms

The active likelihood/constraint set includes:

- table-based oscillation likelihoods:
  - `Theta12`, `Theta13`, `Theta23`, `deltaCP`, `dm21`, `dm3l`
- cosmological sum-of-masses hard cut
- Higgs mass Gaussian
- `HiggsRgg` Gaussian
- LFV hard upper limits
- correlated `S,T` Gaussian

## Remaining Gaps

The remaining gap is the micrOMEGAs-dependent dark-matter backend layer:

- relic density `Omega`
- direct-detection rate / p-value logic
- exact micrOMEGAs odd-particle identity

These are not faked in the example. The current model metadata marks the example as `micromegas_pending`, and the migration status is documented in:

- `docs/migration_oneloop.md`
- `docs/current_status.md`
- `docs/dm_status.md`

If you need the exact latest-master DM backend path rather than the frozen
baseline example, use:

- `models/oneloop_master/model.yaml`
- `docs/oneloop_master.md`

## Running The Example

Compile and evaluate the default point:

```bash
python examples/oneloop_full/run_example.py
```

Run a scan:

```bash
python examples/oneloop_full/run_scan.py \
  --run-dir examples/oneloop_full/runs/example_scan
```

## Validation

The repository test suite includes:

- model loading for the full example
- equivalence between the modular manifest and the preserved single-file reference
- graph compilation
- one-point evaluation at a valid seed point
- callback consistency between direct evaluation and scan evaluation
- a serial-random scan smoke test
