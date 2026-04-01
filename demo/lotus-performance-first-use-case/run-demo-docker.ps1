param(
    [string]$GeneratedFolderName = "generated-docker",
    [switch]$UseProjectEnvFile,
    [switch]$EnableLiveProvider,
    [switch]$OverrideLiveCallerPolicies
)

$ErrorActionPreference = "Stop"

$DemoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $DemoRoot)
$PerformanceRepo = Join-Path (Split-Path -Parent $RepoRoot) "lotus-performance"
$GeneratedRoot = Join-Path $DemoRoot $GeneratedFolderName
$CaptureRoot = Join-Path $GeneratedRoot "captures"
$RuntimeRoot = Join-Path $GeneratedRoot "runtime"
$RequestRoot = Join-Path $DemoRoot "requests"
$DockerEnvFile = if ($UseProjectEnvFile) {
    Join-Path $RepoRoot ".env"
} else {
    Join-Path $RuntimeRoot ".env.docker-demo"
}
$ComposeProject = "lotus-ai-first-use-case-demo"
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

function Write-DockerEnvFile() {
    if ($UseProjectEnvFile) {
        if (-not (Test-Path $DockerEnvFile)) {
            throw "Project env file $DockerEnvFile does not exist."
        }
        return
    }
    $lines = @(
        "APP_ENV=local",
        "LOG_LEVEL=INFO",
        "ROUNDING_POLICY_VERSION=v1",
        "LOTUS_AI_AUDIT_STORE_MODE=sqlalchemy",
        "LOTUS_AI_PROMPT_STORE_MODE=sqlalchemy",
        "LOTUS_AI_RETRIEVAL_STORE_MODE=sqlalchemy",
        "LOTUS_AI_ACCESS_CONTROL_STORE_MODE=sqlalchemy",
        "LOTUS_AI_ARTIFACT_STORE_MODE=sqlalchemy",
        "LOTUS_AI_ARTIFACT_OBJECT_STORE_MODE=memory",
        "LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy",
        "LOTUS_AI_STARTUP_READINESS_POLICY=warn",
        "LOTUS_AI_READINESS_PROBE_POLICY=observe",
        "LOTUS_AI_RETRIEVAL_MODE=disabled",
        "LOTUS_AI_EMBEDDING_PROVIDER_MODE=disabled"
    )
    Set-Content -Path $DockerEnvFile -Value $lines
}

function Get-EnvValue([string]$Name) {
    if (-not (Test-Path $DockerEnvFile)) {
        return $null
    }
    foreach ($line in Get-Content $DockerEnvFile) {
        if ($line -match "^\s*$Name=(.*)$") {
            return $Matches[1]
        }
    }
    return $null
}

function Assert-LiveProviderConfiguration() {
    $requiredValues = @{
        "LOTUS_AI_PROVIDER_MODE" = "openai"
        "LOTUS_AI_PROVIDER_ROLLOUT_STATE" = "CANARY_ENABLED"
        "LOTUS_AI_LIVE_TEXT_PROVIDER_ID" = "text.openai"
    }
    foreach ($entry in $requiredValues.GetEnumerator()) {
        $configuredValue = Get-EnvValue $entry.Key
        if ($configuredValue -ne $entry.Value) {
            throw "Expected $($entry.Key)=$($entry.Value) in $DockerEnvFile for the live-provider pass."
        }
    }

    $requiredPresence = @(
        "LOTUS_AI_LIVE_TEXT_MODEL_ID",
        "LOTUS_AI_LIVE_TEXT_PROVIDER_API_KEY",
        "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS"
    )
    foreach ($name in $requiredPresence) {
        $configuredValue = Get-EnvValue $name
        if ([string]::IsNullOrWhiteSpace($configuredValue)) {
            throw "Expected $name to be configured in $DockerEnvFile for the live-provider pass."
        }
    }

    if ((Get-EnvValue "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS") -notmatch "(^|,)explain\.v1($|,)") {
        throw "LOTUS_AI_LIVE_TEXT_ALLOWED_TASK_IDS in $DockerEnvFile must include explain.v1 for the live-provider pass."
    }
}

function Invoke-LotusAiCompose([string[]]$Arguments) {
    $env:LOTUS_AI_ENV_FILE = $DockerEnvFile
    docker compose -p $ComposeProject @Arguments
}

function Reset-LotusAiDockerStack() {
    Write-DockerEnvFile
    try {
        Invoke-LotusAiCompose @("down", "-v", "--remove-orphans") | Out-Null
    } catch {
    }
}

function Start-LotusAiDockerStack() {
    Write-DockerEnvFile
    Invoke-LotusAiCompose @("up", "-d", "--build", "redis", "lotus-ai", "lotus-ai-worker") | Out-Null
}

function Enable-LiveProviderCallerPolicyOverrides() {
    $script = @'
import sqlite3

conn = sqlite3.connect("/data/lotus-ai.db")
conn.execute(
    "UPDATE caller_policies SET allow_live_provider = 1 WHERE caller_app IN (?, ?)",
    ("lotus-performance", "lotus-platform"),
)
conn.commit()
conn.close()
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($script))
    Invoke-LotusAiCompose @(
        "exec",
        "-T",
        "lotus-ai",
        "python",
        "-c",
        "import base64; exec(base64.b64decode('$encoded').decode('utf-8'))"
    ) | Out-Null
}

