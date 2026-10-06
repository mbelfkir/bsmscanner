# Corrected scotogenic Ma model — changes vs `BSMScanner/models/scotogenic_ma` (v0.1.0)

Source copied from BSMScanner commit `1517934` (bsm-scanner 0.1.6). The upstream repo is untouched.

## Blocking fixes

| ID | Layer | Upstream | Corrected | Evidence |
|----|-------|----------|-----------|----------|
| B1 | software | `deltaCP_deg` in [0, 360) fed to NuFIT table on [-180, 180] → every δ > 180° hit the 1e6 out-of-range cap (4/8 test points) | likelihood reads the core `deltaCP_deg_m180_180` ∈ [-180, 180] (added to `core/neutrino/observables_common.yaml`); `deltaCP_deg_0_360` and alias `deltaCP_deg` kept as outputs | `test_casas_ibarra_reference_point` (δ = -130°: finite table term) |
| B2 | maths | `method: svd_complex` on a complex-symmetric Majorana matrix: U_svd = U*·(arbitrary phases) → δ reported as −δ, α21/α31 meaningless, m_ββ wrong up to ×2.5 | `diagonalize: true` on the `majorana_mass` matrix → automatic Takagi (Uᵀ M U = diag(m) ≥ 0), node `diag__neutrino` read by the core PMNS blocks | Casas–Ibarra reference: m_i (rtol 1e-9), s_ij (1e-10), δ, α21, α31 (1e-6 deg), m_ββ (1e-9) recovered |
| B3 | physics | Ma Eq. (11) prefactor 1/(16π²) | 1/(32π²) | Merle & Platscher arXiv:1507.06314 (text after Eq. 6): factor ½ from η⁰ = (η_R + iη_I)/√2. Independent derivation: each real scalar couples as h/√2 → h_i h_j M/(32π²)[B₀(m_I) − B₀(m_R)]. Toma & Vicente 1312.2840 Eq. (6) inherits Ma's 1/(16π²). |

Consequence of B3: for the same h, M_ν halves; the physical Yukawas are √2 × the upstream fitted values.
The oscillation-only χ²_min is invariant under this rescaling (up to the ±3 bounds and the Σ|h|² < 36π guard), but any Yukawa-dependent observable (LFV, DM, colliders) is not.

## Neutrino observables from the BSMScanner core

The model defines no neutrino observables of its own. Like `radiative_neutrino`, it imports
`core:neutrino/constants_normal.yaml`, `core:neutrino/observables_common.yaml` and
`core:neutrino/observables_normal.yaml`, and the likelihoods read the core NuFIT tables
`core:data/nufit/Normal/*.csv` (byte-identical to the former local copies, which were removed).
Core names used: `s12`, `s13`, `s23`, `deltaCP_deg_m180_180`, `log10_dm21`, `dm3l_meV`, `sum_m`,
`mbeta`, `mbetabeta`, `alpha21_deg`, `alpha31_deg`.

**Mass-scale convention (read before interpreting fits).** The core defines
`m_i = scale · m_i_raw` with `scale = sqrt((bf_dm21/dm21_raw + bf_dm3l/dm3l_raw)/2)`, i.e. the
overall mass scale is anchored to the NuFIT best fit. The scotogenic prediction itself is
`m*_raw` (GeV singular values, saved as outputs). Consequently `dm21`, `dm3l`, `sum_m`, `mbeta`,
`mbetabeta` are the anchored values; the oscillation likelihood constrains the mixing and the
ratio dm21/dm3l, not the absolute scale set by λ5, h and M_k (see the comment on `scale` in
`observables_common.yaml`). The loop normalisation (B3) therefore matters for the Yukawa-dependent
terms (LFV) and for `m*_raw`, not for the oscillation χ².

## Convention documentation (M1)

- Potential: `V ⊃ λ1|Φ|⁴ + λ2|η|⁴ + λ3|Φ|²|η|² + λ4|Φ†η|² + (λ5/2)[(Φ†η)² + h.c.]`, v = 246.22 GeV.
  λ3, λ4, λ5 are identical to Ma Eq. (6); **λ1, λ2 are half of Ma's** (Ma has ½λ1, ½λ2). New outputs `lambda1_ma`, `lambda2_ma`.
