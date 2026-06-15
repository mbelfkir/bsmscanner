# Guided Sampling

`guided_sampling` is an optional, model-agnostic layer that modifies sampled
parameter points before they are evaluated. It is useful when a model has a
tiny viable region and pure uniform sampling rarely reaches useful points.

Guided sampling does not contain physics logic in the framework core. The user
declares proposal stages in YAML, and optional model-specific logic can live in
a normal Python function that takes a point dictionary and returns a modified
point dictionary.

## Placement

Guided sampling can be placed in its own imported YAML file:

```yaml
imports:
  - guided_sampling.yaml
```

with:

```yaml
guided_sampling:
  enabled: true
  apply_to: [exploration, progressive_exploration, refinement]

  stages:
    - name: balanced_yukawas
      type: complex_vector_norm
      probability: 0.5
      vectors:
        - components:
            real: [yr1, yr2, yr3]
            imag: [yi1, yi2, yi3]
          norm_range: [1.0e-5, 1.0]
          scale: log
```

For `basin_scan`, this block is merged into the existing proposal layer. If
`guided_sampling.enabled` is false or absent, behavior is unchanged.

## Built-In Proposal Types

### `prior_profile`

Draw selected parameters from simple Gaussian or discrete weighted profiles.

```yaml
- name: target_s12_region
  type: prior_profile
  probability: 0.3
  parameters:
    - name: x
      mean: 0.5
      sigma: 0.05
```

### `complex_vector_norm`

Samples complex vectors with a chosen total norm and random complex direction.
This is useful for generic Yukawa-like vectors without hard-coding their names.

```yaml
- name: balanced_vectors
  type: complex_vector_norm
  probability: 0.75
  vectors:
    - components:
        real: [Y1r1, Y1r2, Y1r3]
        imag: [Y1i1, Y1i2, Y1i3]
      norm_range: [1.0e-6, 1.0]
      scale: log
```

The sampled values are clipped to the scan bounds before evaluation.

### `parameter_rescale`

Multiplies a list of parameters by a random factor.

```yaml
- name: mass_scale_probe
  type: parameter_rescale
  probability: 0.2
  parameters: [yprime]
  factor_range: [1.0e-2, 1.0e2]
  scale: log
```

### `point_function`

Calls user code to modify a sampled point. The function must return a mapping
of parameter names to new values, or `None` to leave the point unchanged.

```yaml
- name: construct_from_targets
  type: point_function
  probability: 0.3
  function: /absolute/path/to/my_guided_sampling.py:construct_point
  apply_to: [exploration, progressive_exploration]
  options:
    target_source: nufit_profile
```

The function may accept any subset of these keyword arguments:

```python
def construct_point(point, rng=None, options=None, context=None):
    point["x"] = 1.0
    return point
```

`context` includes the sampling stage, parameter names, bounds, and proposal
metadata. The framework does not interpret the physics meaning of the returned
values.

## Stages

Proposal stages can restrict where they apply:

```yaml
apply_to:
  - exploration
  - progressive_exploration
  - refinement
```

When omitted, the stage applies wherever the scan engine calls guided sampling.

## Oneloop Example

The oneloop model imports:

```yaml
imports:
  - guided_sampling.yaml
```

That file currently declares generic complex-vector norm proposals for the
`yn` and `Y1` vectors and a scale probe for `ypr11`/`ypi11`.

It also ships disabled model-local hook stages for the original one-loop
scanner proposal family:

- `physical_neutrino_targets_NO` / `physical_neutrino_targets_IO`: construct
  Yukawa entries from sampled neutrino targets.
- `neutrino_scale_sum_NO` / `neutrino_scale_sum_IO`: rescale `yprime` to a
  target neutrino mass-sum window.
- `chi_visible_si_corridor_NO` / `chi_visible_si_corridor_IO`: bias the chi-DM
  branch toward visible direct-detection and LFV-friendly corridors.
- `h01_scalar_dm_corridor`: bias the scalar-DM branch toward compressed and
  Higgs-funnel regions.

These stages are disabled in the shared file because the same file is imported
by normal/inverted and chi/H01 variants. Enable only the stages matching the
scan, and quote YAML hierarchy labels:

```yaml
guided_sampling:
  enabled: true
  stages:
    - name: physical_neutrino_targets_NO
      enabled: true
      options:
        hierarchy: "NO"
        target_dm: chi
```

Runtime failures inside a `point_function` are treated as proposal rejections
for that point and are counted in `proposal_summary.json`; missing functions or
invalid proposal configuration still raise validation errors.
