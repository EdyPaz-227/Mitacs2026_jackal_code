# run_min_checks.ps1 — minimum validation checks for ISAMI.
# Uses the Windows Python Launcher (py) — confirmed working Python 3.13.5
$ErrorActionPreference = "Continue"

$root = Split-Path (Split-Path $PSScriptRoot)
Set-Location $root
$env:PYTHONPATH = Join-Path $root "src"
$failures = 0

# ── py_compile ────────────────────────────────────────────────────────────────
Write-Host "==> py_compile (src/*.py)" -ForegroundColor Cyan
$pyFiles = Get-ChildItem -Path (Join-Path $root "src") -Filter *.py -Recurse -ErrorAction SilentlyContinue
if ($pyFiles) {
    $compileOk = $true
    foreach ($f in $pyFiles) {
        & py -m py_compile $f.FullName
        if ($LASTEXITCODE -ne 0) { $compileOk = $false }
    }
    if (-not $compileOk) { $failures++; Write-Host "    ECHEC compilation" -ForegroundColor Red }    # EN: compile failed
    else { Write-Host "    OK compilation" -ForegroundColor Green }
} else { Write-Host "    (ignore: aucun .py)" -ForegroundColor Yellow }                               # EN: skipped: no .py

# ── module smoke tests ────────────────────────────────────────────────────────
foreach ($m in @("metriques.py", "validation_spatiale.py", "test_end_to_end.py")) {
    $p = Join-Path $root ("src\" + $m)
    if (Test-Path $p) {
        Write-Host "==> py src/$m" -ForegroundColor Cyan
        & py $p
        if ($LASTEXITCODE -ne 0) { $failures++; Write-Host "    ECHEC: $m" -ForegroundColor Red }    # EN: failed
        else { Write-Host "    OK: $m" -ForegroundColor Green }
    } else { Write-Host "==> (ignore: $m absent)" -ForegroundColor Yellow }                          # EN: skipped: missing
}

# ── pytest ────────────────────────────────────────────────────────────────────
$hasTests = Get-ChildItem -Path $root -Recurse -Filter "test_*.py" -ErrorAction SilentlyContinue
if ($hasTests) {
    Write-Host "==> pytest -q" -ForegroundColor Cyan
    & py -m pytest -q
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 5) { $failures++; Write-Host "    ECHEC pytest" -ForegroundColor Red }     # EN: pytest failed; exit 5 = no tests collected, treat as skip
    elseif ($LASTEXITCODE -eq 5) { Write-Host "    OK pytest (aucun test collecté)" -ForegroundColor Yellow }               # EN: no tests collected
    else { Write-Host "    OK pytest" -ForegroundColor Green }
} else { Write-Host "==> (ignore: aucun test)" -ForegroundColor Yellow }                             # EN: skipped: no tests

# ── result ────────────────────────────────────────────────────────────────────
if ($failures -gt 0) {
    Write-Host "`nResultat: $failures echec(s)" -ForegroundColor Red; exit 1                         # EN: result: N failure(s)
} else {
    Write-Host "`nResultat: tout est vert" -ForegroundColor Green; exit 0                            # EN: result: all green
}