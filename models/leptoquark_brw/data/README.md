# External data for the LHC S1 pair-production limits (HEPData)

These tables are **not shipped** (they are not redistributed here), so `model.yaml` runs
*without* this constraint. To include it, place the files below in this directory
(two columns: mass [GeV], cross section [fb]) and run `model_with_lhc_pair.yaml` instead of `model.yaml`:

- `lhc_pair/sigma_pair_nnlo.csv -- theory sigma(pp -> S1 S1*) at 13 TeV [fb] vs mass [GeV] (NNLO+NNLL)`
- `lhc_pair/limit_ttau.csv, limit_bnu.csv, limit_ctau.csv, limit_snu.csv -- observed 95 % CL limits on sigma x BR^2 [fb] vs mass [GeV] for the t tau, b nu, c tau, s nu final states`

Without the files, `model_with_lhc_pair.yaml` fails with an explicit `FileNotFoundError` on the first
evaluation -- there is deliberately no silent fallback. See `constraints/lhc_pair.yaml` and `plugins/` for the
exact use, and `CHANGES.md` for the physics.
