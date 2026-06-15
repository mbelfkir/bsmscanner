# Weinberg Scan Failure Diagnosis

This report is generated from existing artifacts only. It does not modify framework code, model code, scan engines, or scan configs.

## Executive conclusion

- The first failing stage for `examples/weinberg/runs/firsttest` is **exploration/selection followed by focused-box construction**.
- The reference point is valid and has much lower objective than the scan-found point under the same `models/weinberg/model_no.yaml` evaluator.
- The final focused box excludes the reference basin, so the focused `adaptive_diver` run never had access to the true solution.
- `balanced_terms` did not recover the reference basin in this run; it selected a cloud with `g2t` too low and then the focused box clipped away `g2t≈3.08`, `g3t≈-1.63`, and `Imtau≈1.19`.

## Direct point comparison

| point | valid | nLL | chi2 |
|---|---:|---:|---:|
| reference positive | True | 0.07831972522 | 0.1566394504 |
| failed-run best | True | 271.8714766 | 543.7429533 |

### Likelihood-term comparison

| term | reference nLL contribution | failed-best contribution | difference |
|---|---:|---:|---:|
| dm21_term | 0.03173294411 | 0.1719613333 | 0.1402283891 |
| dm3l_term | 0.0465867811 | 2.885661538 | 2.839074757 |
| me_over_mu_term | 1.460208357e-11 | 2.873052988e-05 | 2.873051527e-05 |
| mu_over_tau_term | 2.242609026e-16 | 1.392913978 | 1.392913978 |
| s12_term | 1.901036061e-15 | 28.04323857 | 28.04323857 |
| s13_term | 6.81154318e-19 | 7.653336697 | 7.653336697 |
| s23_term | 1.129503325e-17 | 231.7243358 | 231.7243358 |

Dominant failed-best terms are `s23_term`, `s12_term`, and `s13_term`; the point is technically valid but physically a poor fit.

## Failed run summary

- Run: `examples/weinberg/runs/firsttest`
- Model: `models/weinberg/model_no.yaml`
- Engine: `basin_scan`
- Evaluations: `2350841`
- Valid points: `2350841`
- Best nLL: `271.8714766`
- Best chi2: `543.7429533`

### Parameter bounds

| parameter | lower | upper |
|---|---:|---:|
| Retau | -0.5 | 0.5 |
| Imtau | 0.866 | 3.5 |
| a2t | -2 | 2 |
| a3t | -3 | 3 |
| g2t | -3.5 | 3.5 |
| g3t | -2 | 2 |

## Exploration and final selection

### Exploration points

- Rows: `2100000`
- Valid rows: `2100000`
- Best nLL / chi2: `334.4471588` / `668.8943175`
- Median nLL: `497331.3583`
- q10/q25/q75/q90/q99 nLL: `52559.62523`, `204020.075`, `1599329.299`, `8084365.547`, `977525792.6`

Best point:

```json
{
  "Retau": -0.021716601747268596,
  "Imtau": 2.0209429063483575,
  "a2t": 1.9802417029148704,
  "a3t": 2.5265646385192655,
  "g2t": -0.5804488908822146,
  "g3t": 0.35333275602459785
}
```

Positive reference distance diagnostics:

- Minimum normalized distance: `0.06471281455`
- Median normalized distance: `1.174419768`
- Closest point chi2: `1354184.107`
- Closest point raw distance: `0.2597135909`

Negative reference distance diagnostics:

- Minimum normalized distance: `0.06347568329`
- Median normalized distance: `1.174451163`
- Closest point chi2: `51329.15774`
- Closest point raw distance: `0.2556441247`

Reference-like cut counts:

- Positive branch: `{'all_6': 24, 'at_least_5': 613, 'at_least_4': 9631, 'best_chi2_all_6': 16581.8279446135}`
- Negative branch: `{'all_6': 24, 'at_least_5': 578, 'at_least_4': 9523, 'best_chi2_all_6': 16581.8279446135}`

