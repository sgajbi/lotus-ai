$ErrorActionPreference = "Stop"

$DemoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunnerPath = Join-Path $DemoRoot "run-demo-docker.ps1"

if (-not (Test-Path $RunnerPath)) {
    throw "Expected docker demo runner at $RunnerPath"
}

& $RunnerPath `
    -GeneratedFolderName "generated-live-provider" `
    -UseProjectEnvFile `
    -EnableLiveProvider `
    -OverrideLiveCallerPolicies
