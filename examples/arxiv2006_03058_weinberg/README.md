# arxiv2006_03058_weinberg Example

This example wraps `models/arxiv2006_03058_weinberg`.

Normal ordering:

```bash
python examples/arxiv2006_03058_weinberg/run_scan.py \
  --model examples/arxiv2006_03058_weinberg/model_no.yaml \
  --run-dir examples/arxiv2006_03058_weinberg/runs/no_smoke
```

Inverted ordering:

```bash
python examples/arxiv2006_03058_weinberg/run_scan.py \
  --model examples/arxiv2006_03058_weinberg/model_io.yaml \
  --run-dir examples/arxiv2006_03058_weinberg/runs/io_smoke
```
