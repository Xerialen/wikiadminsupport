# Wiki Stats Generator (`generate_wiki_stats.py`)

This tool automates the creation of advanced player statistics tables for QuakeWorld tournaments. It scans a specific folder of match logs (KTX JSON format) and generates a pre-formatted **MediaWiki** table ready for copy-pasting into your wiki.

It uses **Map Aware** logic to calculate accurate averages. For example, it counts a player's "Avg Lightning Gun Kills" only based on the games played on maps that actually *have* a Lightning Gun.

## 📂 Directory Structure

Ensure your project folder is organized as follows:

```text
/
├── generate_wiki_stats.py        # The main script
├── config/
│   └── maps_items.json           # Database defining items per map
└── data/
    └── wiki/
        └── Season2_Division1/    # Folder containing your JSON match files
            ├── match1.json
            ├── match2.json
            └── ...
			


1. Run the Script
Open your terminal and pass the folder path as an argument:

Bash

python3 generate_wiki_stats.py "data/wiki/Season2_Division1"

2. Get the Output
The script creates a text file named after the folder (e.g., Season2_Division1.txt).

Open this file, copy the content, and paste it directly into your Wiki page.

Configuration (maps_items.json)
The script relies on config/maps_items.json to calculate "True Averages." It compares the map name in every match file to this database.

Denominator Logic:

If a player plays DM2 (which has no Lightning Gun), that game is excluded from their LG Average.

If a player plays DM3 (which has LG), that game is included.

Rocket Launcher & Shotgun: These are assumed to exist on all maps.

How Calculations Are Made
The script distinguishes between General Averages (Global Sum / Total Games) and Percentage Averages (Average of specific game percentages).

1. General & Movement Stats
Calculated as the global sum divided by the Total Games Played.
Column,JSON Source,Formula
Avg Frags,stats.frags,Sum(Frags) / Games
Avg Deaths,stats.deaths,Sum(Deaths) / Games
EWEP,dmg.given,Sum(Damage) / Games
To Die,dmg.taken-to-die,Sum(TakenToDie) / Games
Avg Spd,speed.avg,Sum(AvgSpeed) / Games
Max Spd,speed.max,Sum(MaxSpeed) / Games

2. Efficiency & Accuracy (Per-Game Method)
Calculated by determining the percentage for each specific game, then averaging those percentages. This ensures a short game has equal weight to a long game.
Column,Formula,Notes
Eff %,Avg(Frags / (Frags + Deaths)),Measures engagement efficiency per match.
LG %,Avg(Hits / Attacks),Calculated only for games where shots were fired.
SG %,Avg(Hits / Attacks),Calculated only for games where shots were fired.

3. Weapons
Calculated using Enemy Kills (ignoring team kills) divided by Opportunities (Map Availability).
Column,JSON Source,Formula
RL Kills,weapons.rl.kills.enemy,Sum(EnemyKills) / Total Games
RL Xfer,player.xferRL,Sum(Transfers) / Total Games (Passes to teammates/intentional suicides)
RL Hits,weapons.rl.acc.hits,Sum(DirectHits) / Total Games
RL Taken,weapons.rl.pickups.total-taken,Sum(Taken) / Total Games
RL Drop,weapons.rl.pickups.dropped,Sum(Dropped) / Total Games
LG Kills,weapons.lg.kills.enemy,Sum(EnemyKills) / Games_WithLG
GL Kills,weapons.gl.kills.enemy,Sum(EnemyKills) / Games_WithGL

4. Items (Powerups/Armor)
Calculated strictly based on Map Config. If a map lacks the item, the game is excluded from the average.
Column,Config Key,Formula
Quad,quad,Sum(Quads) / Games_WithQuad
Pent,pent,Sum(Pents) / Games_WithPent
Ring,ring,Sum(Rings) / Games_WithRing
RA,ra,Sum(RedArmors) / Games_WithRA
YA,ya,Sum(YellowArmors) / Games_WithYA
MH,mh,Sum(MegaHealths) / Games_WithMH