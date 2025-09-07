#!/bin/bash

# Navigate to the directory where the script is located
cd "$(dirname "$0")"

# Load the environment variables from the .env file
source .env

# Activate the Python virtual environment
source venv/bin/activate

# Run the Python script
python3 leaderboard.py