# Scan Engines and Basin-Scan Methodology in BSMScanner

## Abstract

BSMScanner separates physics-model definition from numerical exploration. A model
defines scanned parameters, fixed parameters, derived quantities, matrices,
theory checks, likelihood terms, and saved outputs. A scan engine receives the
compiled evaluator and a deterministic scanner vector, maps each vector component
to a named model parameter, evaluates the scalar objective, records validity
diagnostics, and writes reproducible artifacts. This manuscript documents all
currently implemented scan engines and gives a complete reference for the
`basin_scan` engine, including its rules, inputs, free parameters, outputs, and
techniques.

## 1. Common Scan Formalism

All engines operate on the same canonical problem. Let

```text
theta = (theta_1, ..., theta_D)
```

be the vector of scanned real-valued model parameters, in YAML declaration
order. Each scanned parameter has a name, lower and upper bounds, a prior
coordinate convention, and optionally a default value. Fixed parameters are
stored in metadata but are not passed to the scanner vector.

The compiled evaluator returns a structured point record containing a technical
status, a physics-validity flag, a failure reason, saved outputs, likelihood
terms, and `total_nll`. The scanner objective is selected by
`scan.settings.objective`:

- `nll`: minimize the evaluator's `total_nll`.
- `posterior_nll`: minimize `total_nll` plus declared parameter-prior
  contributions.

The scanner always minimizes `scanner_target`. If `maximize: true`, the target is
the negative of the metric. Invalid, failed, or non-finite evaluations are mapped
to `invalid_objective` / `invalid_penalty`, while diagnostics remain available in
the output files.

### 1.1 Common Inputs

Every engine receives:

- A compiled BSMScanner model plan and evaluator.
- The scanned-parameter list: names, contiguous indices, bounds, priors,
  defaults, and signed-log `min_abs` values where relevant.
- The fixed-parameter list.
- The objective mode, maximization flag, invalid-point penalty, random seed,
  save cadence, and verbosity.
- The list of selected outputs and likelihood-term names.
- A run directory in which all artifacts are written.

Scanned parameters must currently be real scalars. Log priors require strictly
positive lower bounds. Signed-log priors require bounds that straddle zero and a
positive `min_abs` smaller than the physical span.

### 1.2 Common Outputs

All scan runs write the standard artifact set:

- `points.csv`: saved evaluations, parameters, outputs, and likelihood terms.
- `metadata.json`: model identity, scan settings, parameter order, engine
  options, bounds, priors, and reproducibility metadata.
- `best_fit.json`: the best valid point found, if any.
- `summary.json`: evaluation counts, valid counts, best objective, interruption
  state, and failure counters.

Engines may also write specialized artifacts such as `history.json`,
`final_population.csv`, `exploration_points.csv`, `focused_boxes.json`, or
`basin_results.json`.

## 2. Implemented Engines

### 2.1 `serial_random`

`serial_random` is the simplest native engine. It draws independent random
points until `max_evaluations` is reached or the run is interrupted. It is most
useful for smoke tests, regression tests, and baseline exploration.

**Technique.** The engine uses a C++ Mersenne Twister seeded by `scan.seed`.
Linear-prior parameters are sampled uniformly in their declared interval. Log
priors are sampled uniformly in log space. Signed-log priors are sampled across
negative and positive logarithmic support with a gap controlled by `min_abs`.

**Required inputs.** A compiled model, at least one scanned real parameter, valid
bounds, a seed, and `settings.max_evaluations > 0`.

**Free parameters.**

| Option | Meaning |
| --- | --- |
| `max_evaluations` | Number of random points to evaluate. Required. |
| `seed` | Random generator seed. |
| `objective` | `nll` or `posterior_nll`. |
| `invalid_objective` / `invalid_penalty` | Objective assigned to invalid points. |
| `save_invalid_points` | Whether invalid rows are written to `points.csv`. |
| `save_every` | Flush cadence for scan artifacts. |
| `verbose` | Native verbosity level. |

**Outputs.** The common scan artifacts only.

### 2.2 `diver`

`diver` is the native bridge to the external Diver library. It preserves
compatibility with legacy Diver-style workflows when the native extension is
built with Diver support.

**Technique.** BSMScanner supplies Diver with a bounded objective callback. Diver
drives population-based differential evolution internally and calls back into the
same BSMScanner evaluator used by all engines. The bridge currently configures a
single civilization, adaptive `jDE`-style parameters, duplicate removal, bounded
search, and disabled Diver-side file output so that BSMScanner remains the
artifact owner.

