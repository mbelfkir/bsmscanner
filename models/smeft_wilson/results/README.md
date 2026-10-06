# Reference best-fit runs

Finished scans of `smeft_wilson` made with `../run_best_fit.py` during the review of this model.
Only `best_fit.json` (best point and objective), `summary.json` (run summary) and
`metadata.json` (scan configuration) are kept; the full point lists are omitted for size.

`interim_kappaV_*` was run with the INTERIM Higgs-coupling constraint (kappa_V only) described in `../CHANGES.md`.

`tests/test_tutorial_reference_results.py` re-evaluates every `best_fit.json` through the
shipped model and checks that the stored objective is reproduced, so these results cannot
drift from the model. The tutorial notebook reads them from here.
