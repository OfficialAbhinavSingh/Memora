$ErrorActionPreference = "Stop"

$BenchDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $BenchDir

$officialCandidates = @(
    (Join-Path $RepoRoot "bench-p02-context"),
    (Join-Path $RepoRoot "official-harness\bench-p02-context"),
    (Join-Path (Split-Path -Parent $RepoRoot) "bench-p02-context")
)

$Official = $null
foreach ($candidate in $officialCandidates) {
    if (Test-Path (Join-Path $candidate "run.py")) {
        $Official = $candidate
        break
    }
}

Push-Location $BenchDir
try {
    python worked_example_check.py
    if ($LASTEXITCODE -ne 0) { throw "worked_example_check.py failed (exit $LASTEXITCODE)" }
    python regression_check.py
    if ($LASTEXITCODE -ne 0) { throw "regression_check.py failed (exit $LASTEXITCODE)" }
}
finally {
    Pop-Location
}

if (-not $Official) {
    Write-Host "Official Anvil harness not found."
    Write-Host "Place bench-p02-context at one of:"
    foreach ($candidate in $officialCandidates) {
        Write-Host "  $candidate"
    }
    $reportPath = Join-Path $RepoRoot "report.json"
    Push-Location $BenchDir
    try {
        python local_report.py $reportPath
        if ($LASTEXITCODE -ne 0) { throw "local_report.py failed (exit $LASTEXITCODE)" }
    }
    finally {
        Pop-Location
    }
    $webPublic = Join-Path $RepoRoot "web\public"
    if (Test-Path $webPublic) {
        Copy-Item $reportPath (Join-Path $webPublic "benchmark-report.json") -Force
        Write-Host "Copied fallback report to web\public\benchmark-report.json"
    }
    Write-Host "Then place the official harness and rerun bench\run.ps1 for scored metrics."
    exit 0
}

$adapterDir = Join-Path $Official "adapters"
New-Item -ItemType Directory -Force -Path $adapterDir | Out-Null
Copy-Item (Join-Path $BenchDir "adapters\memora.py") (Join-Path $adapterDir "memora.py") -Force

Push-Location $Official
try {
    # Quick L2 self-check, for local iteration only (not scored).
    python self_check.py --adapter adapters.memora:Engine --quick
    if ($LASTEXITCODE -ne 0) { throw "self_check.py failed (exit $LASTEXITCODE)" }

    # L3 final bench - the official submission run. Stretch config and
    # the council seeds are locked inside run.py; do NOT pass --seeds /
    # --n-services / --days, the harness will reject them.
    $reportPath = Join-Path $Official "l3_report.json"
    python run.py --adapter adapters.memora:Engine --out $reportPath
    if ($LASTEXITCODE -ne 0) { throw "L3 run.py failed (exit $LASTEXITCODE); l3_report.json NOT written, web/public left untouched" }

    # Mirror to repo root for convenience.
    Copy-Item $reportPath (Join-Path $RepoRoot "report.json") -Force

    $webPublic = Join-Path $RepoRoot "web\public"
    if (Test-Path $webPublic) {
        Copy-Item $reportPath (Join-Path $webPublic "benchmark-report.json") -Force
        Write-Host "Copied L3 report to web\public\benchmark-report.json"
    }
}
finally {
    Pop-Location
}
