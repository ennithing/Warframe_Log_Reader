import os
import sys
import time
import ctypes
import inspect
import threading
import re
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime, timedelta

VERSION = '1.2 - 19.06.2026'
ctypes.windll.kernel32.SetConsoleTitleW("   Warframe Combat Log " + str(VERSION))

DEBUG = False

APPDATA = os.getenv("LOCALAPPDATA")
LOG_FILE_PATH = os.path.join(APPDATA, "Warframe", "EE.log") if APPDATA else "EE.log"

CLEAR_LINE = "\033[K"

BOLD_RED     = "\033[1;38;5;210m"
NORMAL_RED   = "\033[0;38;5;210m"

BOLD_GREEN   = "\033[1;38;5;121m"
NORMAL_GREEN = "\033[0;38;5;121m"

BOLD_D_GREEN   = "\033[1;38;5;71m"
NORMAL_D_GREEN = "\033[0;38;5;71m"

BOLD_YELLOW   = "\033[1;38;5;222m"
NORMAL_YELLOW = "\033[0;38;5;222m"

BOLD_ORANGE   = "\033[1;38;2;249;158;54m"
NORMAL_ORANGE = "\033[0;38;2;249;158;54m"

BOLD_BLUE   = "\033[1;38;5;117m"
NORMAL_BLUE = "\033[0;38;5;117m"

BOLD_D_BLUE   = "\033[1;38;5;67m"
NORMAL_D_BLUE = "\033[0;38;5;67m"

RESET = "\033[0m"

_ANSI_256 = {
    67:  "#5f87af",
    71:  "#5faf5f",
    117: "#87d7ff",
    121: "#87ffaf",
    210: "#ff8787",
    222: "#ffd787",
}

_ANSI_RGB_COLORS = {
    "249;158;54": "#f99e36",
}

def _ansi_to_hex(ansi_code: str):
    """Gibt den Hex-Farbwert für einen ANSI-Escape zurück, oder None."""
    m256 = re.search(r'38;5;(\d+)', ansi_code)
    if m256:
        idx = int(m256.group(1))
        return _ANSI_256.get(idx)
    mrgb = re.search(r'38;2;(\d+;\d+;\d+)', ansi_code)
    if mrgb:
        return _ANSI_RGB_COLORS.get(mrgb.group(1))
    return None

_COLOR_TAGS = {}

INITIAL_OFFSET = None
LOG_START_DT = None

MIN_WIDTH = 102
MIN_HEIGHT = 20

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short),
                ("Y", ctypes.c_short)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left",   ctypes.c_short),
                ("Top",    ctypes.c_short),
                ("Right",  ctypes.c_short),
                ("Bottom", ctypes.c_short)]

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
    "mission_name": None,
    "nemesis_spawn_time": None,
    "nemesis_kill_time": None,
    "nemesis_killed_match": 0,
    "nemesis_kill_record_match": None,
    "warframe_recognized": False,
    "pending_start": False,
    "pending_line": None,
    "mission_success": None,
}

root        = None
log_widget  = None
dash_labels = {}

_drag_x = 0
_drag_y = 0

MIN_WIDTH_PX  = 900
MIN_HEIGHT_PX = 560

PALETTE = {
    "bg":           "#0e0e0e",
    "bg_title":     "#1a1a1a",
    "bg_dash":      "#111111",
    "fg":           "#d0d0d0",
    "fg_dim":       "#555555",
    "accent":       "#2a2a2a",
    "title_text":   "#cccccc",
    "btn_close":    "#c0392b",
    "btn_min":      "#888888",
    "font_ui":      ("Segoe UI", 9),
    "font_mono":    ("Cascadia Mono", 10),
    "font_mono_fb": ("Consolas", 10),
}

ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    ",.-;:_#'+*´`?ß!\"§$%&/()=<>^°"
)


def get_mono_font() -> tuple:
    available = tkfont.families()
    name = PALETTE["font_mono"][0] if PALETTE["font_mono"][0] in available else PALETTE["font_mono_fb"][0]
    return (name, PALETTE["font_mono"][1])

def uniform_player_name(name: str) -> str:
    if not name:
        return name
    if name[-1] not in ALLOWED_CHARS:
        return name[:-1]
    return name


