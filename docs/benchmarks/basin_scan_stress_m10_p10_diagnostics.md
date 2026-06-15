# basin_scan [-10, 10]^6 Stress Diagnostics

Run directory: `examples/arxiv2006_03058_weinberg/runs/no_basin_scan_stress_m10_p10_full`

This is an artifact-only diagnostic report. It does not modify framework code,
physics code, `adaptive_diver`, or `basin_scan`.

## Reference

- Reference chi2: `0.000953766671751`
- Reference point: `{"Retau": 0.02644089, "Imtau": 1.187476025, "a2t": 1.730159126, "a3t": 2.768453506, "g2t": 3.080703752, "g3t": -1.631334962}`
- Sign/CP-degenerate reference: `{"Retau": -0.026441557, "Imtau": 1.187490493, "a2t": 1.73015854, "a3t": 2.768502712, "g2t": 3.080879954, "g3t": -1.631623365}`

## Exploration Summary

- Total rows: `300000`
- Finite objectives: `300000`
- Valid points: `166701`
- Invalid points: `133299`
- NaN/inf objectives: `0`
- Best exploration nLL: `430.8533430361918`
- Best exploration chi2: `861.7066860723836`
- Worst finite nLL: `1.1846678150613752e+32`
- Median nLL: `1000000000000.0`
- Objective quantiles: q10 `377188.3192017766`, q25 `1848307.7699109428`, q75 `1000000000000.0`, q90 `3.2265226224000915e+17`, q99 `1.657695309729995e+24`
- Best exploration point: `{"Retau": -6.532696879532555, "Imtau": -0.32333143695597677, "a2t": -3.1149631670170734, "a3t": -3.9463805206614495, "g2t": 5.752340010679514, "g3t": 4.888988178267713}`

## Selected Points

- Selected points: `554`
- Best selected nLL: `430.8533430361918`
- Best selected chi2: `861.7066860723836`
- Worst selected nLL: `3397.392290733646`
- Median selected nLL: `2128.7536262841318`
- Selected objective quantiles: q10 `995.2321234322944`, q25 `1511.2389097017444`, q75 `2798.6241133325725`, q90 `3212.11822415049`, q99 `3384.359296997945`

| parameter | selected min | selected q05 | selected median | selected q95 | selected max | reference | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Retau | -9.96663 | -8.76647 | 0.785446 | 9.01292 | 9.95647 | 0.0264409 | inside selected central 5%-95% range |
| Imtau | -0.518218 | -0.287249 | 3.01612 | 4.85146 | 5.98653 | 1.18748 | inside selected central 5%-95% range |
| a2t | -9.75695 | -8.2262 | 2.43142 | 8.2389 | 9.94753 | 1.73016 | inside selected central 5%-95% range |
| a3t | -9.98528 | -9.36093 | 1.85517 | 9.50021 | 9.99192 | 2.76845 | inside selected central 5%-95% range |
| g2t | -9.55054 | -1.10456 | 5.65795 | 9.33955 | 9.99418 | 3.0807 | inside selected central 5%-95% range |
| g3t | -9.98893 | -9.25064 | -0.140122 | 9.24941 | 9.9831 | -1.63133 | inside selected central 5%-95% range |

## Distance To Reference

Exploration:

- Minimum raw distance: `1.7995139927990247`
- Minimum normalized distance: `0.08997569963995124`
- Median normalized distance: `0.7363281114415905`
- Normalized-distance quantiles: `{"0.01": 0.3511511562933424, "0.05": 0.4618204386625573, "0.1": 0.5233040442601844, "0.5": 0.7363281114415905}`
- Closest exploration point: `{"objective": 616814.5234620314, "chi2": 1233629.0469240628, "point": {"Retau": -0.43087968453738235, "Imtau": 0.3502235754017562, "a2t": 2.1222694074348674, "a3t": 1.3211926255726976, "g2t": 3.314170001541264, "g3t": -1.790381557465043}, "raw_distance": 1.7995139927990247, "normalized_distance": 0.08997569963995124}`

