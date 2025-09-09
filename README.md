# Table Tennis Leaderboard Bot

This project provides a Python script to generate and display a comprehensive table tennis leaderboard system. It fetches match data from Google Sheets, calculates player rankings using the Elo rating system, and sends detailed leaderboard reports to a Telegram group.

## Features

- **Google Sheets Integration**: Reads match data directly from Google Sheets
- **Elo Rating System**: Advanced player ranking based on match history and opponent strength
- **Comprehensive Reports**: Weekly, monthly, and all-time performance analysis
- **Head-to-Head Matrices**: Visual win/loss records between all players
- **Ranking Progression**: Track player performance trends over time
- **Telegram Integration**: Automated report delivery with charts and visualizations
- **Robust Error Handling**: SSL retry logic and connection resilience

## Prerequisites

- Python 3.8+
- Google Cloud Project with Sheets API enabled
- Google Service Account with JSON credentials
- A Telegram bot token and chat ID for sending reports
- Google Sheets document with match data

## Data Format

Your Google Sheets document should have the following columns:
- **Timestamp**: Date and time in format `22/8/2025 00:00:00` (DD/MM/YYYY HH:MM:SS)
- **Winner**: Name of the winning player
- **Runner up**: Name of the losing player (also supports "Loser" for backward compatibility)
- **Set Score**: Match score in format `2-1` (winner sets - loser sets)
- **Date (Optional - if played today)**: Override date in MM/DD/YYYY format (Month/Day/Year)

Example data:
```
Timestamp               Winner      Runner up   Set Score   Date (Optional - if played today)
22/8/2025 00:00:00     Kiran       SrikanthK   2-1         
9/8/2025 19:41:50      Pavan       Kiran       2-0         
9/8/2025 21:42:43      Pavan       Kiran       2-1         9/8/2025
9/8/2025 21:44:09      Pavan       Kiran       2-0         8/25/2025
```

**Date Format Logic**: 
- **Timestamp column**: Uses DD/MM/YYYY HH:MM:SS format (Day/Month/Year with time)
- **Optional Date column**: Uses MM/DD/YYYY format (Month/Day/Year)
- If the optional Date column has a value, that date is used for the match
- If the optional Date column is empty, the Timestamp date is used
- This allows for backdating matches or correcting dates when needed

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Google Cloud Setup

#### Enable Google Sheets API
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click on it and press "Enable"

#### Create Service Account
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in the service account details:
   - Name: `leaderboard-sheets-access`
   - Description: `Service account for leaderboard Google Sheets access`
4. Click "Create and Continue"
5. Skip the optional steps and click "Done"

#### Generate Service Account Key
1. In the "Credentials" page, find your service account
2. Click on the service account email
3. Go to the "Keys" tab
4. Click "Add Key" > "Create New Key"
5. Choose "JSON" format
6. Download the JSON file and save it in your project directory

### 5. Share Google Sheet with Service Account
1. Open your Google Sheet
2. Click the "Share" button
3. Add the service account email (found in the JSON file as `client_email`)
4. Give it "Editor" permissions
5. Click "Send"

### 6. Configure Environment Variables

Create a `.env` file in the project root directory with your credentials:

```bash
# Copy the example and edit with your values
cp .env.example .env
```

Edit the `.env` file with your actual credentials:

