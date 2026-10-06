# External data for the ATLAS dilepton Z' limit (arXiv:1903.06248, HEPData)

These tables are **not shipped** (they are not redistributed here), so `model.yaml` runs
*without* this constraint. To include it, place the files below in this directory
(two columns: mass [GeV], value [fb]) and run `model_with_lhc_dilepton.yaml` instead of `model.yaml`:

- `atlas_dilepton_139/ssm_theory.csv -- sigma x B(Z'_SSM -> l l) [fb] vs mass [GeV], ATLAS theory curve`
- `atlas_dilepton_139/observed_limit.csv -- observed 95 % CL upper limit on sigma x B(l l) [fb] vs mass [GeV]`

Without the files, `model_with_lhc_dilepton.yaml` fails with an explicit `FileNotFoundError` on the first
evaluation -- there is deliberately no silent fallback. See `constraints/lhc_dilepton.yaml` and `plugins/` for the
exact use, and `CHANGES.md` for the physics.