Selected:

- Minimum raw distance: `4.159391472601655`
- Minimum normalized distance: `0.20796957363008273`
- Median normalized distance: `0.6592787319617456`
- Normalized-distance quantiles: `{"0.01": 0.3464234972815338, "0.05": 0.40639142706574993, "0.1": 0.4520088670632708, "0.5": 0.6592787319617456}`
- Closest selected point: `{"objective": 3342.681465848959, "chi2": 6685.362931697918, "point": {"Retau": 0.4833406648447518, "Imtau": 3.0219786077878545, "a2t": 1.4450093630623222, "a3t": 1.9231730577362924, "g2t": -0.5113906109027901, "g3t": -1.7969518582532444}, "raw_distance": 4.159391472601655, "normalized_distance": 0.20796957363008273}`

The closest-to-reference points are not low-objective points. The closest
exploration point has chi2 `1233629.0469240628`,
whereas the best exploration chi2 is `861.7066860723836`.

## Best-N Exploration Diagnostics

| N | obj min | obj median | obj max | min d_norm | median d_norm | ref in all envelopes |
| --- | --- | --- | --- | --- | --- | --- |
| 20 | 430.853 | 638.288 | 730.117 | 0.477133 | 0.671141 | True |
| 100 | 430.853 | 966.277 | 1304.61 | 0.354546 | 0.617286 | True |
| 1000 | 430.853 | 3216.37 | 5346.9 | 0.20797 | 0.664809 | True |

## Correlations

Pearson correlations between parameters and objective using all finite
exploration rows:

`{"Retau": -0.0015208551605286672, "Imtau": 0.0036177727523681097, "a2t": -0.0006237369079283265, "a3t": 0.0012879236585300506, "g2t": -0.0009202061286300556, "g3t": 0.0008827189683008368}`

Spearman correlations between parameters and objective using all finite
exploration rows:

`{"Retau": -0.0042153617224197784, "Imtau": -0.03977460002674542, "a2t": -0.004405540439788758, "a3t": 0.002298036731832814, "g2t": -0.1370050494883163, "g3t": 0.010818147704440154}`

Pearson correlations using valid-only exploration rows:

`{"Retau": -0.0020406642105322893, "Imtau": 0.00448080169413176, "a2t": -0.0008350339768204587, "a3t": 0.0017306821098755183, "g2t": -0.0012308680887567276, "g3t": 0.0011844457989960903}`

These correlations are weak/misleading as one-dimensional guidance: the best
region selected by objective is far from the known low-chi2 basin.

## Cluster And Focused-Box Diagnostics

- Number of clusters: `1`
- Noise points: `0`

| cluster | size | best nLL | best chi2 |
| --- | --- | --- | --- |
| 0 | 554 | 430.853 | 861.707 |

| basin | relative volume | contains ref | contains sign-ref |
| --- | --- | --- | --- |
| 0 | 0.496331 | True | True |

Winning box bounds:

