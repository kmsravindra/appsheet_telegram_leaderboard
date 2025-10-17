# Table Tennis Leaderboard Bot

This project provides a Python script to generate and display a comprehensive table tennis leaderboard system. It fetches match data from Google Sheets, calculates player rankings using the Elo rating system, and sends detailed leaderboard reports to a Telegram group.

## Features

- **Google Sheets Integration**: Reads match data directly from Google Sheets with flexible date parsing
- **Elo Rating System**: Advanced player ranking based on match history and opponent strength
- **Comprehensive Reports**: Weekly, monthly, last month's final standings, and all-time performance analysis
- **Head-to-Head Matrices**: Visual win/loss records between all players with color-coded performance indicators
- **Ranking Progression**: Track player performance trends over the last 5 weeks
- **Smart Reporting**: Conditional charts that only appear when matches exist in specific periods
- **Telegram Integration**: Automated report delivery with charts and visualizations
- **Robust Error Handling**: SSL retry logic, connection resilience, and comprehensive error recovery
- **Flexible Date Handling**: Support for both timestamp and optional date override columns
- **Enhanced Shell Script**: Automated environment setup with dependency management

## Prerequisites

- Python 3.8+
- Google Cloud Project with Sheets API enabled
- Google Service Account with JSON credentials
- A Telegram bot token and chat ID for sending reports
- Google Sheets document with match data

## Data Format

Your Google Sheets document should have the following columns:
- **Timestamp**: Date and time in MM/DD/YYYY HH:MM:SS format (Month/Day/Year with time)
- **Winner**: Name of the winning player
- **Runner up**: Name of the losing player (also supports "Loser" for backward compatibility)
- **Set Score**: Match score in format `2-1` (winner sets - loser sets, also supports "Score" or "Final Score")
- **Date (Optional - if played today)**: Override date in MM/DD/YYYY format (Month/Day/Year)

Example data:
```
Timestamp               Winner      Runner up   Set Score   Date (Optional - if played today)
9/8/2025 19:41:50      Pavan       Kiran       2-0         
9/8/2025 21:42:43      Pavan       Kiran       2-1         9/8/2025
9/8/2025 21:44:09      Pavan       Kiran       2-0         8/25/2025
```

**Date Format Logic**: 
- **Timestamp column**: Uses MM/DD/YYYY HH:MM:SS format (e.g., `9/8/2025 21:54:42`)
- **Optional Date column**: Uses MM/DD/YYYY format (e.g., `9/8/2025`, `8/25/2025`)
- If the optional Date column has a value, that date is used for the match
- If the optional Date column is empty, the Timestamp date is used
- This allows for backdating matches or correcting dates when needed
- **Flexible Parsing**: Supports both formats: `%m/%d/%Y %H:%M:%S` and `%m/%d/%Y`
- **Column Name Flexibility**: Score column accepts "Set Score", "Score", or "Final Score"

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Google Cloud Setup

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
6. Download the JSON file and save it as `google-service-account.json` in your project directory

**Note**: You can reference `google-service-account.json.example` to see the expected structure of the service account file.

### 3. Share Google Sheet with Service Account
1. Open your Google Sheet
2. Click the "Share" button
3. Add the service account email (found in the JSON file as `client_email`)
4. Give it "Editor" permissions
5. Click "Send"

### 4. Configure Environment Variables

Create a `.env` file in the project root directory with your credentials:

```bash
# Copy the example and edit with your values
cp .env.example .env
```

Edit the `.env` file with your actual credentials:

```env
# Google Sheets Configuration
GOOGLE_SHEETS_ID=your_google_sheets_document_id_here
GOOGLE_SHEET_NAME=Form Responses
GOOGLE_SERVICE_ACCOUNT_FILE=./google-service-account.json

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

**Important**: 
- Replace the placeholder values with your actual credentials
- The `.env` file is automatically ignored by git for security
- Never commit credentials to version control
- The script automatically loads environment variables using `python-dotenv`

## Running the Script

Execute the script using the enhanced shell script:

```bash
./run_bot.sh
```

The shell script provides comprehensive automation:
1. **Environment Validation**: Checks for required files (`.env`, `google-service-account.json`)
2. **Virtual Environment Management**: Creates and activates Python virtual environment automatically
3. **Dependency Management**: Installs/updates requirements only when needed (tracks with `.installed` file)
4. **Error Handling**: Provides clear error messages and exit codes
5. **Progress Feedback**: Shows detailed status updates throughout execution
6. **Automatic Cleanup**: Properly deactivates virtual environment on completion

**Manual Execution** (only if you prefer not to use `run_bot.sh`):
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the script
python leaderboard.py

# Deactivate when done
deactivate
```

