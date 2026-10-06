# Reference best-fit runs

Finished scans of `minimal_bl` made with `../run_best_fit.py` during the review of this model.
Only `best_fit.json` (best point and objective), `summary.json` (run summary) and
`metadata.json` (scan configuration) are kept; the full point lists are omitted for size.

`seed_11064462_no_dilepton` was run without the optional LHC dilepton constraint, i.e. with the default `model.yaml`.

`tests/test_tutorial_reference_results.py` re-evaluates every `best_fit.json` through the
shipped model and checks that the stored objective is reproduced, so these results cannot
drift from the model. The tutorial notebook reads them from here.
