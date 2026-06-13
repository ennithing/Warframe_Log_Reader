import os
import sys
import time
import ctypes
import inspect
import threading
from datetime import datetime, timedelta

VERSION = '1.1.5 - 13.06.2026'
ctypes.windll.kernel32.SetConsoleTitleW("Warframe Log Observer")


_stdout_lock = threading.Lock()

DEBUG = False

APPDATA = os.getenv("LOCALAPPDATA")
LOG_FILE_PATH = os.path.join(APPDATA, "Warframe", "EE.log") if APPDATA else "EE.log"

CLEAR_LINE = "\033[K"

BOLD_RED = "\033[1;38;5;210m"
NORMAL_RED = "\033[0;38;5;210m"

BOLD_GREEN = "\033[1;38;5;121m"
NORMAL_GREEN = "\033[0;38;5;121m"

BOLD_D_GREEN = "\033[1;38;5;71m"
NORMAL_D_GREEN = "\033[0;38;5;71m"

BOLD_YELLOW = "\033[1;38;5;222m"
NORMAL_YELLOW = "\033[0;38;5;222m"

BOLD_ORANGE = "\033[1;38;2;249;158;54m"
NORMAL_ORANGE = "\033[0;38;2;249;158;54m"

BOLD_BLUE = "\033[1;38;5;117m"
NORMAL_BLUE = "\033[0;38;5;117m"

BOLD_D_BLUE = "\033[1;38;5;67m"
NORMAL_D_BLUE = "\033[0;38;5;67m"

RESET = "\033[0m"

INITIAL_OFFSET = None
LOG_START_DT = None

MIN_WIDTH = 102
MIN_HEIGHT = 20


last_zone_entered = None
initial_log_scan = True

global_stats = {
    "player_name": "Unknown",
    "warframe": "Unknown",
    "matches": 0,
    "deaths": 0,
    "downs": 0,
    "neg_err": 0,
    "high_err": 0,
    "warn": 0,
    "highest_hit_peak": 0.0,
    "highest_hit_peak_time": None,
    "nemesis_killed_session": 0,
    "nemesis_kill_record": None,
}

current_match = {
    "active": False,
    "id": 0,
    "deaths": 0,
    "downs": 0,
    "highest_hit": 0.0,
    "start_time": 0.0,
    "nemesis_spawn_time": None,
    "nemesis_kill_time": None,
    "nemesis_killed_match": 0,
    "nemesis_kill_record_match": None,
    "warframe_recognized": False
}



def startup():
    print_scroll_text(f"""
Warframe Log Observer --- © {BOLD_ORANGE}steak_de{RESET} / contact@ennithing.de / Version: {VERSION}

Please be aware that this script is intended for solo mode.
While it works with other players aswell, it is not fully tested and bugs are expected.
On top of that, the logs vary in detail with more players, with a tendency to display less info.

EE.log gets updated in bulk. If a lot is happening at the same time, it takes a couple seconds
for Warframe to print new log lines into the log. This results in a feeling of slow readings
sometimes.

When reading a previous log session, times are being reconstructed through timestamps within 
the log itself. This results in slightly different times (1-2 seconds offset) in hindsight.

Hint: Warframe only logs exceptionally high damage numbers. Lower Damage Threshold is around 20
Million Damage to a single Enemy. Everything below that threshold goes unnoticed.
Seeing higher ingame numbers than recorded? Might have been a terrain object.
Maybe you annihilated a flower pot with that 200M crit. Poor Thing...


Legend: {BOLD_D_GREEN}Zone Damage Record{RESET} - {BOLD_GREEN}Session Damage Record{RESET} - {BOLD_YELLOW}Downed Recorded{RESET} - {BOLD_RED}Death Recorded{RESET}


Resizing this window might result in line cabbage. It is recommended to keep it at default.
 
 
""")


def parse_start_time(start_time):
    global LOG_START_DT, INITIAL_OFFSET
    explosion = str(start_time).split()
    content = []
    for _ in explosion:
        content.append(str(_).replace("'", '').replace(",",'').replace('[','').replace(']', ''))

    time_offset = content[0]
    INITIAL_OFFSET = time_offset
    weekday = content[2]
    month = content[3]
    day = content[4]
    clock = content[5]
    year = content[6]

    day_uniform = {'1': '01',
                   '2': '02',
                   '3': '03',
                   '4': '04',
                   '5': '05',
                   '6': '06',
                   '7': '07',
                   '8': '08',
                   '9': '09'}

    if day in day_uniform:
        day = day_uniform[day]

    month_translation = {'Jan': '01',
                         'Feb': '02',
                         'Mar': '03',
                         'Apr': '04',
                         'May': '05',
                         'Jun': '06',
                         'Jul': '07',
                         'Aug': '08',
                         'Sep': '09',
                         'Oct': '10',
                         'Nov': '11',
                         'Dec': '12'}

    weekday_translation = {'Mon': 'Monday',
                           'Tue': 'Tuesday',
                           'Wed': 'Wednesday',
                           'Thu': 'Thursday',
                           'Fri': 'Friday',
                           'Sat': 'Saturday',
                           'Sun': 'Sunday'}

    start_time_string = f'{weekday_translation[weekday]}, {day}.{month_translation[month]}.{year} - {clock}'

    uniform_time_str = f'{year}-{month_translation[month]}-{day} {clock}'
    LOG_START_DT = uniform_time_str    


    return start_time_string, time_offset
