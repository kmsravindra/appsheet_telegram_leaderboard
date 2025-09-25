import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import io
import gspread
from google.oauth2.service_account import Credentials
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from dotenv import load_dotenv

# --- Load Environment Variables from .env file ---
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Securely Load Configuration from Environment Variables ---
GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID")
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class PlayerRankingSystem:
    def __init__(self, match_data, default_elo=1500, k_factor=32):
        self.default_elo = default_elo
        self.k_factor = k_factor
        self.players = {}


        logging.info(f"Total lines read from sheet: {len(match_data)}")
        
        self.match_history = self._preprocess_data(match_data)
        
        logging.info(f"Total processed: {len(self.match_history)} matches")
        
        self._calculate_elo_ratings()
        self._log_player_statistics()

    def _normalize_player_name(self, name):
        # Since all data is now in CamelCase format, just use the names directly
        if not isinstance(name, str):
            return "Unknown" # Handle potential non-string data
        
        # Simply return the name as-is after stripping whitespace
        # This preserves the exact CamelCase format from the spreadsheet
        return name.strip()

    def _parse_flexible_date(self, timestamp_str):
        """Parse date from timestamp string, handling multiple date formats flexibly."""
        # Handle various timestamp formats found in the data
        
        # List of possible timestamp formats to try (most specific first)
        timestamp_formats = [
            '%m/%d/%Y %H:%M:%S',  # MM/DD/YYYY HH:MM:SS (e.g., 9/16/2025 10:29:21)
            '%d/%m/%Y %H:%M:%S',  # DD/MM/YYYY HH:MM:SS (e.g., 22/8/2025 00:00:00)
            '%m/%d/%Y %H:%M:%S',  # M/D/YYYY H:MM:SS (e.g., 9/8/2025 0:00:00)
            '%d/%m/%Y %H:%M:%S',  # D/M/YYYY H:MM:SS (e.g., 7/9/2025 0:00:00)
            '%m/%d/%Y',           # MM/DD/YYYY (e.g., 9/16/2025)
            '%d/%m/%Y',           # DD/MM/YYYY (e.g., 22/8/2025)
        ]
        
        for date_format in timestamp_formats:
            try:
                if ' ' in timestamp_str and ' ' not in date_format:
                    # Try parsing just the date part if format doesn't include time
                    date_part = timestamp_str.split(' ')[0]
                    return datetime.strptime(date_part, date_format)
                else:
                    return datetime.strptime(timestamp_str, date_format)
            except ValueError:
                continue
        
        # If all formats fail, try a more flexible approach
        # Handle cases where day/month might be ambiguous
        try:
            # Split the timestamp to get date and time parts
            parts = timestamp_str.split(' ')
            date_part = parts[0]
            
            # Split date by '/'
            date_components = date_part.split('/')
            if len(date_components) == 3:
                part1, part2, year = date_components
                
                # Try both interpretations: MM/DD and DD/MM
                for month, day in [(part1, part2), (part2, part1)]:
                    try:
                        # Validate day and month ranges
                        day_int, month_int = int(day), int(month)
                        if 1 <= day_int <= 31 and 1 <= month_int <= 12:
                            # Create datetime object
                            if len(parts) > 1:
                                time_part = parts[1]
                                time_components = time_part.split(':')
                                hour = int(time_components[0]) if len(time_components) > 0 else 0
                                minute = int(time_components[1]) if len(time_components) > 1 else 0
                                second = int(time_components[2]) if len(time_components) > 2 else 0
                                return datetime(int(year), month_int, day_int, hour, minute, second)
                            else:
                                return datetime(int(year), month_int, day_int)
                    except (ValueError, TypeError):
                        continue
        except (ValueError, IndexError):
            pass
        
        # If all formats fail, raise an error with details
        raise ValueError(f"Could not parse timestamp '{timestamp_str}' with any known format")

    def _preprocess_data(self, match_data):
        processed_matches = []
        if not match_data:
            return processed_matches
        
        for record_idx, record in enumerate(match_data):
            try:
                # Handle the new Google Sheets format: Timestamp, Winner, Loser, Set Score, Date (Optional)
                # Expected format: 22/8/2025 00:00:00	Kiran	SrikanthK	2-1	[optional date]
                
                # Check if we have the required fields for the new format
                if 'Timestamp' in record and 'Winner' in record and ('Loser' in record or 'Runner up' in record):
                    # New Google Sheets format
                    timestamp_str = str(record['Timestamp']).strip()
                    raw_winner = record['Winner']
                    raw_loser = record.get('Loser', record.get('Runner up', ''))
                    
                    winner_name = self._normalize_player_name(raw_winner)
                    loser_name = self._normalize_player_name(raw_loser)
                    
                    # Handle different score column names: 'Set Score', 'Score', or 'Final Score'
                    score_str = str(record.get('Set Score', record.get('Score', record.get('Final Score', '')))).strip()
                    
                    # Check for optional Date column - prioritize this over timestamp
                    optional_date_str = str(record.get('Date (Optional - if played today)', '')).strip()
                    
                    # Determine the actual match date
                    if optional_date_str and optional_date_str.lower() not in ['', 'nan', 'none']:
                        # Use the optional date if present (MM/DD/YYYY format)
                        try:
                            # Optional date column uses MM/DD/YYYY format (e.g., 9/8/2025, 8/25/2025)
                            match_date = datetime.strptime(optional_date_str, '%m/%d/%Y')
                        except ValueError:
                            # If optional date parsing fails, fall back to timestamp
                            match_date = self._parse_flexible_date(timestamp_str)
                    else:
                        # Use timestamp if no optional date provided - try multiple formats
                        match_date = self._parse_flexible_date(timestamp_str)
                    
                    # Parse the score (format: 2-1)
                    scores = list(map(int, score_str.split('-')))
                    
                # Note: Legacy format support removed - only Google Sheets format supported
                else:
                    continue
                
                # Skip records with unknown or identical players
                if 'Unknown' in [winner_name, loser_name] or winner_name == loser_name or not winner_name or not loser_name:
                    continue
                
                processed_matches.append({
                    'date': match_date,
                    'winner': winner_name, 
                    'loser': loser_name,
                    'winner_sets': max(scores), 
                    'loser_sets': min(scores)
                })
                
            except (ValueError, IndexError, KeyError) as e:
                continue
        
        return sorted(processed_matches, key=lambda x: x['date'])

    def _update_elo(self, winner_elo, loser_elo):
        expected_win = 1 / (1 + 10**((loser_elo - winner_elo) / 400))
        new_winner_elo = winner_elo + self.k_factor * (1 - expected_win)
        new_loser_elo = loser_elo + self.k_factor * (0 - (1 - expected_win))
        return round(new_winner_elo), round(new_loser_elo)

    def _calculate_elo_ratings(self):
        all_player_names = set(m['winner'] for m in self.match_history) | set(m['loser'] for m in self.match_history)
        for name in all_player_names:
            self.players[name] = {'elo': self.default_elo}
        for match in self.match_history:
            winner_name, loser_name = match['winner'], match['loser']
            winner_current_elo = self.players[winner_name]['elo']
            loser_current_elo = self.players[loser_name]['elo']
            new_winner_elo, new_loser_elo = self._update_elo(winner_current_elo, loser_current_elo)
            self.players[winner_name]['elo'] = new_winner_elo
            self.players[loser_name]['elo'] = new_loser_elo

    def _log_player_statistics(self):
        """Log simple statistics for each player: PersonName, TotalMatches, TotalWins, TotalLoses."""
        # Calculate statistics for each player
        player_stats = {}
        for player in self.players.keys():
            player_stats[player] = {
                'total_matches': 0,
                'total_wins': 0,
                'total_losses': 0
            }
        
        # Process all matches to gather statistics
        for match in self.match_history:
            winner = match['winner']
            loser = match['loser']
            
            # Update winner stats
            player_stats[winner]['total_matches'] += 1
            player_stats[winner]['total_wins'] += 1
            
            # Update loser stats
            player_stats[loser]['total_matches'] += 1
            player_stats[loser]['total_losses'] += 1
        
        # Log simple statistics for each player
        for player, stats in sorted(player_stats.items()):
            logging.info(f"{player}: TotalMatches={stats['total_matches']}, TotalWins={stats['total_wins']}, TotalLoses={stats['total_losses']}")

    def get_active_players(self, period_days=35):
        """Get a set of players who have been active in the last `period_days`."""
        cutoff_date = datetime.now() - timedelta(days=period_days)
        active_players = set()
        for match in self.match_history:
            if match['date'] >= cutoff_date:
                active_players.add(match['winner'])
                active_players.add(match['loser'])
        return active_players

    def generate_leaderboard(self, period='weekly'):
        today = datetime.now()
        end_date = today

        if period == 'weekly':
            start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            period_name = "This Week's"
        elif period == 'monthly':
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_name = "This Month's"
        elif period == 'last_month':
            first_day_of_current_month = today.replace(day=1)
            end_date = first_day_of_current_month - timedelta(days=1)
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_name = f"{start_date.strftime('%B %Y')}"
        elif period == 'all_time':
            # Use all matches for all-time leaderboard
            period_matches = self.match_history
            player_names_in_period = set(m['winner'] for m in period_matches) | set(m['loser'] for m in period_matches)
            period_name = "All-Time"
        else:
            raise ValueError("Period must be 'weekly', 'monthly', 'last_month', or 'all_time'")

        if period != 'all_time':
            period_matches = [m for m in self.match_history if start_date <= m['date'] <= end_date]
            player_names_in_period = set(m['winner'] for m in period_matches) | set(m['loser'] for m in period_matches)
        
        if not player_names_in_period:
            return f"No matches played for the period: {period_name.lower()}.", period_name

        period_stats = {name: {'Matches': 0, 'Wins': 0, 'Sets Won': 0, 'Sets Lost': 0} for name in player_names_in_period}
        for match in period_matches:
            winner, loser = match['winner'], match['loser']
            period_stats[winner].update({
                'Matches': period_stats[winner]['Matches'] + 1, 'Wins': period_stats[winner]['Wins'] + 1,
                'Sets Won': period_stats[winner]['Sets Won'] + match['winner_sets'], 'Sets Lost': period_stats[winner]['Sets Lost'] + match['loser_sets']
            })
            period_stats[loser].update({
                'Matches': period_stats[loser]['Matches'] + 1,
                'Sets Won': period_stats[loser]['Sets Won'] + match['loser_sets'], 'Sets Lost': period_stats[loser]['Sets Lost'] + match['winner_sets']
            })
            
        leaderboard_data = []
        for name, stats in period_stats.items():
            set_difference = stats['Sets Won'] - stats['Sets Lost']
            current_elo = self.players.get(name, {}).get('elo', self.default_elo)
            
            # This performance-based formula rewards winning matches and winning decisively.
            win_bonus = stats['Wins'] * 10
            dominance_bonus = set_difference * 3
            leaderboard_score = current_elo + win_bonus + dominance_bonus
            
            leaderboard_data.append({
                'Player': name, 'Elo': current_elo, 'Score': leaderboard_score,
                'Matches': stats['Matches'], 'Wins': stats['Wins'], 'Set Diff': set_difference,
            })
        
        df = pd.DataFrame(leaderboard_data).sort_values(by='Score', ascending=False).reset_index(drop=True)
        df.index += 1
        df.rename_axis('Rank', inplace=True)
        return df, period_name

    def generate_leaderboard_image(self, leaderboard, period_name):
        """Generates a visually appealing image of the leaderboard."""
        if isinstance(leaderboard, str): return None

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(8, max(4, len(leaderboard) * 0.5)))
        ax.axis('off')
        table = ax.table(
            cellText=leaderboard.reset_index().values,
            colLabels=['Rank', 'Player', 'Elo', 'Score', 'Matches', 'Wins', 'Set Diff'],
            cellLoc='center', loc='center', colColours=["#2c3e50"] * 7
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.2)
        for (i, j), cell in table.get_celld().items():
            cell.set_edgecolor("#ecf0f1")
            if i == 0:
                cell.set_text_props(weight='bold', color='white')
                cell.set_facecolor("#2c3e50")
            else:
                cell.set_facecolor("#ffffff")
                if i % 2 == 1: cell.set_facecolor("#f7f9fb")
        plt.title(f"{period_name} Leaderboard", fontsize=20, weight='bold', pad=20)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf

    def get_weekly_rankings(self, num_weeks=5):
        """Calculates player rankings based on historical Elo for the last `num_weeks`."""
        today = datetime.now()
        weekly_rankings = {}
        
        # Create a raw list of all historical matches in Google Sheets format
        raw_historical_data = [
            {
                'Timestamp': m['date'].strftime('%d/%m/%Y %H:%M:%S'), 
                'Winner': m['winner'], 
                'Loser': m['loser'], 
                'Final Score': f"{m['winner_sets']}-{m['loser_sets']}"
            } 
            for m in self.match_history
        ]
        
        # Get all players from the current system
        all_players = list(self.players.keys())

        for i in range(num_weeks - 1, -1, -1):
            end_of_week = today - timedelta(weeks=i)
            end_of_week = (end_of_week - timedelta(days=end_of_week.weekday()) + timedelta(days=6)).replace(hour=23, minute=59, second=59)
            
            # Filter matches up to end of this week
            matches_up_to_week = [m for m in self.match_history if m['date'] <= end_of_week]
            
            if not matches_up_to_week: 
                continue
            
            # Create raw data for this week in Google Sheets format
            raw_match_subset = [
                {
                    'Timestamp': m['date'].strftime('%d/%m/%Y %H:%M:%S'), 
                    'Winner': m['winner'], 
                    'Loser': m['loser'], 
                    'Final Score': f"{m['winner_sets']}-{m['loser_sets']}"
                } 
                for m in matches_up_to_week
            ]
            
            # Create temporary ranking system for this week (without logging)
            temp_ranking_system = PlayerRankingSystem.__new__(PlayerRankingSystem)
            temp_ranking_system.default_elo = self.default_elo
            temp_ranking_system.k_factor = self.k_factor
            temp_ranking_system.players = {}
            temp_ranking_system.match_history = temp_ranking_system._preprocess_data(raw_match_subset)
            temp_ranking_system._calculate_elo_ratings()
            players_elo = {p: d['elo'] for p, d in temp_ranking_system.players.items()}
            sorted_players = sorted(players_elo.items(), key=lambda item: item[1], reverse=True)
            
            week_label = (end_of_week - timedelta(days=6)).strftime('Wk %U (%b %d)')
            ranks_for_week = {player: rank + 1 for rank, (player, _) in enumerate(sorted_players)}
            weekly_rankings[week_label] = ranks_for_week

        df = pd.DataFrame(weekly_rankings).reindex(all_players).fillna(0).astype(int)
        return df

    def generate_ranking_progression_chart(self, active_players, weekly_rankings_df):
        """Generates a colorful line chart showing ranking progression for active players."""
        if weekly_rankings_df.empty: return None
        plot_df = weekly_rankings_df[weekly_rankings_df.index.isin(active_players)]
        if plot_df.empty or len(plot_df.columns) < 2: return None

        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(figsize=(12, 8))
        palette = sns.color_palette("husl", len(plot_df.index))
        
        plot_df_inv = plot_df.apply(lambda row: [1/r if r > 0 else 0 for r in row], axis=1, result_type='broadcast')

        for i, player in enumerate(plot_df_inv.index):
            ranks = plot_df_inv.loc[player].values
            ax.plot(plot_df_inv.columns, ranks, marker='o', linestyle='-', label=player, color=palette[i])
        
        current_yticks = ax.get_yticks()
        filtered_yticks = [y for y in current_yticks if y > 0]
        ax.set_yticks(filtered_yticks)
        ax.set_yticklabels([int(round(1/y)) for y in filtered_yticks])

        ax.legend(title="Players", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.title("Player Ranking Progression (Last 5 Weeks)", fontsize=18, weight='bold')
        plt.ylabel("Overall Rank (Lower is Better)")
        plt.xlabel("Week")
        plt.xticks(rotation=45)
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return buf

    def generate_comprehensive_performance_matrix(self, period='all_time'):
        """Generates a comprehensive matrix showing head-to-head results in W-L format with color coding."""
        # Filter matches based on period
        today = datetime.now()
        
        if period == 'weekly':
            start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            filtered_matches = [m for m in self.match_history if m['date'] >= start_date]
            period_title = "This Week's"
        elif period == 'monthly':
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            filtered_matches = [m for m in self.match_history if m['date'] >= start_date]
            period_title = "This Month's"
        else:  # all_time
            filtered_matches = self.match_history
            period_title = "All-Time"
        
        # Get all players who have played matches in this period
        all_players = sorted(list(set(m['winner'] for m in filtered_matches) | set(m['loser'] for m in filtered_matches)))
        
        if len(all_players) < 2:
            return None
            
        # Create matrices for wins and losses
        n_players = len(all_players)
        wins_matrix = [[0 for _ in range(n_players)] for _ in range(n_players)]
        losses_matrix = [[0 for _ in range(n_players)] for _ in range(n_players)]
        
        # Create player index mapping
        player_to_index = {player: i for i, player in enumerate(all_players)}
        
        # Populate matrices with match data from filtered matches
        for match in filtered_matches:
            winner = match['winner']
            loser = match['loser']
            
            winner_idx = player_to_index[winner]
            loser_idx = player_to_index[loser]
            
            # Winner beat loser
            wins_matrix[winner_idx][loser_idx] += 1
            # Loser lost to winner
            losses_matrix[loser_idx][winner_idx] += 1
        
        # Create combined matrix with W-L format and win ratios for coloring
        combined_matrix = []
        color_matrix = []
        
        for i in range(n_players):
            combined_row = []
            color_row = []
            for j in range(n_players):
                if i == j:
                    # Diagonal - no games against self
                    combined_row.append("---")
                    color_row.append(0)  # Neutral color
                else:
                    wins = wins_matrix[i][j]
                    losses = losses_matrix[i][j]
                    total_games = wins + losses
                    
                    if total_games == 0:
                        combined_row.append("0-0")
                        color_row.append(-1)  # Special value for white color (no games)
                    else:
                        combined_row.append(f"{wins}-{losses}")
                        # Color based on win ratio (0 to 1)
                        win_ratio = wins / total_games
                        color_row.append(win_ratio)
            
            combined_matrix.append(combined_row)
            color_matrix.append(color_row)
        
        # Create the visualization
        plt.style.use('seaborn-v0_8-whitegrid')
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        # Convert to DataFrames
        color_df = pd.DataFrame(color_matrix, index=all_players, columns=all_players)
        
        # Create custom colormap: white for no games, then light yellow to dark blue
        from matplotlib.colors import LinearSegmentedColormap
        colors = ['#ffffff', '#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494']  # White -> Light yellow -> Light teal -> Medium teal -> Blue -> Dark blue
        n_bins = 100
        cmap = LinearSegmentedColormap.from_list('win_loss', colors, N=n_bins)
        
        # Plot heatmap with custom annotations and improved readability
        sns.heatmap(color_df, annot=False, cmap=cmap, ax=ax, 
                   cbar_kws={'label': 'Win Ratio'}, square=True, 
                   vmin=-1, vmax=1, linewidths=1.5, linecolor='#333333')
        
        # Add alternating row bands for better readability
        for i in range(n_players):
            if i % 2 == 1:  # Every other row
                ax.axhspan(i, i+1, facecolor='black', alpha=0.05, zorder=0)
        
        # Add alternating column bands for better readability  
        for j in range(n_players):
            if j % 2 == 1:  # Every other column
                ax.axvspan(j, j+1, facecolor='black', alpha=0.05, zorder=0)
        
        # Add custom annotations (W-L format with opponent names)
        for i in range(n_players):
            for j in range(n_players):
                text = combined_matrix[i][j]
                opponent_name = all_players[j]
                
                if text == "---":
                    # Same player - show name only
                    display_text = f"{opponent_name}"
                    ax.text(j + 0.5, i + 0.5, display_text, ha='center', va='center', 
                           fontsize=8, weight='bold', color='black')
                elif text == "0-0":
                    # No matches - show opponent name and 0-0
                    display_text = f"{opponent_name}\n{text}"
                    ax.text(j + 0.5, i + 0.5, display_text, ha='center', va='center', 
                           fontsize=7, color='gray')
                else:
                    # Has matches - show opponent name and W-L record
                    display_text = f"{opponent_name}\n{text}"
                    # Choose text color based on background (optimized for blue color scheme)
                    win_ratio = color_matrix[i][j]
                    text_color = 'white' if win_ratio > 0.6 else 'black'
                    ax.text(j + 0.5, i + 0.5, display_text, ha='center', va='center', 
                           fontsize=7, weight='bold', color=text_color)
        
        ax.set_title(f'{period_title} Head-to-Head Results (W-L Format)', fontsize=16, weight='bold', pad=20)
        ax.set_xlabel('Opponent (Column)', fontsize=12)
        ax.set_ylabel('Player (Row)', fontsize=12)
        
        # Rotate labels for better readability
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        plt.close(fig)
        return buf

    def generate_head_to_head_chart(self, player_name):
        """Generates a bar chart of wins for a specific player against their opponents."""
        wins = {}
        normalized_player_name = self._normalize_player_name(player_name)
        for match in self.match_history:
            if match['winner'] == normalized_player_name:
                wins[match['loser']] = wins.get(match['loser'], 0) + 1
        if not wins: return None
        sorted_wins = sorted(wins.items(), key=lambda item: item[1], reverse=True)
        opponents = [item[0] for item in sorted_wins]
        win_counts = [item[1] for item in sorted_wins]
        plt.style.use('seaborn-v0_8-darkgrid')
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x=win_counts, y=opponents, palette="viridis", ax=ax, orient='h')
        ax.set_title(f"Head-to-Head Wins for {normalized_player_name}", fontsize=16, weight='bold')
        ax.set_xlabel("Number of Wins")
        ax.set_ylabel("Opponent")
        for index, value in enumerate(win_counts):
            ax.text(value, index, f' {value}', va='center', weight='bold')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        return buf

