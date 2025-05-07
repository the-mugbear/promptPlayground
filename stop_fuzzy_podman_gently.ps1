# stop_fuzzy_podman_gently.ps1 - Script to stop the containerized application stack (without removing containers)

Write-Host "Stopping containerized development environment via Podman Compose..." -ForegroundColor Yellow

# --- Configuration ---
$ComposeFile = "docker-compose.yml" # Your compose file name
# --------------------

# Get the directory where this script is located
$ScriptDirectory = $PSScriptRoot

# Navigate to the project directory
try {
    Set-Location -Path $ScriptDirectory -ErrorAction Stop
} catch {
    Write-Error "Failed to change directory to '$ScriptDirectory'. Exiting."
    Exit 1
}

# --- Activate Virtual Environment (Optional) ---
$VenvActivateScript = Join-Path -Path $ScriptDirectory -ChildPath ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivateScript) {
    Write-Host "Activating virtual environment: $VenvActivateScript" -ForegroundColor DarkGray
    try {
        . $VenvActivateScript
    } catch {
        Write-Warning "Failed to activate virtual environment. Ensure 'podman-compose' is in your system PATH if not installed in venv."
    }
} elseif (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
    Write-Error "Command 'podman-compose' not found. Please install it ('pip install podman-compose') or ensure venv is activated."
    Exit 1
}
# ---------------------------------------------

# --- Check if Compose file exists ---
if (-not (Test-Path $ComposeFile)) {
    Write-Error "Compose file '$ComposeFile' not found in directory '$(Get-Location)'. Exiting."
    Exit 1
}
# -----------------------------------

# --- Stop services using Podman Compose ---
Write-Host "Stopping services defined in '$ComposeFile' (containers will be stopped, not removed)..."
try {
    # 'stop' stops running containers without removing them.
    podman-compose -f $ComposeFile stop
    Write-Host "Application stack containers have been stopped." -ForegroundColor Green
    Write-Host "Named volumes (like your database) are preserved."
    Write-Host "You can restart them later with 'podman-compose -f $ComposeFile start' or 'podman-compose -f $ComposeFile up -d'."
} catch {
    Write-Error "Failed to stop services with podman-compose. Error: $($_.Exception.Message)"
    Exit 1
}
# -----------------------------------------

Write-Host "Script finished." -ForegroundColor Green