```env
# Google Sheets Configuration
GOOGLE_SHEETS_ID=your_google_sheets_document_id
GOOGLE_SHEET_NAME=Form Responses
GOOGLE_SERVICE_ACCOUNT_FILE=./google-service-account.json

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

**Important**: 
- Replace the placeholder values with your actual credentials
- The `.env` file is automatically ignored by git for security
- Never commit credentials to version control

## Running the Script

Execute the script using the provided shell script:

```bash
./run_bot.sh
```

This will:
1. Activate the Python virtual environment
2. Set up environment variables
3. Execute the `leaderboard.py` script
4. Generate and send comprehensive reports to your Telegram chat

## Report Structure

The bot sends reports in the following order:

1. **📊 Metrics Explanation**: Guide on how to read the charts and understand the report flow
2. **🏆 Weekly Leaderboard** (if matches played this week)
3. **📅 Weekly Head-to-Head Matrix** (if matches played this week)
4. **🗓️ Monthly Leaderboard** (if matches played this month)
5. **🗓️ Monthly Head-to-Head Matrix** (if matches played this month)
6. **📅 Last Month's Final Standings** (only during first week of new month)
7. **📈 Ranking Progression Trends**: Shows who's climbing the ranks over the last 5 weeks
8. **🎯 All-Time Head-to-Head Overview**: Complete historical performance matrix

### Smart Reporting Features

- **Conditional Charts**: Weekly and monthly leaderboards/matrices only appear when matches exist in those periods
- **Automatic Scheduling**: Last month's final standings only show during the first 7 days of a new month
- **Clean Interface**: Individual player head-to-head charts are disabled for cleaner reports (functionality preserved in code)
- **Comprehensive Coverage**: All-time matrix always shows complete historical head-to-head data

### Understanding the Reports

#### Leaderboard Columns
- **Elo**: Long-term skill rating based on entire match history
- **Score**: Period performance = Elo + Win Bonus + Set Difference Bonus
- **Set Diff**: Sets won minus sets lost in the period

#### Head-to-Head Matrix
- **Format**: 'Wins-Losses' (e.g., '3-1' = 3 wins, 1 loss vs that opponent)
- **Colors**: White = no games, Light Yellow = struggling, Dark Blue = dominating
- **Usage**: Find your name on the left (row), look across for your record vs each opponent

## How It Works

The `leaderboard.py` script performs the following operations:

1. **Data Fetching**: Connects to Google Sheets using service account authentication
2. **Data Processing**: Normalizes player names and validates match records
3. **Elo Calculation**: Computes skill ratings based on match outcomes and opponent strength
4. **Report Generation**: Creates multiple leaderboard views for different time periods
5. **Visualization**: Generates charts and matrices using Matplotlib and Seaborn
6. **Telegram Delivery**: Sends formatted reports with robust error handling

## Player Name Normalization

The system includes intelligent player name normalization to handle:
- Case variations (e.g., "john" → "John")
- Spacing differences (e.g., "Srikanth K" → "SrikanthK")
- Common aliases and variations

## Error Handling

The script includes comprehensive error handling:
- **SSL Connection Issues**: Automatic retry with exponential backoff
- **Data Validation**: Skips invalid records with detailed logging
- **Network Resilience**: Robust session management for API calls
- **Detailed Logging**: Complete audit trail of operations and errors

## Troubleshooting

### Common Issues

1. **Authentication Error**: Verify service account JSON file path and permissions
2. **Permission Denied**: Ensure Google Sheet is shared with service account email
3. **Sheet Not Found**: Check sheet name matches exactly (case-sensitive)
4. **API Not Enabled**: Confirm Google Sheets API is enabled in your project

### Logs

The script provides detailed logging output. Check console messages for specific error information and troubleshooting guidance.

## File Structure

```
├── leaderboard.py              # Main script
├── requirements.txt            # Python dependencies
├── run_bot.sh                 # Execution script with environment setup
├── README.md                  # This documentation
└── google-service-account.json   # Google service account credentials
```

## Dependencies

- `pandas`: Data manipulation and analysis
- `requests`: HTTP library with retry capabilities
- `matplotlib`: Chart and visualization generation
- `seaborn`: Statistical data visualization
- `gspread`: Google Sheets API client
- `google-auth`: Google authentication library

## Security Notes

- Keep your service account JSON file secure and never commit it to version control
- Use environment variables for sensitive configuration
- Regularly rotate service account keys as per security best practices
- Ensure proper access controls on your Google Sheets document

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the leaderboard system.
