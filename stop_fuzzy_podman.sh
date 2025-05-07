#!/bin/bash

# stop_fuzzy_podman.sh - Script to stop and remove the containerized application stack

# --- Configuration ---
COMPOSE_FILE="docker-compose.yml" # Your compose file name
# --------------------

# --- Helper Functions ---
echo_color() {
    echo -e "\033[${1}m${2}\033[0m"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo_color "31" "Error: Command '$1' not found. Please install it or ensure your PATH is configured correctly."
        exit 1
    fi
}
# --------------------

echo_color "33" "Stopping and removing containerized development environment via Podman Compose..."

# Get the directory where this script is located
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# echo "Detected project directory: $SCRIPT_DIRECTORY" # Optional

# Navigate to the project directory
cd "$SCRIPT_DIRECTORY" || { echo_color "31" "Failed to change directory to '$SCRIPT_DIRECTORY'. Exiting."; exit 1; }
# echo "Ensured current directory is: $(pwd)" # Optional

# --- Activate Virtual Environment (Optional) ---
VENV_ACTIVATE_SCRIPT="$SCRIPT_DIRECTORY/.venv/bin/activate"
if [ -f "$VENV_ACTIVATE_SCRIPT" ]; then
    echo_color "36" "Activating virtual environment: $VENV_ACTIVATE_SCRIPT"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE_SCRIPT"
    # echo_color "36" "Virtual environment activated."
elif ! command -v podman-compose &> /dev/null; then
    echo_color "31" "Error: Command 'podman-compose' not found. Please install it ('pip install podman-compose') or ensure venv is activated."
    exit 1
fi
# ---------------------------------------------

# --- Check if Compose file exists ---
if [ ! -f "$COMPOSE_FILE" ]; then
    echo_color "31" "Error: Compose file '$COMPOSE_FILE' not found in directory '$(pwd)'. Exiting."
    exit 1
fi
# -----------------------------------

# --- Stop services using Podman Compose ---
echo "Stopping and removing services defined in '$COMPOSE_FILE'..."
if podman-compose -f "$COMPOSE_FILE" down --volumes --remove-orphans; then
    echo_color "32" "Application stack has been stopped and removed."
else
    echo_color "31" "Failed to stop services with podman-compose."
    exit 1
fi
# -----------------------------------------

echo_color "32" "Script finished."