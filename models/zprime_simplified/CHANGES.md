# Corrected Z′ simplified DM model — changes vs `BSMScanner/models/zprime_simplified` (v0.1.0)

Reference model: ATLAS/CMS DM Forum, arXiv:1507.00966, vector mediator, Dirac DM, Eq. (2.1).
Upstream repo untouched.

## Blocking fix
| ID | Layer | Upstream | Corrected |
|---|---|---|---|
| B1 | statistics/physics | "monojet" g_q²g_χ²/(M/TeV)⁴ < 0.2 and "dilepton" g_q²g_ℓ²/(M/TeV)⁴ < 0.02: dimensionless proxies with arbitrary thresholds, contact-interaction scaling (wrong for on-shell mediators) | removed; replaced by the spin-independent DM–nucleon cross section vs the LZ 90 % CL limit |

## Physics
- σ_SI = f² g_χ² μ_nχ²/(π M⁴), f = 3 g_q, m_n = 0.939 GeV (Boveia et al., arXiv:1603.04156,
  Eqs. 4.1–4.2); reproduces their Eq. (4.3) normalisation 6.9×10⁻⁴¹ cm² to < 1 % (tested).
- Width: DM Forum Eq. (2.3) with all quark thresholds (upstream 18 g_q²M/12π ignored m_t: 17 % too
  large below M = 2m_t, tested).
- Leptophobic, as in the Forum benchmark; upstream g_ℓ removed (would be a flat direction, and its
  lepton width counted the neutrinos as full Dirac vector fermions).
- Γ/M < 0.3 kept as a validity cut. `pi_ref`, `resonant_dm_open` removed.

## Data — PENDING
`data/lz_si_limit.csv`: LZ SI 90 % CL limit (arXiv:2410.17036), columns m_χ [GeV], σ [cm²].
`plugins/si_limit.py` interpolates log–log, extrapolates ∝ m_χ above the table, applies no constraint
below it, and raises if the file is missing.

## Statistical caveat
All constraints are vetoes (90 % CL limit, width validity): every allowed point has NLL = 0. The
scan maps the allowed region; there is no best-fit point. A measurement-type term (e.g. the Planck
relic density Ωh² = 0.120 ± 0.001 via micrOMEGAs) would be required for one.

## Validation (`tests/test_zprime_corrected.py`)
Width vs independent Eq. (2.3) at 4 points incl. thresholds; top-threshold regression; σ_SI exact and
vs Eq. (4.3) at 3 points; plugin interpolation/extrapolation/below-range; loud failure without data.

## Packaged layout (BSMScanner 0.1.9)
`model.yaml` excludes the LZ spin-independent limit (arXiv:2410.17036, official data release / HEPData) because its data tables are not shipped, so it runs out of
the box. `model_with_direct_detection.yaml` imports `model.yaml` plus `constraints/direct_detection.yaml`; supply the tables listed in
`data/README.md` to use it. `run_best_fit.py` selects the variant with its `--with-*` flag.