**Required inputs.** A Diver-enabled build, a compiled model, scanned real
parameters, valid bounds, and either `max_generations` or `max_evaluations`.

**Free parameters.**

| Option | Meaning |
| --- | --- |
| `population_size` / `NP` | Diver population size. If absent, the bridge uses a dimension-dependent default. |
| `max_generations` / `maxgen` | Maximum Diver generations. |
| `max_evaluations` | Can be used to derive a generation count when `max_generations` is absent. |
| `convergence_threshold` / `convthresh` | Diver convergence threshold. |
| `convergence_steps` / `convsteps` | Diver convergence patience. |
| `max_init_attempts` | Maximum initialization attempts for viable vectors. |
| `seed`, `objective`, `invalid_objective`, `save_invalid_points`, `save_every`, `verbose` | Common scan controls. |

**Outputs.** The common scan artifacts. Diver's own raw output is disabled by
the bridge.

### 2.3 `de_scipy`

`de_scipy` is a Python reference backend built on
`scipy.optimize.differential_evolution`. It exists as a trusted comparison point
for differential-evolution semantics and as an optional engine for users who
have SciPy installed.

**Technique.** SciPy proposes bounded population members. BSMScanner evaluates
them, converts invalid points to the configured invalid penalty, captures all
diagnostics, and records per-generation progress through a callback. The current
reference path requires `workers: 1` so artifact capture remains deterministic.

**Required inputs.** SciPy, a compiled model, scanned parameters and bounds, and
valid SciPy DE options.

**Free parameters.**

| Option | Default | Rule |
| --- | ---: | --- |
| `strategy` | `best1bin` | One of SciPy's supported DE strategies: `best1bin`, `best1exp`, `rand1bin`, `rand1exp`, `rand2bin`, `rand2exp`, `randtobest1bin`, `randtobest1exp`, `currenttobest1bin`, `currenttobest1exp`, `best2bin`, `best2exp`. |
| `maxiter` / `max_generations` / `maxgen` | `100` | Maximum DE iterations. |
| `popsize` / `population_size` / `NP` | `15` | SciPy population multiplier. |
| `tol` / `convergence_threshold` | `0.01` | Relative convergence tolerance. |
| `atol` | `0.0` | Absolute convergence tolerance. |
| `mutation` | `[0.5, 1.0]` | Float or `[low, high]`, satisfying `0 <= low <= high < 2`. |
| `recombination` | `0.7` | Crossover probability, `0 <= value <= 1`. |
| `init` | `latinhypercube` | `latinhypercube`, `sobol`, `halton`, or `random`. |
| `updating` | `deferred` | `immediate` or `deferred`. |
| `workers` | `1` | Must be `1` in this implementation. |
| `polish` | `false` | Whether SciPy performs final polishing. |
| `x0` | unset | Optional initial vector of dimension `D`. |
| `seed` | top-level seed | Optional engine-level seed override. |
| `progress_interval` / `progress_every` / `log_every` | `100` | Progress print cadence when `verbose > 0`; `0` disables periodic logs. |

**Outputs.** The common artifacts plus `history.json` with DE progress,
convergence messages, and best-target snapshots.

### 2.4 `adaptive_diver`

`adaptive_diver` is BSMScanner's native, model-agnostic, Diver-inspired
differential-evolution engine. It is intended for focused optimization in
correlated, invalid, or moderately multimodal landscapes.

**Technique.** The engine implements a JADE-like current-to-pbest mutation with
binomial crossover:

```text
v_i = x_i + F_i (x_pbest - x_i) + F_i (x_r1 - x_r2).
```

Mutation scales `F_i` and crossover probabilities `CR_i` are sampled around
running means. Successful trials update `mu_F` with a Lehmer-style update and
`mu_CR` with an arithmetic update. Bounds can be handled by clipping,
reflection, or resampling. Optional SciPy local refinement can refine elite
final-population points with `Powell` or `L-BFGS-B`.

**Required inputs.** A compiled model, at least four population members, scanned
parameters and bounds, objective settings, and a random seed.

**Free parameters.**