# Friday, 05.06.2026 - 23:09:45 ◄ start_time_string
# 2026-06-05 23:09:45           ◄ uniform_time_str
# 2026-06-07 11:30:29.289916    ◄ datetime.now()


def debugprint(print_text: str = None):
    if DEBUG:
        caller_frame = inspect.currentframe().f_back
        func_name = caller_frame.f_code.co_name
        line_no = caller_frame.f_lineno
        fehlerquelle = f"[{func_name}:L{line_no}]: "
        print(f"{NORMAL_ORANGE}# {fehlerquelle}{print_text}{RESET}")


def reconstruct_event_time(line: str) -> str:
    global LOG_START_DT, INITIAL_OFFSET
    try:
        relative_seconds = float(line.split(maxsplit=1)[0])
        if INITIAL_OFFSET is not None:
            corrected_seconds = relative_seconds - float(INITIAL_OFFSET)
        else:
            corrected_seconds = relative_seconds
        base_datetime = LOG_START_DT
        if isinstance(base_datetime, str):
            base_datetime = datetime.strptime(base_datetime, "%Y-%m-%d %H:%M:%S")
        event_time = base_datetime + timedelta(seconds=corrected_seconds)
        return event_time.strftime("%H:%M:%S")
    except (ValueError, IndexError):
        if isinstance(LOG_START_DT, str):
            return LOG_START_DT.split()[-1]
        return LOG_START_DT.strftime("%H:%M:%S")


def format_damage_value(val_str):
    try:
        clean = val_str.replace(",", "").strip()
        if "e" in clean.lower():
            return float(clean)
        return float(clean)
    except ValueError:
        return 0.0


def clean_player_name(name):
    debugprint('name: ' + str(name) + ' ► ' + str("".join(c for c in name if c.isalnum() or c in "_- ")))
    return "".join(c for c in name if c.isalnum() or c in "_- ")


def parse_warframe_name(line):
    ignore_keywords = ["Card", "Augment", "Ability", "Abilities", "Skin", "SuitCustomization", "Operator"]
    if any(keyword in line for keyword in ignore_keywords):
        return None
    debugprint('line: ' + str(line))
    parts = line.split("/Lotus/Powersuits/")
    debugprint('parts: ' + str(parts))
    if len(parts) > 1:
        sub_path = parts[1].strip()
        sub_parts = sub_path.split("/")
        raw_name = sub_parts[-1]
        if not raw_name or " " in raw_name:
            return None
        if "ChildOperator" in raw_name:
            return "Operator"
        if "Prime" in raw_name and not raw_name.startswith("Prime"):
            base = raw_name.replace("Prime", "")
            return f"{base} Prime"
        return raw_name
    return "Unknown"


def start_match_if_needed():
    if current_match["active"]:
        return
    debugprint('Neues Match gestartet!')
    global_stats["matches"] += 1

    current_match["id"] = global_stats["matches"]
    current_match["active"] = True
    current_match["deaths"] = 0
    current_match["downs"] = 0
    current_match["highest_hit"] = 0.0
    current_match["start_time"] = time.time()
    current_match["nemesis_killed_match"] = 0
    current_match["nemesis_kill_record_match"] = None
    update_dashboard()

    now_str = datetime.now().strftime("Entered: %H:%M:%S")

    line1_content = f"Zone {current_match['id']}".center(93)
    line2_content = (now_str if not initial_log_scan else '  ----  ' + " (Activity Trigger)").center(93)

    header = f"""
#################################################################################################
# {line1_content} #
# {line2_content} #"""


    print_scroll_text(header)
def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 120


def get_terminal_height():
    try:
        return os.get_terminal_size().lines
    except OSError:
        return 30
last_height = get_terminal_height()


def setup_terminal():
    global last_height
    current_height = get_terminal_height()
    sys.stdout.write("\033[2J")
    sys.stdout.write("\033[H")
    scroll_end = max(1, current_height - 8)
    sys.stdout.write(f"\033[1;{scroll_end}r")
    sys.stdout.write("\033[H")
    sys.stdout.flush()