- Masses: m²(η±) = m₂² + ½λ3 v², m²_{R,I} = m₂² + ½(λ3 + λ4 ± λ5) v² — Ma Eqs. (8)–(10) with v_Ma = v/√2.
- Boundedness from below is convention-invariant (unchanged). Perturbativity |λ| < 4π is now applied to Ma-normalised λ1, λ2.
- Yukawa: `h_{αk}(ν_α η⁰ − ℓ_α η⁺)N_k`, α = flavour; M_ν = h Λ hᵀ; PMNS = Takagi U.
- Objective: every likelihood term is a **Δχ²** (NuFIT tables are Δχ²; Gaussian terms use σ/√2 because BSMScanner's `gaussian` returns z²/2). The scanner stores the sum as `total_nll`, but it is a χ². `de_weighted` statistics (which treat the metric as χ²) are consistent; an MCMC run with `objective: nll` would over-weight the likelihood by a factor 2.

## Added constraints (M2–M4)

| Constraint | Implementation | Source |
|---|---|---|
| μ→eγ | hard cut BR < 1.5×10⁻¹³ (90% CL) | MEG II 2025, arXiv:2504.15711 |
| τ→eγ, τ→μγ | hard cuts 3.3×10⁻⁸, 4.2×10⁻⁸ | BaBar arXiv:0908.2381; Belle arXiv:2103.12994 |
| LFV formula | A_D = Σ_k h*_{βk} h_{αk} F₂(M_k²/m²_η±)/(32π² m²_η±), BR = 3(4π)³α/(4G_F²)\|A_D\|² BR(ℓ→ℓνν̄) | Toma & Vicente 1312.2840 Eqs. (13)–(14), (A1) |
| Oblique T | Gaussian T = 0.00 ± 0.06, T = [F(m±,m_R)+F(m±,m_I)−F(m_R,m_I)]/(16π²α(M_Z)v²) | PDG 2024 Eq. (10.99b) (U = 0 fit); Barbieri–Hall–Rychkov hep-ph/0603188 |
| Charged relic | fatal check m_η± > lightest neutral Z2-odd mass | exact Z2 ⇒ lightest odd state stable |
| LEP | m_R + m_I > m_Z; m_η± + min(m_R,m_I) > m_W; m_η± > 70 GeV; LEP II box (m_light < 80, m_heavy < 100, Δm > 8 GeV) excluded | Pierce & Thaler hep-ph/0703056; Lundström, Gustafsson, Edsjö arXiv:0810.3924 |

## Numerical changes

- `ma_term(r) = r ln r/(r−1)` with a Taylor branch for |r−1| < 1e-6 (removable singularity); the ineffective absolute `loop_eps` fatal check was removed.
- `lfv_F2` uses its series about x = 1 for |x−1| < 0.02 (direct form loses ~1e-16/(x−1)⁴).
- `oblique_F` uses m₁²ε²/6 for |ε| < 1e-4 (degenerate R/I limit at small λ5).

## Validation (`tests/test_scotogenic_corrected.py`, 26 tests, all passing)

- Loop kernel = ½ × Ma Eq. (11) vs 50-digit mpmath; small-λ5 cancellation (λ5 = 1e-4, 1e-8, 1e-12) within the predicted round-off bound; m_R = M_k removable singularity.
- Casas–Ibarra reference points (3 phase sets, complex orthogonal R) through the production evaluator.
- LFV BRs vs mpmath Toma–Vicente for ξ = M²/m²_η± across 0.0085, ≈1, 1.002, 1.033, 2.4×10⁴ (both F₂ branches).
- T vs mpmath (4 points), custodial limit T → 0, small-splitting BHR approximation (2%).
- Vetoes: charged-relic, LEP II box, MEG II.

Run: `pytest -q models/scotogenic_ma/tests` (also collected by the repository `pytest`).

## Not done / residual risks

- No DM relic density or direct detection (needs micrOMEGAs; BSMScanner 0.1.6 has a generic plugin). `dm_mass_analytic` is a label only.
- Inert-doublet S parameter neglected (O(10⁻²)); T is used alone with the U = 0 marginal.
- μ→3e and μ–e conversion not included (Toma & Vicente show they can be competitive).
- NuFIT version of `core:data/nufit/Normal/*.csv` is not recorded upstream — provenance unknown.
- LFV/LEP bounds are hard cuts → invalid points (penalty 1e12), i.e. walls in the objective; the smoke scan (768 evals) had 434 invalid points, mostly BFB, charged-relic, Σm_ν and MEG II.
- Parameter defaults unchanged; with B3 the default point's masses are half the upstream values.
