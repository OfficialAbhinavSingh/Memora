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
    python regression_check.py
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
    python self_check.py --adapter adapters.memora:Engine --quick
    $reportPath = Join-Path $RepoRoot "report.json"
    python run.py --adapter adapters.memora:Engine --mode fast `
        --seeds 9999 31415 27182 16180 11235 `
        --n-services 20 --days 14 `
        --out $reportPath

    $webPublic = Join-Path $RepoRoot "web\public"
    if (Test-Path $webPublic) {
        Copy-Item $reportPath (Join-Path $webPublic "benchmark-report.json") -Force
        Write-Host "Copied benchmark report to web\public\benchmark-report.json"
    }
}
finally {
    Pop-Location
}
