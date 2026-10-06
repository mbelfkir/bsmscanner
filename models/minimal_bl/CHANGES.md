# Corrected minimal B−L model — changes vs `BSMScanner/models/minimal_bl` (v0.1.0)

Reference: L. Basso, S. Moretti, G. M. Pruna, arXiv:1106.4462 (BMP below). Upstream repo untouched.

## Verified unchanged (BMP equations)
- M_Z′ = 2 g′₁ x (2.25); M_N = √2 y^M x (2.35); `vBL` ≡ x with ⟨χ⟩ = x/√2.
- λ₁, λ₂, λ₃ from (m_h1, m_h2, α), Eqs. (2.31)–(2.33); test reproduces the spectrum through (2.26)–(2.30).
- LEP-II contact bound M_Z′/g′₁ ≥ 7 TeV (3.2).

## Blocking fix
| ID | Layer | Upstream | Corrected | Evidence |
|---|---|---|---|---|
| B1 | physics | Γ_Z′/M_Z′ = g′²/(12π) (one unit-charge Dirac channel) | Eq. (3.7) summed over quarks (C_f Q² = 1/3 each), charged leptons, light Majorana ν (½ each), heavy Majorana N (½ β³ each), with all mass thresholds | massless limits 13g′²/(24π) (N closed) and 8g′²/(12π) (N open); BR(Z′→ee) = 1/6.5–1/8 = 15.4–12.5 %, the range quoted in BMP §3.1; Γ/M < 0.1 now excludes g′ ≳ 0.7, upstream allowed up to 1.94 |

## Updated / added physics
- **Higgs signal strength:** μ = cos²α · cos²α Γ_SM /(cos²α Γ_SM + Γ_exotic), with
  Γ(h₁→N N) = sin²α M_N² m_h β³/(16π x²) (Majorana, from Eq. 2.10 with χ = (x+h′)/√2) and
  Γ(h₁→Z′Z′) = sin²α m_h³/(32π x²)(1−4r+12r²)√(1−4r), r = M_Z′²/m_h². The Z′Z′ channel opens for
  M_Z′ < m_h/2 (allowed by the scan: M_Z′ ≥ 7 GeV) and reaches BR ≈ 3 % at x = 3.5 TeV, sin α = 0.3.
  Γ_SM = 4.088 MeV (LHC HXSWG YR4).
- **μ input:** 1.025 ± 0.06 from ATLAS 1.05 ± 0.06 (Nature 607, 52) and CMS 1.002 ± 0.057
  (Nature 607, 60); inverse-variance mean, σ kept at 0.06 because the signal-theory systematics are
  common and no official combination exists (assumption).
- **LHC dilepton Z′ limit** (`constraints/lhc_dilepton.yaml`, `plugins/lhc_dilepton.py`):
  σB(Z′_B−L→ℓℓ)/σB_limit = r_prod · BR_B−L(ee) · σ_SSM(M)/σB_limit(M), using the ATLAS 139 fb⁻¹
  Z′_SSM theory curve and observed limit (arXiv:1903.06248). LO narrow-width ratio
  r_prod = (4g′²/9g_Z²)(L_u+L_d)/(c_u L_u + c_d L_d) with R_ud = L_u/L_d = 3; the factor varies by
  ±2.5 % for R_ud ∈ [2, 5] (tested). Limitations: SSM-like width assumed by the limit (B−L up to 10 %);
  no constraint outside the tabulated 250 GeV–6 TeV. **Requires the HEPData tables in
  `data/atlas_dilepton_139/` (`ssm_theory.csv`, `observed_limit.csv`); the plugin raises if absent.**
- Perturbativity of λ₁, λ₂, λ₃ added; BFB condition written as BMP (2.11)–(2.12)
  (identically satisfied for couplings inverted from physical masses; kept as a numerical guard).
- Removed unused `h2_to_zpzp_open` and `pi_ref` (built-in `pi` used).

## Validation (`tests/test_minimal_bl_corrected.py`)
14 pass, 1 skipped until the ATLAS tables are present: masses; scalar-spectrum round trip; Z′ width
massless limits, BRs and a generic threshold point vs an independent sum; narrow-width regression;
μ in the decoupling limit and with h₁→NN, Z′Z′ vs independent formulas; SSM couplings and
BR(Z′_SSM→ee) ≈ 3.08 %; production-ratio insensitivity; plugin interpolation and loud failure.

## Statistical caveat (unchanged by these fixes)
μ ≤ cos²α ≤ 1 while the measurement is 1.025, so the likelihood is minimised at sin α = 0 with
Δχ²-like NLL = 0.087; g′, x, m_h2 and y_N enter only through vetoes (LEP, narrow width, dilepton).
The minimum is therefore a flat region, not a point: this model maps an allowed region.

## Packaged layout (BSMScanner 0.1.9)
`model.yaml` excludes the ATLAS dilepton Z' limit (arXiv:1903.06248, HEPData) because its data tables are not shipped, so it runs out of
the box. `model_with_lhc_dilepton.yaml` imports `model.yaml` plus `constraints/lhc_dilepton.yaml`; supply the tables listed in
`data/README.md` to use it. `run_best_fit.py` selects the variant with its `--with-*` flag.
