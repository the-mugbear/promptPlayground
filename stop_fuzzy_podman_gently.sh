#!/bin/bash

# stop_fuzzy_podman_gently.sh - Script to stop the containerized application stack (without removing containers)

# --- Configuration ---
COMPOSE_FILE="docker-compose.yml" # Your compose file name
# --------------------

# --- Helper Functions ---
echo_color() {
    # Usage: echo_color "COLOR_CODE" "Message"
    # Colors: 31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan
    echo -e "\033[${1}m${2}\033[0m"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo_color "31" "Error: Command '$1' not found. Please install it or ensure your PATH is configured correctly."
        exit 1
    fi
}
# --------------------

echo_color "33" "Stopping containerized development environment via Podman Compose..."

# Get the directory where this script is located
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Navigate to the project directory
cd "$SCRIPT_DIRECTORY" || { echo_color "31" "Failed to change directory to '$SCRIPT_DIRECTORY'. Exiting."; exit 1; }

# --- Activate Virtual Environment (Optional) ---
VENV_ACTIVATE_SCRIPT="$SCRIPT_DIRECTORY/.venv/bin/activate"
if [ -f "$VENV_ACTIVATE_SCRIPT" ]; then
    echo_color "36" "Activating virtual environment: $VENV_ACTIVATE_SCRIPT"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE_SCRIPT"
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
echo "Stopping services defined in '$COMPOSE_FILE' (containers will be stopped, not removed)..."
if podman-compose -f "$COMPOSE_FILE" stop; then
    echo_color "32" "Application stack containers have been stopped."
    echo_color "32" "Named volumes (like your database) are preserved."
    echo "You can restart them later with 'podman-compose -f $COMPOSE_FILE start' or 'podman-compose -f $COMPOSE_FILE up -d'."
else
    echo_color "31" "Failed to stop services with podman-compose."
    exit 1
fi
# -----------------------------------------

echo_color "32" "Script finished."