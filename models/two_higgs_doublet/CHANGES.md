# Corrected Type II 2HDM — changes vs `BSMScanner/models/two_higgs_doublet` (v0.1.0)

Reference: G. C. Branco et al., Phys. Rept. 516 (2012) 1, arXiv:1106.0034. Upstream repo untouched.
Potential (Branco Eq. 1): ½λ₁|Φ₁|⁴ + ½λ₂|Φ₂|⁴ + λ₃|Φ₁|²|Φ₂|² + λ₄|Φ₁†Φ₂|² + ½λ₅[(Φ₁†Φ₂)² + h.c.],
v = 246.22 GeV, M² = m₁₂²/(s_β c_β), β−α ∈ [0, π] from cos(β−α), α = β − atan2(s_βα, c_βα).

## Blocking fixes
| ID | Layer | Upstream | Corrected | Evidence |
|---|---|---|---|---|
| B1 | physics | λ₁ = λ₂ = (m_h²+m_H²−M²)/v², λ₃ = (2m²_H±−M²)/v² (no α, β dependence; exact only at tan β = 1 and alignment) | full inversion λ₁ = [m_H²c_α²+m_h²s_α²−M²s_β²]/(v²c_β²), λ₂ = [m_H²s_α²+m_h²c_α²−M²c_β²]/(v²s_β²), λ₃ = [(m_H²−m_h²)s_αc_α/(s_βc_β)+2m²_H±−M²]/v² | rebuilt CP-even, CP-odd, charged mass matrices reproduce (m_h, m_H, α, m_A, m_H±) to 1e-9 at 4 points; default point λ₁ = 4.2 vs proxy 1.25 |
| B2 | physics | "stability" = λ₁,₂ > −4π, λ₃ + √\|λ₁λ₂\| > −4π | Branco Eq. (176): λ₁,λ₂ > 0, λ₃ > −√(λ₁λ₂), λ₃+λ₄−\|λ₅\| > −√(λ₁λ₂) | agrees with brute-force minimum of V₄/\|φ\|⁴ over 4×10⁴ random field directions on 4 coupling sets |
| B3 | physics/units | T = (m_H±−m_A)(m_H±−m_H)/(1600π v) [GeV] | Branco Eq. (388)–(389), CP-conserving, incl. c_βα terms with h, H and the Z/W subtraction | numpy re-implementation (4 points), custodial limit T = 0, small-splitting approximation (5 %); ≈20× larger than the proxy |

## Material fix: Type II Yukawa sector
- κ_V = s_βα, κ_u = c_α/s_β, κ_d = κ_ℓ = −s_α/c_β (Branco Table 2); tested against the exact identities
  κ_u = s_βα + c_βα/tan β, κ_d = s_βα − c_βα tan β.
- Upstream used μ = sin²(β−α) (fermion couplings SM-like, no Yukawa type).

## Constraints
- Tree-level perturbative unitarity, |eᵢ| < 8π on the 12 scattering eigenvalues
  (Kanemura–Kubota–Takasugi; Akeroyd–Arhrib–Naimi hep-ph/0006035); replaces |λᵢ| < 4π.
  Single-doublet check: 3λ < 8π normalisation.
- T: PDG 2024 (U = 0) T = 0.00 ± 0.06 (Eq. 10.99b); upstream 0 ± 0.08. S not implemented.
- B → X_sγ, Type II: M_H± > 800 GeV (95 % CL), Misiak–Rehman–Steinhauser JHEP 06 (2020) 175,
  arXiv:2002.01548 §3 (replaces the 130 GeV placeholder).
- **Higgs couplings — INTERIM:** κ_V = 1.035 ± 0.031 from the text of ATLAS Nature 607 (2022) 52
  (κ_V–κ_F fit, κ_F profiled). The universal κ_F is not used (not a Type II quantity).
  **Pending:** resolved κ fit (κ_W, κ_Z, κ_t, κ_b, κ_τ; B_inv = B_u = 0) with correlations from
  HEPData, as a `multivariate_gaussian` in `constraints/higgs_kappa.yaml`.

## Not included
S and U; direct H/A/H± searches (e.g. H/A → ττ at large tan β, A → Zh); B_s → μμ, B → τν;
global vacuum stability (only boundedness from below); RGE running of the quartics.

## Reachability: soft-mass parameterisation and scan engine
- With the corrected couplings, boundedness from below and unitarity confine M² to a window of
  width ~ v²/tan²β just below m_H² (alignment: λ₁ = [m_h² + (m_H²−M²)tan²β]/v²). Under the
  upstream prior (m₁₂² flat in [0, 10⁶] GeV²) only 1 in 2×10⁵ random points is valid.
- `m12sq` is replaced as a scan variable by `delta_soft` ≡ (m_H² − M²) tan²β / v² ∈ [−0.3, 8]
  (= λ₁ − m_h²/v² at alignment; spans BFB to unitarity). m₁₂² is a derived output. This changes
  the prior (relevant for weighted/posterior statistics, not for the best fit).
- Valid fraction under the new priors: 1.4×10⁻⁴ (50k-point test), still too small for a 128-member
  random DE population (observed 0/1418 valid, stall). The scan uses `basin_scan`: 4×10⁵-point
  Latin-hypercube exploration, DBSCAN on valid points, adaptive_diver in focused boxes seeded
  with them.

## Cleanup
Removed `pi_ref` (built-in `pi`) and the unused `beta` duplicate; scan engine switched from
`serial_random` (2000 evaluations) to `adaptive_diver` for best-fit searches.
