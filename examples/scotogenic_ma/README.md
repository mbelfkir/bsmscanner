# Scotogenic Ma model

This example wraps the implementation in `models/scotogenic_ma`.

Reference:

```text
E. Ma, Verifiable Radiative Seesaw Mechanism of Neutrino Mass and Dark Matter,
Phys. Rev. D 73, 077301 (2006), arXiv:hep-ph/0601225.
```

The current manifest implements the analytic one-loop neutrino-mass sector,
inert-doublet scalar spectrum, perturbativity and bounded-from-below checks,
and normal-ordering oscillation likelihoods. Relic-density and direct-detection
observables require an external dark-matter backend and are intentionally not
approximated in this declarative model.

Run a small scan from the repository root:

```bash
python examples/scotogenic_ma/run_scan.py \
  --model examples/scotogenic_ma/model_no.yaml \
  --run-dir examples/scotogenic_ma/runs/normal
```
