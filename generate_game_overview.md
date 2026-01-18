This script analyzes QuakeWorld match JSON logs to generate an interactive HTML match report. It is very helpful when you have a pile of JSON files representing individual maps and you want to turn them into a series where you can see players.

Functionality
Scans JSON Logs: Reads match data (players, scores, maps, timestamps) from a specified directory.

Groups Matches: intelligently groups individual maps into series/matches based on:

Teams: Matches must involve the same two teams.

Time Gap: Games played more than 90 minutes apart are treated as separate series.

Calculates Scores: Determines map winners and series scores based on team frag totals.

Generates HTML Report: Creates a single HTML file containing:

Match Summary: Date, server, teams, and final series score.

Expandable Details: Clicking a match reveals individual map scores, player rosters with frag counts, and the source filename for each map.

Visual Cues: Colors winners (green) and losers (red) for easy identification.

Usage
Run the script from the command line, providing the directory containing your JSON logs:

Bash

python generate_game_overview.py "path/to/json/logs"
The script will generate an HTML file (named after the directory) in the same location.