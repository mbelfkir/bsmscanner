# Implemented vs Deferred

This document classifies the current repository state conservatively. It is intended to be cited when deciding which sectors are safe to use in scans and which sectors remain outside the current milestone claim.

## Framework Infrastructure

### Implemented And Validated

- Model loading from YAML: implemented and covered by unit tests.
- Modular manifest/import support: implemented with nested relative imports, duplicate detection, and merge validation.
- Schema validation: implemented for parameters, constants, functions, derived nodes, matrices, diagonalizations, observables, theory checks, likelihoods, outputs, and scan metadata.
- Dependency graph construction and cycle rejection: implemented and tested.
- Graph lowering to a native plan: implemented and exercised in tests and examples.
- C++ compiled point evaluator: implemented and exercised by direct backend tests.
- Native scan runner: implemented for `serial_random`, Diver-backed execution,
  and the model-agnostic `adaptive_diver` Differential Evolution engine.
- Output writing: implemented as `points.csv`, `metadata.json`, `best_fit.json`, and `summary.json`.
- Python bindings: implemented through the native extension.
- Documentation: implemented for architecture, model schema, scan runner, modular models, oneloop migration, and the milestone documents added here.
- Test suite: implemented and currently passing locally and on the server.

### Implemented But Only Partially Validated