**Note**: The `run_bot.sh` script handles all of the above automatically, including environment creation, dependency management, and cleanup.

## Report Structure

The bot sends reports in the following order:

1. **📊 Metrics Explanation**: Comprehensive guide on how to read the charts and understand the report flow
2. **🏆 Weekly Leaderboard** (conditional - only if matches played this week)
3. **📅 Weekly Head-to-Head Matrix** (conditional - only if matches played this week)
4. **🗓️ Monthly Leaderboard** (conditional - only if matches played this month)
5. **🗓️ Monthly Head-to-Head Matrix** (conditional - only if matches played this month)
6. **📅 Last Month's Final Standings** (conditional - only during first 7 days of new month)
7. **📈 Ranking Progression Trends**: Shows who's climbing the ranks over the last 5 weeks
8. **🏆 All-Time Leaderboard**: Overall performance across all matches ever played
9. **🎯 All-Time Head-to-Head Overview**: Complete historical performance matrix

### Smart Reporting Features

- **Conditional Charts**: Weekly and monthly leaderboards/matrices only appear when matches exist in those periods
- **Automatic Scheduling**: Last month's final standings only show during the first 7 days of a new month (`datetime.now().day <= 7`)
- **Clean Interface**: Individual player head-to-head charts are disabled for cleaner reports (functionality preserved in code)
- **Comprehensive Coverage**: All-time leaderboard and matrix always show complete historical data
- **Intelligent Progression**: Ranking progression charts only appear when meaningful ranking variations exist
- **Active Player Focus**: Progression tracking focuses on players active within the last 35 days
- **Fallback Messaging**: Provides informative messages when no matches exist for specific periods
- **Mock Mode**: Console output fallback when Telegram credentials are not configured

### Understanding the Reports

#### Leaderboard Columns
- **Elo**: Long-term skill rating based on entire match history (default: 1500, K-factor: 32)
- **Score**: Period performance = Elo + (Wins × 10) + (Set Difference × 3)
- **Matches**: Total matches played in the period
- **Wins**: Total wins in the period
- **Set Diff**: Sets won minus sets lost in the period

#### Scoring Formula Details
- **Base Elo**: Calculated using standard Elo rating system with K-factor of 32
- **Win Bonus**: 10 points per match win (rewards consistency)
- **Dominance Bonus**: 3 points per positive set difference (rewards decisive victories)
- **Active Player Threshold**: 35 days (for progression tracking)

#### Head-to-Head Matrix
- **Format**: 'Wins-Losses' (e.g., '3-1' = 3 wins, 1 loss vs that opponent)
- **Colors**: Custom colormap with 6-color gradient: `['#ffffff', '#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494']`
- **Color Logic**: White = no games (-1), Light Yellow to Dark Blue gradient based on win ratio (0.0 to 1.0)
- **Text Color Optimization**: White text for win ratios > 0.6, black text otherwise
- **Usage**: Find your name on the left (row), look across for your record vs each opponent
- **Enhanced Readability**: Alternating row/column bands (5% black alpha overlay) and optimized text colors
- **Opponent Names**: Each cell shows both the opponent's name and the W-L record
- **Matrix Size**: Automatically scales based on number of players (minimum 2 players required)

## How It Works

The `leaderboard.py` script performs the following operations:

1. **Environment Setup**: Loads configuration from `.env` file using `python-dotenv`
2. **Data Fetching**: Connects to Google Sheets using service account authentication with retry logic (up to 5 attempts)
3. **Data Processing**: 
   - Normalizes player names and validates match records
   - Handles flexible date parsing with multiple format support
   - Skips invalid records (unknown players, identical players, parsing errors)
   - Sorts matches chronologically by date
4. **Elo Calculation**: 
   - Initializes all players with default Elo rating (1500)
   - Uses K-factor of 32 for rating adjustments
   - Processes matches chronologically to update ratings
5. **Statistical Analysis**:
   - Tracks active players (last 35 days of activity)
   - Calculates weekly rankings for progression analysis (last 5 weeks)
   - Generates period-specific statistics (weekly, monthly, all-time)
6. **Report Generation**: 
   - Creates multiple leaderboard views with scoring formula: `Elo + (Wins × 10) + (Set Difference × 3)`
   - Generates conditional reports based on match availability
   - Includes comprehensive head-to-head matrices with win-loss ratios