def _resize_watcher():
    global last_height
    last_width = get_terminal_width()
    while True:
        try:
            size = os.get_terminal_size()
            new_height = size.lines
            new_width = size.columns
        except OSError:
            time.sleep(0.5)
            continue
        too_small = new_width < MIN_WIDTH or new_height < MIN_HEIGHT
        if too_small:
            with _stdout_lock:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(f"  Terminal zu klein!\n")
                sys.stdout.write(f"  Mindestgröße: {MIN_WIDTH}x{MIN_HEIGHT}\n")
                sys.stdout.write(f"  Aktuell: {new_width}x{new_height}\n")
                sys.stdout.flush()
            time.sleep(0.5)
            continue
        if new_height != last_height or new_width != last_width:
            last_height = new_height
            last_width = new_width
            scroll_end = max(1, new_height - 8)
            with _stdout_lock:
                sys.stdout.write(f"\033[1;{scroll_end}r")
                sys.stdout.flush()
            update_dashboard()
        time.sleep(0.5)


def update_dashboard():
    with _stdout_lock:
        height = get_terminal_height()
        start_row = max(1, height - 7)
        p_name = global_stats["player_name"]
        wf = global_stats["warframe"]
        m_rec = str(global_stats["matches"])
        d_rec = str(global_stats["deaths"])
        p_rec = str(global_stats["downs"])
        n_err = str(global_stats["neg_err"])
        h_err = str(global_stats["high_err"])
        h_wrn = str(global_stats["warn"])
        hi_hit = global_stats["highest_hit_peak"]
        hi_hit_str = f"{hi_hit:,.0f}".replace(",", ".") if hi_hit > 0 else "0"
        dmg_record_text = f"Session Damage Peak: {NORMAL_GREEN}{hi_hit_str}{RESET}"
        if global_stats['highest_hit_peak_time'] != None:
            dmg_record_text = dmg_record_text + f" @{global_stats['highest_hit_peak_time']}"
        if not global_stats['nemesis_kill_record'] == None:
            minutes = int(global_stats['nemesis_kill_record'] // 60)
            seconds = int(global_stats['nemesis_kill_record'] % 60)
            milliseconds = int((global_stats['nemesis_kill_record'] % 1) * 100000)
            time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:05d}"
            nemesis_record_text = time_str
        else:
            nemesis_record_text = 'No Session Record'
        sys.stdout.write(f"\033[{start_row};1H" + f"╔═════════════╦═════════════════════╦══════════════════════╦════════════════════════════════════╗{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+1};1H" + f"║ Player Name ║ {NORMAL_ORANGE}{p_name:<20}{RESET}║ Zones Recorded:  {m_rec:<4}║ Negative Damage Errors: {n_err:<11}║{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+2};1H" + f"╠═════════════╬═════════════════════╣ Deaths Recorded: {d_rec:<4}║ Dmg too high Warnings:  {h_err:<11}║{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+3};1H" + f"║ Warframe    ║ {wf:<20}║ Downed Recorded: {p_rec:<4}║ High Dmg Warnings:      {h_wrn:<11}║{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+4};1H" + f"╠═════════════╩═════════════════════╩═══════════╦══════════╩════════════════════════════════════╣{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+5};1H" + f"║ {dmg_record_text[:62]:<62} ║ Fastest Nemesis Kill: {NORMAL_BLUE}{nemesis_record_text:<23}{RESET} ║{CLEAR_LINE}")
        sys.stdout.write(f"\033[{start_row+6};1H" + f"╚═══════════════════════════════════════════════╩═══════════════════════════════════════════════╝{CLEAR_LINE}")
        sys.stdout.flush()


def print_scroll_text(text):
    with _stdout_lock:
        height = get_terminal_height()
        scroll_end = max(1, height - 8)
        lines = text.strip("\n").split("\n")
        for line in lines:
            sys.stdout.write(f"\033[{scroll_end};1H\033[2K{line}\n")
        sys.stdout.flush()


