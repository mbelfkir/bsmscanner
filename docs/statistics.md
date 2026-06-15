# Statistics Output Layer

## Scope

The statistics layer is an additive post-processing step over completed scan
artifacts.

It is intentionally separate from the scan engines:

`engine -> raw scan/statistical outputs -> external plotting scripts or notebooks`

The engine does not generate plots. The statistics layer does not generate
plots. Both only write machine-readable outputs.

## Current Method

The first supported method is:

- `de_weighted`

This method treats the saved scan points as evaluated DE-style points and
computes likelihood-style weights from the chi2-like scan objective.

It is not yet a true posterior sampler.

## Weight Definition

For each physics-valid point:

- `chi2 = metric_value`
- `chi2_min = min(valid chi2)`
- `delta_chi2 = chi2 - chi2_min`
- `loglike = -0.5 * chi2`
- `shifted_loglike = -0.5 * delta_chi2`

The normalized weight is then:

```text
w_i = exp(-0.5 * (chi2_i - chi2_min)) / sum_j exp(-0.5 * (chi2_j - chi2_min))
```

The shift by `chi2_min` is required for numerical stability and avoids
underflow from very large chi2 values.

## Validity Semantics

Scan outputs distinguish two concepts:

- `status`
  - technical evaluation status: whether the evaluator callback ran normally
- `valid`
  - physics/model validity: whether the point passed bounds, theory checks,
    finite-output checks, backend/plugin calls, and likelihood-input checks

`status == ok, valid == false` is a normal diagnostic state. It means the
framework evaluated the point, but the model rejected it physically and the
scanner received the configured invalid penalty.

Large finite chi2 values are not automatically invalid. A point is excluded
from statistics only when `valid == false` or when the point cannot provide a
finite chi2-like value.

For new scan outputs, `de_weighted` uses the `valid` column from `points.csv`.
For old outputs without a `valid` column, it falls back to `status == ok` for
backward compatibility and writes a diagnostics warning:

```text
valid column missing; inferred validity from status == ok for backward compatibility
```

## Configuration

Models may declare:

```yaml
statistics:
  enabled: true
  method: de_weighted
  credible_levels: [0.68, 0.95]
  output_samples: true
  include_observables: true
```

If the block is absent or `enabled: false`, scan behavior is unchanged.

## Files Written

When enabled, the scan output directory gains:

```text
statistics/
  de_weighted_samples.csv
  de_weighted_summary.json
  de_credible_intervals.json
  diagnostics.json
```

These are plot-ready inputs for later external analysis such as:

- corner plots
- weighted 1D parameter summaries
- likelihood-profile overlays
- parameter-correlation studies

## Notes

- `de_weighted` currently uses the saved `metric_value` column as the chi2-like
  quantity.
- Invalid points are retained in `de_weighted_samples.csv` for debugging, but
  they receive zero statistical weight and do not contribute to `chi2_min`,
  weighted summaries, credible intervals, or effective sample size.
- `diagnostics.json` records `validity_source`, currently either
  `valid_column` or `status_fallback`.
- Future method names are reserved for:
  - `de_mcmc`
  - `profile_likelihood`
  - `nested_sampling`
