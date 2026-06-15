# `basin_scan`

`basin_scan` is a model-agnostic orchestration engine for scans where the
interesting region occupies a tiny fraction of the original prior volume. It is
not a new physics model and it is not a replacement for `adaptive_diver`.
Instead, it performs broad exploration, optional proposal-assisted sampling,
likelihood-aware selection, optional local seed refinement, focused-box
construction, and independent `adaptive_diver` scans inside those boxes.

The engine only sees scanned parameter names, bounds, scalar objective values,
validity flags, failure reasons, and scan settings. It contains no neutrino,
quark, CKM, PMNS, micrOMEGAs, one-loop, or FlavorPy-specific logic.

## Workflow

1. Sample the full parameter box with Latin-hypercube, Sobol, or uniform random
   points.
2. Optionally apply YAML-configured proposal transforms.
3. Evaluate exploration points through the standard evaluator.
4. Optionally classify points with staged cheap/full diagnostics.
5. Select promising valid finite points by top fraction, chi2 window, or
   likelihood-term-balanced cuts.
6. Optionally add near-miss likelihood-term champions.
7. Optionally jitter/refine selected seeds before clustering.
8. Cluster selected points in normalized parameter coordinates.
9. Construct focused sub-boxes from cluster quantiles plus padding.
10. Clip focused boxes to the original parameter bounds.
11. Run `adaptive_diver` independently inside each focused box.
12. Re-evaluate focused best fits at the basin level, merge, and rank results.

## Progressive Exploration

`progressive_exploration` is an optional staged exploration mode. It is disabled
by default, so existing `basin_scan` configurations keep the original one-shot
exploration behavior unless this block is explicitly enabled.

When enabled, `basin_scan` replaces the single broad exploration pass with
multiple exploration rounds:

1. sample the original global bounds,
2. select promising valid finite points,
3. build loose exploration boxes from the selected cloud,
4. sample the next round inside those boxes,
5. repeat, then pass the final selected points to the usual clustering and
   focused `adaptive_diver` workflow.

This is a heuristic basin-discovery aid, not a guarantee of global convergence
and not a posterior sampler. It remains model-agnostic: it only uses parameter
bounds, objective values, validity flags, and scan settings.

## Likelihood-Term-Aware Selection

If the evaluator provides named likelihood components, point artifacts include
generic `like__<term_name>` columns. The legacy `likelihood::<term_name>`
columns in `points.csv` are still written for compatibility.

`selection.mode: balanced_terms` uses these model-defined components without
knowing what they mean physically. It first keeps a broad top slice by total
objective, then requires the point to be non-catastrophic in every selected
likelihood term. This helps avoid fake valleys where the total objective looks
acceptable only because one term is good while another term is very poor.

Automatic term discovery:

```yaml
selection:
  mode: balanced_terms
  total_top_fraction: 0.10
  term_quantile_cut: 0.30
  max_points: 3000
  min_points: 100
  terms: auto
  fallback_mode: top_fraction
```

Explicit term selection:

```yaml
selection:
  mode: balanced_terms
  total_top_fraction: 0.10
  term_quantile_cut: 0.30
  terms:
    - theta12
    - theta13
    - dm21
    - dm31
  exclude_terms:
    - penalty
```

Term names may be given either as raw model likelihood names or as full
`like__...` column names. If no likelihood-term columns are available,
`balanced_terms` falls back to the configured `fallback_mode` and records the
fallback in `selection_summary.json`.

### Near-Miss Selection

`selection.near_miss` can keep additional useful points that are not globally
best by total objective but are excellent in at least one likelihood component.
This is generic: the engine only sees named likelihood terms.

```yaml
selection:
  mode: balanced_terms
  total_top_fraction: 0.10
  term_quantile_cut: 0.50
  top_fraction: 0.10
  max_points: 3000
  min_points: 1
  terms: auto

  near_miss:
    enabled: true
    max_hard_failures: 0
    max_fit_failures: 3
    objective_cap: 1.0e6
    include_full_eval_points: true
```

## Proposal-Assisted Sampling

`proposals` is disabled by default. When enabled, proposal stages transform
sampled parameter vectors before evaluation and then clip them to the declared
scan bounds. The proposal layer is generic and knows only parameter names.

Supported first-version proposal types:

