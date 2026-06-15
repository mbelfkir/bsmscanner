# Latest-Master Oneloop YAML Variants

The repository now tracks the latest
`/Users/mbelfkir/Downloads/oneloop-master-3.zip` source through explicit YAML
model variants under:

- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model_normal_reduced.yaml`
- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model_normal_full.yaml`
- `/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model_inverted_full.yaml`

The compatibility manifest
`/Users/mbelfkir/HEP/BSMScanner/models/oneloop_master/model.yaml` points to the
reduced normal-ordering variant.

## Source Reconciliation

The latest `nLLConstructor.cxx` is the source of truth for the live physics
content. That means the YAML now treats the following as derived or fixed,
rather than free scan parameters, even though some legacy config files still
list them:

- `MA2`
- `sa`
- `lambda1`

The reason is straightforward:

- `MA2` is obtained from `MA02()`
- `sa` is obtained from `SA2()`
- `lambda1` is fixed by `Lambda1() = m_h^2 / (2 v^2)` with `m_h = 125.09 GeV`

The following are not derived quantities. They are simply absent because the
active latest-source evaluation no longer uses them:

- `Rep`
- `Imgp`

As a result, the live free-parameter set is the same 26-parameter set across
all latest-source variants; only the ranges, ordering, and likelihood settings
change between variants.

## Migration Direction

`oneloop_master` remains the canonical production one-loop model, so migration
to the newer core/model split is intentionally conservative.

Safe alignment already in place:

- ordering-dependent best-fit oscillation constants now come from the shared
  core neutrino constants
- the neutrino mass matrix now carries generic matrix metadata
  (`type: majorana_mass`, `role: neutrino`, `diagonalize: true`)

Still intentionally model-local for now:

- the existing one-loop neutrino observable YAML blocks
- one-loop likelihood blocks and table choices
- micrOMEGAs-backed DM plugin calls
- the grouped `m12+m3l` source-specific likelihood helper

This keeps the model aligned with the new framework direction without taking a
risky full neutrino-sector rewrite in one pass.

## Variants

### `model_normal_reduced.yaml`

This is the source-faithful `config_nr.yaml` style variant:

- normal ordering
- exact micrOMEGAs-backed DM observables
- reduced 26-parameter scan
- signed `k1`, `k4`, and Yukawa components

One legacy config issue is corrected here on purpose: signed scan ranges cannot
use a log prior, so those parameters use flat priors in YAML.

### `model_normal_full.yaml`

This matches the broad normal-ordering scan intent of `config.yaml`, but with
the stale free parameters removed in favor of the latest source formulas.

### `model_inverted_full.yaml`

This matches the broad inverted-ordering scan intent of `config_inv.yaml`, with
the ordering-dependent neutrino projection, `dm3l` convention, tables, and
`mbeta` / `mbetabeta` formulas implemented directly in YAML.

## Likelihood Structure

The YAML now reproduces the current `GetnLL()` decomposition exactly enough to
serve as the canonical production definition:

- one table term each for `Theta12`, `Theta13`, `Theta23`, and `deltaCP`
- one grouped `m12+m3l` term with the same source-style early-return behavior
- `sumOfMass`
- `massPinalety`
- `HiggsRgg`
- `KPinaleties`
- `EVPinaleties`
- `BRPinaleties`
- `Oblique`
- `Omega`
- `DDexp`

`addLambdaPenalty()` remains disabled because it is commented out in the latest
source `GetnLL()`.

The developer-facing canonical summary now lives in:

- [oneloop_master_canonical.md](/Users/mbelfkir/HEP/BSMScanner/docs/oneloop_master_canonical.md)

## DM / Backend Wiring

The micrOMEGAs-backed DM observables stay in YAML through generic `plugin_call`
nodes:

- `Omega`
- `SIxsec`
- `xsecSI`
- `DD_pvalue`
- `DMCandidateMass`
- `darkMatter`
- `DM_target_match`
- `DM_candidate_valid`

The imperative backend interaction still lives only in the dedicated plugin
source:

- `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_micromegas.cpp`

The one source-specific likelihood behavior that still cannot be expressed as a
plain declarative kernel also lives in plugin code:

- `/Users/mbelfkir/HEP/BSMScanner/src/plugins/oneloop_likelihoods.cpp`

The binding map comes from YAML, so changing backend assignment names still does
not require edits to the generic framework core.

## Running The Examples

Default reduced-normal example:

```bash
python /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/run_example.py
```

Alternate manifests can be passed directly to the scan launcher:

```bash
python /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/run_scan.py \
  --model /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/model_normal_full.yaml \
  --run-dir /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/runs/normal_full
```

```bash
python /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/run_scan.py \
  --model /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/model_inverted_full.yaml \
  --run-dir /Users/mbelfkir/HEP/BSMScanner/examples/oneloop_master/runs/inverted_full
```

## Build Requirement

These variants require the optional micrOMEGAs-backed native build for exact DM
evaluation. The plugin-local build logic lives in:

- `/Users/mbelfkir/HEP/BSMScanner/cmake/plugins/oneloop_micromegas.cmake`

Local build example:

```bash
CMAKE_ARGS="-DBSM_SCANNER_BUILD_ONELOOP_MICROMEGAS=ON \
            -DBSM_SCANNER_MICROMEGAS_ROOT=/path/to/micromegas \
            -DBSM_SCANNER_MICROMEGAS_MODEL_ROOT=/path/to/1LRNM-1N1P-New \
            -DBSM_SCANNER_MICROMEGAS_CALCHEP_ROOT=/path/to/CalcHEP_src" \
python -m pip install -e '.[dev]'
```
