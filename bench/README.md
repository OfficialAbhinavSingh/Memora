# Memora Anvil P-02 Benchmark Path

This directory contains the stdlib-only adapter used for the Anvil P-02
Persistent Context Engine benchmark.

## Local checks

```powershell
python bench\worked_example_check.py
python bench\regression_check.py
python -m py_compile bench\adapters\memora.py bench\worked_example_check.py bench\regression_check.py
```

## Official harness

The official harness lives in `bench-p02-context` from:

```text
https://github.com/Sauhard74/Anvil-P-E/tree/main/bench-p02-context
```

Place it at one of these paths:

```text
./bench-p02-context
./official-harness/bench-p02-context
../bench-p02-context
```

Then run:

```sh
sh bench/run.sh
```

On Windows PowerShell, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bench\run.ps1
```

The script copies `bench/adapters/memora.py` into the official harness as
`adapters/memora.py`, runs `self_check.py --quick`, then writes `report.json`
from a multi-seed fast-mode run.

Direct official commands:

```sh
cd bench-p02-context
python self_check.py --adapter adapters.memora:Engine --quick
python run.py --adapter adapters.memora:Engine --mode fast --seeds 9999 31415 27182 16180 11235 --n-services 20 --days 14 --out report.json
python run.py --adapter adapters.memora:Engine --mode deep --seeds 42 101 --out report-deep.json
```

## Dependencies and egress

The adapter uses only Python standard library modules and performs no network
egress. The production Go/React stack is not required for the benchmark path.

## Latest local public-harness result

Command:

```powershell
powershell -ExecutionPolicy Bypass -File .\bench\run.ps1
```

Fast-mode multi-seed stress run:

```text
seeds:              9999 31415 27182 16180 11235
n-services:         20
days:               14
signals:            50
recall@5:           1.000
precision@5_mean:   0.200
remediation_acc:    1.000
latency_p95_ms:     32.00
latency_mean_ms:    30.64
weighted automated: 0.680 / 0.80
```

The ranker now scores behavioral cohorts first, then applies family coverage as
an explicit recall guard when the public harness exposes five or fewer families.
This keeps public recall stable while allowing hidden larger-family scenarios to
prefer truly similar operational shapes.