def register_color_tags(widget) -> None:
    global _COLOR_TAGS
    all_codes = [
        BOLD_RED, NORMAL_RED, BOLD_GREEN, NORMAL_GREEN,
        BOLD_D_GREEN, NORMAL_D_GREEN, BOLD_YELLOW, NORMAL_YELLOW,
        BOLD_ORANGE, NORMAL_ORANGE, BOLD_BLUE, NORMAL_BLUE,
        BOLD_D_BLUE, NORMAL_D_BLUE,
    ]
    mono = get_mono_font()
    for code in all_codes:
        hex_color = _ansi_to_hex(code)
        if not hex_color:
            continue
        is_bold = code.startswith("\033[1;")
        tag = f"ansi_{id(code)}"
        widget.tag_configure(tag,
                             foreground=hex_color,
                             font=(mono[0], mono[1], "bold" if is_bold else "normal"))
        _COLOR_TAGS[code] = tag


def insert_ansi(widget, text: str) -> None:
    pattern = re.compile(r'(\033\[[^m]*m)')
    parts = pattern.split(text)
    current_tag = None
    for part in parts:
        if not part:
            continue
        if pattern.match(part):
            if part == RESET or part == "\033[0m":
                current_tag = None
            else:
                new_tag = _COLOR_TAGS.get(part)
                if new_tag is not None:
                    current_tag = new_tag
        else:
            if current_tag:
                widget.insert(tk.END, part, current_tag)
            else:
                widget.insert(tk.END, part)


def force_taskbar_visibility(win) -> None:
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        GWL_EXSTYLE      = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW  = 0x00040000

        get_style = ctypes.windll.user32.GetWindowLongW
        set_style = ctypes.windll.user32.SetWindowLongW

        style = get_style(hwnd, GWL_EXSTYLE)
        style = style & ~WS_EX_TOOLWINDOW
        style = style | WS_EX_APPWINDOW
        set_style(hwnd, GWL_EXSTYLE, style)
        win.withdraw()
        win.after(10, win.deiconify)
    except Exception:
        pass


