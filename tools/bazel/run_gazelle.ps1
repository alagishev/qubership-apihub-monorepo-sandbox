# Run Gazelle for Go packages on native Windows (PowerShell).
# Root cause of `bazel run //:gazelle-backend` failure: the bash launcher looks for
# gazelle-backend without .exe under the execroot. Invoke gazelle_bin.exe directly.
param(
    [ValidateSet("all", "commons-go", "backend", "linter", "agents-backend")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

if (-not (Test-Path ".bazelrc.user")) {
    $userRoot = "C:/tmp/bazel-out"
    @"
# Auto-created for Windows paths with spaces in %USERPROFILE%.
startup --output_user_root=$userRoot
"@ | Set-Content -Encoding ascii ".bazelrc.user"
    Write-Host "Created .bazelrc.user with output_user_root=$userRoot"
}

bazel build --config=go-only //:gazelle_bin
$gazelle = Get-ChildItem -Path "bazel-bin" -Recurse -Filter "gazelle_bin.exe" |
    Where-Object { $_.FullName -match "gazelle_bin_" } |
    Select-Object -First 1
if (-not $gazelle) {
    throw "gazelle_bin.exe not found under bazel-bin"
}

function Invoke-Gazelle([string]$Prefix, [string]$Path) {
    Write-Host "==> gazelle update $Path"
    & $gazelle.FullName update `
        -index=lazy `
        -repo_root="$Root" `
        -go_prefix="$Prefix" `
        -go_naming_convention=import `
        -external=external `
        $Path
}

switch ($Target) {
    "commons-go" {
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-commons-go" "qubership-apihub-commons-go"
    }
    "backend" {
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service" `
            "qubership-apihub-backend/qubership-apihub-service"
    }
    "linter" {
        Invoke-Gazelle "github.com/Netcracker/qubership-api-linter-service" `
            "qubership-api-linter-service/qubership-api-linter-service"
    }
    "agents-backend" {
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-agents-backend" `
            "qubership-apihub-agents-backend/qubership-apihub-agents-backend"
    }
    "all" {
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-commons-go" "qubership-apihub-commons-go"
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service" `
            "qubership-apihub-backend/qubership-apihub-service"
        Invoke-Gazelle "github.com/Netcracker/qubership-api-linter-service" `
            "qubership-api-linter-service/qubership-api-linter-service"
        Invoke-Gazelle "github.com/Netcracker/qubership-apihub-agents-backend" `
            "qubership-apihub-agents-backend/qubership-apihub-agents-backend"
    }
}

python tools/bazel/sync_go_build_deps.py
Write-Host "Done. Try: bazel build --config=go-only //qubership-apihub-backend/qubership-apihub-service:qubership-apihub-service"
