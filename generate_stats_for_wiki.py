import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data" / "wiki" / "awaitingupload"
MAPS_CONFIG_FILE = BASE_DIR / "config" / "maps_items.json"

# Standard Quake Colors
QUAKE_COLORS = {
    0: "#D3D3D3", 1: "#8B4513", 2: "#D8BFD8", 3: "#008000",
    4: "#8B0000", 12: "#FFFF00", 13: "#0000FF"
}

# Items to track opportunities for
# RL and SG are treated as always available
ALL_TRACKED_ITEMS = [
    # WEAPONS
    "lg", "gl", "sng", "ng", "ssg", 
    # ARMOR / HEALTH
    "mh", "ra", "ya", "ga", 
    # POWERUPS
    "pent", "ring", "quad"
]

def safe_div(n, d):
    return n / d if d > 0 else 0

def load_maps_config():
    try:
        with open(MAPS_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Warning: Could not find config file at {MAPS_CONFIG_FILE}")
        return {}

def get_stats_structure():
    return {
        "games": 0,
        "opportunities": defaultdict(int),
        "team_color": None,
        
        # Core Stats
        "frags": 0, 
        "deaths": 0, 
        "dmg_given": 0,
        "dmg_enemy_weapons": 0, # NEW: Specifically for EWEP
        "dmg_to_die": 0,
        
        # Movement
        "speed_sum": 0,     # Sum of average speeds
        "speed_max_sum": 0, # Sum of max speeds
        
        # Weapons
        "rl": {"k":0, "h":0, "t":0, "d":0, "xfer":0},
        "lg": {"k":0, "h":0, "t":0, "d":0},
        "gl": {"k":0, "h":0, "t":0, "d":0}, 
        "sng": {"k":0, "h":0, "t":0, "d":0}, 
        "ng": {"k":0, "h":0, "t":0, "d":0},  
        "ssg": {"k":0, "h":0, "t":0, "d":0}, 
        
        # Accuracy Accumulators
        "acc_sums": { "lg": 0.0, "sg": 0.0, "eff": 0.0 },
        "acc_counts": { "lg": 0, "sg": 0, "eff": 0 },
        
        # Items
        "items": {"q":0, "p":0, "r":0, "ra":0, "ya":0, "ga":0, "mh":0}
    }

def process_file(filepath, players_db, maps_config):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        map_name = data.get("map", "").lower()
        available_items = maps_config.get(map_name, ALL_TRACKED_ITEMS)

        if "players" not in data: return

        for p in data["players"]:
            name = p.get("name", "Unknown")
            
            if name not in players_db:
                players_db[name] = get_stats_structure()
                tc = p.get("top-color", 0)
                players_db[name]["team_color"] = QUAKE_COLORS.get(tc, "")

            db = players_db[name]
            db["games"] += 1
            
            # --- OPPORTUNITIES ---
            for item in available_items:
                db["opportunities"][item] += 1
            
            # RL is always an opportunity
            db["opportunities"]["rl"] += 1

            # --- CORE STATS ---
            stats = p.get("stats", {})
            p_frags = stats.get("frags", 0)
            p_deaths = stats.get("deaths", 0)
            
            db["frags"] += p_frags
            db["deaths"] += p_deaths
            
            # Damage Stats
            dmg_data = p.get("dmg", {})
            db["dmg_given"] += dmg_data.get("given", 0)
            
            # NEW: Collect Enemy Weapons Damage (fallback to 0 if missing)
            # Checks "enemy-weapons" (standard KTX) and "enemy_weapons" (some variants)
            ewep = dmg_data.get("enemy-weapons", dmg_data.get("enemy_weapons", 0))
            db["dmg_enemy_weapons"] += ewep
            
            # To-Die
            db["dmg_to_die"] += dmg_data.get("taken-to-die", dmg_data.get("taken_to_die", 0))

            # Speed
            speed_data = p.get("speed", {})
            db["speed_sum"] += speed_data.get("avg", 0)
            db["speed_max_sum"] += speed_data.get("max", 0)
            
            # Efficiency
            engagements = p_frags + p_deaths
            if engagements > 0:
                game_eff = p_frags / engagements
                db["acc_sums"]["eff"] += game_eff
                db["acc_counts"]["eff"] += 1
            
            # --- WEAPONS ---
            weap = p.get("weapons", {})
            
            def get_w(key):
                w = weap.get(key, {})
                pickups = w.get("pickups", {})
                return {
                    "k": w.get("kills", {}).get("enemy", 0),
                    "h": w.get("acc", {}).get("hits", 0),
                    "t": pickups.get("total-taken", 0),
                    "d": pickups.get("dropped", 0),
                    "a": w.get("acc", {}).get("attacks", 0)
                }

            # Process RL
            rl_data = get_w("rl")
            db["rl"]["k"] += rl_data["k"]
            db["rl"]["h"] += rl_data["h"]
            db["rl"]["t"] += rl_data["t"]
            db["rl"]["d"] += rl_data["d"]
            
            # RL Xfer (Extracted from root)
            db["rl"]["xfer"] += p.get("xferRL", 0)

            # Process other weapons
            for w_key in ["lg", "gl", "sng", "ng", "ssg"]:
                if w_key in available_items:
                    w_data = get_w(w_key)
                    if w_key in db:
                        db[w_key]["k"] += w_data["k"]
                        db[w_key]["h"] += w_data["h"]
                        db[w_key]["t"] += w_data["t"]
                        db[w_key]["d"] += w_data["d"]

            # Accuracy Accumulators
            if "lg" in available_items:
                lg_data = get_w("lg")
                if lg_data["a"] > 0:
                    db["acc_sums"]["lg"] += (lg_data["h"] / lg_data["a"])
                    db["acc_counts"]["lg"] += 1

            sg_data = get_w("sg")
            if sg_data["a"] > 0:
                db["acc_sums"]["sg"] += (sg_data["h"] / sg_data["a"])
                db["acc_counts"]["sg"] += 1

            # --- ITEMS ---
            items = p.get("items", {})
            
            def get_item_count(key):
                i_data = items.get(key, {})
                return i_data.get("took", i_data.get("taken", 0))

            if "quad" in available_items: db["items"]["q"] += get_item_count("q")
            if "pent" in available_items: db["items"]["p"] += get_item_count("p")
            if "ring" in available_items: db["items"]["r"] += get_item_count("r")
            
            if "mh" in available_items:   db["items"]["mh"] += get_item_count("health_100")
            
            if "ra" in available_items:   db["items"]["ra"] += get_item_count("ra")
            if "ya" in available_items:   db["items"]["ya"] += get_item_count("ya")
            if "ga" in available_items:   db["items"]["ga"] += get_item_count("ga")

    except Exception as e:
        print(f"⚠️ Error reading {filepath.name}: {e}")

def generate_wiki_table(players_db):
    headers = [
        "Player", "Games", 
        "Avg Frags", "Avg Deaths", "Avg Dmg", "EWEP", "To Die", "Eff %",
        "Avg Spd", "Max Spd",
        "RL Kills", "RL Xfer", "RL Hits", "RL Taken", "RL Drop",
        "LG Kills", "LG Taken", "LG Drop",
        "GL Kills",
        "Quad", "Pent", "Ring", "RA", "YA", "MH",
        "LG %", "SG %"
    ]
    
    out = ['{| class="wikitable sortable"']
    out.append("! " + " !! ".join(headers))
    
    sorted_players = sorted(
        players_db.items(), 
        key=lambda x: safe_div(x[1]["frags"], x[1]["games"]), 
        reverse=True
    )

    for name, db in sorted_players:
        g = db["games"]
        if g == 0: continue
        
        opp = db["opportunities"]
        
        # 1. General Stats
        avg_frags = round(db["frags"] / g, 1)
        avg_deaths = round(db["deaths"] / g, 1)
        
        # Avg Damage (Renamed from EWEP)
        avg_dmg = int(db["dmg_given"] / g)
        
        # NEW: EWEP (Enemy Weapons Damage)
        avg_ewep = int(db["dmg_enemy_weapons"] / g)
        
        avg_to_die = int(db["dmg_to_die"] / g)
        
        eff_val = safe_div(db["acc_sums"]["eff"], db["acc_counts"]["eff"])
        eff_pct = f"{eff_val*100:.1f}%"
        
        # 2. Movement
        avg_speed = int(db["speed_sum"] / g)
        max_speed = int(db["speed_max_sum"] / g)

        # 3. Weapons
        # RL
        rl_opp = opp["rl"] if opp["rl"] > 0 else g
        rl_k = round(safe_div(db["rl"]["k"], rl_opp), 1)
        rl_xfer = round(safe_div(db["rl"]["xfer"], rl_opp), 1)
        rl_h = round(safe_div(db["rl"]["h"], rl_opp), 1)
        rl_t = round(safe_div(db["rl"]["t"], rl_opp), 1)
        rl_d = round(safe_div(db["rl"]["d"], rl_opp), 1)
        
        # LG
        lg_k = round(safe_div(db["lg"]["k"], opp["lg"]), 1)
        lg_t = round(safe_div(db["lg"]["t"], opp["lg"]), 1)
        lg_d = round(safe_div(db["lg"]["d"], opp["lg"]), 1)
        
        # GL
        gl_k = round(safe_div(db["gl"]["k"], opp["gl"]), 1)

        # 4. Items
        quad = round(safe_div(db["items"]["q"], opp["quad"]), 1)
        pent = round(safe_div(db["items"]["p"], opp["pent"]), 1)
        ring = round(safe_div(db["items"]["r"], opp["ring"]), 1)
        ra   = round(safe_div(db["items"]["ra"], opp["ra"]), 1)
        ya   = round(safe_div(db["items"]["ya"], opp["ya"]), 1)
        mh   = round(safe_div(db["items"]["mh"], opp["mh"]), 1)
        
        # 5. Accuracy
        lg_acc_val = safe_div(db['acc_sums']['lg'], db['acc_counts']['lg'])
        sg_acc_val = safe_div(db['acc_sums']['sg'], db['acc_counts']['sg'])
        
        lg_acc = f"{lg_acc_val*100:.1f}%"
        sg_acc = f"{sg_acc_val*100:.1f}%"

        color_style = f'style="border-left: 3px solid {db["team_color"]}"' if db["team_color"] else ""
        
        row = [
            f'| {color_style} | {name}',
            g, 
            avg_frags, avg_deaths, avg_dmg, avg_ewep, avg_to_die, eff_pct,
            avg_speed, max_speed,
            rl_k, rl_xfer, rl_h, rl_t, rl_d,
            lg_k, lg_t, lg_d,
            gl_k,
            quad, pent, ring, ra, ya, mh,
            lg_acc, sg_acc
        ]
        
        out.append("|-")
        out.append(" || ".join(map(str, row)))

    out.append("|}")
    return "\n".join(out)

def main():
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
    else:
        target_dir = DEFAULT_INPUT_DIR

    if not target_dir.exists():
        print(f"❌ Error: Directory '{target_dir}' not found.")
        return

    folder_name = target_dir.name
    output_file_name = f"{folder_name}.txt"
    
    print(f"📂 Scanning {target_dir}...")
    maps_config = load_maps_config()
    
    if maps_config:
        print(f"🗺️  Loaded map config from {MAPS_CONFIG_FILE}")
    
    players_db = {}
    files = list(target_dir.glob("*.json"))
    
    if not files:
        print("⚠️  No JSON files found in target directory.")
        return

    for f in files:
        process_file(f, players_db, maps_config)
        
    print(f"📊 Calculated stats for {len(players_db)} players.")
    
    wiki_code = generate_wiki_table(players_db)
    
    with open(output_file_name, "w", encoding="utf-8") as f:
        f.write(wiki_code)
        
    print(f"✅ Done! Wiki code saved to: {output_file_name}")

if __name__ == "__main__":
    main()