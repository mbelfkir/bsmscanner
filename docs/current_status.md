# Current Status

## Milestone State

As of April 19, 2026, this repository contains the canonical production
implementation of the latest one-loop model inside the `BSMScanner` framework.

Working baseline:

- Python model loading, schema validation, modular imports, graph compilation, and lowering
- C++ compiled point evaluation
- generic plugin dispatch for backend-backed observables
- matrix metadata with automatic diagonalization support for declared reusable sectors
- native scan execution
- Diver integration on `mohamed@belfkir-server`
- a temporary SciPy-backed `de_scipy` reference engine for DE-interface validation
- a native model-agnostic `adaptive_diver` Differential Evolution engine with
  adaptive `F/CR`, final-population artifacts, and optional elite local
  refinement
- a model-agnostic `basin_scan` orchestration engine that performs broad
  exploration, clusters promising points, constructs focused sub-boxes, and
  launches `adaptive_diver` inside each basin, with an opt-in progressive
  exploration mode for staged basin discovery in very broad boxes
- an additive machine-readable statistics layer for completed scan outputs
- explicit scan-record validity tracking that separates technical evaluation
  `status` from physics/model `valid`
- generic flavor-sector diagonalization and mixing-matrix construction
  (`takagi`, `svd`, `hermitian_eigh`, PMNS/CKM-style mismatch matrices)
- reusable CKM scalar observables under `core/quark/ckm_observables.yaml`
- reusable quark mass-ratio observables under `core/quark/quark_mass_ratios.yaml`
- machine-readable outputs
- modular full oneloop model under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop`
- active oscillation table likelihoods with the corrected `table_lookup` behavior
- canonical latest-master-faithful model under `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master`
- optional exact micrOMEGAs-backed oneloop DM backend on builds where it is enabled
- reusable core-level neutrino YAML blocks prototyped through `models/leptontest`

Main declared limitation:

- the frozen milestone baseline model under `models/oneloop` still defers exact DM parity
- exact DM parity is available through the canonical `models/oneloop_master` variant and the optional micrOMEGAs build

## Trustworthy Scientific Scope

The framework organization now supports a cleaner split for future models:

- the core may provide reusable declarative YAML for genuinely
  model-independent calculations
- models still own likelihood terms, datasets, and scan composition

The current proof of concept is the leptontest neutrino sector, where shared
constants and ordering-aware neutrino observable logic live under
`/Users/mbelfkir/HEP/BSMScanner/core`, while the model keeps its own likelihood
blocks under `/Users/mbelfkir/HEP/BSMScanner/models/leptontest/constraints`.

The canonical reference example for this split is now:

- `/Users/mbelfkir/HEP/BSMScanner/examples/leptontest`
- `/Users/mbelfkir/HEP/BSMScanner/models/leptontest`

The minimal reference example for generic flavor diagonalization is:

- `/Users/mbelfkir/HEP/BSMScanner/models/flavor_toy`
- `/Users/mbelfkir/HEP/BSMScanner/examples/flavor_toy`

The full lepton+quark reference example is:

- `/Users/mbelfkir/HEP/BSMScanner/models/leptonquarktest`
- `/Users/mbelfkir/HEP/BSMScanner/examples/leptonquarktest`

It follows the FlavorPy detailed modular-flavor example for its parameters and
analytic mass matrices, demonstrating a complete optional-sector model with
`Mnu`, `Ml`, `Mu`, and `Md`, while keeping PMNS/neutrino and CKM/quark
observable formulas in reusable core YAML blocks rather than in the model
manifest.

The current milestone is suitable for scans that rely on the following implemented sectors:

- oscillation observables and oscillation table likelihoods
- neutrino mass outputs such as `m1`, `m2`, `m3`, `sum_m`, `mbeta`, `mbetabeta`
- CKM scalar outputs such as `Vus`, `Vcb`, `Vub`, `deltaCKM`, `J_CKM`,
  and prefixed Wolfenstein parameters when the CKM core block is imported
- quark mass-ratio outputs such as `mu_over_mc`, `mc_over_mt`, `md_over_ms`,
  and `ms_over_mb` when the quark mass-ratio core block is imported
- LFV observables
- `HiggsMass`
- `HiggsRgg`
- electroweak oblique parameters `S` and `T`
- analytic theory checks and perturbative-unitarity checks already encoded in the model
- likelihood-weighted DE-style post-processing summaries when `statistics.enabled: true`

Statistics summaries are validity-aware: new `points.csv` files include a real
`valid` column, invalid physics points can remain in sample CSVs for debugging
with zero weight, and weighted summaries use only `valid == true` rows.

The frozen milestone model under `models/oneloop` is not suitable for claiming exact parity with the original micrOMEGAs-backed DM workflow.

The separate `models/oneloop_master` variant is now the canonical exact-path
option for that workflow, provided the native build includes the micrOMEGAs
backend. That exact path runs through the generic plugin layer rather than
through oneloop-specific core builtins.

## Recommended Production Configuration

Use:

- canonical one-loop production manifest:
  `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml`
- exact normal or inverted variants when needed:
  `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model_normal_full.yaml`
  `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model_inverted_full.yaml`
- the frozen `models/oneloop` baseline only when you explicitly want the older
  milestone reference without exact DM parity

For publication-oriented one-loop scans at this milestone:

- use the canonical `models/oneloop_master` manifests
- include oscillation, Higgs, LFV, electroweak, and DM terms as appropriate for
  the selected variant and enabled backend build
- cite the plugin-backed DM sector explicitly when exact relic-density or direct
  detection parity matters

## What Is Deferred

Deferred items for the canonical one-loop production model are now small:

- only the backend-specific micrOMEGAs bridge and the source-specific grouped
  `m12+m3l` helper remain outside plain declarative YAML

Deferred items are concentrated in the older frozen baseline model:

- relic density `Omega`
- direct-detection observable(s) and p-value logic
- exact backend-selected DM particle identity and naming
- micrOMEGAs-backed nucleon cross section

Those items remain deferred only for the frozen baseline model. They are implemented in the optional latest-master variant.

See:

- `/Users/mbelfkir/HEP/BSMScanner/docs/dm_status.md`
- `/Users/mbelfkir/HEP/BSMScanner/docs/implemented_vs_deferred.md`

## Historical Caveat

Before the April 9, 2026 fix in `/Users/mbelfkir/HEP/BSMScanner/src/constraints.cpp`, `table_lookup` likelihoods returned zero for any point inside the table domain instead of using the interpolated table value.

Consequences:

- any scan produced before that fix and using `table_lookup` constraints is obsolete
- previous oscillation-only results with apparent `nLL = 0` minima should not be used

Corrected runs supersede those earlier scans. See:

- `/Users/mbelfkir/HEP/BSMScanner/docs/release_notes_oneloop.md`

## Validation Basis

The milestone state is supported by:

- the local automated test suite
- full-model load and compile checks
- one-point evaluation checks
- smoke-scan checks
- corrected Diver reruns on the server after the `table_lookup` fix
