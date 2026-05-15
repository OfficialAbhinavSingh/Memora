# Anvil P-02 Submission Guide

## Track

P-02 · Persistent Context Engine.

The scoring adapter is:

```text
bench.adapters.memora:Engine
```

When copied into the official harness, the adapter is:

```text
adapters.memora:Engine
```

## Judge Commands

From the repository root:

```powershell
python bench\worked_example_check.py
python bench\regression_check.py
powershell -ExecutionPolicy Bypass -File .\bench\run.ps1
```

On Linux/macOS:

```sh
python bench/worked_example_check.py
python bench/regression_check.py
sh bench/run.sh
```

If the official `bench-p02-context` harness is present at `./bench-p02-context`,
the runner copies `bench/adapters/memora.py` into the harness and runs:

```sh
python self_check.py --adapter adapters.memora:Engine --quick
python run.py --adapter adapters.memora:Engine --mode fast \
  --seeds 9999 31415 27182 16180 11235 \
  --n-services 20 --days 14 \
  --out report.json
```

If the official harness is absent, the runner still emits a local fallback
`report.json` after the worked example and regression checks pass.

## Latest Benchmark Results

### Corrected Ground-Truth Alignment (29 seeds, 5 tiers)

```text
recall@5:            1.000
precision@5_mean:    0.818
remediation_acc:     1.000
latency_p95_ms:      78 ms
weighted automated:  0.769 / 0.80
```

### Per-Tier Breakdown

| Tier | Services | Days | Seeds | R@5 | P@5 | Weighted |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| Quick (L1/L2) | 6 | 2 | 2 | 1.000 | 0.580 | 0.737 |
| Standard (L2) | 12 | 7 | 5 | 1.000 | 0.780 | 0.767 |
| Competition | 20 | 14 | 5 | 1.000 | 0.904 | 0.786 |
| Stress (L3-preview) | 30 | 21 | 7 | 1.000 | 0.869 | 0.780 |
| Adversarial | 20 | 14 | 10 | 1.000 | 0.818 | 0.773 |

## Reproducibility

The benchmark adapter uses only the Python standard library and performs no
external network egress. The Go API, React UI, Docker Compose stack, and
infrastructure manifests are demo/production scaffolding, not required for the
official P-02 score.

Docker sanity check:

```sh
docker build -t memora-p02 .
docker run --rm memora-p02
```

On the development Windows machine, Docker could not be verified because the
host denied access to the Docker engine pipe/config directory. Native Python
execution is verified and is the canonical benchmark path; the Dockerfile is
kept as the judge-machine reproducibility wrapper.

## Demo Artifacts

- Writeup source: `docs/p02-writeup.md`
- Writeup PDF: `docs/p02-writeup.pdf`
- Demo script: `docs/demo-script.md`
- Benchmark report for frontend: `web/public/benchmark-report.json`
- Custom L3-style benchmark: `bench/custom_benchmark.py`
