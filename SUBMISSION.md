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

## Latest Public Result

```text
recall@5:            1.000
precision@5_mean:   0.200
remediation_acc:    1.000
latency_p95_ms:     47 ms
weighted automated: 0.680 / 0.80
```

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
