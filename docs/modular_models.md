# Modular Model Files

Large models can now be split across multiple YAML fragments instead of living in one large file.

## Top-Level Manifest

The top-level manifest is still a normal model YAML file, but it may now include other YAML fragments with `imports`:

```yaml
metadata:
  name: oneloop_full_normal
  version: 0.2.0

imports:
  - parameters.yaml
  - constants.yaml
  - functions.yaml
  - derived.yaml
  - matrices.yaml
  - diagonalizations.yaml
  - observables/neutrino.yaml
  - observables/higgs.yaml
  - observables/lfv.yaml
  - observables/ew.yaml
  - observables/scalar_sector.yaml
  - observables/dm.yaml
  - constraints/theory_checks.yaml
  - constraints/likelihoods.yaml
  - outputs.yaml
  - scan.yaml
```

`includes:` is accepted as an alias for `imports:`, but only one of them may be used in a fragment.

## Relative Path Rules

- imported YAML fragments are resolved relative to the file that declares them
- `table_file` inside a likelihood is also resolved relative to the fragment that contains it
- nested imports are supported

This means a fragment under `constraints/` should usually refer to tables with paths like `../data/...`, not `data/...`.

## Merge Rules

The loader merges fragments deterministically in the order listed in `imports`.

### List-like top-level sections

These sections concatenate:

- `parameters`
- `constants`
- `functions`
- `derived_scalars`
- `derived_complex`
- `matrices`
- `diagonalizations`
- `observables`
- `theory_checks`
- `likelihoods`

Named entries in those sections must be unique across the fully merged model. A duplicate raises a clear validation error with both fragment paths.

### Mapping-like sections

These sections merge by key:

- `metadata`
- `outputs`
- `scan`

Nested mappings such as `scan.settings` also merge by key.

If the same scalar key is defined twice with different values, loading fails with a conflict error. Identical repeated values are allowed.

### Output list

`outputs.save` concatenates, but duplicate output names raise an error.

## Recommended Layout

For large physics models, use a sector-aware structure like:

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

## Best Practices

- keep `metadata` in the top-level manifest
- keep one conceptual section per fragment when possible
- group observables by physics sector rather than by syntax
- keep theory checks and likelihoods in separate fragments
- keep external data under a model-local `data/` directory
- prefer fragment-relative `table_file` paths so files remain movable as a unit
- use the top-level manifest as the human entry point for the model

## Oneloop Example

The full migrated oneloop model now follows this pattern under:

- `models/oneloop/model.yaml`

The old example path remains available as a compatibility wrapper:

- `examples/oneloop_full/model.yaml`