- `prior_profile`: resample named parameters from Gaussian approximations or
  discrete value/weight lists.
- `complex_vector_norm`: sample listed real/imaginary components as a vector
  with a chosen norm and random direction.
- `parameter_rescale`: multiply a group of parameters by a sampled factor.

Example:

```yaml
proposals:
  enabled: true
  stages:
    - name: targeted_prior
      type: prior_profile
      probability: 0.50
      parameters:
        - name: x
          mean: 3.0
          sigma: 0.1

    - name: balanced_complex_vector
      type: complex_vector_norm
      probability: 0.25
      vectors:
        - components:
            real: [yr1, yr2, yr3]
            imag: [yi1, yi2, yi3]
          norm_range: [1.0e-5, 3.0]
          scale: log

    - name: multiplicative_scale
      type: parameter_rescale
      probability: 0.10
      parameters: [y1, y2]
      factor_range: [0.5, 2.0]
      scale: log
```

## Staged Evaluation

`staged_evaluation` is disabled by default. When enabled, `basin_scan` builds a
reduced cheap-stage graph from the same model by filtering likelihood terms,
theory checks, and output roots by name. It evaluates this cheap graph first and
only evaluates the full graph for points that pass the configured cheap-objective
threshold and hard-failure policy. This is the intended way to avoid expensive
backend calls, such as micrOMEGAs, for points that already fail analytic or
lightweight constraints.

The feature remains model-agnostic: the engine only sees named likelihood terms,
theory checks, and outputs declared by YAML. If no cheap graph is built, the
older compatibility path still classifies already evaluated points into cheap
and full categories for diagnostics.

```yaml
staged_evaluation:
  enabled: true
  cheap_stage:
    include_terms: [neutrino, quark, lfv]
    exclude_terms: [relic_density, direct_detection]
    exclude_theory_checks: [dark_matter_backend_valid]
    exclude_outputs: [Omega, sigma_si]
  expensive_stage:
    include_terms: [relic_density, direct_detection]
  full_eval_policy:
    max_cheap_objective: 1.0e5
    require_no_hard_failures: true
```

Point artifacts then include:

- `objective_cheap`
- `objective_full`
- `stage_reached`
- `hard_failures`
- `fit_failures`
- `terms_evaluated`

## Seed Refinement

`refinement` is an optional local sampling pass before clustering. It jitters
selected seeds inside the original bounds, optionally reapplies proposal hooks,
evaluates the new points through the same evaluator, then reruns selection on
the combined pool.

```yaml
refinement:
  enabled: true
  n_rounds: 2
  points_per_seed: 20
  max_seeds: 50
  jitter_fraction: 0.08
  apply_proposals: true
  keep_near_miss: true
```

## Manifold Refocus

`manifold_refocus` is an optional, model-agnostic refocusing stage. It is
disabled by default. When enabled, it runs after selection/clustering has found
useful points and before `ml_focus` or the focused optimizer. It learns a simple
covariance cloud in prior-aware transformed parameter coordinates, samples that
cloud, and converts the sampled cloud into a smaller physical focused box.

This is intended for thin correlated basins where ordinary axis-aligned
quantile boxes leave too many directions at their original widths. It does not
know any physics names and does not replace the evaluator: it only proposes a
smaller box for the next scan stage.

```yaml
manifold_refocus:
  enabled: true
  method: covariance
  seed: 12345
  source: selected_plus_exploration
  max_train_points: 8000
  min_train_points: 100
  top_fraction_for_training: 0.15

  sampling:
    n_candidates: 250000
    inflate: 1.25
    diagonal_jitter: 1.0e-6
    include_training_points: true

  box:
    enabled: true
    quantile_low: 0.01
    quantile_high: 0.99
    padding_fraction: 0.35
    min_width_fraction: 0.01
    max_shrink_factor: 100.0
    clip_to_original_bounds: true
```

Available sources are:

- `selected`: train only on the final selected points.
- `exploration`: train on all valid finite exploration points, ranked by objective.
- `selected_plus_exploration`: combine both pools, ranked by objective.

When enabled, diagnostics are written to:

- `manifold_refocus_training.csv`
- `manifold_refocus_candidates.csv`
- `manifold_refocus_box.json`
- `manifold_refocus_diagnostics.json`