def generate_zone_summary(line: str):
    hi_hit = current_match["highest_hit"]
    hi_hit_str = f"{hi_hit:,.0f}".replace(",", ".") if hi_hit > 0 else '0'
    if initial_log_scan:
        try:
            timestamp = reconstruct_event_time(line)
            current_seconds = float(line.split(maxsplit=1)[0])
            start_seconds = last_zone_entered if last_zone_entered is not None else current_seconds
            elapsed_seconds = int(current_seconds - start_seconds)
        except (ValueError, IndexError) as e:
            timestamp = "00:00:00"
            elapsed_seconds = 0
            debugprint(e)
    else:
        timestamp = datetime.now().strftime("%H:%M:%S")
        current_seconds = float(line.split(maxsplit=1)[0])
        start_seconds = last_zone_entered if last_zone_entered is not None else current_seconds
        elapsed_seconds = int(current_seconds - start_seconds)
    hours = elapsed_seconds // 3600
    minutes = (elapsed_seconds % 3600) // 60
    seconds = elapsed_seconds % 60
    if hours > 0:
        duration_str = f"{hours}h {minutes}m {seconds}s"
    else:
        duration_str = f"{minutes}m {seconds}s"
    title_content = "Zone Summary:".center(93)
    duration_content = f"Zone left @ {timestamp}    Duration: {duration_str}".center(93)
    summary = f"""#                                                                                               #
# {NORMAL_ORANGE}{title_content}{RESET} #
#                                                                                               #
# {duration_content} #
#                                                                                               #
#       {NORMAL_RED}Deaths: {current_match['deaths']:<3}{RESET} {NORMAL_YELLOW}Downed: {current_match['downs']:<3}{RESET} {NORMAL_D_BLUE}Nemesis killed: {current_match['nemesis_killed_match']:<3}{RESET} {NORMAL_D_GREEN}Highest Damage Warning: {hi_hit_str:<19}{RESET} #
#                                                                                               #
#################################################################################################
 
"""
    return summary


def process_line(line):
    global current_match, INITIAL_OFFSET, LOG_START_DT, last_zone_entered
    now_str = datetime.now().strftime("%H:%M:%S")
    line = line.rstrip()
# 0. SPIELSTART AUFZEICHNEN
    if 'Sys [Diag]: Current time: ' in line:
        log_start_time = line.split('Sys [Diag]: Current time: ')
        parse_start_time(log_start_time)
        debugprint('Startzeit gelesen: ' + str(log_start_time) + str(' aus line: ') + str(line))
        

# 1. SPIELERNAME ERKENNEN
    if "Sys [Info]: Logged in " in line:
        parts = line.split("Sys [Info]: Logged in ")
        if len(parts) > 1:
            raw_name_part = parts[1].strip()
            if "(" in raw_name_part:
                raw_name_part = raw_name_part.split("(")[0].strip()
            global_stats["player_name"] = clean_player_name(raw_name_part)
            debugprint('Spielername gelesen: ' + str(clean_player_name(raw_name_part)) + str(' aus line: ') + str(line))
            update_dashboard()
        return

# 2. WARFRAME ERKENNEN
    if "Game [Info]: /Lotus/Powersuits/" in line and current_match['warframe_recognized'] == False:
        detected_frame = parse_warframe_name(line)
        debugprint('Warframe gelesen: ' + str(detected_frame) + str(' aus line: ') + str(line))
        if detected_frame:
            global_stats["warframe"] = detected_frame
            current_match['warframe_recognized'] = True
            update_dashboard()
        return

# 3. NEUES MATCH ODER PASSIVE ZONE (LOBBY) ERKENNEN
    if "Sys [Info]: ===[ Game successfully connected to:" in line:
        lobby_keywords = [
            "/Orbiter/",
            "/Dojo/",
            "/CampMain/",
            "/Hub/",
            "/Town/",
            "/IronWake/",
            "/TNWDrifterCampMain/"
        ]
        is_lobby = any(keyword in line for keyword in lobby_keywords)
        if current_match["active"]:
            summary = generate_zone_summary(line)
            print_scroll_text(summary)
            current_match["active"] = False
        debugprint('Neue Verbindung erkannt. is_lobby=' + str(is_lobby))
        if is_lobby:
            return

