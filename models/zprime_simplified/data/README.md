# External data for the LZ spin-independent limit (arXiv:2410.17036, official data release / HEPData)

These tables are **not shipped** (they are not redistributed here), so `model.yaml` runs
*without* this constraint. To include it, place the files below in this directory
(two columns: m_chi [GeV], sigma_SI [cm^2]) and run `model_with_direct_detection.yaml` instead of `model.yaml`:

- `lz_si_limit.csv -- 90 % CL upper limit on sigma_SI [cm^2] vs m_chi [GeV]`

Without the files, `model_with_direct_detection.yaml` fails with an explicit `FileNotFoundError` on the first
evaluation -- there is deliberately no silent fallback. See `constraints/direct_detection.yaml` and `plugins/` for the
exact use, and `CHANGES.md` for the physics.
