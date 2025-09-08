#!/bin/bash

# Navigate to the directory where the script is located
cd "$(dirname "$0")"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "💡 Please create a .env file with your credentials."
    echo "📝 See README.md for setup instructions."
    exit 1
fi

echo "🔐 Loading credentials from .env file..."

# Activate the Python virtual environment
source venv/bin/activate

# Install requirements (only if needed)
pip3 install -r requirements.txt --quiet

# Run the Python script (it will load .env automatically)
python3 leaderboard.py