# --- Functions for Google Sheets and Telegram ---
def get_google_sheets_data(max_retries=5):
    """Fetches all rows from the specified Google Sheets document with robust error handling."""
    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        logging.error("GOOGLE_SERVICE_ACCOUNT_FILE environment variable is not set. Cannot fetch data.")
        return None

    # Configure SSL context for better compatibility
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    for attempt in range(max_retries):
        try:
            logging.info(f"Attempting to fetch data from Google Sheets (attempt {attempt + 1}/{max_retries})...")
            
            # Define the scope for Google Sheets API
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            
            # Authenticate using service account with custom session
            creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scope)
            
            # Create a custom session with SSL configuration
            session = requests.Session()
            session.verify = False  # Disable SSL verification temporarily
            
            # Configure retry strategy for the session
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Authorize with custom session
            client = gspread.authorize(creds)
            
            # Open the spreadsheet and worksheet
            sheet = client.open_by_key(GOOGLE_SHEETS_ID)
            worksheet = sheet.worksheet(GOOGLE_SHEET_NAME)
            
            # Get all records as list of dictionaries
            records = worksheet.get_all_records()
            
            logging.info(f"Successfully fetched {len(records)} records from Google Sheets.")
            
            # Debug: Log first few records to understand the data format
            if records:
                logging.info(f"Sample record: {records[0]}")
                logging.info(f"Available columns: {list(records[0].keys())}")
            
            return records
            
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, ssl.SSLError) as e:
            logging.warning(f"SSL/Connection error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)  # Cap wait time at 10 seconds
                logging.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue
        except Exception as e:
            logging.error(f"Error fetching data from Google Sheets on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)
                logging.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue
            else:
                logging.error(f"Failed to fetch Google Sheets data after {max_retries} attempts")
                break
    
    return None

def create_robust_session():
    """Creates a requests session with retry strategy and SSL error handling."""
    session = requests.Session()
    
    # Disable SSL warnings for problematic connections
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Define retry strategy
    retry_strategy = Retry(
        total=5,  # Total number of retries
        backoff_factor=2,  # Wait time between retries (exponential backoff)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
        allowed_methods=["HEAD", "GET", "POST"],  # HTTP methods to retry
    )
    
    # Mount adapter with retry strategy
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def send_telegram_message(message_text, chat_id=TELEGRAM_CHAT_ID, max_retries=3):
    """Sends a text message to the Telegram group with robust error handling."""
    if not all([TELEGRAM_BOT_TOKEN, chat_id]):
        logging.warning("Telegram credentials not set. Printing message to console instead.")
        print(f"--- MOCK TELEGRAM MESSAGE ---\n{message_text}\n---------------------------")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message_text, 'parse_mode': 'Markdown'}
    
    session = create_robust_session()
    
    for attempt in range(max_retries):
        try:
            response = session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            logging.info("Telegram text message sent successfully.")
            return
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logging.warning(f"SSL/Connection error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending Telegram text message on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logging.error(f"Unexpected error sending Telegram message: {e}")
            break
    
    logging.error(f"Failed to send Telegram message after {max_retries} attempts")

def send_telegram_photo(image_buffer, caption, chat_id=TELEGRAM_CHAT_ID, max_retries=3):
    """Sends an image with a caption to the Telegram group with robust error handling."""
    if not all([TELEGRAM_BOT_TOKEN, chat_id]):
        logging.warning("Telegram credentials not set. Printing photo caption to console instead.")
        print(f"--- MOCK TELEGRAM PHOTO ---\nCaption: {caption}\n(Image buffer not displayed)\n-------------------------")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('report_image.png', image_buffer, 'image/png')}
    payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
    
    session = create_robust_session()
    
    for attempt in range(max_retries):
        try:
            # Reset buffer position for retry attempts
            image_buffer.seek(0)
            response = session.post(url, files=files, data=payload, timeout=60)
            response.raise_for_status()
            logging.info(f"Telegram photo sent: {caption}")
            return
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logging.warning(f"SSL/Connection error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending Telegram photo on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logging.error(f"Unexpected error sending Telegram photo: {e}")
            break
    
    logging.error(f"Failed to send Telegram photo after {max_retries} attempts")

def get_metrics_explanation():
    """Returns a formatted string explaining the leaderboard metrics."""
    return (
        "📊 *Understanding the Leaderboard Reports*\n\n"
        "Here's how to read the upcoming charts in order:\n\n"
        "📈 *Report Flow*:\n"
        "   1️⃣ **Weekly Leaderboard** (if matches this week)\n"
        "   2️⃣ **Weekly Head-to-Head Matrix** (if matches this week)\n"
        "   3️⃣ **Monthly Leaderboard** (if matches this month)\n"
        "   4️⃣ **Monthly Head-to-Head Matrix** (if matches this month)\n"
        "   5️⃣ **Last Month's Final Standings** (first week of new month only)\n"
        "   6️⃣ **Ranking Progression Trends** (5-week ranking changes)\n"
        "   7️⃣ **All-Time Leaderboard** (overall performance across all matches)\n"
        "   8️⃣ **All-Time Head-to-Head Overview** (complete historical matrix)\n\n"
        "🏆 *Leaderboard Columns*:\n"
        "   • **Elo**: Long-term skill rating based on entire match history\n"
        "   • **Score**: Period performance = Elo + Win Bonus + Set Difference Bonus\n"
        "   • **Set Diff**: Sets won minus sets lost in the current period\n\n"
        "🎯 *Head-to-Head Matrix (W-L Format)*:\n"
        "   • Format: 'Wins-Losses' (e.g., '3-1' = 3 wins, 1 loss vs that opponent)\n"
        "   • Colors: White = no games, Light Yellow = struggling, Dark Blue = dominating\n"
        "   • Find your name on the left (row), look across for your record vs each opponent\n\n"
        "📊 *Smart Reporting*:\n"
        "   • Weekly/monthly charts only appear when matches exist in those periods\n"
        "   • Ranking progression shows who's climbing or falling over 5 weeks\n"
        "   • All-time matrix always shows complete head-to-head history\n"
        "   • Individual player charts are disabled for cleaner reports"
    )

def main():
    """Main function to run the report generation process."""
    logging.info("Starting the report generation process...")

    data = get_google_sheets_data()
    if not data:
        logging.warning("No data fetched from Google Sheets. Aborting process.")
        send_telegram_message("Could not fetch match data. The leaderboard could not be updated. Please check the data source.")
        return

    ranking_system = PlayerRankingSystem(data)
    
    send_telegram_message(get_metrics_explanation())

    # --- Weekly Leaderboard ---
    weekly_lb, weekly_name = ranking_system.generate_leaderboard('weekly')
    if isinstance(weekly_lb, pd.DataFrame) and not weekly_lb.empty:
        weekly_img = ranking_system.generate_leaderboard_image(weekly_lb, weekly_name)
        if weekly_img:
            send_telegram_photo(weekly_img, caption=f"� Here is *{weekly_name} Leaderboard*! See the legend above for details.")
        
        # Weekly comprehensive matrix (if there are weekly matches)
        comprehensive_chart_weekly = ranking_system.generate_comprehensive_performance_matrix('weekly')
        if comprehensive_chart_weekly:
            send_telegram_photo(comprehensive_chart_weekly, caption="📅 *This Week's Head-to-Head*: Shows only matches from this week. Format: 'Wins-Losses'. Great for seeing current week dynamics!")
    else:
        send_telegram_message(f"No matches played this week yet. Let's get some games in!")

    # --- Monthly Leaderboard ---
    monthly_lb, monthly_name = ranking_system.generate_leaderboard('monthly')
    if isinstance(monthly_lb, pd.DataFrame) and not monthly_lb.empty:
        monthly_img = ranking_system.generate_leaderboard_image(monthly_lb, monthly_name)
        if monthly_img:
            send_telegram_photo(monthly_img, caption=f"🗓️ And here is the progress for the *{monthly_name} Leaderboard*!")
        
        # Monthly comprehensive matrix (if there are monthly matches)
        comprehensive_chart_monthly = ranking_system.generate_comprehensive_performance_matrix('monthly')
        if comprehensive_chart_monthly:
            send_telegram_photo(comprehensive_chart_monthly, caption="🗓️ *This Month's Head-to-Head*: Shows only matches from this month. Format: 'Wins-Losses'. Track monthly rivalries!")
    else:
        send_telegram_message(f"No matches played this month yet.")

    # --- Last Month's Leaderboard (runs only on the first few days of a new month) ---
    if datetime.now().day <= 7:
        last_month_lb, last_month_name = ranking_system.generate_leaderboard('last_month')
        if isinstance(last_month_lb, pd.DataFrame) and not last_month_lb.empty:
            last_month_img = ranking_system.generate_leaderboard_image(last_month_lb, f"Final {last_month_name}")
            if last_month_img:
                send_telegram_photo(last_month_img, caption=f" retrospection: Here are the final standings for the *{last_month_name} Leaderboard*!")
            
    # --- Ranking Progression Trends ---
    active_players = ranking_system.get_active_players(period_days=35)
    if active_players:
        weekly_rankings_df = ranking_system.get_weekly_rankings(num_weeks=5)
        progression_chart = ranking_system.generate_ranking_progression_chart(active_players, weekly_rankings_df)
        if progression_chart:
            send_telegram_photo(progression_chart, caption="📈 *Ranking Trends*: Check out who's climbing the ranks over the last 5 weeks!")

    # --- All-Time Leaderboard ---
    all_time_lb, all_time_name = ranking_system.generate_leaderboard('all_time')
    if isinstance(all_time_lb, pd.DataFrame) and not all_time_lb.empty:
        all_time_img = ranking_system.generate_leaderboard_image(all_time_lb, all_time_name)
        if all_time_img:
            send_telegram_photo(all_time_img, caption=f"🏆 Here is the *{all_time_name} Leaderboard*! This shows overall performance across all matches ever played.")

    # --- Comprehensive Performance Matrices (All-Time Overview) ---
    # All-time comprehensive matrix - placed at the end for complete historical overview
    comprehensive_chart_all = ranking_system.generate_comprehensive_performance_matrix('all_time')
    if comprehensive_chart_all:
        send_telegram_photo(comprehensive_chart_all, caption="🎯 *All-Time Head-to-Head Overview*: Complete historical record between all players. Format: 'Wins-Losses' (e.g., '3-1' = 3 wins, 1 loss). Color intensity shows dominance level.")

    # --- Individual Head-to-Head Stats (COMMENTED OUT) ---
    # if active_players:
    #     send_telegram_message("\n--- *Individual Head-to-Head Stats* ---\n(Shows your total wins against each opponent)")
    #     for player in sorted(list(active_players)):
    #         h2h_chart = ranking_system.generate_head_to_head_chart(player)
    #         if h2h_chart:
    #             send_telegram_photo(h2h_chart, caption=f"Win stats for *{player}*")

    logging.info("Report generation process finished.")

if __name__ == "__main__":
    main()
