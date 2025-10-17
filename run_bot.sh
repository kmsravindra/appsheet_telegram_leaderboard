#!/bin/bash

# Navigate to the directory where the script is located
cd "$(dirname "$0")"

echo "🤖 Starting Leaderboard Bot..."
echo ""

# Check for required files
MISSING_FILES=()

if [ ! -f ".env" ]; then
    MISSING_FILES+=(".env - Environment variables and credentials")
fi

if [ ! -f "google-service-account.json" ]; then
    MISSING_FILES+=("google-service-account.json - Google Sheets access")
fi

# If any files are missing, show error and exit
if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "❌ Error: Required file(s) not found:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   • $file"
    done
    echo ""
    echo "📝 See README.md for setup instructions."
    exit 1
fi

echo "✅ All required files found"
echo ""

# Check if venv exists, create it if not
if [ ! -d "venv" ]; then
    echo "📦 Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "✅ Virtual environment created!"
    echo ""
fi

# Activate the Python virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements only if requirements.txt changed or .installed doesn't exist
if [ ! -f ".installed" ] || [ "requirements.txt" -nt ".installed" ]; then
    echo "📥 Installing/updating requirements..."
    pip install -r requirements.txt --quiet
    touch .installed
    echo "✅ Requirements installed"
else
    echo "✅ Requirements already up to date"
fi

echo ""
echo "🚀 Starting leaderboard.py..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the Python script (it will load .env automatically)
python leaderboard.py

# Capture exit code
EXIT_CODE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Bot stopped successfully"
else
    echo "❌ Bot exited with error code: $EXIT_CODE"
fi

# Deactivate virtual environment
deactivate