The resulting manifold box feeds the normal focused `adaptive_diver` path. If
`ml_focus.enabled: true`, the ML stage receives the manifold box as its input
box and may shrink/refine it further.

## ML Focus

`ml_focus` is an optional stage inside `basin_scan`. It is disabled by default.
When enabled, it runs after exploration/progressive exploration and before the
focused `adaptive_diver` runs. It does not replace the physics evaluator, and
ML-predicted points are never accepted as final scan results unless they are
later evaluated by the real model.

The first implementation is deliberately simple:

1. keep valid finite exploration points,
2. train an `ExtraTreesRegressor` on transformed parameter coordinates,
3. predict `log10(1 + objective)` for generated candidate points,
4. select the best ML-scored candidates,
5. build one conservative focused box in physical parameter space,
6. generate seed points for `adaptive_diver`,
7. let the real evaluator decide the final objective.

This stage requires `scikit-learn` only when `ml_focus.enabled: true`. Existing
`basin_scan` configurations do not import sklearn and behave as before.

```yaml
ml_focus:
  enabled: true
  seed: 12345

  model:
    type: extra_trees_regressor
    n_estimators: 300
    min_samples_leaf: 3
    max_features: sqrt

  training:
    max_train_points: 50000
    min_train_points: 100
    require_valid: true
    finite_objective_only: true
    target_transform: log10_1p

  candidate_generation:
    n_candidates: 100000
    sources:
      selected_box_fraction: 0.50
      elite_local_fraction: 0.30
      global_fraction: 0.20

  selection:
    n_ml_selected: 5000
    include_best_real_points: true
    n_best_real_points: 500
    include_elite_archive: true

  focused_box:
    enabled: true
    quantile_low: 0.02
    quantile_high: 0.98
    padding_fraction: 1.0
    min_width_fraction: 0.05
    max_shrink_factor: 50.0
    clip_to_original_bounds: true

  seeds:
    enabled: true
    max_seeds: 1000
    composition:
      best_real_fraction: 0.40
      ml_selected_fraction: 0.40
      local_mutation_fraction: 0.20
    local_mutation:
      relative_sigma: 0.05
      log_sigma: 0.25
```

Parameter features are prior-aware: flat parameters are normalized linearly,
log-prior parameters are normalized in log space, and signed-log parameters use
a stable signed logarithmic transform. Focused boxes and seeds are written in
physical parameter coordinates.

When enabled, diagnostics are written to:

- `ml_focus_training.csv`
- `ml_focus_candidates.csv`
- `ml_focus_selected.csv`
- `ml_focus_box.json`
- `ml_focus_seeds.csv`
- `ml_focus_diagnostics.json`

The diagnostics include training size, candidate counts, best training
objective, best predicted candidate score, original/focused widths, shrink
factors, and ExtraTrees feature importances. These are debugging aids, not
posterior probabilities.

## YAML Example

```yaml
scan:
  engine: basin_scan
  seed: 12345
  save_every: 1
  settings:
    objective: nll
    invalid_penalty: 1.0e12
    save_invalid_points: true
    verbose: 1
    progress_interval: 1000

  basin_scan:
    exploration:
      method: latin_hypercube
      n_points: 50000
      keep_fraction: 0.02

    selection:
      mode: top_fraction
      top_fraction: 0.02
      max_points: 2000
      near_miss:
        enabled: false

    clustering:
      method: dbscan
      enabled: true
      eps_fraction: 0.08
      min_samples: 10
      max_clusters: 8

    boxes:
      construction: quantile
      q_low: 0.05
      q_high: 0.95
      padding_fraction: 0.25
      min_width_fraction: 0.02
      clip_to_original_bounds: true
      merge_overlapping: false
      max_boxes: 0

    progressive_exploration:
      enabled: false

    proposals:
      enabled: false

    staged_evaluation:
      enabled: false

    refinement:
      enabled: false

    ml_focus:
      enabled: false

    focused_engine:
      name: adaptive_diver
      population_size: 60
      max_generations: 1500
      p_best_fraction: 0.1
      local_refinement:
        enabled: true
        method: Powell
        n_elites: 10

    output:
      save_exploration_points: true
      save_clusters: true
      save_focused_boxes: true
```

Progressive example:

