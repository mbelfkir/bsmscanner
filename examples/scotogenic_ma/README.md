# Scotogenic Ma model

This example wraps the corrected implementation in `models/scotogenic_ma`
(see its `CHANGES.md` for every fix and source).

Reference:

```text
E. Ma, Verifiable Radiative Seesaw Mechanism of Neutrino Mass and Dark Matter,
Phys. Rev. D 73, 077301 (2006), arXiv:hep-ph/0601225.
```

The model implements the one-loop neutrino-mass matrix (with the 1/(32 pi^2)
normalisation of Merle and Platscher, arXiv:1507.06314, diagonalized by a Takagi
factorization), the inert-doublet scalar spectrum, perturbativity and
bounded-from-below checks, NuFIT oscillation likelihoods through the core
`core:neutrino` blocks, and mu -> e gamma, tau -> e gamma, tau -> mu gamma,
oblique T and LEP constraints. Relic density and direct detection are not part
of the fit; they need an external dark-matter backend.

Run a scan from the repository root:

```bash
python examples/scotogenic_ma/run_scan.py \
  --model examples/scotogenic_ma/model_no.yaml \
  --run-dir examples/scotogenic_ma/runs/normal
```

## Running

Quick demonstration of the mechanics (a few seconds; random sampling, **not** a fit):

```bash
python examples/scotogenic_ma/run_scan.py --model examples/scotogenic_ma/model_no.yaml --quick --run-dir examples/scotogenic_ma/runs/quick
```

Without `--quick` the model's own `scan.yaml` runs, which is the full best-fit search used for the
reference results in `models/scotogenic_ma/results/`: up to 4000 generations of 256 individuals; the reference runs used 0.6-1.0 million evaluations. Expect well over half an hour and several hundred MB of output (a test run of the full search was still going, with a 350 MB point file, when stopped after 30 minutes).

```bash
python examples/scotogenic_ma/run_scan.py --model examples/scotogenic_ma/model_no.yaml --run-dir examples/scotogenic_ma/runs/best_fit
```