### Final selected points

- Rows: `2000`
- Valid rows: `2000`
- Best nLL / chi2: `417.9026381` / `835.8052763`
- Median nLL: `1149.607132`
- q10/q25/q75/q90/q99 nLL: `866.692025`, `1056.591525`, `1225.68207`, `1272.818625`, `1299.905128`

Best point:

```json
{
  "Retau": 0.1776371804749345,
  "Imtau": 3.2337824915585145,
  "a2t": -1.6223133914566232,
  "a3t": -2.571987051548499,
  "g2t": -0.14366760705353565,
  "g3t": -1.5199762615981285
}
```

Positive reference distance diagnostics:

- Minimum normalized distance: `0.2035538873`
- Median normalized distance: `0.8343660435`
- Closest point chi2: `2187.699513`
- Closest point raw distance: `0.7807427977`

Negative reference distance diagnostics:

- Minimum normalized distance: `0.223143062`
- Median normalized distance: `0.8329734885`
- Closest point chi2: `2187.699513`
- Closest point raw distance: `0.7863749702`

Reference-like cut counts:

- Positive branch: `{'all_6': 0, 'at_least_5': 1, 'at_least_4': 2, 'best_chi2_all_6': None}`
- Negative branch: `{'all_6': 0, 'at_least_5': 0, 'at_least_4': 3, 'best_chi2_all_6': None}`

### Final selection diagnostics

- Mode: `balanced_terms`
- Candidate points: `2100000`
- After total top cut: `209954`
- After balanced term cuts: `9653`
- Final selected count: `2000`
- Fallback used: `False`
- Best selected nLL: `417.9026381`
- Worst selected nLL: `1302.569975`

Thresholds:

```json
{
  "dm21_term": 435.32965156793153,
  "dm3l_term": 823.8270711946286,
  "me_over_mu_term": 1148.6107771207824,
  "mu_over_tau_term": 16977.289121426784,
  "s12_term": 184.55564824386667,
  "s13_term": 42900.84187737696,
  "s23_term": 244.86195688776883
}
```

## Progressive rounds

### round_00

- Round points: `1000000`, valid `1000000`
- Best round nLL / chi2: `365.9335967` / `731.8671934`
- Selected count: `2774`
- Best selected nLL / chi2: `508.2127605` / `1016.425521`
- Balanced fallback used: `False`
- Terms used: `['dm21_term', 'dm3l_term', 'me_over_mu_term', 'mu_over_tau_term', 's12_term', 's13_term', 's23_term']`

### round_01

- Round points: `500000`, valid `500000`
- Best round nLL / chi2: `387.2610001` / `774.5220001`
- Selected count: `1340`
- Best selected nLL / chi2: `417.9026381` / `835.8052763`
- Balanced fallback used: `False`
- Terms used: `['dm21_term', 'dm3l_term', 'me_over_mu_term', 'mu_over_tau_term', 's12_term', 's13_term', 's23_term']`

### round_02

- Round points: `500000`, valid `500000`
- Best round nLL / chi2: `345.5545918` / `691.1091836`
- Selected count: `2271`
- Best selected nLL / chi2: `417.9026381` / `835.8052763`
- Balanced fallback used: `False`
- Terms used: `['dm21_term', 'dm3l_term', 'me_over_mu_term', 'mu_over_tau_term', 's12_term', 's13_term', 's23_term']`

### round_03

- Round points: `100000`, valid `100000`
- Best round nLL / chi2: `334.4471588` / `668.8943175`
- Selected count: `1419`
- Best selected nLL / chi2: `417.9026381` / `835.8052763`
- Balanced fallback used: `False`
- Terms used: `['dm21_term', 'dm3l_term', 'me_over_mu_term', 'mu_over_tau_term', 's12_term', 's13_term', 's23_term']`

## Focused box diagnostics

### Box 0