```yaml
scan:
  engine: basin_scan

  basin_scan:
    progressive_exploration:
      enabled: true
      n_rounds: 3
      points_per_round: [100000, 60000, 60000]
      combine_with_previous_selected: true

      selection:
        mode: balanced_terms
        total_top_fraction: 0.10
        term_quantile_cut: 0.30
        top_fraction: 0.01
        max_points: 2000
        min_points: 100
        terms: auto
        fallback_mode: top_fraction

      elite_preservation:
        enabled: true
        always_keep_global_best: true
        archive_size: 500
        elite_fraction: 0.05
        min_elite_points: 20
        max_elite_points: 200

      elite_boxes:
        enabled: true
        construction: quantile
        q_low: 0.05
        q_high: 0.95
        padding_fraction: 0.30
        min_width_fraction: 0.01
        max_boxes: 4

      best_centered_box:
        enabled: true
        width_fraction: 0.15
        shrink_per_round: 0.7
        min_width_fraction: 0.005

      boxes:
        construction: quantile
        q_low: 0.02
        q_high: 0.98
        padding_fraction: 0.50
        min_width_fraction: 0.03
        clip_to_original_bounds: true
        merge_overlapping: true
        max_boxes: 8

      sampling:
        method: latin_hypercube
        allocate_points: mixed
        fractions:
          elite_boxes: 0.50
          selected_boxes: 0.30
          global: 0.20
        min_points_per_box: 5000

      output:
        save_round_points: true
        save_round_selected: true
        save_round_boxes: true
```

## Outputs

In addition to standard scan artifacts, `basin_scan` writes:

- `exploration_points.csv`
  - broad exploration evaluations and validity information
- `selected_points.csv`
  - selected promising points before clustering
- `clusters.csv`
  - selected points with assigned cluster ids
- `focused_boxes.json`
  - focused boxes and best-fit boundary-fraction diagnostics
- `basin_results.json`
  - ranked focused adaptive-diver results
- `selection_summary.json`
  - selection mode, finite candidate count, selected count, likelihood terms
    used, term thresholds, relaxation attempts, and fallback status
- `proposal_summary.json`
  - proposal stages used and application counts
- `staged_evaluation_summary.json`
  - cheap/full classification diagnostics when enabled
- `refinement_points.csv` and `refinement_summary.json`
  - written when `refinement.enabled: true`
- `ml_focus_training.csv`, `ml_focus_candidates.csv`,
  `ml_focus_selected.csv`, `ml_focus_box.json`, `ml_focus_seeds.csv`, and
  `ml_focus_diagnostics.json`
  - written when `ml_focus.enabled: true`
- `basin_00/`, `basin_01/`, ...
  - full artifacts from each focused `adaptive_diver` run

When progressive exploration is enabled, `basin_scan` also writes:

- `progressive_exploration_summary.json`
  - per-round evaluation counts, valid counts, best objective/chi2, selected
    counts, box counts, and relative box volumes
- `progressive_exploration/round_XX_points.csv`
  - raw points from each progressive exploration round
- `progressive_exploration/round_XX_selected.csv`
  - selected pool after each round
- `progressive_exploration/round_XX_selection_summary.json`
  - per-round selection diagnostics, including balanced-term thresholds when
    `selection.mode: balanced_terms` is used
- `progressive_exploration/round_XX_boxes.json`
  - loose exploration boxes used to sample the next round

For compatibility, top-level `exploration_points.csv` contains all progressive
exploration points when progressive mode is enabled, with `round_id` and
`source_type`/`box_id` columns. `source_type` records whether the point came
from global sampling, selected-cloud boxes, elite boxes, or a best-centered
box. Top-level `selected_points.csv` contains the final selected set passed
into the normal clustering stage.

Progressive mode keeps an elite archive of the best valid finite points seen
across rounds. If `elite_preservation.always_keep_global_best` is true, the
global best point is retained for later selection/box construction even when a
later round samples a worse region. Round summaries record both the best point
inside that round and the monotonic global best after that round.

Each focused best fit includes fractional positions inside its focused box:

```text
fractional_position = (x - lower) / (upper - lower)
```

Values close to `0` or `1` indicate the focused box may still be cutting off
the basin and should be widened.

## Interpretation

`basin_scan` is useful when a single global DE run spends most of its budget
searching empty prior volume. It improves scan orchestration, not the physics
objective. Its results should still be validated with follow-up focused scans,
larger budgets, and model-specific scientific checks.
