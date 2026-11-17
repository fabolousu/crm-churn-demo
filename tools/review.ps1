# Layered review gate. Powershell 7+.
#
#   pwsh -File tools/review.ps1                 # full gate against origin/main
#   pwsh -File tools/review.ps1 -Base main -Severity major
#   pwsh -File tools/review.ps1 -SkipCodeRabbit # deterministic checks only (offline)
#
# Layer 0  deterministic checks (always required)
# Layer 1  CodeRabbit review (third-party detection)
#
# Gates activate with the code they guard — the same rule CI follows. A branch that only
# touches docs must not be blocked by a model artifact that does not exist yet, and code
# with no tests must never pass.
#
# Exit codes: 0 pass, 1 deterministic failure, 2 CodeRabbit findings, 3 CodeRabbit
# unavailable/errored. Never returns 0 when a check did not actually run.

param(
  [string]$Base = "main",
  [ValidateSet("critical", "major", "minor", "trivial", "info")]
  [string]$Severity = "major",
  [string]$ReportDir = "reports",
  [switch]$SkipCodeRabbit
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

function Fail([string]$layer, [string]$message) {
  Write-Host "[FAIL] $layer — $message" -ForegroundColor Red
}

function Pass([string]$layer, [string]$message) {
  Write-Host "[ ok ] $layer — $message" -ForegroundColor Green
}

function Skip([string]$layer, [string]$message) {
  Write-Host "[skip] $layer — $message" -ForegroundColor DarkGray
}

$layer0Failed = $false

# ── 0a. Tests ───────────────────────────────────────────────────────────────────
$testDirs = @("tests", "ml/tests", "api/tests", "data/tests") | Where-Object { Test-Path $_ }
$codeFiles = @()
foreach ($d in @("data", "ml", "api")) {
  if (Test-Path $d) { $codeFiles += (Get-ChildItem -Path $d -Filter *.py -Recurse -File -ErrorAction SilentlyContinue) }
}

if ($codeFiles.Count -gt 0 -and $testDirs.Count -eq 0) {
  Fail "tests" "Python code exists but no test directory (tests/, ml/tests, api/tests, data/tests)"
  $layer0Failed = $true
} elseif ($testDirs.Count -gt 0) {
  python -m pytest -q
  if ($LASTEXITCODE -ne 0) { Fail "tests" "pytest exited $LASTEXITCODE"; $layer0Failed = $true }
  else { Pass "tests" "pytest green" }
} else {
  Skip "tests" "no Python code or tests yet"
}

# ── 0b. Model quality gate (activates with the training lane) ────────────────────
if (Test-Path "ml/train.py") {
  if (-not (Test-Path "ml/artifacts/metrics.json")) {
    Fail "metrics" "ml/train.py exists but ml/artifacts/metrics.json is missing"
    $layer0Failed = $true
  } else {
    python tools/check_metrics.py
    if ($LASTEXITCODE -ne 0) { Fail "metrics" "check_metrics.py exited $LASTEXITCODE"; $layer0Failed = $true }
    else { Pass "metrics" "within thresholds" }
  }
} else {
  Skip "metrics" "training lane has not landed"
}

# ── 0c. Leakage guard (activates with the feature pipeline) ──────────────────────
if (Test-Path "ml/features.py") {
  $leak = Select-String -Path "ml/features.py" -Pattern "_outcomes" -Quiet
  if ($leak) { Fail "leakage" "features.py references the label table"; $layer0Failed = $true }
  else { Pass "leakage" "features.py does not read labels" }
} else {
  Skip "leakage" "no feature pipeline yet — guard inactive"
}

# ── 0d. Demo smoke test (only once the stack is composed) ────────────────────────
if (Test-Path "compose.yaml") {
  docker compose up -d | Out-Null
  Start-Sleep -Seconds 5
  try {
    $health = Invoke-RestMethod -Uri "http://localhost:8080/api/health" -TimeoutSec 15
    if ($health.model_version) { Pass "smoke" "api healthy, model $($health.model_version)" }
    else { Fail "smoke" "health response has no model_version"; $layer0Failed = $true }
  } catch {
    Fail "smoke" "health check failed: $($_.Exception.Message)"
    $layer0Failed = $true
  } finally {
    docker compose down | Out-Null
  }
} else {
  Skip "smoke" "no compose.yaml yet"
}

if ($layer0Failed) {
  Fail "gate" "deterministic checks failed; CodeRabbit not run (no point reviewing a broken build)"
  exit 1
}

if ($SkipCodeRabbit) {
  Write-Host "[warn] CodeRabbit layer skipped — this is NOT a full review" -ForegroundColor Yellow
  exit 0
}

# ── Layer 1: CodeRabbit ──────────────────────────────────────────────────────────
$report = Join-Path $ReportDir "coderabbit.ndjson"

if (-not (Get-Command coderabbit -ErrorAction SilentlyContinue)) {
  Fail "coderabbit" "CLI not on PATH; install it, then run: coderabbit doctor"
  exit 3
}

$status = coderabbit auth status --agent 2>&1
if ($LASTEXITCODE -ne 0) {
  Fail "coderabbit" "not authenticated; run: coderabbit auth login"
  exit 3
}

# --agent emits NDJSON findings; --gate makes severity blocking via exit 2.
coderabbit review --agent --gate $Severity --base $Base 2>&1 | Tee-Object -FilePath $report
$code = $LASTEXITCODE

Add-Content -Path $report -Value "# exit=$code severity=$Severity base=$Base"

switch ($code) {
  0 { Pass "coderabbit" "no findings at or above '$Severity'"; exit 0 }
  2 {
    Fail "coderabbit" "findings at or above '$Severity' — see $report"
    Write-Host "Hand $report to the triage agent: separate real defects, assign to owning lane, re-run."
    exit 2
  }
  1 {
    Fail "coderabbit" "review incomplete or failed (exit 1 covers 'did not review every file') — see $report"
    exit 2
  }
  default {
    Fail "coderabbit" "unexpected exit $code (auth, network, or usage limit) — see $report"
    exit 3
  }
}