- Diver integration: validated by smoke and medium-size scans on the server, but not yet certified as a long-production-campaign benchmark.
- Full-model scan behavior: validated through smoke tests and targeted reruns, but not yet benchmarked point-by-point against a large original oneloop sample.
- Compatibility wrapper model at `/Users/mbelfkir/HEP/BSMScanner/examples/oneloop_full/model.yaml`: validated as a loader path, but the canonical source of truth is the modular model under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop`.

### Implemented Approximately / Placeholder-Backed

- None at the framework-core level.

### Intentionally Deferred

- None at the framework-core level.

### Blocked By External Backend / Toolchain Dependency

- None at the framework-core level.

## Oneloop Model Migration

### Implemented And Validated

- Full scanned parameter set for the migrated normal-ordering model.
- Fixed constants and helper definitions required by the migrated normal-ordering path.
- Reusable loop/helper functions needed by the current migrated model.
- Matrix definitions and diagonalization declarations used by the migrated model.
- Neutrino-sector observables:
  - `Theta12`, `Theta13`, `Theta23`, `deltaCP`
  - `dm21`, `dm3l`
  - `m1`, `m2`, `m3`, `sum_m`
  - `eta1`, `eta2`, `scale`, `mbeta`, `mbetabeta`
- LFV observables:
  - `mu_to_e_gamma`, `tau_to_e_gamma`, `tau_to_mu_gamma`
  - `mu_to_eee`, `tau_to_eee`, `tau_to_mumumu`
- Higgs observables:
  - `HiggsMass`
  - `HiggsRgg`
- Electroweak observables:
  - `ObliqueS`
  - `ObliqueT`
- Scalar-sector helper outputs and perturbative-unitarity matrices.
- Theory checks:
  - positivity and non-tachyon checks
  - derived-mass validity checks
  - quartic/vacuum-style bounds
  - analytic DM identity check
  - perturbative unitarity bounds from the six scattering matrices
  - finite-sector checks
- Likelihoods:
  - oscillation table likelihoods for `Theta12`, `Theta13`, `Theta23`, `deltaCP`, `dm21`, `dm3l`
  - `sum_m` hard cut
  - Higgs mass Gaussian
  - `HiggsRgg` Gaussian
  - LFV hard cuts
  - correlated `S,T` Gaussian
- Oscillation tables copied into the modular model tree and actively loaded relative to the model fragments.

### Implemented But Only Partially Validated

- Full normal-ordering migration as a whole: validated by tests and scan smoke checks, but not yet benchmarked against a large reference sample from `/Users/mbelfkir/Downloads/oneloop-master2/output/output.rank0.csv`.
- Inverted-ordering table assets: copied into the repository, but not yet wrapped in a dedicated validated inverted-ordering model manifest and example workflow.

### Implemented Approximately / Placeholder-Backed

- DM candidate identity:
  - current implementation uses the analytic theory check `Mpsi < MN, Mphi, MA1, MA2, MH1, MH2`
  - this is a deliberate approximation to the original micrOMEGAs-driven `sortOddParticles` plus `DMtarget` name check
  - it is useful as a guardrail, but it is not exact backend parity

### Intentionally Deferred

- Dark-matter observables and constraints from the original workflow:
  - `Omega`
  - direct-detection likelihood / p-value
  - `darkMatter`
  - `SIxsec`

This deferred classification applies to the frozen baseline model under
`/Users/mbelfkir/HEP/BSMScanner/models/oneloop`.

### Blocked By External Backend / Toolchain Dependency

- Exact micrOMEGAs parity for relic density and direct detection.

## Dark Matter / Backend-Dependent Pieces

This remains the highest-priority deferred area for the frozen baseline model.

### Implemented And Validated

- Analytic DM identity theory check through `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/constraints/theory_checks.yaml`.
- Explicit model metadata tag `micromegas_pending` in `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/model.yaml`.
- Explicitly empty DM observable file `/Users/mbelfkir/HEP/BSMScanner/models/oneloop/observables/dm.yaml`, with comments documenting the deferral.
- Separate exact-path model variant:
  - `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml`
- Optional native micrOMEGAs wrapper:
  - `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_micromegas.cpp`
- Generic plugin dispatch for backend-backed observables:
  - `/Users/mbelfkir/HEP/BSMScanner/include/bsm/core/plugins.hpp`
- Server-validated optional backend support for:
  - `Omega`
  - `SIxsec`
  - `DD_pvalue`
  - exact `~chi` target matching

### Implemented But Only Partially Validated

- Exact DM functionality in `models/oneloop_master`:
  - validated by build/test coverage and one-point backend smoke checks
  - not yet accompanied by a known robust production scan configuration with a high valid-point rate

### Implemented Approximately / Placeholder-Backed

- DM candidate identification is approximate:
  - implemented as an analytic mass-ordering theory check
  - not implemented through micrOMEGAs particle sorting or backend-selected candidate naming

### Intentionally Deferred

- Relic density observable `Omega`.
- Relic-density likelihood term analogous to the original `addRelicDensity()`.
- Direct-detection p-value term analogous to the original `addDDExp()`.
- Direct-detection observable `SIxsec`.
- Output of the backend-selected DM particle name.
- Any production use of DM likelihood terms in scans.

These items remain intentionally deferred only in the frozen baseline model.

### Blocked By External Backend / Toolchain Dependency

- None for the optional `models/oneloop_master` path on environments where the
  micrOMEGAs model tree is installed and linked.

## Known Historical Caveats

### Fixed Bug: In-Range Table Lookup Returned Zero

Historical bug:

- Before the April 9, 2026 fix in `/Users/mbelfkir/HEP/BSMScanner/src/constraints.cpp`, the `table_lookup` likelihood path returned zero for all points inside the table x-range.

Correct behavior now:

- inside table domain: return the interpolated table value
- outside table domain: apply the configured quadratic out-of-range penalty with optional cap

Affected results:

- any scan using `table_lookup` terms before the fix
- known obsolete oscillation-only run: `/home/mohamed/HEP/BSMScanner/examples/oneloop_full/runs/diver_oscillation_only_2026-04-09`
- earlier local and server runs using the old `table_lookup` implementation

Superseding corrected run:

- `/home/mohamed/HEP/BSMScanner/examples/oneloop_full/runs/diver_oscillation_only_fixed_2026-04-09`

Required policy:

- do not use pre-fix `table_lookup` scan outputs in future analyses or papers
- rerun any affected scan with the corrected code state
