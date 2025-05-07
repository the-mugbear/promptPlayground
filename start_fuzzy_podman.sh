#!/bin/bash

# start_fuzzy_podman.sh - Script to start the containerized application stack using Podman Compose

# --- Configuration ---
COMPOSE_FILE="docker-compose.yml" # Your compose file name
# Podman machine name - less relevant for native Linux Podman, but can be set if needed
# PODMAN_MACHINE_NAME="fuzzy-podman"
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

echo_color "33" "Starting containerized development environment via Podman Compose..."

# Get the directory where this script is located
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
echo "Detected project directory: $SCRIPT_DIRECTORY"

# Navigate to the project directory
cd "$SCRIPT_DIRECTORY" || { echo_color "31" "Failed to change directory to '$SCRIPT_DIRECTORY'. Exiting."; exit 1; }
echo "Ensured current directory is: $(pwd)"

# --- Activate Virtual Environment (Optional but Recommended) ---
VENV_ACTIVATE_SCRIPT="$SCRIPT_DIRECTORY/.venv/bin/activate" # Common path for Bash
if [ -f "$VENV_ACTIVATE_SCRIPT" ]; then
    echo "Activating virtual environment: $VENV_ACTIVATE_SCRIPT"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE_SCRIPT"
    echo "Virtual environment activated."
    # Optional: Check if podman-compose exists now
    if ! command -v podman-compose &> /dev/null; then
        echo_color "33" "Warning: Command 'podman-compose' not found after activating venv. Make sure it's installed ('pip install podman-compose')."
    fi
else
    echo_color "33" "Warning: Virtual environment script not found at '$VENV_ACTIVATE_SCRIPT'."
    echo_color "33" "Ensure 'podman-compose' is installed and available in your system PATH."
    check_command "podman-compose"
fi
# --------------------------------------------------------------

# --- Check Podman Service/Socket (for native Linux, machine check is different) ---
# On Linux, podman often runs as a service or via a socket.
# A simple check could be 'podman info' or checking the socket.
# For simplicity, we'll assume podman client can connect if installed.
check_command "podman"
echo "Podman client found."
# If you were using a Podman machine on Linux (less common but possible):
# if [ -n "$PODMAN_MACHINE_NAME" ]; then
#     echo "Checking status of Podman machine '$PODMAN_MACHINE_NAME'..."
#     if ! podman machine inspect "$PODMAN_MACHINE_NAME" &>/dev/null; then
#         echo_color "33" "Podman machine '$PODMAN_MACHINE_NAME' not found. Attempting to start default..."
#         if ! podman machine start; then # Tries to start the default or last used
#             echo_color "31" "Failed to start default Podman machine. Please run 'podman machine init' and 'podman machine start' manually."
#             exit 1
#         fi
#         echo_color "32" "Default Podman machine started."
#     elif ! podman machine inspect "$PODMAN_MACHINE_NAME" | grep -q '"Running": true'; then
#         echo "Podman machine '$PODMAN_MACHINE_NAME' found but not running. Starting..."
#         if ! podman machine start "$PODMAN_MACHINE_NAME"; then
#             echo_color "31" "Failed to start Podman machine '$PODMAN_MACHINE_NAME'."
#             exit 1
#         fi
#         echo_color "32" "Podman machine '$PODMAN_MACHINE_NAME' started successfully."
#     else
#         echo_color "32" "Podman machine '$PODMAN_MACHINE_NAME' is already running."
#     fi
# fi
# ------------------------------------

# --- Check if Compose file exists ---
if [ ! -f "$COMPOSE_FILE" ]; then
    echo_color "31" "Error: Compose file '$COMPOSE_FILE' not found in directory '$(pwd)'. Exiting."
    exit 1
fi
# -----------------------------------

# --- Start services using Podman Compose ---
echo "Starting services defined in '$COMPOSE_FILE' using podman-compose..."
if podman-compose -f "$COMPOSE_FILE" up --build -d; then
    echo_color "32" "Application stack containers should be starting via podman-compose."
    echo "(Use 'podman ps' to check container status)"
    echo ""
    echo "Useful commands:"
    echo "- View running containers : podman ps"
    echo "- View all containers     : podman ps -a"
    echo "- Follow logs             : podman-compose -f '$COMPOSE_FILE' logs -f"
    echo "- Stop services (and remove): podman-compose -f '$COMPOSE_FILE' down"
    echo "- Stop services (retain)  : podman-compose -f '$COMPOSE_FILE' stop"
    echo "- Run migrations          : podman-compose -f '$COMPOSE_FILE' exec web flask db upgrade"
    echo ""
    echo "Web application should become accessible at http://localhost:8021 (or the host port you configured)"
    echo "RabbitMQ Management UI should be accessible at http://localhost:15672"
else
    echo_color "31" "Failed to start services with podman-compose."
    # Optionally run 'down' to clean up partial startup
    # echo_color "33" "Attempting cleanup..."
    # podman-compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
    exit 1
fi
# -----------------------------------------

echo_color "32" "Script finished."