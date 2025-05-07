# stop_fuzzy_podman.ps1 - Script to stop and remove the containerized application stack

Write-Host "Stopping and removing containerized development environment via Podman Compose..." -ForegroundColor Yellow

# --- Configuration ---
$ComposeFile = "docker-compose.yml" # Your compose file name
# --------------------

# Get the directory where this script is located
$ScriptDirectory = $PSScriptRoot
# Write-Host "Detected project directory: $ScriptDirectory" # Optional

# Navigate to the project directory
try {
    Set-Location -Path $ScriptDirectory -ErrorAction Stop
    # Write-Host "Ensured current directory is: $(Get-Location)" # Optional
} catch {
    Write-Error "Failed to change directory to '$ScriptDirectory'. Exiting."
    Exit 1
}

# --- Activate Virtual Environment (Optional) ---
# Primarily for ensuring 'podman-compose' is found
$VenvActivateScript = Join-Path -Path $ScriptDirectory -ChildPath ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivateScript) {
    Write-Host "Activating virtual environment: $VenvActivateScript" -ForegroundColor DarkGray
    try {
        . $VenvActivateScript
        # Write-Host "Virtual environment activated." -ForegroundColor DarkGray
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
Write-Host "Stopping and removing services defined in '$ComposeFile'..."
try {
    # 'down' stops containers, and removes containers, networks, volumes, and images created by 'up'.
    # Add --volumes to also remove named volumes declared in the 'volumes' section of the Compose file and anonymous volumes attached to containers.
    # Add --remove-orphans to remove containers for services not defined in the Compose file.
    podman-compose -f $ComposeFile down --volumes --remove-orphans
    Write-Host "Application stack has been stopped and removed." -ForegroundColor Green
} catch {
    Write-Error "Failed to stop services with podman-compose. Error: $($_.Exception.Message)"
    Exit 1
}
# -----------------------------------------

Write-Host "Script finished." -ForegroundColor Green