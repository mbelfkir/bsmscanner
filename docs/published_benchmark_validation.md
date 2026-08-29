# Published Benchmark Validation

This note records the validation status of the published benchmark models added
for the BSMScanner manuscript study. It separates formula-level validation from
future external-backend validation.

## Scope

The current YAML implementations are validated as analytic benchmark models.
They are not yet validated as replacements for dedicated collider, dark-matter,
or EFT global-fit tools. In particular, collider rates, relic density, direct
detection, and detailed likelihood maps should be connected through plugins
before making final physics claims.

## Source Map

| Model | Reference | Implemented Source-Faithful Core | Current Proxy Layer |
| --- | --- | --- | --- |
| Scotogenic Ma | E. Ma, Phys. Rev. D 73, 077301 (2006), hep-ph/0601225 | Inert scalar masses from Eqs. 8-10; one-loop neutrino mass from Eq. 11; exact Z2-odd spectrum logic. | Oscillation likelihoods use local NuFit-style tables; DM relic/direct detection deferred. |
| Minimal B-L | L. Basso, S. Moretti, G. M. Pruna, arXiv:1106.4462 | \(M_{Z'}=2 g'_1 x\), heavy-neutrino masses from singlet Yukawas, LEP contact-scale bound \(M_{Z'}/g'_1 \ge 7\) TeV. | Higgs mixing and width are simplified analytic proxies. |
| 2HDM | G. C. Branco et al., Phys. Rept. 516 (2012); benchmark planes from arXiv:1507.04281 | CP-conserving mass variables, alignment limit \(g_{hVV}/g_{SM}=s_{\beta-\alpha}\), Scenario-A-style non-alignment inputs. | Quartics, stability, and \(T\) are lightweight proxies pending 2HDMC/HiggsBounds checks. |
| SMEFT Warsaw | B. Grzadkowski et al., JHEP 10 (2010), arXiv:1008.4884 | Warsaw-basis Wilson-coefficient parameterization and \(v^2/\Lambda^2\) expansion variable. | Higgs and oblique shifts are compact proxies pending `wilson`/`flavio`/SMEFiT integration. |
| Zprime simplified DM | ATLAS/CMS DM Forum, arXiv:1507.00966 | Vector-mediator benchmark structure, forum coupling choice \(g_q=0.25, g_\chi=1\), mediator/DM mass scan. | Width and monojet/dilepton rate proxies pending event generation. |
| BRW leptoquark | W. Buchmuller, R. Ruckl, D. Wyler, Phys. Lett. B 191 (1987) | Scalar leptoquark mass and lepton-quark Yukawa scan structure. | Pair-production, contact, and LFV constraints are proxies pending dedicated collider/flavor likelihoods. |
| ALP EFT | J. Jaeckel, A. Ringwald, Ann. Rev. Nucl. Part. Sci. 60 (2010) | Effective ALP couplings and \(\Gamma(a\to\gamma\gamma)\propto g_{a\gamma}^2 m_a^3\). | Search constraints are simple coupling/rate proxies pending exclusion-curve interpolation. |

## Executable Checks

The regression file `tests/test_published_benchmark_validation.py` checks:

- every model loads, compiles, and exposes required outputs at its default point
- Scotogenic neutrino masses vanish when \(\lambda_5=0\)
- Minimal B-L reproduces \(M_{Z'}=2g_{BL}v_{BL}\) and the contact scale
- 2HDM alignment gives unit Higgs signal strength
- SMEFT zero Wilson coefficients return the SM-limit observables
- Zprime forum coupling benchmark gives the expected width/rate proxies
- Leptoquark zero couplings decouple contact and LFV proxies
- ALP zero couplings decouple visible coupling proxies

## Reproduced Known Results

The following values are reproduced by the executable validation tests in the
current environment after rebuilding the native extension.

| Model check | Input point | Reproduced outputs |
| --- | --- | --- |
| Scotogenic Ma scaling | `lambda5 = 1.0e-8` | `inert_neutral_splitting = 9.44348414578e-07`, `loop_N1 = 6.65900549266e-09`, `m1 = 0.00116684158739`, `m2 = 0.00733646689193`, `m3 = 0.0146783234791` |
| Scotogenic Ma scaling | `lambda5 = 1.0e-12` | `inert_neutral_splitting = 9.44169187278e-11`, `loop_N1 = 6.65970689742e-13`, `m1 = 1.16699719117e-07`, `m2 = 7.33256081003e-07`, `m3 = 1.46769874154e-06` |
| Minimal B-L identity | `gBL = 0.2`, `vBL = 10000`, `sin_alpha = 0` | `MZprime = 4000`, `contact_scale = 20000`, `HeavyNeutrino1Mass = 141.421356237`, `HiggsSignalStrength = 1` |
| 2HDM alignment | `cos_ba = 0`, `mH = 300`, `mA = 500`, `mHp = 500` | `HiggsSignalStrength = 1`, `ObliqueTProxy = 0` |
| SMEFT SM limit | all Wilson coefficients at default zero | `ObliqueSProxy = 0`, `ObliqueTProxy = 0`, `HiggsMuGGFProxy = 1`, `HiggsMuGammaGammaProxy = 1` |
| Zprime forum point | `MZp = 1000`, `mchi = 10`, `gq = 0.25`, `gchi = 1`, `gl = 0` | `WidthFractionProxy = 0.0563673740866`, `MonojetRateProxy = 0.0625`, `DileptonRateProxy = 0`, `ResonantDMOpen = 1` |
| BRW leptoquark decoupling | all leptoquark Yukawas set to zero | `WidthFractionProxy = 0`, `ElectronContactProxy = 0`, `MuonContactProxy = 0`, `MuEFlavorProxy = 0` |
| ALP decoupling | `cgam = cgg = cee = cmumu = 0` | `PhotonCoupling = 0`, `GluonCoupling = 0`, `ElectronCoupling = 0`, `MuonCoupling = 0`, `GluonColliderProxy = 0`, `EFTValidityRatio = 1.0e-6` |

## Required External Validation Before Publication Claims

- Scotogenic Ma: compare loop matrix, LFV observables, relic density, and direct
  detection against a SARAH/SPheno or micrOMEGAs implementation.
- Minimal B-L: compare \(Z'\) widths and branching ratios against CalcHEP,
  MadGraph, or the original B-L implementation.
- 2HDM: compare scalar spectrum, unitarity, stability, and Higgs constraints
  against 2HDMC plus HiggsBounds/HiggsSignals.
- SMEFT: compare Wilson-coefficient predictions against `wilson`, `flavio`,
  SMEFTsim, or SMEFiT conventions.
- Zprime simplified DM: validate widths and signal rates through the ATLAS/CMS
  DM Forum UFO/MadGraph setup.
- Leptoquark: validate collider and flavor likelihoods with a dedicated BRW
  implementation or public reinterpretation tables.
- ALP: replace proxy hard cuts with interpolated exclusion curves or a public
  ALP recast package.
