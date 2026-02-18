from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Tuple

import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.static import teams

# --- Helpers ---------------------------------------------------------------

def season_str(end_year: int) -> str:
    """Convert end-year 1980 -> '1979-80' for nba_api season string."""
    start = end_year - 1
    return f"{start}-{str(end_year)[-2:]}"


def height_to_inches(h: str) -> int | None:
    """Convert '6-7' -> 79 inches."""
    if not isinstance(h, str):
        return None
    h = h.strip()
    if "-" not in h:
        return None
    try:
        ft, inch = h.split("-")
        return int(ft) * 12 + int(inch)
    except Exception:
        return None


def inches_to_ftin(x: float) -> str:
    """Convert inches to 6'7\" style string."""
    if pd.isna(x):
        return "NA"
    x = int(round(float(x)))
    return f"{x//12}'{x%12}\""


# --- Data collection -------------------------------------------------------

def get_season_players_heights(end_year: int, sleep_s: float = 0.6) -> pd.DataFrame:
    """
    Fetch all team rosters for a season via nba_api, return unique players with heights.
    Dedup players by PERSON_ID (trades won't duplicate).
    """
    season = season_str(end_year)
    team_list = teams.get_teams()

    rows = []
    for t in team_list:
        team_id = t["id"]
        try:
            r = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
            df = r.get_data_frames()[0]  # roster
            if not df.empty:
                for _, row in df.iterrows():
                    hin = height_to_inches(row.get("HEIGHT", None))
                    if hin is None:
                        continue
                    rows.append(
                        {
                            "season_end_year": end_year,
                            "season": season,
                            "team_id": team_id,
                            "team_name": t["full_name"],
                            "player_id": int(row["PLAYER_ID"]),
                            "player_name": row["PLAYER"],
                            "height_in": hin,
                        }
                    )
        except Exception:
            # Some historical seasons may have missing/partial roster coverage; skip that team
            pass

        time.sleep(sleep_s)

    if not rows:
        return pd.DataFrame(columns=["season_end_year", "season", "player_id", "player_name", "height_in"])

    df_all = pd.DataFrame(rows)
    # Deduplicate by player_id within season
    df_unique = df_all.sort_values(["player_id", "team_id"]).drop_duplicates(subset=["season_end_year", "player_id"])
    return df_unique


def build_summary(start_end_year: int = 1980) -> pd.DataFrame:
    now = datetime.now()
    last_end_year = now.year  # include current end-year; may be partial

    summaries = []
    for end_year in tqdm(range(start_end_year, last_end_year + 1), desc="Seasons"):
        players = get_season_players_heights(end_year)

        if players.empty:
            # keep record but mark as missing
            summaries.append(
                {
                    "season_end_year": end_year,
                    "season": season_str(end_year),
                    "avg_height_in": float("nan"),
                    "tallest_height_in": float("nan"),
                    "n_players": 0,
                }
            )
            continue

        summaries.append(
            {
                "season_end_year": end_year,
                "season": season_str(end_year),
                "avg_height_in": players["height_in"].mean(),
                "tallest_height_in": players["height_in"].max(),
                "n_players": int(players["player_id"].nunique()),
            }
        )

    return pd.DataFrame(summaries)


# --- Plot ------------------------------------------------------------------

def plot_summary(summary: pd.DataFrame, out_png: str = "nba_heights_1980_present.png") -> None:
    summary = summary.sort_values("season_end_year")
    # Drop missing seasons (if any)
    summary_plot = summary.dropna(subset=["avg_height_in", "tallest_height_in"])

    plt.figure(figsize=(11, 6))
    plt.plot(summary_plot["season_end_year"], summary_plot["avg_height_in"], label="Average height (inches)")
    plt.plot(summary_plot["season_end_year"], summary_plot["tallest_height_in"], label="Tallest player (inches)")
    plt.title("NBA Heights by Season (1980–Present)")
    plt.xlabel("Season end year (e.g., 1980 = 1979–80)")
    plt.ylabel("Height (inches)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    print(f"Saved chart: {out_png}")

    latest = summary_plot.iloc[-1]
    print(
        f"Latest included season ({int(latest['season_end_year'])} / {latest['season']}): "
        f"avg={inches_to_ftin(latest['avg_height_in'])}, "
        f"tallest={inches_to_ftin(latest['tallest_height_in'])}, "
        f"players={int(latest['n_players'])}"
    )

    plt.show()


def main():
    summary_csv = "nba_heights_by_season.csv"

    summary = build_summary(1980)
    summary.to_csv(summary_csv, index=False)
    print(f"Saved data: {summary_csv}")

    plot_summary(summary)


if __name__ == "__main__":
    main()