| Option | Default | Rule |
| --- | ---: | --- |
| `strategy` | `current_to_pbest` | Currently the only supported adaptive strategy. |
| `population_size` / `popsize` / `NP` | `40` | Must be at least `4`. |
| `max_generations` / `maxiter` / `maxgen` | `1000` | Maximum generations. |
| `max_evaluations` | `0` | Optional cap; if nonzero, must be at least the population size. |
| `p_best_fraction` | `0.1` | Fraction of top population used for p-best selection, `0 < p <= 1`. |
| `archive` | `true` | Whether to retain replaced vectors for mutation diversity. |
| `mutation.F_min` / `F_min` | `0.1` | Lower adaptive mutation bound. |
| `mutation.F_max` / `F_max` | `1.0` | Upper adaptive mutation bound, `<= 2`. |
| `mutation.initial_mean` / `F_initial` | `0.5` | Initial `mu_F`, with `F_min <= initial <= F_max`. |
| `mutation.learning_rate` / `F_learning_rate` | `0.1` | Update rate, `<= 1`. |
| `crossover.CR_min` / `CR_min` | `0.0` | Lower crossover bound. |
| `crossover.CR_max` / `CR_max` | `1.0` | Upper crossover bound, `<= 1`. |
| `crossover.initial_mean` / `CR_initial` | `0.9` | Initial `mu_CR`. |
| `crossover.learning_rate` / `CR_learning_rate` | `0.1` | Update rate, `<= 1`. |
| `bounds.handling` / `bounds_handling` | `reflect` | `clip`, `reflect`, or `resample`. |
| `convergence.patience` / `patience` | `200` | Generations without sufficient improvement before stopping; `0` disables patience stopping. |
| `convergence.min_delta_chi2` / `min_delta_chi2` | `1.0e-8` | Improvement threshold. |
| `convergence.population_std_tol` / `population_std_tol` | `0.0` | Population objective-spread tolerance; `0` disables this criterion. |
| `local_refinement.enabled` | `false` | Enables SciPy elite refinement. |
| `local_refinement.method` | `Powell` | `Powell` or `L-BFGS-B`. |
| `local_refinement.n_elites` | `5` | Number of elite points to refine. |
| `local_refinement.maxiter` | `2000` | Local optimizer iteration cap. |
| `statistics.enabled` / `adaptive_statistics` | `false` | Writes final-population summaries. |
| `statistics.confidence_levels` | `[0.68, 0.95]` | Levels in `(0, 1)`. |
| `elite_size` | `10` | Number of elite rows in `elite_points.csv`. |
| `output.save_history` | `true` | Write `history.json`. |
| `output.save_population` | `true` | Write `final_population.csv`. |
| `output.save_elites` | `true` | Write `elite_points.csv`. |
| `progress_interval` | `100` | Progress print cadence when verbose. |

`adaptive_de` is accepted as an alias for `adaptive_diver`.

**Outputs.** The common artifacts plus `history.json`, `final_population.csv`,
`elite_points.csv`, and, when enabled, `local_refinement.json`,
`parameter_summary.json`, and `correlation_matrix.json`.

### 2.5 `basin_scan`

`basin_scan` is an orchestration engine rather than a single optimizer. It
combines broad exploration, likelihood-aware preselection, optional guided or
machine-learning-assisted refocusing, clustering, focused-box construction, and
independent `adaptive_diver` runs inside each focused box.

**Technique.** The method is deliberately model-agnostic. It sees only parameter
names, parameter bounds, prior coordinate types, scalar objective values, named
likelihood components, validity flags, failure reasons, and scan options. It
does not contain neutrino, quark, CKM, PMNS, micrOMEGAs, or one-loop-specific
logic.

The default one-shot workflow is:

1. Draw an exploration population in the full parameter box.
2. Optionally apply proposal or guided-sampling transforms.
3. Evaluate points through the standard evaluator or staged cheap/full policy.
4. Select promising points by top fraction, chi-square window, or balanced
   likelihood-term cuts.
5. Optionally preserve near-miss points that are good in selected terms.
6. Optionally refine selected seeds by local jittered sampling.
7. Cluster selected points in normalized coordinates using DBSCAN.
8. Construct quantile-based focused boxes, optionally padded, clipped, merged,
   and capped in number.
9. Optionally replace/refine the boxes with manifold or ML focus stages.
10. Launch one focused `adaptive_diver` run per focused box.
11. Re-evaluate and rank focused best fits.

The next section gives the complete option catalogue.

## 3. Complete `basin_scan` Reference

### 3.1 Top-Level Structure

The engine is selected as:

```yaml
scan:
  engine: basin_scan
  seed: 12345
  settings:
    objective: nll
    invalid_penalty: 1.0e12
    save_invalid_points: false
    verbose: 1

  basin_scan:
    exploration: {}
    selection: {}
    clustering: {}
    boxes: {}
    focused_engine: {}
```

