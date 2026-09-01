import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

from tkinter import font as tkfont
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image
from tkcalendar import Calendar


APP_NAME = "FocusLock"
APP_VERSION = "2.6.0"

DATA_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", os.path.expanduser("~")),
    APP_NAME,
)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
HOSTS_FILE = r"C:\Windows\System32\drivers\etc\hosts"

BLOCK_START = "# FOCUSLOCK BEGIN"
BLOCK_END = "# FOCUSLOCK END"
BLOCK_IP = "0.0.0.0"

TASK_GUI = "FocusLock"
TASK_BACKGROUND = "FocusLockBackground"
CREATE_NO_WINDOW = 0x08000000

POPULAR_PLATFORMS = {
    "Instagram": "instagram.com",
    "Reddit": "reddit.com",
    "YouTube": "youtube.com",
    "X / Twitter": "x.com",
    "Facebook": "facebook.com",
    "TikTok": "tiktok.com",
    "LinkedIn": "linkedin.com",
}

COLOR = {
    "bg": "#121212",
    "surface": "#181818",
    "mid": "#1f1f1f",
    "card": "#252525",
    "card_alt": "#272727",
    "text": "#ffffff",
    "muted": "#b3b3b3",
    "muted2": "#cbcbcb",
    "accent": "#7C3AED",
    "accent_hover": "#8B5CF6",
    "accent_border": "#6D28D9",
    "on_accent": "#ffffff",
    "ink": "#0B1220",
    "black": "#000000",
    "negative": "#f3727f",
    "warning": "#ffa42b",
    "info": "#539df5",
    "border": "#4d4d4d",
    "outline": "#7c7c7c",
}
RADIUS = 8
RADIUS_BTN = 8
RADIUS_INPUT = 8
CARD_RADIUS = 8
CHIP_RADIUS = 8
CONTROL_BORDER = "#2F2F2F"
CONTROL_FILL = "#242424"
CONTROL_FILL_HOVER = "#2A2A2A"


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def pick_ui_font():
    available = {name.lower() for name in tkfont.families()}
    for candidate in (
        "Segoe UI Variable Display",
        "Segoe UI Variable Text",
        "Bahnschrift",
        "Segoe UI",
        "Calibri",
        "Arial",
    ):
        if candidate.lower() in available:
            return candidate
    return "Segoe UI"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_scheduled_task(name):
    try:
        completed = subprocess.run(
            ["schtasks", "/run", "/tn", name],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def restart_as_admin():
    arguments = " ".join(f'"{argument}"' for argument in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        arguments,
        None,
        1,
    )
    raise SystemExit


def ensure_elevated():
    if is_admin():
        return

    task_name = TASK_BACKGROUND if "--background" in sys.argv else TASK_GUI
    if run_scheduled_task(task_name):
        raise SystemExit

    restart_as_admin()


def default_config():
    return {
        "enabled": False,
        "sites": [],
        "locked_until": None,
    }


def ensure_data_directory():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_config():
    ensure_data_directory()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            config = default_config()
            config.update(json.load(file))
            return config
    except Exception:
        return default_config()


def save_config(config):
    ensure_data_directory()
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)


def normalize_domain(value):
    value = value.strip().lower()
    if not value:
        return None

    if "://" in value:
        value = urlparse(value).netloc

    value = value.split("/")[0]
    value = value.split(":")[0]

    if value.startswith("www."):
        value = value[4:]

    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", value):
        return None

    return value


def lock_is_active(config):
    locked_until = config.get("locked_until")
    if not locked_until:
        return False
    try:
        return time.time() < float(locked_until)
    except Exception:
        return False


def remaining_lock_text(config):
    try:
        seconds = max(0, int(float(config.get("locked_until")) - time.time()))
    except Exception:
        return ""

    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m left"
    if minutes:
        return f"{minutes}m {secs:02d}s left"
    return f"{secs}s left"


def remove_focuslock_block(text):
    pattern = re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\s*"
    return re.sub(pattern, "", text, flags=re.S)


def create_block(sites):
    domains = set()
    for site in sites:
        domain = normalize_domain(site)
        if domain:
            domains.add(domain)
            domains.add("www." + domain)

    lines = [BLOCK_START, "# Managed by FocusLock"]
    for domain in sorted(domains):
        lines.append(f"{BLOCK_IP} {domain}")
    lines.append(BLOCK_END)
    return "\n".join(lines) + "\n"


