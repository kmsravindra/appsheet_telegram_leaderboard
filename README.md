# Table Tennis Leaderboard Bot

This project provides a Python script to generate and display a table tennis leaderboard. It fetches match data from an AppSheet application, calculates player rankings using the Elo rating system, and sends leaderboard reports to a Telegram group.

## Prerequisites

- Python 3.8+
- An AppSheet account with a table for match data.
- A Telegram bot token and a chat ID for sending reports.

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file:**
    Create a file named `.env` in the root of the project directory. This file will store your sensitive credentials.

5.  **Add environment variables to the `.env` file:**
    Open the `.env` file and add the following lines, replacing the placeholder values with your actual credentials:

    ```env
    export APPSHEET_APP_ID="YOUR_APPSHEET_APP_ID"
    export APPSHEET_ACCESS_KEY="YOUR_APPSHEET_ACCESS_KEY"
    export APPSHEET_TABLE_NAME="YOUR_APPSHEET_TABLE_NAME" # Optional, defaults to ASPTTDailyScores
    export TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    export TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"
    ```

## Running the Script

You can run the script using the provided shell script, which handles sourcing the environment variables and activating the virtual environment.

```bash
bash run_bot.sh
```

This will execute the `leaderboard.py` script, which will then generate and send the reports to your configured Telegram chat.

## How it Works

The `leaderboard.py` script performs the following actions:
-   Fetches match data from the specified AppSheet table.
-   Normalizes player names to handle aliases and variations.
-   Calculates Elo ratings for all players based on match history.
-   Generates weekly, monthly, and last month's leaderboards.
-   Creates visualizations for leaderboards, ranking progression, and head-to-head stats using Matplotlib and Seaborn.
-   Sends the generated reports and charts as messages and photos to the specified Telegram group. 