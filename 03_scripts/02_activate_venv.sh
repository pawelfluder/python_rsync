#!/bin/bash

# run instructions:
# source '03_scripts/02_activate_venv.sh'

# Get the current working directory
CURRENT_DIR="$(pwd)"
# echo "CURRENT_DIR: $CURRENT_DIR"

# Check if .venv directory exists in the current working directory
if [ ! -d "$CURRENT_DIR/.venv" ]; then
  echo "Error: .venv directory does not exist in the current working directory. Please create a virtual environment first."
  return 1
fi

# Activate the virtual environment
source "$CURRENT_DIR/.venv/bin/activate"

# Confirm activation
echo "Virtual environment '.venv' activated from $CURRENT_DIR."
