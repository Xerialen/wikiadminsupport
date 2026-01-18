import json
import sys
import os
from datetime import datetime
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
# Default folder to scan if no arguments are provided
DEFAULT_TARGET_DIR = BASE_DIR / "data" / "wiki" / "awaitingupload"

# Max time gap (minutes) to group maps into one series
SERIES_GAP_MINUTES = 90

def normalize(name):
    """Normalize strings for comparison."""
    return str(name).lower().strip()

def parse_date(date_str):
    try:
        if "+" in date_str:
            clean_date = date_str.split("+")[0].strip()
        else:
            clean_date = date_str
        return datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
    except:
        return datetime.min

def get_team_score(json_data, team_name):
    target = normalize(team_name)
    # 1. Try explicit team score
    if "teams" in json_data and isinstance(json_data["teams"], list):
        for team in json_data["teams"]:
            t_name = team.get("name", "") if isinstance(team, dict) else str(team)
            if normalize(t_name) == target:
                if isinstance(team, dict) and "score" in team:
                    return int(team["score"])
    # 2. Fallback: Sum player frags
    total = 0
    found = False
    if "players" in json_data:
        for p in json_data["players"]:
            if normalize(p.get("team", "")) == target:
                total += int(p.get("frags", 0))
                found = True
    return total if found else 0

def load_match_metadata(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        dt = parse_date(data.get("date", ""))
        
        teams = []
        if "teams" in data:
            teams = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in data["teams"]]
        elif "players" in data:
            teams = list(set(p.get("team", "Unknown") for p in data["players"]))
        
        teams_clean = [normalize(t) for t in teams]
        teams_sorted = tuple(sorted(teams_clean))
        
        return {
            "path": filepath,
            "date": dt,
            "teams": teams_sorted,
            "data": data
        }
    except Exception as e:
        print(f"⚠️ Error loading {filepath}: {e}")
        return None

def generate_wiki_for_series(series_matches):
    if not series_matches: return

    # Get display names from the first match
    first_data = series_matches[0]["data"]
    raw_teams_list = []
    if "teams" in first_data:
        raw_teams_list = [t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in first_data["teams"]]
    elif "players" in first_data:
        raw_teams_list = list(set(p.get("team", "Unknown") for p in first_data["players"]))
    
    # Sort alphabetically to keep Player1/Player2 consistent
    raw_teams_list.sort(key=lambda x: x.lower())

    if len(raw_teams_list) >= 2:
        t1_raw, t2_raw = raw_teams_list[0], raw_teams_list[1]
    else:
        t1_raw, t2_raw = "Team1", "Team2"
    
    # Calculate Results
    matches_output = []
    t1_wins = 0
    t2_wins = 0
    
    print(f"🏆 SERIES FOUND: {t1_raw} vs {t2_raw} ({len(series_matches)} maps)")

    for m in series_matches:
        data = m["data"]
        map_name = data.get("map", "unknown")
        s1 = get_team_score(data, t1_raw)
        s2 = get_team_score(data, t2_raw)
        
        winner = ""
        if s1 > s2:
            winner = "1"
            t1_wins += 1
        elif s2 > s1:
            winner = "2"
            t2_wins += 1
            
        matches_output.append({
            "map": map_name,
            "s1": s1,
            "s2": s2,
            "win": winner
        })

    series_winner = ""
    if t1_wins > t2_wins: series_winner = "1"
    elif t2_wins > t1_wins: series_winner = "2"

    # --- WIKI OUTPUT ---
    wiki = "{{MatchMaps\n"
    wiki += f"|player1={t1_raw} |player1flag=\n"
    wiki += f"|player2={t2_raw} |player2flag=\n"
    wiki += f"|winner={series_winner}\n"
    wiki += "|walkover=\n"
    wiki += f"|games1={t1_wins} |games2={t2_wins}\n"
    wiki += "|details={{BracketMatchSummary\n|date=\n|comment=\n"

    for i, m in enumerate(matches_output):
        n = i + 1
        wiki += f"|map{n}win={m['win']} |map{n}={m['map']} |map{n}p1frags={m['s1']} |map{n}p2frags={m['s2']} |map{n}p1lineup= |map{n}p2lineup= |map{n}ot=\n"

    # Fill empty slots (standard 3 maps)
    if len(matches_output) < 3:
        for n in range(len(matches_output) + 1, 4):
            wiki += f"|map{n}win= |map{n}= |map{n}p1frags= |map{n}p2frags= |map{n}p1lineup= |map{n}p2lineup= |map{n}ot=\n"

    wiki += "}}\n}}"
    print("-" * 40)
    print(wiki)
    print("-" * 40 + "\n")

def main():
    # 1. Determine Target Directory
    target_path = DEFAULT_TARGET_DIR
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])

    if not target_path.exists():
        print(f"❌ Error: Directory not found: {target_path}")
        return

    print(f"📂 Scanning: {target_path}")
    
    # 2. Recursive Scan (rglob) to find files in subfolders
    files = list(target_path.rglob("*.json"))
    
    if not files:
        print("❌ No JSON files found in awaitingupload.")
        return

    # 3. Load & Sort
    all_matches = []
    for f in files:
        meta = load_match_metadata(f)
        if meta: all_matches.append(meta)

    # Sort by date so the series grouping logic works chronologically
    all_matches.sort(key=lambda x: x["date"])

    # 4. Group into Series
    series_list = []
    if all_matches:
        current_series = [all_matches[0]]
        for i in range(1, len(all_matches)):
            prev = current_series[-1]
            curr = all_matches[i]
            
            # Group if: Same Teams AND Time Gap is acceptable
            same_teams = (prev["teams"] == curr["teams"])
            time_diff = (curr["date"] - prev["date"]).total_seconds() / 60
            
            if same_teams and time_diff < SERIES_GAP_MINUTES:
                current_series.append(curr)
            else:
                series_list.append(current_series)
                current_series = [curr]
        series_list.append(current_series)

    # 5. Output
    print(f"✅ Processing {len(series_list)} unique series...\n")
    for s in series_list:
        generate_wiki_for_series(s)

if __name__ == "__main__":
    main()