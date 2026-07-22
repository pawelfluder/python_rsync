#!/bin/bash

# run instructions:
# bash '03_scripts/01_create_venv.sh'

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# echo "SCRIPT_DIR: $SCRIPT_DIR"

# Define the repository path
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# echo "REPO_DIR: $REPO_DIR"

# Check if .venv already exists
if [ -d "$REPO_DIR/.venv" ]; then
  echo "Error: .venv directory already exists in the repository path."
  exit 1
fi

# Create the virtual environment
python3 -m venv "$REPO_DIR/.venv"

# Confirm creation
echo "Virtual environment '.venv' created in $REPO_DIR."