def flush_dns():
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


def apply_blocking(config):
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8", errors="ignore") as file:
            old_hosts = file.read()
    except Exception:
        return

    clean_hosts = remove_focuslock_block(old_hosts)
    new_hosts = clean_hosts

    if config.get("enabled"):
        block = create_block(config.get("sites", []))
        new_hosts = clean_hosts.rstrip() + "\n" + block

    if new_hosts != old_hosts:
        with open(HOSTS_FILE, "w", encoding="utf-8", newline="\n") as file:
            file.write(new_hosts)
        threading.Thread(target=flush_dns, daemon=True).start()


def background_enforcement():
    while True:
        try:
            config = load_config()
            if config.get("enabled"):
                apply_blocking(config)
        except Exception:
            pass
        time.sleep(20)


class DateTimePicker(ctk.CTkFrame):
    def __init__(self, master, font_fn):
        super().__init__(master, fg_color="transparent")
        upcoming = datetime.now() + timedelta(hours=1)
        upcoming = upcoming.replace(second=0, microsecond=0)
        self.hour_var = ctk.StringVar(value=f"{upcoming.hour:02d}")
        self.minute_var = ctk.StringVar(value=f"{upcoming.minute:02d}")
        family = font_fn(13).cget("family")

        host = ctk.CTkFrame(
            self,
            fg_color=CONTROL_FILL,
            corner_radius=RADIUS_INPUT,
            border_width=2,
            border_color=CONTROL_BORDER,
        )
        host.pack(fill="x")

        self.calendar = Calendar(
            host,
            selectmode="day",
            year=upcoming.year,
            month=upcoming.month,
            day=upcoming.day,
            date_pattern="yyyy-mm-dd",
            showweeknumbers=False,
            background=COLOR["mid"],
            disabledbackground=COLOR["mid"],
            bordercolor=COLOR["mid"],
            headersbackground=COLOR["card"],
            headersforeground=COLOR["text"],
            normalbackground=COLOR["surface"],
            normalforeground=COLOR["text"],
            weekendbackground=COLOR["surface"],
            weekendforeground=COLOR["muted2"],
            othermonthbackground=COLOR["mid"],
            othermonthwebackground=COLOR["mid"],
            othermonthforeground="#666666",
            othermonthweforeground="#666666",
            selectbackground=COLOR["accent"],
            selectforeground=COLOR["on_accent"],
            foreground=COLOR["text"],
            font=(family, 11),
        )
        self.calendar.pack(fill="x", padx=10, pady=10)

        time_row = ctk.CTkFrame(self, fg_color="transparent")
        time_row.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(
            time_row,
            text="Time",
            text_color=COLOR["muted"],
            font=font_fn(13),
        ).pack(side="left")

        hours = [f"{hour:02d}" for hour in range(24)]
        minutes = [f"{minute:02d}" for minute in range(0, 60, 5)]
        if self.minute_var.get() not in minutes:
            minutes.append(self.minute_var.get())
            minutes.sort()

        self.hour_menu = ctk.CTkOptionMenu(
            time_row,
            values=hours,
            variable=self.hour_var,
            width=72,
            height=34,
            corner_radius=RADIUS_INPUT,
            fg_color=CONTROL_FILL,
            button_color=COLOR["card"],
            button_hover_color=COLOR["border"],
            text_color=COLOR["text"],
            dropdown_fg_color=COLOR["surface"],
            dropdown_hover_color=COLOR["mid"],
            dropdown_text_color=COLOR["text"],
            font=font_fn(13, "bold"),
        )
        self.hour_menu.pack(side="left", padx=(10, 6))

        ctk.CTkLabel(
            time_row,
            text=":",
            text_color=COLOR["text"],
            font=font_fn(16, "bold"),
        ).pack(side="left")

        self.minute_menu = ctk.CTkOptionMenu(
            time_row,
            values=minutes,
            variable=self.minute_var,
            width=72,
            height=34,
            corner_radius=RADIUS_INPUT,
            fg_color=CONTROL_FILL,
            button_color=COLOR["card"],
            button_hover_color=COLOR["border"],
            text_color=COLOR["text"],
            dropdown_fg_color=COLOR["surface"],
            dropdown_hover_color=COLOR["mid"],
            dropdown_text_color=COLOR["text"],
            font=font_fn(13, "bold"),
        )
        self.minute_menu.pack(side="left", padx=(6, 0))

    def get_datetime(self):
        selected = datetime.strptime(self.calendar.get_date(), "%Y-%m-%d")
        return selected.replace(
            hour=int(self.hour_var.get()),
            minute=int(self.minute_var.get()),
            second=0,
            microsecond=0,
        )


class FocusLockApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.ui_font_family = pick_ui_font()
        self.icon_path = resource_path("assets", "focuslock.ico")
        self.icon_png = resource_path("assets", "icon.png")
        self.icon_small = self.load_icon((32, 32))
        self.icon_medium = self.load_icon((48, 48))

        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1100x720")
        self.minsize(960, 620)
        self.configure(fg_color=COLOR["black"])
        self.apply_window_icon()

        self.config_data = load_config()
        self.platform_variables = {}
        self.platform_cards = {}
        self.chip_widgets = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_main()
        self.create_now_playing_bar()
        self.refresh_ui()
        self.after(200, self.bring_forward)
        self.after(1000, self.tick_status)

    def bring_forward(self):
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass

    def load_icon(self, size):
        if not os.path.exists(self.icon_png):
            return None
        image = Image.open(self.icon_png)
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)

    def apply_window_icon(self):
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

    def font(self, size, weight="normal"):
        return ctk.CTkFont(family=self.ui_font_family, size=size, weight=weight)

    def make_entry(self, parent, placeholder):
        entry = ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            height=46,
            corner_radius=RADIUS_INPUT,
            border_width=2,
            border_color=CONTROL_BORDER,
            fg_color=CONTROL_FILL,
            text_color=COLOR["text"],
            placeholder_text_color="#7D7D7D",
            font=self.font(14),
        )

        def focus_in(_event):
            entry.configure(border_color=COLOR["accent"], fg_color=CONTROL_FILL_HOVER)

        def focus_out(_event):
            entry.configure(border_color=CONTROL_BORDER, fg_color=CONTROL_FILL)

        entry.bind("<FocusIn>", focus_in)
        entry.bind("<FocusOut>", focus_out)
        return entry

    def make_control_button(self, parent, text, command, width=None, height=46):
        kwargs = {
            "text": text,
            "command": command,
            "height": height,
            "corner_radius": RADIUS_BTN,
            "border_width": 2,
            "border_color": CONTROL_BORDER,
            "fg_color": CONTROL_FILL,
            "hover_color": CONTROL_FILL_HOVER,
            "text_color": COLOR["text"],
            "font": self.font(14, "bold"),
        }
        if width:
            kwargs["width"] = width
        return ctk.CTkButton(parent, **kwargs)

    def pill_button(self, parent, text, command, primary=False, width=None):
        kwargs = {
            "text": text,
            "command": command,
            "height": 36,
            "corner_radius": RADIUS_BTN,
            "font": self.font(14, "bold"),
        }
        if width:
            kwargs["width"] = width
        if primary:
            kwargs.update(
                fg_color=COLOR["accent"],
                hover_color=COLOR["accent_hover"],
                border_width=2,
                border_color=COLOR["accent_border"],
                text_color=(COLOR["on_accent"], COLOR["on_accent"]),
            )
        else:
            kwargs.update(
                fg_color=CONTROL_FILL,
                hover_color=CONTROL_FILL_HOVER,
                border_width=2,
                border_color=CONTROL_BORDER,
                text_color=COLOR["text"],
            )
        return ctk.CTkButton(parent, **kwargs)

    def create_sidebar(self):
        sidebar = ctk.CTkFrame(
            self,
            width=242,
            corner_radius=0,
            fg_color=COLOR["black"],
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        library = ctk.CTkFrame(
            sidebar,
            corner_radius=CARD_RADIUS,
            fg_color=COLOR["surface"],
        )
        library.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        brand = ctk.CTkFrame(library, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(16, 20))

        mark = ctk.CTkLabel(
            brand,
            text="",
            image=self.icon_small,
            width=32,
            height=32,
        )
        mark.pack(side="left")

        ctk.CTkLabel(
            brand,
            text=APP_NAME,
            text_color=COLOR["text"],
            font=self.font(16, "bold"),
        ).pack(side="left", padx=(10, 0))

        self.nav_home = ctk.CTkLabel(
            library,
            text="Home",
            text_color=COLOR["text"],
            font=self.font(14, "bold"),
            anchor="w",
        )
        self.nav_home.pack(fill="x", padx=16, pady=(0, 8))

        self.nav_list = ctk.CTkLabel(
            library,
            text="Your blocklist",
            text_color=COLOR["muted"],
            font=self.font(14),
            anchor="w",
        )
        self.nav_list.pack(fill="x", padx=16, pady=(0, 4))

        self.count_label = ctk.CTkLabel(
            library,
            text="0 sites",
            text_color=COLOR["muted"],
            font=self.font(12),
            anchor="w",
        )
        self.count_label.pack(fill="x", padx=16, pady=(0, 16))

        divider = ctk.CTkFrame(library, height=1, fg_color=COLOR["mid"])
        divider.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            library,
            text="STATUS",
            text_color=COLOR["muted"],
            font=self.font(10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16)

        self.status_dot = ctk.CTkLabel(
            library,
            text="Paused",
            text_color=COLOR["text"],
            font=self.font(14, "bold"),
            anchor="w",
        )
        self.status_dot.pack(fill="x", padx=16, pady=(6, 0))

        self.status_detail = ctk.CTkLabel(
            library,
            text="Choose sites, then press Enable.",
            text_color=COLOR["muted"],
            font=self.font(12),
            wraplength=190,
            justify="left",
            anchor="w",
        )
        self.status_detail.pack(fill="x", padx=16, pady=(4, 0))

        ctk.CTkLabel(
            library,
            text=f"Version {APP_VERSION}",
            text_color=COLOR["muted"],
            font=self.font(10),
            anchor="w",
        ).pack(side="bottom", fill="x", padx=16, pady=16)

    def create_main(self):
        shell = ctk.CTkFrame(self, fg_color=COLOR["black"], corner_radius=0)
        shell.grid(row=0, column=1, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        panel = ctk.CTkFrame(
            shell,
            corner_radius=CARD_RADIUS,
            fg_color=COLOR["bg"],
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(8, 4))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="Blocked sites",
            text_color=COLOR["text"],
            font=self.font(24, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Toggle platforms, add custom domains, then lock in a session.",
            text_color=COLOR["muted"],
            font=self.font(14),
        ).pack(anchor="w", pady=(2, 0))

        self.scroll = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            scrollbar_button_color=COLOR["mid"],
            scrollbar_button_hover_color=COLOR["outline"],
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.scroll.grid_columnconfigure(0, weight=1)

        self.create_platform_section()
        self.create_custom_section()
        self.create_lock_section()

    def create_now_playing_bar(self):
        bar = ctk.CTkFrame(
            self,
            height=76,
            corner_radius=0,
            fg_color=COLOR["surface"],
        )
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        self.play_indicator = ctk.CTkLabel(
            left,
            text="",
            image=self.icon_medium,
            width=48,
            height=48,
        )
        self.play_indicator.pack(side="left")

        copy = ctk.CTkFrame(left, fg_color="transparent")
        copy.pack(side="left", padx=(12, 0))

        self.status_title = ctk.CTkLabel(
            copy,
            text="Blocking is off",
            text_color=COLOR["text"],
            font=self.font(14, "bold"),
        )
        self.status_title.pack(anchor="w")

        self.bar_meta = ctk.CTkLabel(
            copy,
            text="No sites protected",
            text_color=COLOR["muted"],
            font=self.font(12),
        )
        self.bar_meta.pack(anchor="w")

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e", padx=16)

        self.disable_button = self.pill_button(
            actions,
            "TURN OFF",
            self.disable_blocking,
            primary=False,
            width=120,
        )
        self.disable_button.pack(side="left", padx=(0, 8))

        self.enable_button = self.pill_button(
            actions,
            "ENABLE BLOCKING",
            self.enable_blocking,
            primary=True,
            width=180,
        )
        self.enable_button.pack(side="left")

    def section_heading(self, parent, title, subtitle):
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            block,
            text=title,
            text_color=COLOR["text"],
            font=self.font(18, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            block,
            text=subtitle,
            text_color=COLOR["muted"],
            font=self.font(14),
        ).pack(anchor="w")
        return block

    def create_platform_section(self):
        self.section_heading(
            self.scroll,
            "Popular platforms",
            "Turn on the sites you want blocked.",
        )

        list_card = ctk.CTkFrame(
            self.scroll,
            corner_radius=CARD_RADIUS,
            fg_color=COLOR["surface"],
        )
        list_card.pack(fill="x", padx=16, pady=(4, 12))

        list_inner = ctk.CTkFrame(list_card, fg_color="transparent")
        list_inner.pack(fill="x", padx=16, pady=18)

        for index, (name, domain) in enumerate(POPULAR_PLATFORMS.items()):
            variable = ctk.BooleanVar(
                value=domain in self.config_data.get("sites", [])
            )
            self.platform_variables[domain] = variable

            row = ctk.CTkFrame(
                list_inner,
                fg_color="transparent",
            )
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=str(index + 1),
                width=28,
                text_color=COLOR["muted"],
                font=self.font(14),
                anchor="center",
            ).grid(row=0, column=0, padx=(4, 8), pady=4, sticky="w")

            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.grid(row=0, column=1, sticky="ew", pady=4)
            ctk.CTkLabel(
                text_col,
                text=name,
                text_color=COLOR["text"],
                font=self.font(15, "bold"),
                anchor="w",
                height=20,
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col,
                text=domain,
                text_color=COLOR["muted"],
                font=self.font(12),
                anchor="w",
                height=18,
            ).pack(anchor="w")

            switch = ctk.CTkSwitch(
                row,
                text="",
                width=44,
                variable=variable,
                command=self.platform_changed,
                progress_color=COLOR["accent"],
                button_color=COLOR["text"],
                fg_color=COLOR["border"],
            )
            switch.grid(row=0, column=2, padx=(8, 4), pady=4, sticky="e")
            self.platform_cards[domain] = switch

    def create_custom_section(self):
        self.section_heading(
            self.scroll,
            "Custom websites",
            "Add any other domain.",
        )

        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=CARD_RADIUS,
            fg_color=COLOR["surface"],
        )
        card.pack(fill="x", padx=16, pady=(0, 12))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(18, 8))

        self.custom_entry = self.make_entry(row, "Search or add example.com")
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.custom_entry.bind("<Return>", lambda _event: self.add_custom_site())

        self.add_button = self.make_control_button(
            row,
            "Add",
            self.add_custom_site,
            width=96,
        )
        self.add_button.pack(side="left")

        self.chips_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.chips_frame.pack(fill="x", padx=18, pady=(0, 18))

        self.empty_custom = ctk.CTkLabel(
            self.chips_frame,
            text="No custom sites yet.",
            text_color=COLOR["muted"],
            font=self.font(14),
        )
        self.empty_custom.pack(anchor="w")

    def create_lock_section(self):
        self.section_heading(
            self.scroll,
            "Lock mode",
            "Once a lock starts, sites stay blocked until it ends. You can still add and enable more.",
        )

        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=CARD_RADIUS,
            fg_color=COLOR["surface"],
        )
        card.pack(fill="x", padx=16, pady=(0, 20))

        self.lock_setup_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.lock_setup_frame.pack(fill="x")

        mode_row = ctk.CTkFrame(self.lock_setup_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=18, pady=(18, 10))

        self.lock_mode = ctk.StringVar(value="Hours")
        self.lock_hours_btn = ctk.CTkButton(
            mode_row,
            text="Hours",
            width=120,
            height=36,
            corner_radius=RADIUS_BTN,
            border_width=2,
            font=self.font(13, "bold"),
            command=lambda: self.set_lock_mode("Hours"),
        )
        self.lock_hours_btn.pack(side="left")

        self.lock_date_btn = ctk.CTkButton(
            mode_row,
            text="Date & time",
            width=140,
            height=36,
            corner_radius=RADIUS_BTN,
            border_width=2,
            font=self.font(13, "bold"),
            command=lambda: self.set_lock_mode("Date & time"),
        )
        self.lock_date_btn.pack(side="left", padx=(8, 0))

        self.hours_row = ctk.CTkFrame(self.lock_setup_frame, fg_color="transparent")
        self.hours_row.pack(fill="x", padx=18)

        self.lock_input = self.make_entry(self.hours_row, "Number of hours, e.g. 8")
        self.lock_input.pack(fill="x")

        self.date_picker = DateTimePicker(self.lock_setup_frame, self.font)

        self.lock_button = ctk.CTkButton(
            self.lock_setup_frame,
            text="Start lock",
            height=46,
            corner_radius=RADIUS_BTN,
            border_width=2,
            border_color=COLOR["accent_border"],
            fg_color=COLOR["accent"],
            hover_color=COLOR["accent_hover"],
            text_color=(COLOR["on_accent"], COLOR["on_accent"]),
            font=self.font(14, "bold"),
            command=self.start_lock,
        )
        self.lock_button.pack(fill="x", padx=18, pady=(12, 18))

        self.lock_status_frame = ctk.CTkFrame(card, fg_color="transparent")

        self.lock_badge = ctk.CTkLabel(
            self.lock_status_frame,
            text="LOCKED UNTIL",
            text_color=COLOR["accent"],
            font=self.font(12, "bold"),
        )
        self.lock_badge.pack(anchor="w", padx=18, pady=(18, 6))

        self.lock_until_label = ctk.CTkLabel(
            self.lock_status_frame,
            text="",
            text_color=COLOR["text"],
            font=self.font(22, "bold"),
            wraplength=520,
            justify="left",
        )
        self.lock_until_label.pack(anchor="w", padx=18)

        self.lock_remaining_label = ctk.CTkLabel(
            self.lock_status_frame,
            text="",
            text_color=COLOR["muted"],
            font=self.font(14),
        )
        self.lock_remaining_label.pack(anchor="w", padx=18, pady=(6, 18))

        self.set_lock_mode("Hours")

    def custom_sites(self):
        popular = set(POPULAR_PLATFORMS.values())
        return [
            site
            for site in self.config_data.get("sites", [])
            if site not in popular
        ]

    def get_current_sites(self):
        sites = {
            domain
            for domain, variable in self.platform_variables.items()
            if variable.get()
        }
        sites.update(self.custom_sites())
        return sorted(sites)

    def rebuild_chips(self):
        for widget in self.chip_widgets:
            widget.destroy()
        self.chip_widgets = []

        sites = self.custom_sites()
        locked = lock_is_active(self.config_data)

        if not sites:
            self.empty_custom.pack(anchor="w")
            return

        self.empty_custom.pack_forget()

        for index, site in enumerate(sites):
            chip = ctk.CTkFrame(
                self.chips_frame,
                corner_radius=CHIP_RADIUS,
                fg_color=CONTROL_FILL,
                border_width=2,
                border_color=CONTROL_BORDER,
            )
            chip.grid(row=index // 3, column=index % 3, padx=(0, 8), pady=(0, 8), sticky="w")

            ctk.CTkLabel(
                chip,
                text=site,
                text_color=COLOR["text"],
                font=self.font(12, "bold"),
            ).pack(side="left", padx=(12, 4), pady=6)

            remove = ctk.CTkButton(
                chip,
                text="✕",
                width=28,
                height=24,
                corner_radius=CHIP_RADIUS,
                fg_color="transparent",
                hover_color=COLOR["card"],
                text_color=COLOR["muted"],
                font=self.font(12, "bold"),
                command=lambda value=site: self.remove_custom_site(value),
                state="disabled" if locked else "normal",
            )
            remove.pack(side="left", padx=(0, 6))
            self.chip_widgets.append(chip)

    def persist_sites(self, sites=None):
        if sites is None:
            sites = self.get_current_sites()

        current = set(self.config_data.get("sites", []))
        incoming = set(sites)
        if lock_is_active(self.config_data) and not current.issubset(incoming):
            self.refresh_ui()
            return False

        self.config_data["sites"] = sorted(incoming)
        save_config(self.config_data)
        if self.config_data.get("enabled"):
            apply_blocking(self.config_data)
        self.refresh_ui()
        return True

    def platform_changed(self):
        if lock_is_active(self.config_data):
            locked_sites = set(self.config_data.get("sites", []))
            reverted = False
            for domain, variable in self.platform_variables.items():
                if domain in locked_sites and not variable.get():
                    variable.set(True)
                    reverted = True
            if reverted:
                return
        self.persist_sites()

    def add_custom_site(self):
        domain = normalize_domain(self.custom_entry.get())
        if not domain:
            messagebox.showerror(
                APP_NAME,
                "Please enter a valid website.\nFor example: example.com",
            )
            return

        sites = set(self.config_data.get("sites", []))
        sites.add(domain)
        self.custom_entry.delete(0, "end")
        self.persist_sites(sorted(sites))

    def remove_custom_site(self, domain):
        if lock_is_active(self.config_data):
            messagebox.showwarning(
                APP_NAME,
                "FocusLock is locked. You can change the list after this lock ends.",
            )
            return

        sites = [
            site
            for site in self.config_data.get("sites", [])
            if site != domain
        ]
        self.persist_sites(sites)

    def enable_blocking(self):
        sites = self.get_current_sites()
        if not sites:
            messagebox.showerror(APP_NAME, "Select at least one website first.")
            return

        self.config_data["sites"] = sites
        self.config_data["enabled"] = True
        save_config(self.config_data)
        apply_blocking(self.config_data)
        self.refresh_ui()

    def disable_blocking(self):
        self.config_data = load_config()
        if lock_is_active(self.config_data):
            messagebox.showwarning(
                APP_NAME,
                "FocusLock is currently locked.\nBlocking cannot be disabled yet.",
            )
            return

        if not messagebox.askyesno(APP_NAME, "Turn off all website blocking?"):
            return

        self.config_data["enabled"] = False
        save_config(self.config_data)
        apply_blocking(self.config_data)
        self.refresh_ui()

    def set_lock_mode(self, value):
        self.lock_mode.set(value)
        selected = {
            "fg_color": COLOR["accent"],
            "hover_color": COLOR["accent_hover"],
            "border_color": COLOR["accent_border"],
            "text_color": (COLOR["on_accent"], COLOR["on_accent"]),
        }
        idle = {
            "fg_color": CONTROL_FILL,
            "hover_color": CONTROL_FILL_HOVER,
            "border_color": CONTROL_BORDER,
            "text_color": (COLOR["text"], COLOR["text"]),
        }
        if value == "Hours":
            self.lock_hours_btn.configure(**selected)
            self.lock_date_btn.configure(**idle)
            self.date_picker.pack_forget()
            self.hours_row.pack(fill="x", padx=18, before=self.lock_button)
        else:
            self.lock_hours_btn.configure(**idle)
            self.lock_date_btn.configure(**selected)
            self.hours_row.pack_forget()
            self.date_picker.pack(fill="x", padx=18, pady=(0, 4), before=self.lock_button)

    def lock_mode_changed(self, value):
        self.set_lock_mode(value)

    def start_lock(self):
        sites = self.get_current_sites()
        if not sites:
            messagebox.showerror(
                APP_NAME,
                "Select at least one website before starting a lock.",
            )
            return

        try:
            if self.lock_mode.get() == "Hours":
                hours = float(self.lock_input.get())
                if hours <= 0:
                    raise ValueError
                locked_until = time.time() + hours * 3600
            else:
                chosen = self.date_picker.get_datetime()
                locked_until = chosen.timestamp()
                if locked_until <= time.time():
                    raise ValueError
        except Exception:
            messagebox.showerror(
                APP_NAME,
                "Please choose a valid future duration or date and time.",
            )
            return

        self.config_data["sites"] = sites
        self.config_data["enabled"] = True
        self.config_data["locked_until"] = locked_until
        save_config(self.config_data)
        apply_blocking(self.config_data)
        self.refresh_ui()

    def update_status_copy(self):
        locked = lock_is_active(self.config_data)
        enabled = self.config_data.get("enabled")
        count = len(self.config_data.get("sites", []))
        count_text = f"{count} site{'s' if count != 1 else ''}"
        self.count_label.configure(text=count_text)

        if locked:
            unlock_time = datetime.fromtimestamp(
                float(self.config_data["locked_until"])
            ).strftime("%d %b %Y, %I:%M %p")
            self.status_dot.configure(text="Locked", text_color=COLOR["warning"])
            self.status_detail.configure(
                text=f"Until {unlock_time}. {remaining_lock_text(self.config_data)}"
            )
            self.status_title.configure(text="Focus lock on")
            self.bar_meta.configure(text=f"{count_text} · {remaining_lock_text(self.config_data)}")
            self.nav_list.configure(text_color=COLOR["text"], font=self.font(14, "bold"))
        elif enabled:
            self.status_dot.configure(text="Blocking", text_color=COLOR["accent"])
            self.status_detail.configure(text="Selected sites stay blocked.")
            self.status_title.configure(text="Blocking is on")
            self.bar_meta.configure(text=f"{count_text} protected")
            self.nav_list.configure(text_color=COLOR["text"], font=self.font(14, "bold"))
        else:
            self.status_dot.configure(text="Paused", text_color=COLOR["text"])
            self.status_detail.configure(text="Choose sites, then press Enable.")
            self.status_title.configure(text="Blocking is off")
            self.bar_meta.configure(text=f"{count_text} selected")
            self.nav_list.configure(text_color=COLOR["muted"], font=self.font(14))

        self.update_lock_panel()

    def update_lock_panel(self):
        locked = lock_is_active(self.config_data)
        if locked:
            unlock_time = datetime.fromtimestamp(
                float(self.config_data["locked_until"])
            ).strftime("%d %b %Y, %I:%M %p")
            if not self.lock_status_frame.winfo_ismapped():
                self.lock_setup_frame.pack_forget()
                self.lock_status_frame.pack(fill="x")
            self.lock_until_label.configure(text=unlock_time)
            remaining = remaining_lock_text(self.config_data) or "Unlocking soon"
            self.lock_remaining_label.configure(text=remaining)
        elif self.lock_status_frame.winfo_ismapped():
            self.lock_status_frame.pack_forget()
            self.lock_setup_frame.pack(fill="x")
            self.set_lock_mode(self.lock_mode.get())

    def apply_lock_rules(self):
        locked = lock_is_active(self.config_data)
        lock_controls = "disabled" if locked else "normal"
        for switch in self.platform_cards.values():
            switch.configure(state="normal")
        self.add_button.configure(state="normal")
        self.custom_entry.configure(state="normal")
        self.lock_hours_btn.configure(state=lock_controls)
        self.lock_date_btn.configure(state=lock_controls)
        self.lock_input.configure(state=lock_controls)
        self.lock_button.configure(state=lock_controls)
        self.date_picker.hour_menu.configure(state=lock_controls)
        self.date_picker.minute_menu.configure(state=lock_controls)
        try:
            self.date_picker.calendar.configure(state=lock_controls)
        except Exception:
            pass
        self.disable_button.configure(state=lock_controls)
        if locked:
            self.disable_button.configure(
                fg_color=CONTROL_FILL,
                text_color=COLOR["muted"],
            )
            self.enable_button.configure(
                state="disabled",
                fg_color=CONTROL_FILL,
                hover_color=CONTROL_FILL,
                text_color=COLOR["muted"],
                border_color=CONTROL_BORDER,
            )
        else:
            self.disable_button.configure(
                fg_color=CONTROL_FILL,
                text_color=COLOR["text"],
            )
            self.enable_button.configure(
                state="normal",
                fg_color=COLOR["accent"],
                hover_color=COLOR["accent_hover"],
                text_color=(COLOR["on_accent"], COLOR["on_accent"]),
                border_color=COLOR["accent_border"],
            )

    def refresh_ui(self):
        self.config_data = load_config()
        locked = lock_is_active(self.config_data)

        for domain, variable in self.platform_variables.items():
            variable.set(domain in self.config_data.get("sites", []))

        self.rebuild_chips()
        self.update_status_copy()
        self.apply_lock_rules()

    def tick_status(self):
        previous = self.config_data
        self.config_data = load_config()
        if lock_is_active(previous) and not lock_is_active(self.config_data):
            self.refresh_ui()
        else:
            self.update_status_copy()
        self.after(1000, self.tick_status)


if __name__ == "__main__":
    ensure_elevated()

    config = load_config()
    if config.get("enabled"):
        apply_blocking(config)

    threading.Thread(target=background_enforcement, daemon=True).start()

    if "--background" not in sys.argv:
        app = FocusLockApp()
        app.mainloop()