function Capture-LotusAiDockerLogs() {
    Invoke-LotusAiCompose @("ps") | Set-Content -Path (Join-Path $RuntimeRoot "lotus-ai-compose-ps.txt")
    Invoke-LotusAiCompose @("logs", "--no-color", "lotus-ai") | Set-Content -Path (Join-Path $RuntimeRoot "lotus-ai.log")
    Invoke-LotusAiCompose @("logs", "--no-color", "lotus-ai-worker") | Set-Content -Path (Join-Path $RuntimeRoot "lotus-ai-worker.log")
    Invoke-LotusAiCompose @("logs", "--no-color", "redis") | Set-Content -Path (Join-Path $RuntimeRoot "redis.log")
}

function Wait-ForEndpoint([string]$Uri, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-RestMethod -Uri $Uri -Method Get
            if ($response.status -eq "ready") {
                return
            }
        } catch {
        }
    } while ((Get-Date) -lt $deadline)

    throw "Endpoint $Uri did not become ready within the timeout."
}

function Ensure-LotusPerformanceReady() {
    Push-Location $PerformanceRepo
    try {
        docker compose up -d --build performance-lineage-db performance-analytics performance-lineage-worker performance-compute-executor | Out-Null
    }
    finally {
        Pop-Location
    }
    Wait-ForEndpoint "$PerformanceBaseUrl/health/ready" 90
}

function Wait-ForEvaluationRun([string]$RunId) {
    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 2
        $run = Invoke-RestMethod -Uri "$LotusAiBaseUrl/platform/evals/runs/$RunId" -Method Get
        $runStatus = $run.run.status
        if ($runStatus -in @("COMPLETED", "FAILED")) {
            Write-JsonFile (Join-Path $CaptureRoot "21-lotus-ai-first-use-case-eval-run-detail.response.json") $run
            return $run
        }
    } while ((Get-Date) -lt $deadline)

    throw "Evaluation run $RunId did not reach a terminal state within the timeout."
}

Ensure-Directory $GeneratedRoot
Ensure-Directory $CaptureRoot
Ensure-Directory $RuntimeRoot
Get-ChildItem $CaptureRoot -File -ErrorAction SilentlyContinue | Remove-Item -Force

Reset-LotusAiDockerStack
Ensure-LotusPerformanceReady
if ($EnableLiveProvider) {
    Assert-LiveProviderConfiguration
}
Start-LotusAiDockerStack
Wait-ForEndpoint "$LotusAiBaseUrl/health/ready" 120
if ($EnableLiveProvider -and $OverrideLiveCallerPolicies) {
    Enable-LiveProviderCallerPolicyOverrides
}
Capture-LotusAiDockerLogs

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

Invoke-CapturedGet -Name "30-lotus-ai-audit-detail" -Uri "$LotusAiBaseUrl/ai/audit/$($taskResponse.audit.request_id)" | Out-Null
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

$evalSubmission = Invoke-CapturedPost `
    -Name "19-lotus-ai-first-use-case-eval-submit" `
    -Uri "$LotusAiBaseUrl/platform/evals/runs/submit" `
    -RequestPath (Join-Path $RequestRoot "lotus-ai-first-use-case-eval.request.json")

$evalRun = Wait-ForEvaluationRun $evalSubmission.run_id
Set-Content -Path (Join-Path $CaptureRoot "20-lotus-ai-first-use-case-eval-worker.txt") -Value "Eval run completed through docker worker path with status $($evalRun.run.status)."

Invoke-CapturedGet -Name "44-lotus-ai-first-use-case-readiness-after-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/readiness" | Out-Null
Invoke-CapturedGet -Name "45-lotus-ai-first-use-case-governance-after-eval" -Uri "$LotusAiBaseUrl/platform/use-cases/first-production-use-case/governance-status" | Out-Null
Invoke-CapturedGet -Name "46-lotus-ai-evals-run-catalog" -Uri "$LotusAiBaseUrl/platform/evals/runs" | Out-Null

Capture-LotusAiDockerLogs

$summary = [pscustomobject]@{
    demo_mode = if ($EnableLiveProvider) { "docker-live-provider" } else { "docker-stub-provider" }
    performance_base_url = $PerformanceBaseUrl
    lotus_ai_base_url = $LotusAiBaseUrl
    capture_root = $CaptureRoot
    runtime_root = $RuntimeRoot
    docker_env_file = $DockerEnvFile
    docker_compose_project = $ComposeProject
    live_provider_enabled = $EnableLiveProvider.IsPresent
    caller_policy_live_override_applied = ($EnableLiveProvider.IsPresent -and $OverrideLiveCallerPolicies.IsPresent)
    explanation_request_id = $taskResponse.audit.request_id
    evaluation_run_id = $evalSubmission.run_id
    performance_calculation_id = $performanceResponse.calculation_id
    completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
}
Write-JsonFile (Join-Path $GeneratedRoot "demo-summary.json") $summary

Write-Host "Docker demo complete. Captures written to $CaptureRoot"
