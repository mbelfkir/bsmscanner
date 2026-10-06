# Corrected Warsaw-basis SMEFT — changes vs `BSMScanner/models/smeft_wilson` (v0.1.0)

Basis: Grzadkowski et al., arXiv:1008.4884. L = L_SM + Σ (C_i/Λ²) Q_i, Λ = 1 TeV fixed, ε = v²/Λ².
Upstream repo untouched.

## Blocking fixes
| ID | Layer | Upstream | Corrected | Source |
|---|---|---|---|---|
| B1 | physics (normalisation) | S = 4ε c_WB | S = 4 s_W c_W ε C_HWB/α (×54) | Han–Skiba hep-ph/0412166 Eq. (16) |
| B2 | physics (normalisation) | κ_g = 1 + ε(c_yt + 12 c_GG) | δκ_g = δκ_t + 4π ε C_HG/(α_s I_g) ≈ δκ_t + 284 ε C_HG | Brivio–Trott 1706.08945 Eq. (A.80), I_g = 0.375 |
| B3 | physics (normalisation + structure) | κ_γ = 1 + ε(c_WW + c_BB − c_WB) | κ_γ = [κ_V A_W + κ_t A_t + (8π/α) ε (c²C_HB + s²C_HW − s c C_HWB)]/A_SM | derived from L_eff = (α A_SM/8πv) h FF; equals Brivio–Trott Eq. (9.9) with I_γ = A_SM/4 (tested) |
| B4 | physics (structure) | μ_ggF = κ_g²κ_h², μ_γγ = κ_γ²κ_h² (no width, no production in μ_γγ) | signal strengths removed; Higgs data enter as κ's | κ framework |

## Material fixes
- `cH` was a SILH-like universal shift, not Warsaw Q_H = (H†H)³. Replaced by C_H□ with the field
  normalisation ε(C_H□ − C_HD/4) (Brivio–Trott Eq. 9.7), which also brings in C_HD.
- Λ removed as a scan parameter (exact flat direction: all observables depend on C_i/Λ² only).
- Yukawa operators: δκ_f = ε(C_H□ − C_HD/4) − ε v C_fH/(√2 m_f) (Brivio–Trott Eq. 9.7; Wells–Zhang
  1512.03056 Eq. C.4); upstream ε c_y_f omitted the v/(√2 m_f) enhancement.
- Parameters now: C_H□, C_HD, C_HWB, C_HG, C_HW, C_HB, (C_uH)₃₃, (C_dH)₃₃, (C_eH)₃₃.
- S, T: PDG 2024 STU fit S = −0.04 ± 0.10, T = 0.01 ± 0.12, ρ = 0.93 as one 2D Gaussian
  (upstream: S = −0.05 ± 0.10, T = 0 ± 0.12 uncorrelated).
- Linear-EFT guard |δκ| < 0.5 added.

## Approximations (documented, not hidden)
- Tree level / LO, linear in C/Λ²; no RG running between Λ and the EW scale.
- κ_W = κ_Z = κ_V: custodial-violating C_HD, C_HWB effects on the Z/W normalisation and the
  {α, G_F, m_Z} input-scheme shifts (C_Hl^(3), C_ll′) are not included in this operator set.
- κ_g: top loop only (bottom interference neglected); h → γγ: W and top loops only.
- m_f in y_f = √2 m_f/v: m_t pole, m_b(m_b), m_τ — sets the normalisation of C_fH.

## Higgs data — INTERIM
κ_V = 1.035 ± 0.031 (ATLAS Nature 607 (2022) 52, text). **Pending:** resolved κ fit with correlations
from HEPData (shared with the 2HDM tutorial). Until then C_HG, C_HW, C_HB, C_fH are bounded only by
the linear-EFT guard, and C_H□ − C_HD/4 by κ_V.

## Validation (`tests/test_smeft_corrected.py`, 8 tests)
SM limit; Han–Skiba S, T and the ×54 regression; LO loop functions (A_W = −8.33, A_t = 1.84, heavy
limits 4/3 and −7); Yukawa maps vs Eq. (9.7); gluon-fusion factor 284; h → γγ matching derived from
the SM width formula and cross-checked against Eq. (9.9); no Λ flat direction; S–T correlation.
