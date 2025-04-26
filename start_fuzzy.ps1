# start_dev.ps1 - Script to start Flask dev server and Celery worker
# (Assumes this script is located in the project's root directory)

Write-Host "Starting development environment..."

# --- Configuration ---

# Get the directory where this script is located
$ProjectDirectory = $PSScriptRoot
Write-Host "Detected project directory: $ProjectDirectory"

# Relative path to the virtual environment from the project directory
# Assumes a standard '.venv' folder structure
$VenvActivateScript = Join-Path -Path $ProjectDirectory -ChildPath ".venv\Scripts\Activate.ps1"

# Flask App configuration
$env:FLASK_APP = "fuzzy_prompts:create_app" # Points to your create_app factory
$env:FLASK_DEBUG = "1" # Enable Flask debug mode (optional)

# Celery App configuration
# IMPORTANT: Still needs to be the Python import path, not a file system path.
#            Replace 'fuzzy_prompts.celery' if your Celery app instance is elsewhere.
$CeleryAppPath = "celery_app.celery"

# ---------------------

# Navigate to the project directory (where the script is)
cd $ProjectDirectory
Write-Host "Ensured current directory is: $(Get-Location)"

# Activate virtual environment (if found)
if (Test-Path $VenvActivateScript) {
    Write-Host "Activating virtual environment: $VenvActivateScript"
    . $VenvActivateScript
    Write-Host "Virtual environment activated."
} else {
    Write-Host "Virtual environment activation script not found at expected location: $VenvActivateScript"
    Write-Host "Ensure '.venv' exists in project root or adjust the path."
    Write-Host "Attempting to continue without virtual environment activation..."
}

# Start Flask Development Server in a new window
# 'flask run' should work correctly now as we are in the project directory
Write-Host "Starting Flask development server (FLASK_APP=$env:FLASK_APP)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& flask run"

# Wait a few seconds (optional)
Start-Sleep -Seconds 3

# Start Celery Worker in a new window
# 'celery -A ...' should also find the app now due to the working directory
Write-Host "Starting Celery worker (App: $CeleryAppPath)..."
# Use the eventlet pool for Windows compatibility
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& celery -A $CeleryAppPath worker -P eventlet --loglevel=info"

Write-Host "Flask server and Celery worker processes started in separate windows."
Write-Host "Close the respective PowerShell windows to stop the processes."