At build time, `scan.settings` and `scan.basin_scan` are merged for the basin
engine. The following top-level basin blocks are recognized:

- `exploration`
- `selection`
- `clustering`
- `boxes`
- `progressive_exploration`
- `proposals`
- `guided_sampling`
- `staged_evaluation`
- `refinement`
- `manifold_refocus`
- `ml_focus`
- `focused_engine`
- `output`

### 3.2 Exploration

Exploration defines the initial broad sample.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `exploration.method` | `latin_hypercube` | `latin_hypercube`, `sobol`, or `random` | Sampling rule in the original bounds. |
| `exploration.n_points` | `50000` | integer `>= 1` | Number of exploration evaluations. |
| `exploration.keep_fraction` | `0.02` | `0 < f <= 1` | Default top fraction used by selection when no explicit selection fraction is supplied. |

Latin-hypercube and Sobol sampling use `scipy.stats.qmc` when available and fall
back to uniform random sampling if SciPy cannot be imported.

### 3.3 Selection

Selection reduces the exploration cloud to points that should seed clustering.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `selection.mode` | `top_fraction` | `top_fraction`, `chi2_window`, or `balanced_terms` | Selection rule. |
| `selection.top_fraction` | `exploration.keep_fraction` | `0 < f <= 1` | Fraction of best finite points kept in top-fraction mode. |
| `selection.max_points` | `2000` | integer `>= 1` | Maximum selected points. |
| `selection.min_points` | `1` | integer `>= 1`, `<= max_points` | Minimum retained points when possible. |
| `selection.chi2_window` | `0.0` | float `>= 0` | Keep points within this objective window above the best point. |
| `selection.total_top_fraction` | `top_fraction` | `0 < f <= 1` | Broad total-objective slice for balanced-term selection. |
| `selection.term_quantile_cut` | `0.30` | `0 <= q <= 1` | Per-term quantile threshold for balanced-term cuts. |
| `selection.terms` | `auto` | `auto` or list of names | Likelihood terms used by balanced selection. |
| `selection.exclude_terms` | `[]` | list | Terms excluded from automatic discovery. |
| `selection.combine_with_top_fraction` | `true` | boolean | Adds top-fraction points to balanced-term selections. |
| `selection.fallback_mode` | `top_fraction` | `top_fraction` or `chi2_window` | Fallback if balanced-term selection cannot find term columns. |

`balanced_terms` uses generic `like__<term>` columns. It first restricts to a
broad total-objective slice and then keeps points that are not catastrophic in
each selected likelihood term. Term names may be raw likelihood names or full
`like__...` column names.

### 3.4 Near-Miss Selection

`selection.near_miss` augments the selected set with points that may be
scientifically useful even when they are not globally best by total objective.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `enabled` | `false` | boolean | Enables near-miss augmentation. |
| `keep_accepted` | `true` | boolean | Retains accepted points alongside near misses. |
| `keep_per_term_best` | `true` | boolean | Keeps champions for individual likelihood terms. |
| `include_invalid` | `false` | boolean | Allows invalid points into the near-miss candidate pool. |
| `max_hard_failures` | `0` | integer `>= 0` | Maximum hard failures tolerated. |
| `max_fit_failures` | `3` | integer `>= 0` | Maximum likelihood-fit failures tolerated. |
| `objective_cap` | invalid penalty | float `>= 0` | Maximum objective accepted for near-miss candidates. |
| `include_full_eval_points` | `true` | boolean | Keeps points reaching full evaluation in staged mode. |
| `max_accepted_points` | `100` | integer `>= 0` | Cap for accepted-retention additions. |
| `max_near_miss_points` | `100` | integer `>= 0` | Cap for near-miss additions. |

Near-miss diagnostics are written to `selection_summary.json`, and rows are also
separated into `accepted_points.csv` and `near_miss_points.csv`.

### 3.5 Clustering

Clustering turns selected points into candidate basins.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `clustering.enabled` | `true` | boolean | Enables DBSCAN; if disabled, all selected points form one cluster. |
| `clustering.method` | `dbscan` | `dbscan` | Current clustering method. |
| `clustering.eps_fraction` | `0.08` | `> 0` | DBSCAN radius in normalized parameter coordinates. |
| `clustering.min_samples` | `10` | integer `>= 1` | DBSCAN core-point threshold. |
| `clustering.max_clusters` | `8` | integer `>= 1` | Maximum clusters kept, sorted by best objective. |

If DBSCAN finds no non-noise cluster, the selected cloud is treated as one
cluster so the workflow can continue.