# 3.1. WENN KEINE LOBBY: KAMPFZONE STARTEN
        global_stats["matches"] += 1
        current_match["id"] = global_stats["matches"]
        current_match["active"] = True
        current_match['nemesis_killed_match'] = 0
        current_match["deaths"] = 0
        current_match["downs"] = 0
        current_match["highest_hit"] = 0.0
        current_match["start_time"] = time.time()
        current_match["nemesis_spawn_time"] = None
        current_match["nemesis_kill_time"] = None
        current_match['nemesis_kill_record_match'] = None
        update_dashboard()
        now_str = datetime.now().strftime("%H:%M:%S")
        timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
        debugprint('Neue Matchaufzeichnung begonnen. line: ' + str(line))
        debugprint('timestamp: ' + str(timestamp))
        line1_content = f"Zone {current_match['id']}".center(93)
        line2_content = str('Zone entered @ ' + str(timestamp) + ' (in a previous session)').center(93) if initial_log_scan else str('Zone entered @ ' + str(timestamp)).center(93)
        last_zone_entered = float(str(line).split(maxsplit=1)[0])
        header = f"""
#################################################################################################
# {line1_content} #
# {line2_content} #
# {' '.center(93)} #"""
        print_scroll_text(header)
        return


    # 4. SCHADENS-REKORDE & FEHLER-COUNTER
    if "Game [Warning]:  high dmg:" in line:
        start_match_if_needed()
        if not initial_log_scan: global_stats["warn"] += 1
        try:
            parts = line.split("high dmg:")
            if len(parts) > 1:
                after_high_dmg = parts[1]
                dmg_string = after_high_dmg.split(",")[0].strip()
                val = format_damage_value(dmg_string)
                
                now_str = datetime.now().strftime("%H:%M:%S")
                val_str = f"{val:,.0f}".replace(",", ".")
                timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
                output = ""
                if val > current_match["highest_hit"]:
                    debugprint('Matchrekord durch "high dmg:": ' + str(val) + 'ersetzt alten Wert: ' + str(current_match['highest_hit']) + '\n# Line: ' + str(line))
                    current_match["highest_hit"] = val
                    output += f"""{NORMAL_D_GREEN}# ┌──────────────────┬──────────┬─────────────────────────────────────────────────────────────┐ #
# │  {BOLD_D_GREEN}ZONE HIGHSCORE{NORMAL_D_GREEN}  │ {timestamp:<8} │ New Zone Damage Peak: {val_str:<37} │ #
# └──────────────────┴──────────┴─────────────────────────────────────────────────────────────┘ #{RESET}"""
                if val > global_stats["highest_hit_peak"]:
                    debugprint('Sessionrekord durch "high dmg:": ' + str(val) + 'ersetzt alten Wert: ' + str(global_stats['highest_hit_peak']) + '\n# Line: ' + str(line))
                    global_stats["highest_hit_peak"] = val
                    global_stats["highest_hit_peak_time"] = datetime.now().strftime("%H:%M:%S")
                    if output:
                        output += "\n"
                    output += f"""{NORMAL_GREEN}# ┌──────────────────┬──────────┬─────────────────────────────────────────────────────────────┐ #
# │  {BOLD_GREEN}SESSION RECORD{NORMAL_GREEN}  │ {timestamp:<8} │ New Session Damage Peak: {val_str:<34} │ #
# └──────────────────┴──────────┴─────────────────────────────────────────────────────────────┘ #{RESET}"""
                if output:
                    print_scroll_text(output)
        except Exception as e:
            debugprint('Fehler in "high dmg:"-Event: ' + str(e))
        update_dashboard()
        return


    if "Game [Warning]:" in line and "Damage too high:" in line:
        start_match_if_needed()
        if not initial_log_scan: global_stats["high_err"] += 1
        try:
            parts = line.split("Damage too high:")
            if len(parts) > 1:
                val = format_damage_value(parts[1])
                now_str = datetime.now().strftime("%H:%M:%S")
                val_str = f"{val:,.0f}".replace(",", ".")
                timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
                output = ""
                if val > current_match["highest_hit"]:
                    debugprint('Matchrekord durch "Damage too high": ' + str(val) + ' ersetzt alten Wert: ' + str(current_match['highest_hit']) + '\n# Line: ' + str(line))
                    current_match["highest_hit"] = val
                    output += f"""{NORMAL_D_GREEN}# ┌──────────────────┬──────────┬─────────────────────────────────────────────────────────────┐ #
# │  {BOLD_D_GREEN}ZONE HIGHSCORE{NORMAL_D_GREEN}  │ {timestamp:<8} │ New Zone Damage Peak: {val_str:<37} │ #
# └──────────────────┴──────────┴─────────────────────────────────────────────────────────────┘ #{RESET}"""
                if val > global_stats["highest_hit_peak"]:
                    debugprint('Sessionrekord durch "Damage too high": ' + str(val) + ' ersetzt alten Wert: ' + str(global_stats['highest_hit_peak']) + '\n# Line: ' + str(line))
                    global_stats["highest_hit_peak"] = val
                    global_stats["highest_hit_peak_time"] = datetime.now().strftime("%H:%M:%S")
                    if output:
                        output += "\n"
                    output += f"""{NORMAL_GREEN}# ┌──────────────────┬──────────┬─────────────────────────────────────────────────────────────┐ #
# │  {BOLD_GREEN}SESSION RECORD{NORMAL_GREEN}  │ {timestamp:<8} │ New Session Damage Peak: {val_str:<34} │ #
# └──────────────────┴──────────┴─────────────────────────────────────────────────────────────┘ #{RESET}"""
                if output:
                    print_scroll_text(output)
        except Exception as e:
            debugprint('Fehler in "Damage too high:"-Event: ' + str(e))
        update_dashboard()
        return


    # 5. KAMPFUNFÄHIG (DOWNED)
    if "Game [Info]:" in line and "was downed by" in line:
        start_match_if_needed()
        if not initial_log_scan: global_stats["downs"] += 1
        current_match["downs"] += 1
        update_dashboard()
        enemy, level, dmg_inflicted, weapon = "Unknown", "---", "---", "Unknown" 
        debugprint('Downed-Event\n# Line: ' + str(line))
        try:
            content = line.split("Game [Info]:")[1].strip()
            rest = content.split("was downed by")[1].strip()
            dmg_inflicted = rest.split("damage")[0].strip()
            if "from" not in rest and 'using' not in rest:
                enemy = "Suicide - e.g. Martyr Symbiosis"
                level = "---"
                weapon = "Died of Natural Causes"
            if "from" not in rest and "using" in rest:
                enemy = "Suicide"
                level = '----'
                weapon = rest.split("using a")[1].strip()
            else:
                try:
                    rest2 = rest.split("damage from a level")[1].strip() if 'a level' in str(rest) else rest.split('damage from')[1].strip() if not 'damage from a' in str(rest) else rest.split('damage from a')[1].strip()
                except IndexError:
                    rest2 = None
                if not rest2 == None:
                    try:
                        level = rest2.split()[0].strip() if rest2.split()[0].isnumeric() == True else '----'
                    except IndexError:
                        level = None
                enemy_and_weapon = None
                if not rest2 == None:
                    try:
                        enemy_and_weapon = rest2.replace(level if level != 'Unknown' and level != None else 'Unknown', "", 1).strip()
                    except IndexError:
                        enemy_and_weapon = None
                if not enemy_and_weapon == None:
                    try:
                        enemy = enemy_and_weapon.split("using a")[0].strip()
                    except IndexError:
                        enemy = 'Unknown'
                    try:
                        weapon = enemy_and_weapon.split("using a")[1].strip()
                    except IndexError:
                        weapon = 'Unknown'
            subject = content.split()[0].strip()
            subject_part_two = None
            if 'Kavat' in content.split()[1].strip() or 'Kubrow' in content.split()[1].strip() or 'Vulpaphyla' in content.split()[1].strip() or 'Sentinel' in content.split()[1].strip():
                try:
                    subject_part_two = content.split()[1].strip()
                except Exception as e:
                    print('508: ' + str(e))
            
            subject_full = subject + ' ' + subject_part_two if subject_part_two != None else subject
        except ValueError as e:
            debugprint('Error bei downed event\n# Line: ' + str(line) + '\n# ' + str(e))
        timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
        box = f"""{NORMAL_YELLOW}# ┌────────┬───────────────────┬─────────── {BOLD_YELLOW}{timestamp}{NORMAL_YELLOW} ────────────────────────┬────────────────┐ #
# │ {BOLD_YELLOW}DOWNED {NORMAL_YELLOW}│{BOLD_YELLOW} {subject_full[:17].center(16):<17}{NORMAL_YELLOW} │ Enemy: {enemy[:36]:<36} │ Level: {level[:7]:<7} │ #
# ├────────┴───────────────────┴──────────────┬──────────────────────────────┴────────────────┤ #
# │ Damage Inflicted: {dmg_inflicted[:23]:<23} │ Damage Source: {weapon[:30]:<30} │ #
# └───────────────────────────────────────────┴───────────────────────────────────────────────┘ #{RESET}"""
        print_scroll_text(box)
        return

    #6. TOT (KILLED)
    if "Game [Info]:" in line and "was killed by" in line:
        debugprint('Killed-Event\n# Line: ' + str(line))
        start_match_if_needed()
        if not initial_log_scan: global_stats["deaths"] += 1
        current_match["deaths"] += 1
        update_dashboard()
        try:
            content = line.split("Game [Info]:")[1].strip()
            subject = content.split()[0].strip()
            
            subject_part_two = None
            if 'Kavat' in content.split()[1].strip() or 'Kubrow' in content.split()[1].strip() or 'Vulpaphyla' in content.split()[1].strip() or 'Sentinel' in content.split()[1].strip():
                try:
                    subject_part_two = content.split()[1].strip()
                except Exception as e:
                    debugprint('# Error bei downed event\n# Line: ' + str(line) + '\n# ' + str(e))
            subject_full = subject + ' ' + subject_part_two if subject_part_two != None else subject
            rest = content.split("was killed by")[1].strip()
            dmg_inflicted = rest.split("damage from a level")[0].strip() if 'a level' in str(rest) else rest.split('damage from')[0].strip() 
            rest2 = rest.split("damage from a level")[1].strip() if 'a level' in str(rest) else rest.split('damage from')[1].strip() if not 'damage from a' in str(rest) else rest.split('damage from a')[1].strip()
            level = rest2.split()[0].strip() if rest2.split()[0].isnumeric() == True else '----'
            enemy_and_weapon = None
            if not rest2 == None:
                try:
                    enemy_and_weapon = rest2.replace(level if level != '----' and level != None else '----', "", 1).strip()
                except IndexError:
                    enemy_and_weapon = None
            if not enemy_and_weapon == None:
                try:
                    enemy = enemy_and_weapon.split("using a")[0].strip()
                except IndexError:
                    enemy = 'Unknown'
                try:
                    weapon = enemy_and_weapon.split("using a")[1].strip()
                except IndexError:
                    weapon = 'Unknown'
        except Exception as e:
            debugprint('# Error bei killed event\n# Line: ' + str(line) + '\n# ' + str(e))
            enemy, level, dmg_inflicted, weapon, subject_full = "Unknown", "----", "----", "Unknown", "Unknown"
        timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
        box = f"""{NORMAL_RED}# ┌────────┬───────────────────┬─────────── {BOLD_RED}{timestamp}{NORMAL_RED} ────────────────────────┬────────────────┐ #
# │{BOLD_RED} KILLED {NORMAL_RED}│{BOLD_RED} {subject_full[:17].center(16):<17} {NORMAL_RED}│ Enemy: {enemy[:36]:<36} │ Level: {level[:7]:<7} │ #
# ├────────┴───────────────────┴──────────────┬──────────────────────────────┴────────────────┤ #
# │ Damage Inflicted: {dmg_inflicted[:23]:<23} │ Damage Source: {weapon[:30]:<30} │ #
# └───────────────────────────────────────────┴───────────────────────────────────────────────┘ #{RESET}"""
        print_scroll_text(box)
        return

    # 7. NEMESIS EVENTS
    if "persistent enemy" in line and "spawned" in line:
        debugprint('# Nemesis gespawnt.\n# line: ' + str(line))
        start_match_if_needed()
        current_match["nemesis_spawn_time"] = float(line.split(maxsplit=1)[0])
        return

    if "persistent enemy" in line and "was killed" in line:
        debugprint('# Nemesis gestorben.\n# line: ' + str(line))
        start_match_if_needed()
        current_match["nemesis_kill_time"] = float(line.split(maxsplit=1)[0])
        if not initial_log_scan: global_stats["nemesis_killed_session"] += 1
        current_match["nemesis_killed_match"] += 1
        now_str = datetime.now().strftime("%H:%M:%S")
        timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
        kill_time = None
        if current_match["nemesis_spawn_time"] is not None and current_match["nemesis_kill_time"] is not None:
            kill_time = current_match['nemesis_kill_time'] - current_match["nemesis_spawn_time"]
        else:
            kill_time = 0.0
        minutes = int(kill_time // 60)
        seconds = int(kill_time % 60)
        milliseconds = int((kill_time % 1) * 1000)
        time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        match_record = current_match["nemesis_kill_record_match"]
        session_record = global_stats["nemesis_kill_record"]
        match_record_cmp = match_record if match_record is not None else float('inf')
        session_record_cmp = session_record if session_record is not None else float('inf')
        new_match_best = kill_time < match_record_cmp
        new_session_best = kill_time < session_record_cmp
        if match_record is None or kill_time < match_record:
            current_match["nemesis_kill_record_match"] = kill_time
        if session_record is None or kill_time < session_record:
            global_stats["nemesis_kill_record"] = kill_time
        cval = current_match['nemesis_kill_record_match']
        current_match_record = f"{int(cval // 60):02d}:{int(cval % 60):02d}.{int((cval % 1) * 1000):03d}" if cval != None else 'No Record'[:9]
        sval = global_stats['nemesis_kill_record']
        session_record_str = f"{int(sval // 60):02d}:{int(sval % 60):02d}.{int((sval % 1) * 1000):03d}" if sval != None else 'No Record'[:9]
        if new_match_best and new_session_best:
            kill_message = f"""# ┌──────────────────┬──────────┬─────────────────────────┬─ {BOLD_D_BLUE}RECORD!{RESET} ─┬─ {BOLD_BLUE}RECORD!{RESET} ─┬───────────┐ #
# │   NEMESIS KILL   │ {timestamp[:8]:<8} │ Killed in: {time_str[:12]:<12} │ {NORMAL_D_BLUE}{current_match_record[:9]:<9}{RESET} │ {NORMAL_BLUE}{session_record_str[:9]:<9}{RESET} │ {str(current_match['nemesis_killed_match'])[:3]:<3} {'Kills' if  int(current_match['nemesis_killed_match']) != 1 else 'Kill '} │ #
# └──────────────────┴──────────┴─────────────────────────┴───────────┴───────────┴───────────┘ #"""
        elif new_match_best:
            kill_message = f"""# ┌──────────────────┬──────────┬─────────────────────────┬─ {BOLD_D_BLUE}RECORD!{RESET} ─┬───────────┬───────────┐ #
# │   NEMESIS KILL   │ {timestamp[:8]:<8} │ Killed in: {time_str[:12]:<12} │ {NORMAL_D_BLUE}{current_match_record[:9]:<9}{RESET} │ {NORMAL_BLUE}{session_record_str[:9]:<9}{RESET} │ {str(current_match['nemesis_killed_match'])[:3]:<3} {'Kills' if  int(current_match['nemesis_killed_match']) != 1 else 'Kill '} │ #
# └──────────────────┴──────────┴─────────────────────────┴───────────┴───────────┴───────────┘ #"""
        elif new_session_best:
            kill_message = f"""# ┌──────────────────┬──────────┬─────────────────────────┬───────────┬─ {BOLD_BLUE}RECORD!{RESET} ─┬───────────┐ #
# │   NEMESIS KILL   │ {timestamp[:8]:<8} │ Killed in: {time_str[:12]:<12} │ {NORMAL_D_BLUE}{current_match_record[:9]:<9}{RESET} │ {NORMAL_BLUE}{session_record_str[:9]:<9}{RESET} │ {str(current_match['nemesis_killed_match'])[:3]:<3} {'Kills' if  int(current_match['nemesis_killed_match']) != 1 else 'Kill '} │ #
# └──────────────────┴──────────┴─────────────────────────┴───────────┴───────────┴───────────┘ #"""
        else:
            kill_message = f"""# ┌──────────────────┬──────────┬─────────────────────────┬───────────┬───────────┬───────────┐ #
# │   NEMESIS KILL   │ {timestamp[:8]:<8} │ Killed in: {time_str[:12]:<12} │ {NORMAL_D_BLUE}{current_match_record[:9]:<9}{RESET} │ {NORMAL_BLUE}{session_record_str[:9]:<9}{RESET} │ {str(current_match['nemesis_killed_match'])[:3]:<3} {'Kills' if  int(current_match['nemesis_killed_match']) != 1 else 'Kill '} │ #
# └──────────────────┴──────────┴─────────────────────────┴───────────┴───────────┴───────────┘ #"""

        print_scroll_text(kill_message)
        current_match["nemesis_spawn_time"] = None
        update_dashboard()
        return


    # 99. MATCH-ENDE (Zusätzliche Absicherung über alternative Logzeilen)
    if "CommitInventoryChangesToDB" in line or "SetSquadMissionResult" in line:
        if current_match["active"]:
            summary = generate_zone_summary(line)
            print_scroll_text(summary)
            current_match["active"] = False
        return


def watch_log():
    global initial_log_scan
    while True:
        while not os.path.exists(LOG_FILE_PATH):
            time.sleep(1)
        try:
            f = open(LOG_FILE_PATH, "rb")
        except OSError:
            time.sleep(1)
            continue

        now_str = datetime.now().strftime("%H:%M:%S")
        with f:
            print_scroll_text(
                f"{NORMAL_GREEN}# [SYSTEM {now_str}] Observing EE.log...{RESET}" if not initial_log_scan else f"{NORMAL_GREEN}# [SYSTEM {now_str}] Reading existing log lines if there are any...{RESET}"
            )
            update_dashboard()
            while True:
                current_position = f.tell()
                line_bytes = f.readline()
                if line_bytes:
                    line = line_bytes.decode(
                        "utf-8",
                        errors="ignore"
                    )
                    process_line(line)
                    continue
                if initial_log_scan:
                    initial_log_scan = False
                    print_scroll_text(f"{NORMAL_GREEN}# [SYSTEM {now_str}] Finished reading log, observing log for new lines...{RESET}")
                    global_stats['matches'] = 0
                    global_stats['nemesis_kill_record'] = None
                    global_stats["highest_hit_peak"] = 0
                    global_stats["highest_hit_peak_time"] = None
                    update_dashboard()
                try:
                    actual_size = os.path.getsize(
                        LOG_FILE_PATH
                    )
                except OSError:
                    break
                if actual_size < current_position:
                    print_scroll_text(
                        f"\n{BOLD_YELLOW}# [SYSTEM {now_str}] Log rotation detected. Continuing Observation on updated Log File...{RESET}"
                    )
                    update_dashboard()
                    break
                time.sleep(0.1)


def cleanup_terminal():
    sys.stdout.write("\033[r")
    sys.stdout.flush()


if __name__ == "__main__":
    setup_terminal()
    update_dashboard()
    startup()
    watcher = threading.Thread(target=_resize_watcher, daemon=True)
    watcher.start()
    try:
        watch_log()
    except Exception as e:
        import traceback
        cleanup_terminal()
        print("\nUNHANDLED EXCEPTION\n")
        traceback.print_exc()
        input("\nPress ENTER to exit...")
    except KeyboardInterrupt:
        pass

    finally:
        cleanup_terminal()