def build_ui() -> None:
    global root, log_widget, dash_labels

    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg=PALETTE["bg"])
    root.minsize(MIN_WIDTH_PX, MIN_HEIGHT_PX)
    root.wm_title("Warframe Combat Log " + str(VERSION))
    _logo_path = None
    try:
        if getattr(sys, 'frozen', False):
            _base = sys._MEIPASS
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        _candidate = os.path.join(_base, "logo.png")
        if os.path.exists(_candidate):
            _logo_path = _candidate
    except Exception:
        _logo_path = None

    _taskbar_icon_img = None
    _title_icon_img   = None
    if _logo_path:
        try:
            _full_img = tk.PhotoImage(file=_logo_path)
            _taskbar_icon_img = _full_img.subsample(6, 6)
            _title_icon_img   = _full_img.subsample(11, 11)
            root.wm_iconphoto(True, _taskbar_icon_img)
        except Exception:
            _taskbar_icon_img = None
            _title_icon_img   = None

    root.update_idletasks()
    force_taskbar_visibility(root)

    def _on_close():
        root.destroy()

    def _on_minimize():
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        ctypes.windll.user32.ShowWindow(hwnd, 6)

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = 870, 680
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    title_bar = tk.Frame(root, bg=PALETTE["bg_title"], height=32)
    title_bar.pack(fill=tk.X, side=tk.TOP)
    title_bar.pack_propagate(False)

    if _title_icon_img:
        icon_label = tk.Label(title_bar, image=_title_icon_img, bg=PALETTE["bg_title"])
        icon_label.image = _title_icon_img
        icon_label.pack(side=tk.LEFT, padx=(8, 0))

    tk.Label(title_bar, text="  Warframe Combat Log " + str(VERSION),
             bg=PALETTE["bg_title"], fg=PALETTE["title_text"],
             font=PALETTE["font_ui"], anchor="w"
             ).pack(side=tk.LEFT, padx=(4, 0))

    tk.Button(title_bar, text="✕", command=_on_close,
              bg=PALETTE["bg_title"], fg=PALETTE["btn_close"],
              activebackground=PALETTE["btn_close"], activeforeground="#fff",
              relief=tk.FLAT, bd=0, padx=10, pady=4,
              font=PALETTE["font_ui"], cursor="hand2"
              ).pack(side=tk.RIGHT)

    tk.Button(title_bar, text="─", command=_on_minimize,
              bg=PALETTE["bg_title"], fg=PALETTE["btn_min"],
              activebackground=PALETTE["accent"], activeforeground="#fff",
              relief=tk.FLAT, bd=0, padx=10, pady=4,
              font=PALETTE["font_ui"], cursor="hand2"
              ).pack(side=tk.RIGHT)

    def _start_drag(e):
        global _drag_x, _drag_y
        _drag_x, _drag_y = e.x, e.y

    def _do_drag(e):
        root.geometry(f"+{root.winfo_x()+e.x-_drag_x}+{root.winfo_y()+e.y-_drag_y}")

    title_bar.bind("<ButtonPress-1>", _start_drag)
    title_bar.bind("<B1-Motion>",     _do_drag)

    resize_bar = tk.Frame(root, bg=PALETTE["bg_title"], height=6, cursor="sb_v_double_arrow")
    resize_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _start_resize(e):
        resize_bar._start_y = e.y_root
        resize_bar._start_h = root.winfo_height()

    def _do_resize(e):
        delta = e.y_root - resize_bar._start_y
        nh = max(MIN_HEIGHT_PX, resize_bar._start_h + delta)
        root.geometry(f"{root.winfo_width()}x{nh}")

    resize_bar.bind("<ButtonPress-1>", _start_resize)
    resize_bar.bind("<B1-Motion>",     _do_resize)

    mono = get_mono_font()

    log_frame = tk.Frame(root, bg=PALETTE["bg"])
    log_frame.pack(fill=tk.BOTH, expand=True)

    log_scroll = tk.Scrollbar(log_frame, bg=PALETTE["accent"],
                               troughcolor=PALETTE["bg"],
                               relief=tk.FLAT, bd=0, width=8)
    log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    log_widget = tk.Text(log_frame,
                         bg=PALETTE["bg"], fg=PALETTE["fg"],
                         insertbackground=PALETTE["fg"],
                         font=mono,
                         relief=tk.FLAT, bd=0,
                         padx=8, pady=6,
                         wrap=tk.NONE,
                         state=tk.DISABLED,
                         yscrollcommand=log_scroll.set)
    log_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    log_scroll.config(command=log_widget.yview)

    register_color_tags(log_widget)

    def _center_text(event=None):
        try:
            f = tkfont.Font(font=log_widget.cget("font"))
            sample_line = "─" * 102
            text_px    = f.measure(sample_line)
            char_width = f.measure("─")
            available  = log_widget.winfo_width()
            pad        = max(0, (available - text_px) // 2) + (char_width * 2)
            log_widget.configure(padx=pad)
        except Exception:
            pass

    log_widget.bind("<Configure>", _center_text)
    root.after(100, _center_text)

    tk.Frame(root, bg=PALETTE["accent"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

    dash = tk.Frame(root, bg=PALETTE["bg_dash"], pady=6, padx=10)
    dash.pack(fill=tk.X, side=tk.BOTTOM)

    dash.columnconfigure(0, minsize=140)   # Player
    dash.columnconfigure(1, minsize=180)   # Warframe
    dash.columnconfigure(2, minsize=60)    # Zones
    dash.columnconfigure(3, minsize=60)    # Deaths
    dash.columnconfigure(4, minsize=60)    # Downed
    dash.columnconfigure(5, minsize=80)    # Warnings
    dash.columnconfigure(6, minsize=80)    # Neg.Err
    dash.columnconfigure(7, minsize=80)    # 

    def _lbl(parent, text="", col=0, row=0, fg=None, bold=False, columnspan=1):
        f = (mono[0], mono[1], "bold") if bold else (mono[0], mono[1])
        lbl = tk.Label(parent, text=text,
                       bg=PALETTE["bg_dash"], fg=fg or PALETTE["fg"],
                       font=f, anchor="w")
        lbl.grid(row=row, column=col, sticky="w",
                 padx=(0, 4), pady=1, columnspan=columnspan)
        return lbl

    for col, name in enumerate(["Player", "Warframe", "Zones", "Deaths",
                                  "Downed", "DMG WARNINGS    ", "NEG. ERRORS",]):
        _lbl(dash, name, col=col, row=0, fg=PALETTE["fg_dim"])

    dash_labels["player"]   = _lbl(dash, "Unknown", col=0, row=1, fg=_ANSI_RGB_COLORS["249;158;54"], bold=True)
    dash_labels["warframe"] = _lbl(dash, "Unknown", col=1, row=1)
    dash_labels["matches"]  = _lbl(dash, "0",       col=2, row=1)
    dash_labels["deaths"]   = _lbl(dash, "0",       col=3, row=1)
    dash_labels["downs"]    = _lbl(dash, "0",       col=4, row=1)
    dash_labels["warn"]  = _lbl(dash, "0",       col=5, row=1)
    dash_labels["neg_err"] = _lbl(dash, "0",       col=6, row=1)

    tk.Frame(dash, bg=PALETTE["accent"], height=1
             ).grid(row=2, column=0, columnspan=8, sticky="ew", pady=(6, 4))

    _lbl(dash, "Session Damage Peak", col=0, row=3, fg=PALETTE["fg_dim"])
    dash_labels["dmg_peak"]    = _lbl(dash, "0",                col=1, row=3,
                                      fg=_ANSI_256[121], columnspan=3)
    _lbl(dash, "Fastest Nemesis Kill", col=4, row=3, fg=PALETTE["fg_dim"])
    dash_labels["nemesis_rec"] = _lbl(dash, "No Session Record", col=5, row=3,
                                      fg=_ANSI_256[117], columnspan=3)


def startup() -> None:
    print_scroll_text(f"""
Warframe Combat Log --- © {BOLD_ORANGE}steak_de{RESET} / contact@ennithing.de / Version: {VERSION}

Please be aware that this program is intended for and tested in solo mode.
While it works with other players aswell, it is not fully tested and bugs are expected.
On top of that, the logs vary in detail with more players, with a tendency to display less info.

EE.log gets updated in bulk. If a lot is happening at the same time, it takes a couple seconds
for Warframe to print new log lines into the log. This results in a feeling of slow readings
sometimes. Occasionally, if you kill a nemesis very quickly, the Log puts spawn and kill in the
same bulk which gets displayed as 0:00:000s kill time. Invalidating an instant kill was not
my intention so i went with it and 0:00:000 is considered an instant kill.

Hint: Warframe only logs exceptionally high damage numbers. Lower Damage Threshold is around 20
Million Damage to a single Enemy. Everything below that threshold goes unnoticed per se.
Not every damage event gets logged at all times. A lot do, but not each and every single one.



Legend: {BOLD_D_GREEN}Zone Damage Record{RESET} - {BOLD_GREEN}Session Damage Record{RESET} - {BOLD_YELLOW}Downed Recorded{RESET} - {BOLD_RED}Death Recorded{RESET}
 
""")


def parse_start_time(start_time: str) -> str:
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


def format_damage_value(val_str: str) -> float:
    try:
        clean = val_str.replace(",", "").strip()
        if "e" in clean.lower():
            return float(clean)
        return float(clean)
    except ValueError:
        return 0.0


def clean_player_name(name: str) -> str:
    debugprint('name: ' + str(name) + ' ► ' + str("".join(c for c in name if c.isalnum() or c in "_- ")))
    return "".join(c for c in name if c.isalnum() or c in "_- ")


def parse_warframe_name(line) -> str:
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


def start_match(line=None, mission_name=None) -> None:
    if current_match["active"]:
        return
    debugprint('Neues Match gestartet!')
    global last_zone_entered
    if current_match["active"]:
        return
    current_match["pending_start"] = False
    current_match["pending_line"] = None

    global_stats["matches"] += 1
    current_match["id"] = global_stats["matches"]
    current_match["active"] = True
    current_match["deaths"] = 0
    current_match["downs"] = 0
    current_match["highest_hit"] = 0.0
    current_match["start_time"] = time.time()
    current_match["nemesis_killed_match"] = 0
    current_match["nemesis_kill_record_match"] = None
    current_match["nemesis_spawn_time"] = None
    current_match["nemesis_kill_time"] = None

    if line is not None:
        timestamp = reconstruct_event_time(line) if initial_log_scan else datetime.now().strftime("%H:%M:%S")
        last_zone_entered = float(str(line).split(maxsplit=1)[0])
    else:
        timestamp = datetime.now().strftime("%H:%M:%S")

    update_dashboard()

    line1_content = f"Zone {current_match['id']}".center(93)
    if line is None:
        line2_content = (f"Entered: {timestamp}" if not initial_log_scan else "  ----   (Activity Trigger)").center(93)
        header = f"""
#################################################################################################
# {line1_content} #
# {line2_content} #"""
    else:
        line2_content = str('Zone entered @ ' + timestamp + (' (in a previous session)' if initial_log_scan else '')).center(93)
        mission_line = (f"Mission: {mission_name}" if mission_name else ' ').center(93)
        header = f"""
#################################################################################################
# {line1_content} #
# {line2_content} #
# {mission_line} #
# {" ".center(93)} #"""

    print_scroll_text(header)


def get_terminal_width() -> None:
    return 120


def get_terminal_height() -> None:
    return 40


def update_dashboard() -> None:
    if initial_log_scan:
        return
    def _update():
        hi_hit = global_stats["highest_hit_peak"]
        hi_hit_str = f"{hi_hit:,.0f}".replace(",", ".") if hi_hit > 0 else "0"
        if global_stats["highest_hit_peak_time"]:
            hi_hit_str += f"  @{global_stats['highest_hit_peak_time']}"
        if global_stats["nemesis_kill_record"] is not None:
            v = global_stats["nemesis_kill_record"]
            nem_str = f"{int(v//60):02d}:{int(v%60):02d}.{int((v%1)*100000):05d}"
        else:
            nem_str = "No Session Record"
        dash_labels["player"].config(text=global_stats["player_name"])
        dash_labels["warframe"].config(text=global_stats["warframe"])
        dash_labels["matches"].config(text=str(global_stats["matches"]))
        dash_labels["deaths"].config(text=str(global_stats["deaths"]))
        dash_labels["downs"].config(text=str(global_stats["downs"]))
        dash_labels["neg_err"].config(text=str(global_stats["neg_err"]))
        #dash_labels["high_err"].config(text=str(global_stats["high_err"]))
        dash_labels["warn"].config(text=str(global_stats["warn"]))
        dash_labels["dmg_peak"].config(text=hi_hit_str)
        dash_labels["nemesis_rec"].config(text=nem_str)
    if root:
        root.after(0, _update)


def print_scroll_text(text) -> None:
    def _insert():
        log_widget.configure(state=tk.NORMAL)
        insert_ansi(log_widget, text.strip("\n") + "\n")
        log_widget.configure(state=tk.DISABLED)
        log_widget.see(tk.END)
    if root:
        root.after(0, _insert)




def generate_zone_summary(line: str) -> str:
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


def process_line(line) -> None:
    global current_match, INITIAL_OFFSET, LOG_START_DT, last_zone_entered
    now_str = datetime.now().strftime("%H:%M:%S")
    debugprint(now_str + ' Line gelesen: ' + str(line))
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

# 2.1 MISSIONSN ERKENNEN
    if "Script [Info]: MissionIntro.lua: MissionName:" in line:
        current_match["mission_name"] = line.split("MissionName:")[-1].strip()
        if current_match.get("pending_start"):
            current_match["pending_start"] = False
            start_match(line=current_match["pending_line"], mission_name=current_match["mission_name"])
            current_match["pending_line"] = None
        return

# 3. NEUES MATCH ODER PASSIVE ZONE (LOBBY) ERKENNEN
    if "Sys [Info]: ===[ Game successfully connected to:" in line:
        lobby_keywords = [
            "/Orbiter/", "/Dojo/", "/CampMain/", "/Hub/",
            "/Town/", "/IronWake/", "/TNWDrifterCampMain/"
        ]
        is_lobby = any(keyword in line for keyword in lobby_keywords)
        if current_match["active"]:
            summary = generate_zone_summary(line)
            print_scroll_text(summary)
            current_match["active"] = False
        debugprint('Neue Verbindung erkannt. is_lobby=' + str(is_lobby))
        if is_lobby:
            current_match["pending_start"] = False
            current_match["pending_line"] = None
            return
        current_match["pending_start"] = True
        current_match["pending_line"] = line
        current_match["mission_name"] = None
        return


    # 4. SCHADENS-REKORDE & FEHLER-COUNTER
    if " high dmg:" in line:
        start_match()
        if not initial_log_scan: global_stats["warn"] += 1
        try:
            parts = line.split("high dmg:")
            if len(parts) > 1:
                after_high_dmg = parts[1]
                after_high_dmg = after_high_dmg.split("Vict")[0]
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

#[DAMAGE TOO HIGH leider obsolet seit Update 43]

    if "Sys [Error]: GOT NEGATIVE AMOUNT DAMAGE IN PROCESS TEXT:" in line:
        if not initial_log_scan: global_stats['neg_err'] += 1
        debugprint('Negative Error: ' + line)

    # 5. KAMPFUNFÄHIG (DOWNED)
    if "Game [Info]:" in line and "was downed by" in line:
        start_match()
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
        start_match()
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
            subject_full = uniform_player_name(subject_full)
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
        enemy = uniform_player_name(enemy)
        timestamp = reconstruct_event_time(line) if initial_log_scan else now_str
        box = f"""{NORMAL_RED}# ┌────────┬───────────────────┬─────────── {BOLD_RED}{timestamp}{NORMAL_RED} ────────────────────────┬────────────────┐ #
# │{BOLD_RED} KILLED {NORMAL_RED}│{BOLD_RED} {subject_full[:17].center(17):<17} {NORMAL_RED}│ Enemy: {enemy[:36]:<36} │ Level: {level[:7]:<7} │ #
# ├────────┴───────────────────┴──────────────┬──────────────────────────────┴────────────────┤ #
# │ Damage Inflicted: {dmg_inflicted[:23]:<23} │ Damage Source: {weapon[:30]:<30} │ #
# └───────────────────────────────────────────┴───────────────────────────────────────────────┘ #{RESET}"""
        print_scroll_text(box)
        return


    # 7. NEMESIS EVENTS
    if "persistent enemy" in line and "spawned" in line:
        debugprint('# Nemesis gespawnt.\n# line: ' + str(line))
        start_match()
        current_match["nemesis_spawn_time"] = float(line.split(maxsplit=1)[0])
        return

    if "persistent enemy" in line and "was killed" in line:
        debugprint('# Nemesis gestorben.\n# line: ' + str(line))
        start_match()
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
    if "Script [Info]: EndOfMatch.lua: EndOfMatch.lua - Close" in line:
        if current_match["active"]:
            summary = generate_zone_summary(line)
            print_scroll_text(summary)
            current_match["active"] = False
        return


def _report_crash(context: str = "") -> None:
    import traceback
    tb_text = traceback.format_exc()

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_lines = [
        f"Warframe Combat Log — Crash Report",
        f"Version: {VERSION}",
        f"Zeitpunkt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Kontext: {context}",
        f"",
        f"Letzte verarbeitete Match-Stats:",
        f"  current_match: {current_match}",
        f"  global_stats:  {global_stats}",
        f"",
        f"Traceback:",
        tb_text,
    ]
    report_text = "\n".join(str(l) for l in report_lines)

    try:
        report_dir = os.path.join(os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, 'frozen', False) else __file__
        )), "crash_reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"crash_{now}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
    except Exception:
        report_path = None

    short_msg = f"\n{BOLD_RED}# [SYSTEM] An Error has occured. The Program has crashed.\nTrying to resume operation in 3 Seconds.{RESET}"
    if report_path:
        short_msg += f"\n{NORMAL_RED}# Crash-Report has been saved to: {report_path}{RESET}"
    short_msg += f"\n{NORMAL_RED}# Context: {context[:150]}{RESET}\n"
    print_scroll_text(short_msg)


def watch_log() -> None:
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
                    try:
                        process_line(line)
                    except Exception:
                        _report_crash(context=f"process_line() bei Zeile: {line.strip()[:200]}")
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


if __name__ == "__main__":
    build_ui()

    def _run_logic():
        startup()
        restart_count = 0
        while True:
            try:
                watch_log()
                break
            except Exception:
                _report_crash(context="watch_log() — Beobachtungsschleife abgestürzt")
                restart_count += 1
                if restart_count > 5:
                    print_scroll_text(
                        f"\n{BOLD_RED}# [SYSTEM] Too many consecutive crashes. Stopping operation.{RESET}\n"
                        f"{NORMAL_RED}# A folder named 'crash_reports' was created next to this Program's exe.\nPlease check the crash report inside and send it to me.\nEither on reddit or directly to contact@ennithing.de{RESET}\n"
                    )
                    break
                time.sleep(2)  # Kurze Pause vor Restart nach Crash
            except KeyboardInterrupt:
                break

    logic_thread = threading.Thread(target=_run_logic, daemon=True)
    logic_thread.start()

    root.mainloop()
