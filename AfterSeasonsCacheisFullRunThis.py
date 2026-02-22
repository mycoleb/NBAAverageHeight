# python AfterSeasonsCacheisFullRunThis.py
import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime
from requests.exceptions import ReadTimeout

from nba_api.stats.endpoints import leaguedashplayerbiostats, teamplayerdashboard
from nba_api.stats.static import teams

# --- Constants & Setup ---
HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.nba.com/',
}

CACHE_DIR = "season_cache"
CHAMP_CACHE_DIR = "champ_cache"
for d in [CACHE_DIR, CHAMP_CACHE_DIR]:
    if not os.path.exists(d): os.makedirs(d)

CHAMPIONS = {
    1980: "Los Angeles Lakers", 1981: "Boston Celtics", 1982: "Los Angeles Lakers",
    1983: "Philadelphia 76ers", 1984: "Boston Celtics", 1985: "Los Angeles Lakers",
    1986: "Boston Celtics", 1987: "Los Angeles Lakers", 1988: "Los Angeles Lakers",
    1989: "Detroit Pistons", 1990: "Detroit Pistons", 1991: "Chicago Bulls",
    1992: "Chicago Bulls", 1993: "Chicago Bulls", 1994: "Houston Rockets",
    1995: "Houston Rockets", 1996: "Chicago Bulls", 1997: "Chicago Bulls",
    1998: "Chicago Bulls", 1999: "San Antonio Spurs", 2000: "Los Angeles Lakers",
    2001: "Los Angeles Lakers", 2002: "Los Angeles Lakers", 2003: "San Antonio Spurs",
    2004: "Detroit Pistons", 2005: "San Antonio Spurs", 2006: "Miami Heat",
    2007: "San Antonio Spurs", 2008: "Boston Celtics", 2009: "Los Angeles Lakers",
    2010: "Los Angeles Lakers", 2011: "Dallas Mavericks", 2012: "Miami Heat",
    2013: "Miami Heat", 2014: "San Antonio Spurs", 2015: "Golden State Warriors",
    2016: "Cleveland Cavaliers", 2017: "Golden State Warriors", 2018: "Golden State Warriors",
    2019: "Toronto Raptors", 2020: "Los Angeles Lakers", 2021: "Milwaukee Bucks",
    2022: "Golden State Warriors", 2023: "Denver Nuggets", 2024: "Boston Celtics",
    2025: "Oklahoma City Thunder"
}

def season_str(end_year: int) -> str:
    return f"{end_year-1}-{str(end_year)[-2:]}"

# --- Data Collection ---

def get_season_roster(end_year: int, retries=3) -> pd.DataFrame:
    file_path = os.path.join(CACHE_DIR, f"nba_players_{end_year}.csv")
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if len(df) > 100: return df

    season = season_str(end_year)
    for attempt in range(retries):
        try:
            # Added a longer 60s timeout
            r = leaguedashplayerbiostats.LeagueDashPlayerBioStats(season=season, headers=HEADERS, timeout=60)
            df = r.get_data_frames()[0]
            df = df[['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'PLAYER_HEIGHT_INCHES']]
            df.columns = ['player_id', 'player_name', 'team_id', 'height_in']
            # Force ID to integer for matching
            df['player_id'] = df['player_id'].astype(int)
            df.to_csv(file_path, index=False)
            return df
        except ReadTimeout:
            print(f"Timeout on {season}, retrying ({attempt+1}/{retries})...")
            time.sleep(5) # Wait longer before retry
        except Exception as e:
            print(f"Error on {season}: {e}")
            break
    return pd.DataFrame()

def get_champ_avg(end_year: int, roster_df: pd.DataFrame, retries=2) -> float | None:
    txt_path = os.path.join(CHAMP_CACHE_DIR, f"champ_{end_year}.txt")
    if os.path.exists(txt_path):
        with open(txt_path, 'r') as f:
            val = f.read().strip()
            if val != 'nan': return float(val)

    champ_name = CHAMPIONS.get(end_year)
    if not champ_name or roster_df.empty: return None

    season = season_str(end_year)
    try:
        team_id = [t for t in teams.get_teams() if t['full_name'] == champ_name][0]['id']
        for attempt in range(retries):
            try:
                stats = teamplayerdashboard.TeamPlayerDashboard(team_id=team_id, season=season, headers=HEADERS, timeout=60)
                stats_df = stats.get_data_frames()[1]
                top_5_ids = stats_df.sort_values(by="MIN", ascending=False).head(5)["PLAYER_ID"].astype(int).tolist()
                
                # DIAGNOSTIC: Check how many starters we actually find in the roster
                matched_players = roster_df[roster_df["player_id"].isin(top_5_ids)]
                avg_h = matched_players["height_in"].mean()
                
                if pd.isna(avg_h):
                    print(f"Warning: Calculated NaN for {end_year}. Found {len(matched_players)}/5 starters.")
                
                with open(txt_path, 'w') as f: f.write(str(avg_h))
                return avg_h
            except ReadTimeout:
                time.sleep(2)
    except Exception:
        return None

# --- Main Run ---
def main():
    results = []
    # If it's going slow, just run the next 5 years to test!
    years = range(1980, 2026) 
    
    for year in tqdm(years, desc="NBA Evolution"):
        roster = get_season_roster(year)
        champ_avg = get_champ_avg(year, roster)
        
        if not roster.empty:
            results.append({
                "year": year,
                "league_avg": roster["height_in"].mean(),
                "champ_avg": champ_avg
            })
        # Important: Small pause to keep the API happy
        time.sleep(1.5)

    df = pd.DataFrame(results)
    df.to_csv("final_nba_heights.csv", index=False)
    print("Process Complete. Check final_nba_heights.csv")

if __name__ == "__main__":
    main()