- Type: `selected_cloud`
- Relative volume: `3.633091442e-05`
- Positive reference inside: `False`
- Positive reference excluded by: `['Imtau', 'g2t', 'g3t']`
- Negative reference inside: `False`
- Negative reference excluded by: `['Imtau', 'g2t', 'g3t']`

| parameter | lower | upper |
|---|---:|---:|
| Retau | -0.1997219434 | 0.1367771893 |
| Imtau | 1.785148975 | 2.483673677 |
| a2t | 1.476988142 | 2 |
| a3t | 1.703691735 | 3 |
| g2t | -0.3485505051 | 0.04498826672 |
| g3t | -0.1088140478 | 0.9165741228 |

## Focused adaptive_diver diagnostics

- Run: `examples/weinberg/runs/firsttest/basin_00`
- Final nLL / chi2: `271.8714766` / `543.7429533`
- Stop reason: `max_generations`
- Evaluations: `250840`
- Local refinement enabled: `True`
- Closest final-population point to positive reference chi2: `543.7429533`
- Closest elite point to positive reference chi2: `543.7429533`

Because the focused box excludes the reference basin, this is not evidence that `adaptive_diver` failed inside a good box.

## Successful focused/narrow run

- Run: `examples/arxiv2006_03058_weinberg/runs/no_adaptive_diver_range_g3_minus2_0`
- Best nLL / chi2: `0.0004953532786` / `0.0009907065572`

Best point:

```json
{
  "Retau": -0.026441556948224226,
  "Imtau": 1.1874904927201686,
  "a2t": 1.7301585404561923,
  "a3t": 2.76850271227416,
  "g2t": 3.080879953661591,
  "g3t": -1.6316233645891267
}
```

Elite-point 5%-95% parameter ranges:

| parameter | q05 | q95 | width |
|---|---:|---:|---:|
| Retau | -0.02643703165 | 0.02644513854 | 0.05288217019 |
| Imtau | 1.187485139 | 1.190884716 | 0.003399577006 |
| a2t | 1.730158524 | 1.733952965 | 0.003794440697 |
| a3t | 2.768410807 | 2.771040583 | 0.002629775324 |
| g2t | 3.080896966 | 3.090340379 | 0.009443413271 |
| g3t | -1.637822285 | -1.631598403 | 0.006223881865 |

## Latest broad progressive balanced comparison

- Run: `examples/arxiv2006_03058_weinberg/runs/no_basin_scan_progressive_balanced_full`
- Best nLL / chi2: `63.0514212` / `126.1028424`
- Focused boxes: `1`

- Box 0 positive inside `False`, excluded by `['Imtau', 'g2t', 'g3t']`, relative volume `3.275578378e-06`

## Answers to required questions

1. **Was the reference basin ever sampled approximately?** Not in a useful way in `firsttest`. Approximate reference-like counts are zero for all six cuts; the closest raw point was high chi2.
2. **If sampled, was it selected or discarded?** Reference-like points were not sampled closely enough. The final selected range also excludes the positive reference in `g2t`.
3. **Did balanced_terms help?** It produced balanced term diagnostics and avoided fallback, but it did not recover the true basin; in this run it selected a wrong cloud.
4. **Did focused box construction cut away the true basin?** Yes. The final focused box excludes the reference basin.
5. **Did adaptive_diver ever get a box containing the true basin?** No for `firsttest`.
6. **Which likelihood terms dominate the failed best point?** `s23_term`, `s12_term`, and `s13_term` dominate.
7. **How small/correlated is the successful basin?** The successful focused run has a tiny elite spread compared with the broad box, especially in the modular-form parameters; see elite 5%-95% table.
8. **First failing stage:** exploration/selection, followed by focused-box construction that excludes the basin.
9. **Most justified next improvement:** delayed focusing or diverse multi-basin boxes with explicit global-best/elite retention into final focused boxes. Parameter-domain tightening/transforms for `tau` and modular coefficients are also justified, but that is a model-domain choice rather than a scanner-only change.
