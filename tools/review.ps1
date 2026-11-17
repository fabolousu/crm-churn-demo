# Layered review gate. Powershell 7+.
#
#   pwsh -File tools/review.ps1                 # full gate against origin/main
#   pwsh -File tools/review.ps1 -Base main -Severity major
#   pwsh -File tools/review.ps1 -SkipCodeRabbit # deterministic checks only (offline)
#
# Layer 0  deterministic checks (always required)
# Layer 1  CodeRabbit review (third-party detection)
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

# ── Layer 0: deterministic checks ────────────────────────────────────────────────
$layer0Failed = $false

# 0a. Test suite. A missing suite is a failure, not a skip.
if (Test-Path "tests") {
  python -m pytest -q
  if ($LASTEXITCODE -ne 0) { Fail "tests" "pytest exited $LASTEXITCODE"; $layer0Failed = $true }
  else { Pass "tests" "pytest green" }
} else {
  Fail "tests" "no tests/ directory — the gate has nothing to verify"
  $layer0Failed = $true
}

# 0b. Model quality gate. Thresholds live in tools/check_metrics.py so CI and this
# script cannot drift apart.
if (Test-Path "ml/artifacts/metrics.json") {
  python tools/check_metrics.py
  if ($LASTEXITCODE -ne 0) {
    Fail "metrics" "check_metrics.py exited $LASTEXITCODE"
    $layer0Failed = $true
  } else {
    Pass "metrics" "within thresholds"
  }
} else {
  Fail "metrics" "ml/artifacts/metrics.json missing"
  $layer0Failed = $true
}

# 0c. Leakage guard: feature code must not read the label table.
if (Test-Path "ml/features.py") {
  $leak = Select-String -Path "ml/features.py" -Pattern "_outcomes" -Quiet
  if ($leak) { Fail "leakage" "features.py references the label table"; $layer0Failed = $true }
  else { Pass "leakage" "features.py does not read labels" }
}

# 0d. Demo smoke test — the thing the pitch depends on.
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
  Fail "coderabbit" "not authenticated; run: coderabbit auth login --api-key <key>"
  exit 3
}

# --agent emits NDJSON findings; --gate makes severity blocking via exit 2.
coderabbit review --agent --gate $Severity --base $Base 2>&1 | Tee-Object -FilePath $report
$code = $LASTEXITCODE

# Normalize stderr noise into the report so the triage agent reads one artifact.
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
