#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting development environment via podman-compose..."

# Get the directory where this script is located
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "Detected project directory: $SCRIPT_DIR"

# Navigate to the project directory (where docker-compose.yml is)
cd "$SCRIPT_DIR"
echo "Ensured current directory is: $(pwd)"

# --- Optional: Activate Virtual Environment ---
# You might only need this if you need to run host-based commands
# like installing podman-compose itself, or potentially initial migrations
# if not done via `podman-compose exec`. Compose usually reads .env automatically.
VENV_PATH=".venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
    echo "Activating virtual environment: $VENV_PATH"
    source "$VENV_PATH"
    echo "Virtual environment activated."

    # Optional: Check/Install podman-compose if needed
    # if ! command -v podman-compose &> /dev/null; then
    #     echo "podman-compose could not be found. Installing..."
    #     pip install podman-compose
    # fi
else
    echo "Virtual environment activation script not found at $VENV_PATH"
    echo "Ensure '.venv' exists or adjust the path if needed."
    echo "Ensure 'podman-compose' is installed and available in your PATH."
fi
# --------------------------------------------

# --- Define Compose File ---
# Allows easy modification if you rename your file
COMPOSE_FILE="docker-compose.yml"
# ---------------------------

# --- Start all services defined in the compose file ---
echo "Starting services defined in $COMPOSE_FILE..."
# --build: Rebuild the app image if Dockerfile or context changed
# -d: Run in detached mode (background)
podman-compose -f "$COMPOSE_FILE" up --build -d

echo ""
echo "Application stack containers started successfully using podman-compose."
echo "Services defined in '$COMPOSE_FILE' should be running."
echo ""
echo "Next steps you might need:"
echo "- Run migrations (if needed): podman-compose -f '$COMPOSE_FILE' exec web flask db upgrade"
echo "- View logs: podman-compose -f '$COMPOSE_FILE' logs -f"
echo "- Stop services: podman-compose -f '$COMPOSE_FILE' down"
echo ""
echo "Web application should be accessible at http://localhost:8000 (or the port you configured)"
echo "RabbitMQ Management UI (if running): http://localhost:15672"

# You can optionally add the migration command here if you always want it run on start:
# echo "Running database migrations..."
# podman-compose -f "$COMPOSE_FILE" exec web flask db upgrade
# echo "Migrations complete."

# You can optionally add log following here, but it will keep the script running:
# echo "Following logs (Press Ctrl+C to stop)..."
# podman-compose -f "$COMPOSE_FILE" logs -f