# stop_fuzzy_podman.ps1 - Script to stop and remove the containerized application stack

Write-Host "Stopping and removing containerized development environment via Podman Compose..." -ForegroundColor Yellow

# --- Configuration ---
$ComposeFile = "docker-compose.yml" # Your compose file name
# --------------------

# Navigate to the script directory
try {
    Set-Location -Path $PSScriptRoot -ErrorAction Stop
} catch {
    Write-Error "Failed to change directory to '$PSScriptRoot'. Exiting."
    Exit 1
}

# --- Activate Virtual Environment (Optional) ---
$VenvActivateScript = Join-Path -Path $PSScriptRoot -ChildPath ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivateScript) {
    Write-Host "Activating virtual environment: $VenvActivateScript" -ForegroundColor DarkGray
    try {
        . $VenvActivateScript
    } catch {
        Write-Warning "Failed to activate virtual environment. Ensure 'podman-compose' is in your PATH."
    }
} elseif (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
    Write-Error "Command 'podman-compose' not found. Please install it or activate your venv."
    Exit 1
}
# ---------------------------------------------

# Check for compose file
if (-not (Test-Path $ComposeFile)) {
    Write-Error "Compose file '$ComposeFile' not found in directory '$(Get-Location)'. Exiting."
    Exit 1
}

# Prompt: remove volumes?
$volInput = Read-Host "Do you want to remove volumes as well? [y/N]"
if ($volInput -match '^[Yy]') {
    $volumesFlag = "--volumes"
    Write-Host "→ Volumes will be removed." -ForegroundColor Yellow
} else {
    $volumesFlag = ""
    Write-Host "→ Volumes will be preserved." -ForegroundColor Yellow
}

# Stop services using Podman Compose
Write-Host "Stopping and removing services defined in '$ComposeFile'..." -ForegroundColor Yellow

try {
    # Build argument list dynamically
    $args = @("-f", $ComposeFile, "down")
    if ($volumesFlag) { $args += $volumesFlag }
    $args += "--remove-orphans"

    podman-compose @args

    Write-Host "Application stack has been stopped and removed." -ForegroundColor Green
} catch {
    Write-Error "Failed to stop services with podman-compose. Error: $($_.Exception.Message)"
    Exit 1
}

Write-Host "Script finished." -ForegroundColor Green
