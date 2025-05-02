# start_fuzzy_podman.ps1 - Script to start the containerized application stack using Podman Compose

# to stop use command "podman-compose -f docker-compose.yml down"

Write-Host "Starting containerized development environment via Podman Compose..." -ForegroundColor Yellow

# --- Configuration ---
$ComposeFile = "docker-compose.yml" # Your compose file name
# Set this to the name of your default podman machine if unsure, or leave blank to use default
$PodmanMachineName = "fuzzy-podman" # Or determine default automatically later if needed
# --------------------

# Get the directory where this script is located
$ScriptDirectory = $PSScriptRoot
Write-Host "Detected project directory: $ScriptDirectory"

# Navigate to the project directory
try {
    Set-Location -Path $ScriptDirectory -ErrorAction Stop
    Write-Host "Ensured current directory is: $(Get-Location)"
} catch {
    Write-Error "Failed to change directory to '$ScriptDirectory'. Exiting."
    Exit 1
}

# --- Activate Virtual Environment (Optional but Recommended) ---
# Primarily needed to ensure 'podman-compose' command is found if installed via pip in venv
$VenvActivateScript = Join-Path -Path $ScriptDirectory -ChildPath ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivateScript) {
    Write-Host "Activating virtual environment: $VenvActivateScript"
    try {
        . $VenvActivateScript
        Write-Host "Virtual environment activated."
        # Optional: Check if podman-compose exists now
        if (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
             Write-Warning "Command 'podman-compose' not found after activating venv. Make sure it's installed ('pip install podman-compose')."
             # Optionally exit here: Exit 1
        }
    } catch {
        Write-Warning "Failed to activate virtual environment. Ensure 'podman-compose' is in your system PATH if not installed in venv."
    }
} else {
    Write-Warning "Virtual environment script not found at '$VenvActivateScript'."
    Write-Warning "Ensure 'podman-compose' is installed and available in your system PATH."
    if (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
         Write-Error "Command 'podman-compose' not found. Please install it ('pip install podman-compose') or ensure venv is activated."
         Exit 1
    }
}
# --------------------------------------------------------------

# --- Check and Start Podman Machine ---
Write-Host "Checking status of Podman machine '$PodmanMachineName'..."
$machineStatus = podman machine list --format "{{.Name}} {{.Running}}" | Where-Object { $_ -match "^$PodmanMachineName\s" }

if ($machineStatus -match "true$") {
    Write-Host "Podman machine '$PodmanMachineName' is already running." -ForegroundColor Green
} elseif ($machineStatus -match "false$") {
    Write-Host "Podman machine '$PodmanMachineName' found but not running. Starting..."
    try {
        podman machine start $PodmanMachineName -ErrorAction Stop
        Write-Host "Podman machine '$PodmanMachineName' started successfully." -ForegroundColor Green
    } catch {
        Write-Error "Failed to start Podman machine '$PodmanMachineName'. Please check Podman setup. Error: $($_.Exception.Message)"
        Exit 1
    }
} else {
    Write-Warning "Podman machine '$PodmanMachineName' not found or status unknown. Attempting to start default machine..."
    try {
        # Attempt to start the default machine if specific one not found/running
        podman machine start -ErrorAction Stop
        Write-Host "Default Podman machine started successfully." -ForegroundColor Green
    } catch {
         Write-Error "Failed to start default Podman machine. Please run 'podman machine init' and 'podman machine start' manually. Error: $($_.Exception.Message)"
         Exit 1
    }
}
# ------------------------------------

# --- Check if Compose file exists ---
if (-not (Test-Path $ComposeFile)) {
    Write-Error "Compose file '$ComposeFile' not found in directory '$(Get-Location)'. Exiting."
    Exit 1
}
# -----------------------------------

# --- Start services using Podman Compose ---
Write-Host "Starting services defined in '$ComposeFile' using podman-compose..."
try {
    # Use --build flag to rebuild image if Dockerfile or context changed
    # Use -d flag to run in detached (background) mode
    # Use -f to specify the compose file name
    # REMOVED '-ErrorAction Stop' from the end of this line:
    podman-compose -f $ComposeFile up --build -d

    Write-Host "Application stack containers should be starting via podman-compose." -ForegroundColor Green
    Write-Host "(Use 'podman ps' to check container status)"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "- View running containers : podman ps"
    Write-Host "- View all containers     : podman ps -a"
    Write-Host "- Follow logs           : podman-compose -f '$ComposeFile' logs -f"
    Write-Host "- Stop services         : podman-compose -f '$ComposeFile' down"
    Write-Host "- Run migrations        : podman-compose -f '$ComposeFile' exec web flask db upgrade"
    Write-Host ""
    # Use the host port mapped in the compose file (e.g., 8021)
    Write-Host "Web application should become accessible at http://localhost:8021 (or the host port you configured)"
    Write-Host "RabbitMQ Management UI should be accessible at http://localhost:15672"

} catch {
    Write-Error "Failed to start services with podman-compose. Error: $($_.Exception.Message)"
    # Optionally run 'down' to clean up partial startup
    # Write-Warning "Attempting cleanup..."
    # podman-compose -f $ComposeFile down --volumes --remove-orphans
    Exit 1
}
# -----------------------------------------