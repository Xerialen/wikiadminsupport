import json
import os
import sys
import glob
from collections import defaultdict
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# How much time between games implies a NEW series? (Minutes)
SERIES_GAP_THRESHOLD_MINUTES = 90

def get_team_scores(players):
    """Calculates total frags per team from the player list."""
    teams = defaultdict(int)
    team_rosters = defaultdict(list)
    
    for p in players:
        t_name = p.get("team", "Unknown")
        if t_name.lower() in ["spec", "spectator", ""]:
            continue
            
        frags = p.get("stats", {}).get("frags", 0)
        teams[t_name] += frags
        team_rosters[t_name].append({
            "name": p.get("name", "Unknown"),
            "frags": frags
        })
    
    return teams, team_rosters

def parse_games(input_dir):
    """
    Scans JSON files and returns a SORTED list of processed individual game objects.
    """
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    valid_games = []

    print(f"📂 Scanning {len(json_files)} files in {input_dir}...")

    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # --- DATE PARSING ---
            date_str = data.get("date", "1970-01-01 00:00:00")
            clean_date_str = date_str[:19] # Strip timezone offsets
            
            try:
                date_obj = datetime.strptime(clean_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                date_obj = datetime.min

            # --- TEAM PARSING ---
            teams_score, rosters = get_team_scores(data.get("players", []))
            
            if len(teams_score) != 2:
                continue

            team_names = list(teams_score.keys())
            t1, t2 = sorted(team_names) 
            
            # Store processed game data
            valid_games.append({
                "date_obj": date_obj,
                "team1": t1,
                "team2": t2,
                "server": data.get("server", data.get("hostname", "Unknown")),
                "map": data.get("map", "unknown"),
                "score_t1": teams_score[t1],
                "score_t2": teams_score[t2],
                "roster_t1": rosters[t1],
                "roster_t2": rosters[t2],
                "file": os.path.basename(filepath) # Capture filename
            })

        except Exception as e:
            print(f"⚠️ Skipped {os.path.basename(filepath)}: {e}")
            
    # Sort ALL games by time (Oldest -> Newest)
    valid_games.sort(key=lambda x: x["date_obj"])
    
    return valid_games

def group_into_matches(sorted_games):
    """
    Groups games into matches based on Team Pairing and Time Gap.
    """
    matches = []
    active_series = {}

    for game in sorted_games:
        pair_key = (game["team1"], game["team2"])
        
        if pair_key in active_series:
            current_match = active_series[pair_key]
            last_game_time = current_match["last_game_time"]
            
            delta = game["date_obj"] - last_game_time
            gap_minutes = delta.total_seconds() / 60
            
            if gap_minutes > SERIES_GAP_THRESHOLD_MINUTES:
                matches.append(current_match)
                new_match = create_new_match(game)
                active_series[pair_key] = new_match
            else:
                current_match["maps"].append(game)
                current_match["last_game_time"] = game["date_obj"]
                current_match["server"] = game["server"]
        else:
            new_match = create_new_match(game)
            active_series[pair_key] = new_match
            
    for m in active_series.values():
        matches.append(m)
        
    matches.sort(key=lambda x: x["start_time"])
    return matches

def create_new_match(first_game):
    return {
        "team1": first_game["team1"],
        "team2": first_game["team2"],
        "start_time": first_game["date_obj"], 
        "last_game_time": first_game["date_obj"], 
        "server": first_game["server"],
        "maps": [first_game]
    }

def generate_html(matches, output_filename):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>QuakeWorld Match Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; color: #bb86fc; }}
            .container {{ max-width: 900px; margin: 0 auto; }}
            
            .match-card {{ background-color: #1e1e1e; margin-bottom: 15px; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            
            .match-summary {{ 
                display: flex; justify-content: space-between; align-items: center; 
                padding: 15px 20px; cursor: pointer; transition: background 0.2s;
            }}
            .match-summary:hover {{ background-color: #2c2c2c; }}
            
            .date-server {{ font-size: 0.85em; color: #888; width: 160px; }}
            .teams {{ flex-grow: 1; text-align: center; font-size: 1.2em; font-weight: bold; }}
            .score-badge {{ 
                padding: 5px 15px; border-radius: 20px; font-weight: bold; background: #333; min-width: 40px; text-align: center;
            }}
            .winner {{ color: #00e676; }}
            .loser {{ color: #cf6679; }}
            .draw {{ color: #ffb74d; }}
            
            details > summary {{ list-style: none; }}
            details > summary::-webkit-details-marker {{ display: none; }}
            
            .match-details {{ padding: 0 20px 20px 20px; border-top: 1px solid #333; background: #252525; }}
            
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th {{ text-align: left; color: #bb86fc; border-bottom: 2px solid #444; padding: 10px; }}
            td {{ padding: 10px; border-bottom: 1px solid #333; vertical-align: top; }}
            
            .map-winner {{ color: #00e676; font-weight: bold; }}
            .sub-stats {{ font-size: 0.85em; color: #aaa; margin-top: 4px; }}
            .frags {{ color: #fff; font-weight: bold; }}
            
            /* New Style for Filenames */
            .file-name {{ 
                display: block; 
                font-size: 0.7em; 
                color: #555; 
                margin-top: 4px; 
                font-family: 'Consolas', 'Monaco', monospace; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Match Overview: {output_filename.replace('.html', '')}</h1>
    """

    if not matches:
        html_content += "<p style='text-align:center'>No matches found.</p>"

    for m in matches:
        t1_maps = 0
        t2_maps = 0
        for game in m['maps']:
            if game['score_t1'] > game['score_t2']: t1_maps += 1
            elif game['score_t2'] > game['score_t1']: t2_maps += 1
        
        t1_class = "winner" if t1_maps > t2_maps else ("loser" if t1_maps < t2_maps else "draw")
        t2_class = "winner" if t2_maps > t1_maps else ("loser" if t2_maps < t1_maps else "draw")

        date_display = m['start_time'].strftime("%Y-%m-%d %H:%M")

        html_content += f"""
        <div class="match-card">
            <details>
                <summary class="match-summary">
                    <div class="date-server">
                        <div>{date_display}</div>
                        <div>{m['server']}</div>
                    </div>
                    <div class="teams">
                        <span class="{t1_class}">{m['team1']}</span> 
                        <span style="color:#666; margin:0 10px;">vs</span> 
                        <span class="{t2_class}">{m['team2']}</span>
                    </div>
                    <div class="score-badge">
                        <span class="{t1_class}">{t1_maps}</span> : <span class="{t2_class}">{t2_maps}</span>
                    </div>
                </summary>
                
                <div class="match-details">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 20%;">Map</th>
                                <th style="width: 40%;">{m['team1']} Frags</th>
                                <th style="width: 40%;">{m['team2']} Frags</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        for game in m['maps']:
            s1 = game['score_t1']
            s2 = game['score_t2']
            s1_style = 'class="map-winner"' if s1 > s2 else ''
            s2_style = 'class="map-winner"' if s2 > s1 else ''
            
            r1 = sorted(game['roster_t1'], key=lambda x: x['frags'], reverse=True)
            r2 = sorted(game['roster_t2'], key=lambda x: x['frags'], reverse=True)
            
            r1_str = ", ".join([f"{p['name']} <span class='frags'>({p['frags']})</span>" for p in r1])
            r2_str = ", ".join([f"{p['name']} <span class='frags'>({p['frags']})</span>" for p in r2])

            html_content += f"""
                            <tr>
                                <td>
                                    {game['map']}
                                    <span class="file-name">{game['file']}</span>
                                </td>
                                <td {s1_style}>{s1} <div class="sub-stats">{r1_str}</div></td>
                                <td {s2_style}>{s2} <div class="sub-stats">{r2_str}</div></td>
                            </tr>
            """

        html_content += """
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
        """

    html_content += "</div></body></html>"
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Report generated: {output_filename}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = os.getcwd()

    if not os.path.isdir(target_dir):
        print(f"❌ Error: Directory '{target_dir}' not found.")
    else:
        folder_name = os.path.basename(os.path.normpath(target_dir))
        if not folder_name: 
             folder_name = "match_overview"
        output_file = f"{folder_name}.html"
        
        raw_games = parse_games(target_dir)
        grouped_matches = group_into_matches(raw_games)
        generate_html(grouped_matches, output_file)