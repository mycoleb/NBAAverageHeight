from __future__ import annotations
import os
import time
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

from nba_api.stats.endpoints import commonteamroster, teamplayerdashboard
from nba_api.stats.static import teams

# --- Constants -------------------------------------------------------------
CACHE_DIR = "season_cache"
CHAMP_CACHE_DIR = "champ_cache"

for d in [CACHE_DIR, CHAMP_CACHE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- Champions Mapping (1980 - 2026) ---------------------------------------
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
    2025: "Oklahoma City Thunder", 2026: "Oklahoma City Thunder"
}

# --- Helpers ---------------------------------------------------------------

def season_str(end_year: int) -> str:
    return f"{end_year-1}-{str(end_year)[-2:]}"

def height_to_inches(h: str) -> int | None:
    if not isinstance(h, str) or "-" not in h: return None
    try:
        ft, inch = h.split("-")
        return int(ft) * 12 + int(inch)
    except: return None

def inches_to_ftin(x: float) -> str:
    if pd.isna(x): return "NA"
    x = int(round(float(x)))
    return f"{x//12}'{x%12}\""

# --- Caching Logic ---------------------------------------------------------

def get_season_players_heights(end_year: int, sleep_s: float = 0.6) -> pd.DataFrame:
    file_path = os.path.join(CACHE_DIR, f"nba_players_{end_year}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path)

    season = season_str(end_year)
    team_list = teams.get_teams()
    rows = []

    print(f"\nCache miss: Fetching roster for {season}...")
    for t in tqdm(team_list, desc=f"Teams in {season}", leave=False):
        try:
            r = commonteamroster.CommonTeamRoster(team_id=t["id"], season=season)
            df = r.get_data_frames()[0]
            for _, row in df.iterrows():
                hin = height_to_inches(row.get("HEIGHT"))
                if hin:
                    rows.append({"player_id": int(row["PLAYER_ID"]), "height_in": hin})
            time.sleep(sleep_s)
        except: pass

    df_unique = pd.DataFrame(rows).drop_duplicates(subset=["player_id"]) if rows else pd.DataFrame()
    df_unique.to_csv(file_path, index=False)
    return df_unique

def get_champion_starters_height(end_year: int, roster_df: pd.DataFrame) -> float | None:
    """Finds avg height of top 5 players by minutes for the champion."""
    file_path = os.path.join(CHAMP_CACHE_DIR, f"champ_avg_{end_year}.txt")
    
    # Check cache first
    if os.path.exists(file_path):
        with open(file_path, 'r') as f: return float(f.read())

    champ_name = CHAMPIONS.get(end_year)
    if not champ_name or roster_df.empty: return None
    
    try:
        team_id = [t for t in teams.get_teams() if t['full_name'] == champ_name][0]['id']
        # FIXED: Correct endpoint name is TeamPlayerDashboard
        stats = teamplayerdashboard.TeamPlayerDashboard(team_id=team_id, season=season_str(end_year))
        stats_df = stats.get_data_frames()[1] # PlayersSeasonTotals is usually at index 1
        
        top_5_ids = stats_df.sort_values(by="MIN", ascending=False).head(5)["PLAYER_ID"].tolist()
        avg_h = roster_df[roster_df["player_id"].isin(top_5_ids)]["height_in"].mean()
        
        # Save to cache
        with open(file_path, 'w') as f: f.write(str(avg_h))
        return avg_h
    except Exception as e:
        print(f"Error fetching champ stats for {end_year}: {e}")
        return None

# --- Main Logic ------------------------------------------------------------

def build_summary(start_year: int = 1980) -> pd.DataFrame:
    summaries = []
    current_year = datetime.now().year
    for year in tqdm(range(start_year, current_year + 1), desc="Total Progress"):
        players = get_season_players_heights(year)
        champ_avg = get_champion_starters_height(year, players)
        
        summaries.append({
            "season_end_year": year,
            "avg_height_in": players["height_in"].mean() if not players.empty else None,
            "champ_starter_avg": champ_avg,
            "tallest_height_in": players["height_in"].max() if not players.empty else None,
        })
    return pd.DataFrame(summaries)

def plot_summary(df: pd.DataFrame):
    df = df.dropna(subset=["avg_height_in"])
    plt.figure(figsize=(12, 6))
    plt.plot(df["season_end_year"], df["avg_height_in"], marker='o', label="League Avg")
    plt.plot(df["season_end_year"], df["tallest_height_in"], marker='s', label="League Tallest")
    plt.plot(df["season_end_year"], df["champ_starter_avg"], marker='x', color='gold', linewidth=2, label="Champ Starters Avg")
    
    plt.title("NBA Height Trends: League vs. Champions (1980-Present)")
    plt.xlabel("Season End Year")
    plt.ylabel("Height (inches)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig("nba_heights_comparison.png", dpi=200)
    plt.show()

if __name__ == "__main__":
    summary = build_summary()
    plot_summary(summary)