### 3.6 Focused Boxes

Boxes define the search volume for focused `adaptive_diver` runs.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `boxes.construction` | `quantile` | `quantile` | Box construction method. |
| `boxes.q_low` | `0.05` | `0 <= q_low < q_high <= 1` | Lower quantile per parameter. |
| `boxes.q_high` | `0.95` | `0 <= q_low < q_high <= 1` | Upper quantile per parameter. |
| `boxes.padding_fraction` | `0.25` | `>= 0` | Padding applied to quantile widths. |
| `boxes.min_width_fraction` | `0.02` | `0 <= f <= 1` | Minimum width as a fraction of original width. |
| `boxes.clip_to_original_bounds` | `true` | boolean | Clip boxes to declared scan bounds. |
| `boxes.merge_overlapping` | `false` | boolean | Merge overlapping boxes before focused runs. |
| `boxes.max_boxes` | `0` | integer `>= 0` | Maximum boxes kept; `0` means no explicit cap beyond clustering. |

Each box records lower and upper parameter bounds, relative volume, source
cluster, selected count, and whether it contains the global best exploration
point when that information is available.

### 3.7 Progressive Exploration

`progressive_exploration` replaces the one-shot exploration pass with staged
rounds. It is disabled by default.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `enabled` | `false` | boolean | Enables staged exploration. |
| `n_rounds` | `2` | integer `>= 1` | Number of exploration rounds. |
| `points_per_round` | `[n_points] * n_rounds` | list length equals `n_rounds` | Evaluation budget per round. |
| `combine_with_previous_selected` | `true` | boolean | Carries selected points across rounds. |

Progressive selection has the same schema as ordinary `selection`, including
`near_miss`, but defaults inherit from the ordinary selection block.

Progressive boxes have the same quantile construction schema as `boxes`, with
defaults inherited from the ordinary box block except:

| Option | Default | Meaning |
| --- | ---: | --- |
| `progressive_exploration.boxes.merge_overlapping` | `true` | Merge round boxes by default. |
| `progressive_exploration.boxes.max_boxes` | `clustering.max_clusters` | Cap boxes used for later rounds. |

Progressive sampling controls how new points are allocated in later rounds:

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `sampling.method` | exploration method | `latin_hypercube`, `sobol`, or `random` | Sampling method inside boxes and global fraction. |
| `sampling.allocate_points` | `proportional_volume` | `equal`, `proportional_volume`, or `mixed` | Allocation rule across boxes/global component. |
| `sampling.min_points_per_box` | `1` | integer `>= 1` | Minimum per sampled box. |
| `sampling.fractions.elite_boxes` | `0.5` | nonnegative | Mixed allocation share for elite boxes. |
| `sampling.fractions.selected_boxes` | `0.3` | nonnegative | Mixed allocation share for selected boxes. |
| `sampling.fractions.global` | `0.2` | nonnegative | Mixed allocation share for the full global box. |

The three mixed fractions must sum to a positive value and are normalized
internally.

Elite preservation keeps high-quality points from being lost between rounds:

| Option | Default | Rule |
| --- | ---: | --- |
| `elite_preservation.enabled` | `true` | boolean |
| `elite_preservation.always_keep_global_best` | `true` | boolean |
| `elite_preservation.archive_size` | `500` | integer `>= 1` |
| `elite_preservation.elite_fraction` | `0.05` | `0 < f <= 1` |
| `elite_preservation.min_elite_points` | `20` | integer `>= 1` |
| `elite_preservation.max_elite_points` | `200` | integer `>= 1`, not below minimum |

Elite boxes add boxes around the elite archive:

| Option | Default |
| --- | ---: |
| `elite_boxes.enabled` | `true` |
| `elite_boxes.construction` | `quantile` |
| `elite_boxes.q_low` | `0.05` |
| `elite_boxes.q_high` | `0.95` |
| `elite_boxes.padding_fraction` | `0.30` |
| `elite_boxes.min_width_fraction` | `0.01` |
| `elite_boxes.max_boxes` | `4` |

The best-centered box keeps a shrinking box around the current best point:

| Option | Default | Rule |
| --- | ---: | --- |
| `best_centered_box.enabled` | `true` | boolean |
| `best_centered_box.width_fraction` | `0.15` | `0 < f <= 1` |
| `best_centered_box.shrink_per_round` | `0.7` | `0 < f <= 1` |
| `best_centered_box.min_width_fraction` | `0.005` | `0 <= f <= 1` |

