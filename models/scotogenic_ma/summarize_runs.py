"""Compare best fits across seed runs written by run_best_fit.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RUNS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "runs"
OBS = ["m1_raw", "m2_raw", "m3_raw", "scale", "m1_scaled", "m2_scaled", "m3_scaled", "sum_m_scaled", "dm21_scaled", "dm3l_scaled", "s12", "s13", "s23",
       "deltaCP_deg_m180_180", "mbetabeta_scaled", "br_mu_e_gamma", "br_tau_mu_gamma", "oblique_T",
       "m_eta_charged", "m_eta_R", "m_eta_I", "dm_mass_analytic", "yukawa_norm_sq"]
PAR = ["m_eta_sq", "lambda2", "lambda3", "lambda4", "lambda5", "MN1", "MN2", "MN3"]

rows = []
for run in sorted(RUNS.glob("seed_*")):
    best = json.loads((run / "best_fit.json").read_text())
    summ = json.loads((run / "summary.json").read_text())
    s = summ.get("summary", summ)
    rows.append((run.name, best, s))

for name, best, s in rows:
    eng = s.get("engine_details", {})
    print(f"== {name}: chi2 = {best['best_metric_value']:.6g}  evals = {s.get('evaluations')}  "
          f"valid = {s.get('valid_points')}  stop = {eng.get('stop_reason')}  gens = {eng.get('generations')}  "
          f"local_ref = {eng.get('local_refinement_attempts')}")
    terms = {k: round(v, 4) for k, v in best["likelihood_terms"].items() if v != 0.0}
    print("   nonzero terms:", terms)

print("\nparameters")
print("name".ljust(22) + "".join(n.rjust(14) for n, _, _ in rows))
for p in PAR:
    print(p.ljust(22) + "".join(f"{b['parameters'][p]:14.5g}" for _, b, _ in rows))
print("\nobservables")
for o in OBS:
    print(o.ljust(22) + "".join(f"{b['outputs'].get(o, float('nan')):14.5g}" for _, b, _ in rows))
