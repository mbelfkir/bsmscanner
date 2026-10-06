# Reference best-fit runs

Finished scans of `scotogenic_ma` made with `../run_best_fit.py` during the review of this model.
Only `best_fit.json` (best point and objective), `summary.json` (run summary) and
`metadata.json` (scan configuration) are kept; the full point lists are omitted for size.

`seed_*` are the short runs of `run_best_fit.py` with different seeds (15k-130k evaluations); `g4000_p400_*` and `g4000_p1000_*` are long runs (4000 generations, populations 400 and 1000; 0.6M and 1.0M evaluations).

`tests/test_tutorial_reference_results.py` re-evaluates every `best_fit.json` through the
shipped model and checks that the stored objective is reproduced, so these results cannot
drift from the model. The tutorial notebook reads them from here.