Progressive output switches:

| Option | Default |
| --- | ---: |
| `output.save_round_points` | `true` |
| `output.save_round_selected` | `true` |
| `output.save_round_boxes` | `true` |

When enabled, the run writes `progressive_exploration_summary.json` and a
`progressive_exploration/` directory containing round-level points, selections,
and boxes according to the output switches.

### 3.8 Proposal-Assisted and Guided Sampling

`proposals` and `guided_sampling` transform sampled points before evaluation.
Both are disabled by default. `guided_sampling.stages` are normalized and merged
with `proposals.stages`; `guided_sampling.apply_to` can provide a default
application stage.

| Option | Default | Meaning |
| --- | ---: | --- |
| `proposals.enabled` | `false` | Enables proposal stages. |
| `guided_sampling.enabled` | `false` | Also enables proposal processing. |
| `stages[].name` | `proposal_<index>` | Diagnostic name. |
| `stages[].type` | required | Proposal type. |
| `stages[].enabled` | `true` | Per-stage switch. |
| `stages[].probability` | `1.0` | Application probability, `0 <= p <= 1`. |
| `stages[].apply_to` | all stages | Optional list: `exploration`, `progressive_exploration`, `refinement`, `all`, or aliases. |

Supported proposal types are:

- `prior_profile`: resample named parameters from Gaussian profiles
  (`mean`, `sigma`) or discrete `values` with optional `weights`.
- `complex_vector_norm`: assign real and imaginary component parameters a
  random direction with a sampled norm, with `scale: linear` or `scale: log`.
- `parameter_rescale`: multiply listed parameters by a sampled factor from
  `factor_range`, with linear or log scaling.
- `point_function`: call a user-provided Python function and apply returned
  parameter updates.

All transformed points are clipped back to declared scan bounds. Diagnostics are
written to `proposal_summary.json`.

### 3.9 Staged Evaluation

`staged_evaluation` is a cheap/full evaluation policy. It can build a reduced
cheap-stage model by filtering likelihoods, theory checks, and outputs by name,
then fully evaluate only points that pass the cheap policy.

| Option | Default | Meaning |
| --- | ---: | --- |
| `enabled` | `false` | Enables staged evaluation. |
| `cheap_stage.include_terms` | `[]` | Keep only these likelihood terms in the cheap graph. |
| `cheap_stage.exclude_terms` | `[]` | Exclude these terms from the cheap graph. |
| `cheap_stage.include_theory_checks` | `[]` | Keep only these theory checks. |
| `cheap_stage.exclude_theory_checks` | `[]` | Exclude these theory checks. |
| `cheap_stage.include_outputs` | `[]` | Keep only these outputs. |
| `cheap_stage.exclude_outputs` | `[]` | Exclude these outputs; otherwise cheap outputs are opt-in. |
| `expensive_stage.include_terms` | `[]` | Terms interpreted as expensive and excluded from cheap sums if no cheap list is explicit. |
| `full_eval_policy.max_cheap_objective` | invalid penalty | Cheap objective threshold. |
| `full_eval_policy.require_no_hard_failures` | `true` | Reject cheap-stage points with hard failures. |
| `save_rejected_cheap_points` | `true` | Retain rejected cheap diagnostics. |
| `save_full_eval_points` | `true` | Retain full-evaluation diagnostics. |

Point artifacts may include `objective_cheap`, `objective_full`,
`stage_reached`, `hard_failures`, `fit_failures`, and `terms_evaluated`.
Diagnostics are written to `staged_evaluation_summary.json`.

### 3.10 Seed Refinement

`refinement` performs local jittered sampling around selected seeds before
clustering.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `enabled` | `false` | boolean | Enables refinement. |
| `n_rounds` | `1` | integer `>= 1` | Number of refinement rounds. |
| `points_per_seed` | `10` | integer `>= 1` | Jittered points per selected seed. |
| `max_seeds` | `20` | integer `>= 1` | Maximum selected seeds refined. |
| `seed_source` | `selected_plus_elite` | string | Diagnostic source label / seed-source policy. |
| `jitter_fraction` | `0.08` | `>= 0` | Jitter width as a fraction of original parameter width. |
| `apply_proposals` | `true` | boolean | Reapply proposal stages during refinement. |
| `keep_near_miss` | `true` | boolean | Preserve near-miss points in combined reselection. |

Artifacts include `refinement_points.csv` and `refinement_summary.json` when
enabled.

### 3.11 Manifold Refocus

