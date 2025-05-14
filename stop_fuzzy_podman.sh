#!/bin/bash
set -euo pipefail # Exit on error, unset variable, or pipe failure

# stop_fuzzy_podman.sh - Script to stop and optionally remove volumes for the containerized application stack

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

echo_color "33" "Preparing to stop containerized environment via Podman Compose..."

# Get the directory where this script is located
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Navigate to the project directory
cd "$SCRIPT_DIRECTORY" || { echo_color "31" "Failed to change directory to '$SCRIPT_DIRECTORY'. Exiting."; exit 1; }
echo "Operating in directory: $(pwd)"

# --- Activate Virtual Environment (Optional but Recommended) ---
VENV_ACTIVATE_SCRIPT="$SCRIPT_DIRECTORY/.venv/bin/activate" # Common path for Bash
if [ -f "$VENV_ACTIVATE_SCRIPT" ]; then
    echo_color "36" "Activating virtual environment: $VENV_ACTIVATE_SCRIPT"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE_SCRIPT"
    # Optional: Check if podman-compose exists now
    if ! command -v podman-compose &> /dev/null; then
        echo_color "33" "Warning: Command 'podman-compose' not found after activating venv. Make sure it's installed ('pip install podman-compose')."
        # If it's critical and not found, you might want to exit
        # exit 1
    fi
else
    echo_color "33" "Warning: Virtual environment script not found at '$VENV_ACTIVATE_SCRIPT'."
    echo_color "33" "Ensure 'podman-compose' is installed and available in your system PATH."
    check_command "podman-compose" # Check if it's available globally if venv is not used
fi
# --------------------------------------------------------------

# --- Check if Compose file exists ---
if [ ! -f "$COMPOSE_FILE" ]; then
    echo_color "31" "Error: Compose file '$COMPOSE_FILE' not found in directory '$(pwd)'. Exiting."
    exit 1
fi
# -----------------------------------

# --- Ask about removing volumes ---
REMOVE_VOLUMES_OPTION=""
read -r -p "$(echo_color '33' 'Do you want to remove Docker volumes (e.g., database data)? (yes/No): ')" USER_CHOICE

# Convert choice to lowercase
USER_CHOICE_LOWER=$(echo "$USER_CHOICE" | tr '[:upper:]' '[:lower:]')

if [[ "$USER_CHOICE_LOWER" == "yes" || "$USER_CHOICE_LOWER" == "y" ]]; then
    REMOVE_VOLUMES_OPTION="--volumes"
    echo_color "31" "Volumes will be removed."
else
    echo_color "32" "Volumes will be kept."
fi
# ----------------------------------

# --- Stop services using Podman Compose ---
echo_color "33" "Stopping and removing services defined in '$COMPOSE_FILE'..."
# The --remove-orphans flag is generally safe and good for cleanup.
# The $REMOVE_VOLUMES_OPTION will either be "--volumes" or an empty string.
if podman-compose -f "$COMPOSE_FILE" down $REMOVE_VOLUMES_OPTION --remove-orphans; then
    if [ -n "$REMOVE_VOLUMES_OPTION" ]; then
        echo_color "32" "Application stack has been stopped, and volumes have been removed."
    else
        echo_color "32" "Application stack has been stopped. Volumes have been preserved."
    fi
else
    echo_color "31" "Failed to stop services with podman-compose."
    exit 1
fi
# -----------------------------------------

echo_color "32" "Script finished."