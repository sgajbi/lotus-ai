$ErrorActionPreference = "Stop"

$DemoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $DemoRoot)
$PerformanceRepo = Join-Path (Split-Path -Parent $RepoRoot) "lotus-performance"
$GeneratedRoot = Join-Path $DemoRoot "generated"
$CaptureRoot = Join-Path $GeneratedRoot "captures"
$RuntimeRoot = Join-Path $GeneratedRoot "runtime"
$RequestRoot = Join-Path $DemoRoot "requests"
$DatabasePath = Join-Path $RuntimeRoot "lotus-ai-demo.db"
$StdoutLog = Join-Path $RuntimeRoot "lotus-ai.stdout.log"
$StderrLog = Join-Path $RuntimeRoot "lotus-ai.stderr.log"
$PidFile = Join-Path $RuntimeRoot "lotus-ai.pid"
$LotusAiBaseUrl = if ($env:LOTUS_AI_BASE_URL) { $env:LOTUS_AI_BASE_URL } else { "http://127.0.0.1:8140" }
$PerformanceBaseUrl = if ($env:LOTUS_PERFORMANCE_BASE_URL) { $env:LOTUS_PERFORMANCE_BASE_URL } else { "http://performance.dev.lotus" }

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Write-JsonFile([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 100
    Set-Content -Path $Path -Value $json
}

function Invoke-CapturedGet([string]$Name, [string]$Uri) {
    $response = Invoke-RestMethod -Uri $Uri -Method Get
    Write-JsonFile (Join-Path $CaptureRoot "$Name.response.json") $response
    return $response
}

function Invoke-CapturedPost([string]$Name, [string]$Uri, [string]$RequestPath) {
    Copy-Item $RequestPath (Join-Path $CaptureRoot "$Name.request.json") -Force
    $body = Get-Content $RequestPath -Raw
    $response = Invoke-RestMethod -Uri $Uri -Method Post -ContentType "application/json" -Body $body
    Write-JsonFile (Join-Path $CaptureRoot "$Name.response.json") $response
    return $response
}

function Stop-LotusAiIfRunning() {
    if (Test-Path $PidFile) {
        $existingId = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($existingId) {
            Stop-Process -Id $existingId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Start-LotusAiDemo() {
    Ensure-Directory $RuntimeRoot
    Remove-Item $DatabasePath -Force -ErrorAction SilentlyContinue
    Remove-Item $StdoutLog -Force -ErrorAction SilentlyContinue
    Remove-Item $StderrLog -Force -ErrorAction SilentlyContinue

    $env:PYTHONPATH = "src"
    $env:LOTUS_AI_DATABASE_URL = "sqlite:///./demo/lotus-performance-first-use-case/generated/runtime/lotus-ai-demo.db"
    $env:LOTUS_AI_AUDIT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_PROMPT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ACCESS_CONTROL_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ARTIFACT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE = "memory"
    $env:LOTUS_AI_ARTIFACT_OBJECT_STORE_ROOT = ""
    $env:LOTUS_AI_ASYNC_RUNTIME_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE = "sqlalchemy"

    python -m alembic upgrade head

    $process = Start-Process python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8140" `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog `
        -PassThru
    Set-Content -Path $PidFile -Value $process.Id

    $deadline = (Get-Date).AddSeconds(45)
    do {
        Start-Sleep -Seconds 1
        try {
            $ready = Invoke-RestMethod -Uri "$LotusAiBaseUrl/health/ready" -Method Get
            if ($ready.status -eq "ready") {
                return
            }
        } catch {
        }
    } while ((Get-Date) -lt $deadline)

    throw "lotus-ai did not become ready within the timeout."
}

function Ensure-LotusPerformanceReady() {
    Push-Location $PerformanceRepo
    try {
        docker compose up -d --build performance-lineage-db performance-analytics performance-lineage-worker performance-compute-executor | Out-Null
    }
    finally {
        Pop-Location
    }
    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 2
        try {
            $ready = Invoke-RestMethod -Uri "$PerformanceBaseUrl/health/ready" -Method Get
            if ($ready.status -eq "ready") {
                return
            }
        } catch {
        }
    } while ((Get-Date) -lt $deadline)

    throw "lotus-performance did not become ready within the timeout."
}

function Run-FirstUseCaseEval() {
    $submission = Invoke-CapturedPost `
        -Name "19-lotus-ai-first-use-case-eval-submit" `
        -Uri "$LotusAiBaseUrl/platform/evals/runs/submit" `
        -RequestPath (Join-Path $RequestRoot "lotus-ai-first-use-case-eval.request.json")

    $env:PYTHONPATH = "src"
    $env:LOTUS_AI_DATABASE_URL = "sqlite:///./demo/lotus-performance-first-use-case/generated/runtime/lotus-ai-demo.db"
    $env:LOTUS_AI_AUDIT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_PROMPT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ACCESS_CONTROL_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ARTIFACT_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE = "memory"
    $env:LOTUS_AI_ASYNC_RUNTIME_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE = "sqlalchemy"
    $env:LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE = "sqlalchemy"

    $python = @"
from app.services.eval_async_execution import run_next_evaluation_execution_job
result = run_next_evaluation_execution_job(worker_id="demo-worker-1")
print(result)
"@
    $result = $python | python -
    Set-Content -Path (Join-Path $CaptureRoot "20-lotus-ai-first-use-case-eval-worker.txt") -Value $result

    Invoke-CapturedGet `
        -Name "21-lotus-ai-first-use-case-eval-run-detail" `
        -Uri ("$LotusAiBaseUrl/platform/evals/runs/" + $submission.run_id) | Out-Null
}

Ensure-Directory $GeneratedRoot
Ensure-Directory $CaptureRoot
Ensure-Directory $RuntimeRoot
Get-ChildItem $CaptureRoot -File -ErrorAction SilentlyContinue | Remove-Item -Force

Stop-LotusAiIfRunning
Ensure-LotusPerformanceReady
Start-LotusAiDemo

Invoke-CapturedGet -Name "01-lotus-performance-health-ready" -Uri "$PerformanceBaseUrl/health/ready" | Out-Null
Invoke-CapturedGet -Name "02-lotus-ai-health" -Uri "$LotusAiBaseUrl/health" | Out-Null
Invoke-CapturedGet -Name "03-lotus-ai-health-ready" -Uri "$LotusAiBaseUrl/health/ready" | Out-Null
Invoke-CapturedGet -Name "04-lotus-ai-root" -Uri "$LotusAiBaseUrl/" | Out-Null
Invoke-CapturedGet -Name "05-lotus-ai-metadata" -Uri "$LotusAiBaseUrl/metadata" | Out-Null
Invoke-CapturedGet -Name "06-lotus-ai-platform-runtime-status" -Uri "$LotusAiBaseUrl/platform/runtime-status" | Out-Null
Invoke-CapturedGet -Name "07-lotus-ai-capabilities" -Uri "$LotusAiBaseUrl/platform/capabilities" | Out-Null
Invoke-CapturedGet -Name "08-lotus-ai-task-runtime-status" -Uri "$LotusAiBaseUrl/platform/tasks/runtime-status" | Out-Null
Invoke-CapturedGet -Name "09-lotus-ai-access-control-runtime-status" -Uri "$LotusAiBaseUrl/platform/access-control/runtime-status" | Out-Null
Invoke-CapturedGet -Name "10-lotus-ai-access-control-caller-policies" -Uri "$LotusAiBaseUrl/platform/access-control/caller-policies" | Out-Null
Invoke-CapturedGet -Name "11-lotus-ai-provider-catalog" -Uri "$LotusAiBaseUrl/platform/providers" | Out-Null
Invoke-CapturedGet -Name "12-lotus-ai-retrieval-sources" -Uri "$LotusAiBaseUrl/platform/retrieval/sources" | Out-Null
Invoke-CapturedGet -Name "13-lotus-ai-safety-policy" -Uri "$LotusAiBaseUrl/platform/safety/policy" | Out-Null
Invoke-CapturedGet -Name "14-lotus-ai-prompt-runtime-status" -Uri "$LotusAiBaseUrl/platform/prompts/runtime-status" | Out-Null
Invoke-CapturedGet -Name "15-lotus-ai-async-runtime-status" -Uri "$LotusAiBaseUrl/platform/async/runtime-status" | Out-Null
Invoke-CapturedGet -Name "16-lotus-ai-artifact-runtime-status" -Uri "$LotusAiBaseUrl/platform/artifacts/runtime-status" | Out-Null
Invoke-CapturedGet -Name "17-lotus-ai-observability-runtime-status" -Uri "$LotusAiBaseUrl/platform/observability/runtime-status" | Out-Null
Invoke-CapturedGet -Name "18-lotus-ai-evals-runtime-status" -Uri "$LotusAiBaseUrl/platform/evals/runtime-status" | Out-Null
Invoke-CapturedGet -Name "22-lotus-ai-first-use-case-contract" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case" | Out-Null
Invoke-CapturedGet -Name "23-lotus-ai-first-use-case-readiness-before-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/readiness" | Out-Null
Invoke-CapturedGet -Name "24-lotus-ai-first-use-case-runbook-readiness" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/runbook-readiness" | Out-Null
Invoke-CapturedGet -Name "25-lotus-ai-first-use-case-governance-before-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/governance-status" | Out-Null
Invoke-CapturedGet -Name "26-lotus-ai-onboarding-template" -Uri "$LotusAiBaseUrl/platform/use-cases/onboarding-template" | Out-Null

$performanceResponse = Invoke-CapturedPost `
    -Name "27-lotus-performance-twr" `
    -Uri "$PerformanceBaseUrl/performance/twr" `
    -RequestPath (Join-Path $RequestRoot "lotus-performance-twr.request.json")

$explainTemplatePath = Join-Path $RequestRoot "lotus-ai-explain.request.json"
$explainRequestPath = Join-Path $CaptureRoot "28-lotus-ai-explain.request.json"
$explain = Get-Content $explainTemplatePath -Raw | ConvertFrom-Json
$explain.context.source_refs[0] = "lotus-performance:calculation:$($performanceResponse.calculation_id)"
Write-JsonFile $explainRequestPath $explain

$taskResponse = Invoke-CapturedPost `
    -Name "29-lotus-ai-explain" `
    -Uri "$LotusAiBaseUrl/ai/tasks/execute" `
    -RequestPath $explainRequestPath

Invoke-CapturedGet -Name "30-lotus-ai-audit-detail" -Uri ("$LotusAiBaseUrl/ai/audit/" + $taskResponse.audit.request_id) | Out-Null
Invoke-CapturedGet -Name "31-lotus-ai-audit-catalog" -Uri "$LotusAiBaseUrl/ai/audit?caller_app=lotus-performance&limit=20" | Out-Null
Invoke-CapturedGet -Name "32-lotus-ai-task-execution-summary" -Uri "$LotusAiBaseUrl/platform/tasks/execution-summary?limit=20" | Out-Null
Invoke-CapturedGet -Name "33-lotus-ai-task-evidence-summary" -Uri "$LotusAiBaseUrl/platform/tasks/evidence-summary?limit=20" | Out-Null
Invoke-CapturedGet -Name "34-lotus-ai-observability-incident-summary" -Uri "$LotusAiBaseUrl/platform/observability/incident-summary" | Out-Null
Invoke-CapturedGet -Name "35-lotus-ai-observability-breakdowns" -Uri "$LotusAiBaseUrl/platform/observability/breakdowns?limit=20" | Out-Null
Invoke-CapturedGet -Name "36-lotus-ai-access-control-governance" -Uri "$LotusAiBaseUrl/platform/access-control/governance-status" | Out-Null
Invoke-CapturedGet -Name "37-lotus-ai-artifact-governance" -Uri "$LotusAiBaseUrl/platform/artifacts/governance-status" | Out-Null
Invoke-CapturedGet -Name "38-lotus-ai-observability-governance" -Uri "$LotusAiBaseUrl/platform/observability/governance-status" | Out-Null
Invoke-CapturedGet -Name "39-lotus-ai-provider-governance" -Uri "$LotusAiBaseUrl/platform/providers/governance-status" | Out-Null
Invoke-CapturedGet -Name "40-lotus-ai-retrieval-governance" -Uri "$LotusAiBaseUrl/platform/retrieval/governance-status" | Out-Null
Invoke-CapturedGet -Name "41-lotus-ai-safety-governance" -Uri "$LotusAiBaseUrl/platform/safety/governance-status" | Out-Null
Invoke-CapturedGet -Name "42-lotus-ai-prompt-governance" -Uri "$LotusAiBaseUrl/platform/prompts/governance-status" | Out-Null
Invoke-CapturedGet -Name "43-lotus-ai-async-governance" -Uri "$LotusAiBaseUrl/platform/async/governance-status" | Out-Null

Run-FirstUseCaseEval

Invoke-CapturedGet -Name "44-lotus-ai-first-use-case-readiness-after-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/readiness" | Out-Null
Invoke-CapturedGet -Name "45-lotus-ai-first-use-case-governance-after-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/governance-status" | Out-Null
Invoke-CapturedGet -Name "46-lotus-ai-evals-run-catalog" -Uri "$LotusAiBaseUrl/platform/evals/runs" | Out-Null

$summary = [pscustomobject]@{
    performance_base_url = $PerformanceBaseUrl
    lotus_ai_base_url = $LotusAiBaseUrl
    capture_root = $CaptureRoot
    runtime_root = $RuntimeRoot
    explanation_request_id = $taskResponse.audit.request_id
    performance_calculation_id = $performanceResponse.calculation_id
    completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
}
Write-JsonFile (Join-Path $GeneratedRoot "demo-summary.json") $summary

Write-Host "Demo complete. Captures written to $CaptureRoot"