`manifold_refocus` is a covariance-based, model-agnostic refocusing stage for
thin correlated basins. It is disabled by default.

| Option | Default | Rule | Meaning |
| --- | ---: | --- | --- |
| `enabled` | `false` | boolean | Enables the stage. |
| `method` | `covariance` | `covariance` | Current method. |
| `seed` | scan seed | integer | Refocus RNG seed. |
| `source` | `selected` | `selected`, `exploration`, or `selected_plus_exploration` | Training source pool. |
| `max_train_points` | `5000` | integer `>= 2` | Training cap. |
| `min_train_points` | `20` | integer `>= 2` | Minimum required; otherwise fallback keeps existing boxes. |
| `top_fraction_for_training` | `1.0` | float `>= 0` | Fraction of best valid source points used. |
| `sampling.n_candidates` | `50000` | integer `>= 1` | Number of covariance candidates. |
| `sampling.inflate` | `1.5` | float `>= 0` | Covariance inflation factor. |
| `sampling.diagonal_jitter` | `1.0e-6` | float `>= 0` | Stabilizing diagonal covariance term. |
| `sampling.include_training_points` | `true` | boolean | Include training points in the box source cloud. |
| `box.enabled` | `true` | boolean | Enables replacement focused box. |
| `box.quantile_low` | `0.02` | `0 <= low < high <= 1` | Candidate-cloud lower quantile. |
| `box.quantile_high` | `0.98` | `0 <= low < high <= 1` | Candidate-cloud upper quantile. |
| `box.padding_fraction` | `0.35` | `>= 0` | Box padding. |
| `box.min_width_fraction` | `0.02` | `0 <= f <= 1` | Minimum width relative to original bounds. |
| `box.max_shrink_factor` | `100.0` | `>= 1` | Prevents boxes narrower than original width divided by this factor. |
| `box.clip_to_original_bounds` | `true` | boolean | Clips the box to original bounds. |

The stage transforms parameters to prior-aware unit coordinates, estimates a
covariance cloud from the best valid points, samples candidate points, converts
them back to physical coordinates, and builds a focused box. Artifacts include
`manifold_refocus_training.csv`, `manifold_refocus_candidates.csv`,
`manifold_refocus_box.json`, and `manifold_refocus_diagnostics.json`.

### 3.12 Machine-Learning Focus

`ml_focus` is an optional surrogate-ranking stage. It is disabled by default and
currently supports only an Extra Trees regressor.

| Option | Default | Rule |
| --- | ---: | --- |
| `enabled` | `false` | boolean |
| `seed` | scan seed | integer |
| `model.type` | `extra_trees_regressor` | only supported value |
| `model.n_estimators` | `300` | integer `>= 1` |
| `model.min_samples_leaf` | `3` | integer `>= 1` |
| `model.max_features` | `sqrt` | passed to the regressor |
| `training.max_train_points` | `50000` | integer `>= 1` |
| `training.min_train_points` | `100` | integer `>= 1` |
| `training.require_valid` | `true` | boolean |
| `training.finite_objective_only` | `true` | boolean |
| `training.target_transform` | `log10_1p` | only supported value |
| `training.top_fraction_for_training` | unset | optional `<= 1` |
| `candidate_generation.n_candidates` | `100000` | integer `>= 1` |
| `candidate_generation.sources.selected_box_fraction` | `0.50` | nonnegative |
| `candidate_generation.sources.elite_local_fraction` | `0.30` | nonnegative |
| `candidate_generation.sources.global_fraction` | `0.20` | nonnegative |
| `selection.n_ml_selected` | `5000` | integer `>= 1` |
| `selection.include_best_real_points` | `true` | boolean |
| `selection.n_best_real_points` | `500` | integer `>= 0` |
| `selection.include_elite_archive` | `true` | boolean |
| `focused_box.enabled` | `true` | boolean |
| `focused_box.quantile_low` | `0.02` | `0 <= low < high <= 1` |
| `focused_box.quantile_high` | `0.98` | `0 <= low < high <= 1` |
| `focused_box.padding_fraction` | `1.0` | `>= 0` |
| `focused_box.min_width_fraction` | `0.05` | `0 <= f <= 1` |
| `focused_box.max_shrink_factor` | `50.0` | `>= 1` |
| `focused_box.clip_to_original_bounds` | `true` | boolean |
| `seeds.enabled` | `true` | boolean |
| `seeds.max_seeds` | `1000` | integer `>= 1` |
| `seeds.composition.best_real_fraction` | `0.40` | nonnegative |
| `seeds.composition.ml_selected_fraction` | `0.40` | nonnegative |
| `seeds.composition.local_mutation_fraction` | `0.20` | nonnegative |
| `seeds.local_mutation.relative_sigma` | `0.05` | `>= 0` |
| `seeds.local_mutation.log_sigma` | `0.25` | `>= 0` |