```json
{
  "cluster_id": 0,
  "selected_count": 554,
  "best_exploration_target": 430.8533430361918,
  "relative_box_volume": 0.49633128817530386,
  "lower": {
    "Retau": -10.0,
    "Imtau": -2.4327197105876435,
    "a2t": -10.0,
    "a3t": -10.0,
    "g2t": -10.0,
    "g3t": -10.0
  },
  "upper": {
    "Retau": 10.0,
    "Imtau": 7.493906052918435,
    "a2t": 10.0,
    "a3t": 10.0,
    "g2t": 10.0,
    "g3t": 10.0
  },
  "best_fit_fractional_position": {
    "Retau": 0.14999941386327126,
    "Imtau": 0.5699894661365004,
    "a2t": 0.21414424401352578,
    "a3t": 0.04978787041299233,
    "g2t": 0.7439372745997875,
    "g3t": 0.5479893407375193
  },
  "best_fit_original_fractional_position": {
    "Retau": 0.14999941386327126,
    "Imtau": 0.6612676204445008,
    "a2t": 0.21414424401352578,
    "a3t": 0.04978787041299233,
    "g2t": 0.7439372745997875,
    "g3t": 0.5479893407375193
  },
  "width": {
    "Retau": 20.0,
    "Imtau": 9.926625763506078,
    "a2t": 20.0,
    "a3t": 20.0,
    "g2t": 20.0,
    "g3t": 20.0
  },
  "width_fraction": {
    "Retau": 1.0,
    "Imtau": 0.49633128817530386,
    "a2t": 1.0,
    "a3t": 1.0,
    "g2t": 1.0,
    "g3t": 1.0
  },
  "reference_inside": true,
  "sign_degenerate_reference_inside": true,
  "reference_fractional_position": {
    "Retau": 0.5013220445,
    "Imtau": 0.36469549893749525,
    "a2t": 0.5865079563,
    "a3t": 0.6384226753,
    "g2t": 0.6540351876,
    "g3t": 0.41843325189999997
  },
  "sign_degenerate_reference_fractional_position": {
    "Retau": 0.49867792215,
    "Imtau": 0.36469695643174804,
    "a2t": 0.586507927,
    "a3t": 0.6384251356,
    "g2t": 0.6540439977,
    "g3t": 0.41841883175000005
  }
}
```

The reference is inside the focused box, but the relative volume is
`0.49633128817530386`.
This means containment is not localization: the box is still roughly half of
the original six-dimensional volume.

## Focused adaptive_diver Diagnostics

- History entries: `3000`
- Initial best nLL: `2772.765621691613`
- Initial best chi2: `5545.531243383226`
- Final history best nLL: `342.2877134242351`
- Final history best chi2: `684.5754268484702`
- Final adaptive_diver best nLL: `342.28414803808766`
- Final adaptive_diver chi2: `684.5682960761753`
- Final adaptive_diver best point: `{"Retau": -7.000011722734575, "Imtau": 3.225352408890016, "a2t": -5.717115119729485, "a3t": -9.004242591740153, "g2t": 4.878745491995751, "g3t": 0.9597868147503856}`
- Closest final-population point to reference: `{"objective": 370.78323391325057, "chi2": 741.5664678265011, "point": {"Retau": -0.2178054185266749, "Imtau": 3.222893999484076, "a2t": -5.692684240670582, "a3t": -7.2531767851113065, "g2t": 4.971269236303492, "g3t": 1.2958049797472029}, "raw_distance": 13.110173378599479, "normalized_distance": 0.6555086689299738}`
- Closest elite point to reference: `{"objective": 370.76768923925897, "chi2": 741.5353784785179, "point": {"Retau": 1.215090314703616, "Imtau": 3.2225538378034306, "a2t": -5.758039502520918, "a3t": -7.33721304321376, "g2t": 4.966232415923365, "g3t": 1.2767553337780928}, "raw_distance": 13.257611088501914, "normalized_distance": 0.6628805544250957}`

The final population did not move toward the known basin. Even the closest
final-population and elite points remain high chi2 compared with the reference.

## Failure-Stage Conclusion

Failure stage: `exploration_selection`.

The first failure is exploration/selection. The broad Latin-hypercube pass did
not sample an informative point near the known low-chi2 basin. Selection
therefore retained high-chi2 points from a different broad region. Clustering
was not meaningful as a physics-basin identifier because it only clustered that
wrong selected population. The focused box included the reference only because
it was very broad, not because the basin was localized. adaptive_diver then
optimized the wrong broad region.

## Recommended Next Step

Before adding second-stage refocusing, prefer progressive exploration rounds or physically motivated/transformed domains. A larger one-shot exploration budget alone is unlikely to be efficient because the selected population did not contain informative low-chi2 points near the known basin.
