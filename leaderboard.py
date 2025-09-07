import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import io

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Securely Load Configuration from Environment Variables ---
APPSHEET_APP_ID = os.environ.get("APPSHEET_APP_ID")
APPSHEET_ACCESS_KEY = os.environ.get("APPSHEET_ACCESS_KEY")
APPSHEET_TABLE_NAME = os.environ.get("APPSHEET_TABLE_NAME", "ASPTTDailyScores") # Default table name if not set
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class PlayerRankingSystem:
    def __init__(self, match_data, default_elo=1500, k_factor=32):
        self.default_elo = default_elo
        self.k_factor = k_factor
        self.players = {}

        # This map standardizes player names to prevent splitting a player's record.
        # It maps a normalized key (lowercase, no spaces) to a single official name.
        self.player_alias_map = {
            # Official Name: SrikanthK
            'srikanthk': 'SrikanthK',   # Catches "SrikanthK"
            'srikanth k': 'SrikanthK',   # Catches "Srikanth K"
            
            # Official Name: SrikanthV (This is a distinct player)
            'srikanthv': 'SrikanthV',
            
            # Official Name: Ravi Gupta (Distinct player)
            'ravigupta': 'Ravi Gupta',
            
            # Official Name: Ravi L (Distinct player)
            'ravil': 'Ravi L',
            
            # Official Name: Jayasankar
            'jayasankar': 'Jayasankar', # Catches "Jayasankar"
            'jayashankar': 'Jayasankar',# Catches "Jayashankar"
            'jayashankar': 'Jayasankar',# Catches "Jaya shankar" (normalizes to the same key)

            # Official Name: Sridhar
            'sridhar': 'Sridhar',     # Catches "Sridhar"
            'sreedhar': 'Sridhar',    # Catches "Sreedhar" and maps it to "Sridhar"            
            # Add other potential aliases here as you discover them
        }

        self.match_history = self._preprocess_data(match_data)
        self._calculate_elo_ratings()

    def _normalize_player_name(self, name):
        # This function uses the alias map for robust name standardization.
        if not isinstance(name, str):
            return "Unknown" # Handle potential non-string data
        
        # Standardize by removing spaces and converting to lowercase to create a lookup key
        normalized_key = name.strip().replace(" ", "").lower()
        
        # Return the official name from the map; otherwise, format the original name cleanly.
        return self.player_alias_map.get(normalized_key, name.strip().title())

    def _preprocess_data(self, match_data):
        processed_matches = []
        if not match_data:
            return processed_matches
        for record in match_data:
            if not all(k in record for k in ['Date', 'Player 1', 'Player 2', 'Winner', 'Final Score']):
                continue
            try:
                # Use the new, robust normalization function
                p1_name = self._normalize_player_name(record['Player 1'])
                p2_name = self._normalize_player_name(record['Player 2'])
                winner_name = self._normalize_player_name(record['Winner'])
                
                # Skip records with unknown or identical players
                if 'Unknown' in [p1_name, p2_name, winner_name] or p1_name == p2_name:
                    continue

                loser_name = p2_name if winner_name == p1_name else p1_name
                scores = list(map(int, record['Final Score'].split('-')))
                
                processed_matches.append({
                    'date': datetime.strptime(record['Date'], '%m/%d/%Y'),
                    'winner': winner_name, 'loser': loser_name,
                    'winner_sets': max(scores), 'loser_sets': min(scores)
                })
            except (ValueError, IndexError):
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
        else:
            raise ValueError("Period must be 'weekly', 'monthly', or 'last_month'")

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
        
        # Create a raw list of all historical matches to pass to the temp system
        raw_historical_data = [
            {'Date': m['date'].strftime('%m/%d/%Y'), 'Player 1': m['winner'], 'Player 2': m['loser'], 'Winner': m['winner'], 'Final Score': '1-0'} 
            for m in self.match_history
        ]
        temp_ranking_system_all = PlayerRankingSystem(raw_historical_data)
        all_players = list(temp_ranking_system_all.players.keys())

        for i in range(num_weeks - 1, -1, -1):
            end_of_week = today - timedelta(weeks=i)
            end_of_week = (end_of_week - timedelta(days=end_of_week.weekday()) + timedelta(days=6)).replace(hour=23, minute=59, second=59)
            
            raw_match_subset = [
                m for m in raw_historical_data if datetime.strptime(m['Date'], '%m/%d/%Y') <= end_of_week
            ]

            if not raw_match_subset: continue
            
            temp_ranking_system = PlayerRankingSystem(raw_match_subset)
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

# --- Functions for AppSheet and Telegram ---
def get_appsheet_data():
    """Fetches all rows from the specified AppSheet table via API."""
    if not all([APPSHEET_APP_ID, APPSHEET_ACCESS_KEY, APPSHEET_TABLE_NAME]):
        logging.error("AppSheet environment variables (APP_ID, ACCESS_KEY, TABLE_NAME) are not set. Cannot fetch data.")
        return None

    url = f"https://api.appsheet.com/api/v2/apps/{APPSHEET_APP_ID}/tables/{APPSHEET_TABLE_NAME}/Action"
    headers = {"ApplicationAccessKey": APPSHEET_ACCESS_KEY, "Content-Type": "application/json"}
    payload = {"Action": "Find", "Properties": {}, "Rows": []}
    
    try:
        logging.info("Attempting to fetch data from AppSheet API...")
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        logging.info("Successfully fetched data from AppSheet.")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from AppSheet: {e}")
        return None