7. **Visualization**: 
   - Uses Matplotlib and Seaborn with 'whitegrid' and 'default' styles
   - Creates color-coded matrices with custom 6-color LinearSegmentedColormap
   - Generates ranking progression charts with meaningful variation detection
   - Chart specifications: Leaderboard tables (8×N), Head-to-Head matrices (12×10), Progression charts (12×8)
   - Automatic font sizing and scaling based on content size
   - High-resolution output (150 DPI for matrices, standard for others)
8. **Telegram Delivery**: 
   - Sends formatted reports with robust error handling and retry logic (up to 3 attempts)
   - Includes fallback to console output when Telegram credentials are missing
   - Uses exponential backoff for connection retries

## Player Name Normalization

The system includes intelligent player name normalization to handle:
- **Whitespace Trimming**: Removes leading/trailing spaces using `name.strip()`
- **Data Type Validation**: Handles non-string data gracefully, converts to "Unknown"
- **Preservation**: Maintains exact format from Google Sheets for consistency
- **Error Handling**: Converts invalid names to "Unknown" for robust processing
- **Simplicity**: Preserves original Google Sheets formatting without complex transformations

**Note**: The system assumes Google Sheets already contains clean, unique player names and focuses on preserving the exact format rather than performing complex normalization.

## Error Handling

The script includes comprehensive error handling:
- **Google Sheets API**: 
  - Up to 5 retry attempts with exponential backoff (capped at 10 seconds)
  - SSL warning suppression for problematic connections
  - Graceful fallback when service account file is missing
- **Telegram API**: 
  - Up to 3 retry attempts with exponential backoff
  - Fallback to console output when credentials are missing
  - Robust session management with retry strategy for HTTP status codes [429, 500, 502, 503, 504]
- **Data Validation**: 
  - Skips invalid records with detailed logging
  - Handles non-string player names gracefully
  - Validates date formats with multiple parsing attempts
  - Filters out matches with identical or unknown players
- **Visualization**: 
  - Checks for meaningful ranking variations before generating progression charts
  - Handles empty datasets gracefully
  - Proper memory management with buffer cleanup
- **Detailed Logging**: Complete audit trail with INFO level logging for all operations

## Troubleshooting

### Common Issues

1. **Authentication Error**: Verify service account JSON file path and permissions
2. **Permission Denied**: Ensure Google Sheet is shared with service account email
3. **Sheet Not Found**: Check sheet name matches exactly (case-sensitive, default: "Form Responses")
4. **API Not Enabled**: Confirm Google Sheets API is enabled in your project
5. **Date Parsing Errors**: Ensure dates follow MM/DD/YYYY format (not DD/MM/YYYY)
6. **Missing Dependencies**: Run `pip install -r requirements.txt` if import errors occur
7. **Telegram Issues**: Check bot token and chat ID; script falls back to console output if invalid

### Logs and Debugging

The script provides detailed logging output with the following information:
- **Data Processing**: Total lines read, processed matches, player statistics
- **Player Stats**: Format: `PlayerName: TotalMatches=X, TotalWins=Y, TotalLoses=Z`
- **API Calls**: Google Sheets and Telegram API success/failure messages
- **Error Details**: Specific error messages for troubleshooting
- **Retry Logic**: Exponential backoff timing and attempt numbers

### Mock Mode Testing

When Telegram credentials are not configured, the script runs in mock mode:
- Prints `--- MOCK TELEGRAM MESSAGE ---` for text messages
- Prints `--- MOCK TELEGRAM PHOTO ---` for image captions
- Allows testing of all functionality without Telegram setup

## File Structure

```
├── leaderboard.py                      # Main script with enhanced features
├── requirements.txt                    # Python dependencies
├── run_bot.sh                         # Enhanced execution script with automation
├── .env.example                       # Environment variables template
├── .env                               # Your actual environment variables (not in git)
├── .gitignore                         # Git ignore rules
├── .installed                         # Dependency tracking file (auto-generated)
├── README.md                          # This documentation
├── LICENSE                            # Project license
├── venv/                              # Python virtual environment (auto-created)
├── google-service-account.json        # Google service account credentials (not in git)
└── google-service-account.json.example # Google service account template
```

## Dependencies

- `pandas`: Data manipulation and analysis
- `requests`: HTTP library with retry capabilities
- `matplotlib`: Chart and visualization generation
- `seaborn`: Statistical data visualization
- `gspread`: Google Sheets API client
- `google-auth`: Google authentication library
- `python-dotenv`: Environment variable management from .env files

## Security Notes

- Keep your service account JSON file secure and never commit it to version control
- Use environment variables for sensitive configuration
- Regularly rotate service account keys as per security best practices
- Ensure proper access controls on your Google Sheets document

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the leaderboard system.