Candidate-source fractions and seed-composition fractions must each sum to a
positive value and are normalized internally. The stage writes diagnostic,
candidate, selected, box, and seed artifacts when enabled.

### 3.13 Focused Engine

`basin_scan` currently supports `adaptive_diver` as its focused engine.

| Option | Default | Rule |
| --- | ---: | --- |
| `focused_engine.name` / `engine` | `adaptive_diver` | `adaptive_diver` or alias `adaptive_de` |
| `population_size` | `60` | Passed to `adaptive_diver`. |
| `max_generations` | `1500` | Passed to `adaptive_diver`. |
| `p_best_fraction` | `0.1` | Passed to `adaptive_diver`. |
| `archive` | `true` | Passed to `adaptive_diver`. |
| `invalid_penalty` | basin invalid penalty | Passed to focused run. |
| `seed` | basin seed | Offset per basin. |
| `verbose` | `0` | Focused-run verbosity unless overridden. |
| `save_invalid_points` | `false` | Focused-run invalid row behavior. |
| `objective` | basin objective | Focused objective. |

Any additional valid `adaptive_diver` options may be supplied under
`focused_engine`, including mutation, crossover, bounds, convergence,
local-refinement, statistics, and output controls.

Selected and ML-generated seed points can be passed into the focused
`adaptive_diver` initial population.

### 3.14 Basin Output Switches

| Option | Default | Meaning |
| --- | ---: | --- |
| `output.save_exploration_points` | `true` | Write `exploration_points.csv`. |
| `output.save_selected_points` | `true` | Write `selected_points.csv`. |
| `output.save_clusters` | `true` | Write `clusters.csv`. |
| `output.save_focused_boxes` | `true` | Write `focused_boxes.json`. |
| `progress_interval` / `progress_every` / `log_every` | `1000` | Basin progress cadence when `verbose > 0`; `0` disables periodic progress. |

Regardless of the focused-box switch, `focused_boxes.json` is written at the end
of the current implementation because it is part of the basin result contract.

### 3.15 Basin Artifacts

A full `basin_scan` run can write:

- Common artifacts: `points.csv`, `metadata.json`, `best_fit.json`,
  `summary.json`.
- Stage history: `history.json`.
- Exploration and selection: `exploration_points.csv`, `selected_points.csv`,
  `accepted_points.csv`, `near_miss_points.csv`, `selection_summary.json`.
- Proposal and staged-evaluation diagnostics: `proposal_summary.json`,
  `staged_evaluation_summary.json`.
- Optional refinement: `refinement_points.csv`, `refinement_summary.json`.
- Clustering and boxes: `clusters.csv`, `focused_boxes.json`.
- Focused optimization: `basin_00/`, `basin_01/`, ... containing
  `adaptive_diver` artifacts.
- Basin ranking: `basin_results.json`.
- Optional progressive exploration:
  `progressive_exploration_summary.json` and round files under
  `progressive_exploration/`.
- Optional manifold refocus: `manifold_refocus_training.csv`,
  `manifold_refocus_candidates.csv`, `manifold_refocus_box.json`,
  `manifold_refocus_diagnostics.json`.
- Optional ML focus: ML diagnostics, candidate, selected, focused-box, and seed
  files.

The top-level `summary.json` includes `engine_details` with exploration counts,
selected counts, accepted and near-miss counts, focused-run counts, enabled
optional stages, focused-evaluation totals, and paths to the principal basin
artifacts.

## 4. Methodological Notes

The engine suite deliberately distinguishes optimization, exploration, and
inference. `serial_random`, `diver`, `de_scipy`, and `adaptive_diver` are scan
or optimization engines. `basin_scan` is a model-agnostic orchestration layer
that calls focused optimizers after basin discovery. The optional statistics and
posterior-MCMC modules are post-processing or refinement layers, not replacements
for global basin discovery.

Population summaries from `adaptive_diver` and likelihood-weighted summaries
from scan points should not be interpreted as fully converged Bayesian
posteriors. For difficult BSM landscapes, a recommended workflow is broad
`basin_scan`, optional focused `adaptive_diver`, and then a dedicated posterior
sampler initialized from discovered viable basins when uncertainty
quantification is required.