def send_telegram_message(message_text, chat_id=TELEGRAM_CHAT_ID):
    """Sends a text message to the Telegram group."""
    if not all([TELEGRAM_BOT_TOKEN, chat_id]):
        logging.warning("Telegram credentials not set. Printing message to console instead.")
        print(f"--- MOCK TELEGRAM MESSAGE ---\n{message_text}\n---------------------------")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message_text, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Telegram text message sent successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram text message: {e}")

def send_telegram_photo(image_buffer, caption, chat_id=TELEGRAM_CHAT_ID):
    """Sends an image with a caption to the Telegram group."""
    if not all([TELEGRAM_BOT_TOKEN, chat_id]):
        logging.warning("Telegram credentials not set. Printing photo caption to console instead.")
        print(f"--- MOCK TELEGRAM PHOTO ---\nCaption: {caption}\n(Image buffer not displayed)\n-------------------------")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('report_image.png', image_buffer, 'image/png')}
    payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, files=files, data=payload)
        response.raise_for_status()
        logging.info(f"Telegram photo sent: {caption}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram photo: {e}")

def get_metrics_explanation():
    """Returns a formatted string explaining the leaderboard metrics."""
    return (
        "📊 *Understanding the Leaderboard Metrics*\n\n"
        "Here’s a quick guide to the terms you'll see in the charts:\n\n"
        "1️⃣. *Elo*:\n"
        "   - This is your long-term *skill rating* based on your entire match history.\n"
        "   - It goes up when you win and down when you lose.\n"
        "   - Beating a higher-rated player gives you more points.\n\n"
        "2️⃣. *Score*:\n"
        "   - This is your performance score *for the current period* (e.g., this week).\n"
        "   - It's calculated as: `Elo + (Wins Bonus) + (Set Difference Bonus)`.\n"
        "   - This formula rewards both high skill and strong recent performance.\n\n"
        "3️⃣. *Set Diff*:\n"
        "   - The total number of sets you've won minus the sets you've lost in the period.\n"
        "   - A higher number means you are winning your matches decisively."
    )

def main():
    """Main function to run the report generation process."""
    logging.info("Starting the report generation process...")

    data = get_appsheet_data()
    if not data:
        logging.warning("No data fetched from AppSheet. Aborting process.")
        send_telegram_message("Could not fetch match data. The leaderboard could not be updated. Please check the data source.")
        return

    ranking_system = PlayerRankingSystem(data)
    
    send_telegram_message(get_metrics_explanation())

    # --- Weekly Leaderboard ---
    weekly_lb, weekly_name = ranking_system.generate_leaderboard('weekly')
    if isinstance(weekly_lb, pd.DataFrame) and not weekly_lb.empty:
        weekly_img = ranking_system.generate_leaderboard_image(weekly_lb, weekly_name)
        if weekly_img:
            send_telegram_photo(weekly_img, caption=f"🏆 Here is *{weekly_name} Leaderboard*! See the legend above for details.")
    else:
        send_telegram_message(f"No matches played this week yet. Let's get some games in!")

    # --- Monthly Leaderboard ---
    monthly_lb, monthly_name = ranking_system.generate_leaderboard('monthly')
    if isinstance(monthly_lb, pd.DataFrame) and not monthly_lb.empty:
        monthly_img = ranking_system.generate_leaderboard_image(monthly_lb, monthly_name)
        if monthly_img:
            send_telegram_photo(monthly_img, caption=f"🗓️ And here is the progress for the *{monthly_name} Leaderboard*!")
    else:
        send_telegram_message(f"No matches played this month yet.")

    # --- Last Month's Leaderboard (runs only on the first few days of a new month) ---
    if datetime.now().day <= 7:
        last_month_lb, last_month_name = ranking_system.generate_leaderboard('last_month')
        if isinstance(last_month_lb, pd.DataFrame) and not last_month_lb.empty:
            last_month_img = ranking_system.generate_leaderboard_image(last_month_lb, f"Final {last_month_name}")
            if last_month_img:
                send_telegram_photo(last_month_img, caption=f" retrospection: Here are the final standings for the *{last_month_name} Leaderboard*!")
            
    # --- Trend Charts and Individual Stats ---
    active_players = ranking_system.get_active_players(period_days=35)
    if active_players:
        weekly_rankings_df = ranking_system.get_weekly_rankings(num_weeks=5)
        progression_chart = ranking_system.generate_ranking_progression_chart(active_players, weekly_rankings_df)
        if progression_chart:
            send_telegram_photo(progression_chart, caption="📈 *Ranking Trends*: Check out who's climbing the ranks over the last 5 weeks!")

        send_telegram_message("\n--- *Individual Head-to-Head Stats* ---\n(Shows your total wins against each opponent)")
        for player in sorted(list(active_players)):
            h2h_chart = ranking_system.generate_head_to_head_chart(player)
            if h2h_chart:
                send_telegram_photo(h2h_chart, caption=f"Win stats for *{player}*")

    logging.info("Report generation process finished.")

if __name__ == "__main__":
    main()