#!/bin/bash

# run instructions:
# source '03_scripts/03_requirements.sh'

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# echo "SCRIPT_DIR: $SCRIPT_DIR"

# Define the repository path
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# echo "REPO_DIR: $REPO_DIR"

# Check if .venv directory exists in the repository path
if [ ! -d "$REPO_DIR/.venv" ]; then
  echo "Error: .venv directory does not exist in the repository path. Please create a virtual environment first."
  echo "Expected path: $REPO_DIR/.venv"
  exit 1
fi

# Activate the virtual environment
source "$REPO_DIR/.venv/bin/activate"

# Upgrade pip to the latest version
pip install --upgrade pip

# Install required packages if requirements.txt exists
if [ -f "$REPO_DIR/requirements.txt" ]; then
  pip install -r "$REPO_DIR/requirements.txt"
else
  echo "Warning: requirements.txt not found. Skipping package installation."
fi

# Confirm installation
echo "Required packages installed successfully."
