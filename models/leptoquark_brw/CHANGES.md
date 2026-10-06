# S1 leptoquark — replaces `BSMScanner/models/leptoquark_brw` (v0.1.0)

Upstream repo untouched. The upstream benchmark could not be corrected in place: it specified no
leptoquark representation (couplings `yeq, ymuq, ytauq` to an unspecified quark and `ybnu`), so no
flavour observable was computable, and all four constraints were hard cuts on dimensionless proxies
with arbitrary thresholds (NLL = 0 everywhere).

## Model
S1 ~ (3̄, 1, 1/3) (Buchmüller–Rückl–Wyler class), L = y_L^{ij} Q̄^C_i iτ₂ L_j S1 + y_R^{ij} ū^C_i e_j S1 + h.c.
(Angelescu et al. arXiv:1808.08179 Eq. 25). Real couplings to the third lepton generation:
y_L^{33} (b–ν_τ, t–τ), y_L^{23} (s–ν_τ, c–τ), y_R^{23} (c–τ_R); mass M_S1 ∈ [0.5, 10] TeV.

## Observables and sources
| Observable | Formula | Source |
|---|---|---|
| g_VL, g_SL = −4g_T at M_S1 | v² y^{bτ}(V y*)^{cτ}/(4V_cb M²), −v² y^{bτ}y_R^{cτ*}/(4V_cb M²) | Angelescu et al. Eqs. (26)–(27) |
| running to m_b | C_VL invariant; (C_SL, C_T)(m_b) = [[1.752, −0.287], [−0.004, 0.842]] (C_SL, C_T)(1 TeV) | Blanke et al. 1811.09603 Eq. (13); reproduces g_SL ≈ −8.5 g_T (tested) |
| R(D), R(D*) | Blanke et al. Eqs. (16)–(17) × SM | HFLAV SM: 0.296 ± 0.004, 0.254 ± 0.005 |
| b → sνν̄ | c_NP = v² y^{bτ}y^{sτ*}/(2M²), c_SM = αλ_t C_L^SM/π, C_L^SM = −6.35; R_νν = [2 + (1 + c_NP/c_SM)²]/3 | Doršner et al. 1603.04993 Table 5, Sec. 3.2.4 |
| B⁺ → K⁺νν̄ | 4.97×10⁻⁶ R_νν + 0.61×10⁻⁶ (long-distance τ part not rescaled) | Belle II 2311.14647 Eq. (1) |
| B_c lifetime | g_P(m_b) = −g_SL(m_b) ∈ (−1.14, 0.68) | Angelescu et al. Eq. (12), B(B_c→τν) < 30 % |
| S1 widths/BRs | |y|² M/(16π)(1 − m_q²/M²)² per chiral channel; tτ, bν, cτ, sν | standard; CKM ≈ 1 in decays |

## Likelihood
- R(D), R(D*): HFLAV 2411.18639 Fig. 27 average 0.342 ± 0.026, 0.287 ± 0.012, ρ = −0.39 (2D Gaussian,
  SM uncertainties added in quadrature). Note: the HFLAV summary table quotes R(D*) = 0.286 and
  Fig. 27 an SM R(D) of 0.298; the figure's average and the text's SM values are used.
- B⁺ → K⁺νν̄: Belle II (2.3 ± 0.5 +0.5/−0.4)×10⁻⁵, asymmetric Gaussian (stat ⊕ syst).
- Hard cuts: B_c lifetime, Γ/M < 0.2.
- **LHC pair production — PENDING data**: `constraints/lhc_pair.yaml` + `plugins/lhc_pair.py`,
  σ(M) BR_c² < σ_lim,c(M) per channel (tτ, bν, cτ, sν), needs `data/lhc_pair/*.csv` (HEPData).

## Approximations
Real couplings (no CP phases, so the imaginary-g_SL solutions are not covered); running matrix from
1 TeV applied at M_S1; CKM ≈ 1 in LQ decay vertices; only same-channel pair limits (no mixed).

## Validation (`tests/test_s1_corrected.py`, 10 tests)
SM limit (R_D, R_D*, B → Kνν̄ reproduce the SM inputs); all flavour observables vs an independent
re-implementation at 3 points; running ratio −8.5; b → sνν̄ interference sign; BR sum and tτ/bν
phase-space ratio; B_c cut fires on a width-allowed point; LHC plugin synthetic tables and failure.

## Packaged layout (BSMScanner 0.1.9)
`model.yaml` excludes the LHC S1 pair-production limits (HEPData) because its data tables are not shipped, so it runs out of
the box. `model_with_lhc_pair.yaml` imports `model.yaml` plus `constraints/lhc_pair.yaml`; supply the tables listed in
`data/README.md` to use it. `run_best_fit.py` selects the variant with its `--with-*` flag.
