"""
Visual theme for fromfacade To-Do Grader.

Central place for colors, fonts, and reusable UI building blocks.
"""

import tkinter as tk
from tkinter import ttk

# --- Colors ---

BG_APP = "#0f0f0d"
BG_PANEL = "#1c1a17"
BG_PANEL_SECONDARY = "#2b2b2b"
BG_TERMINAL = "#111111"
BG_TERMINAL_TITLE = "#1f1f1f"

ACCENT_AMBER = "#f6c343"
ACCENT_BRONZE = "#b77c00"
TEXT_PRIMARY = "#f5f5f5"
TEXT_SECONDARY = "#b8b8b8"
BORDER_MUTED = "#3a2a16"
BORDER_SOFT = "#3a3a3a"

SUCCESS = "#2ecc71"
DANGER = "#e74c3c"

EASY_CHIP_BG = "#1a3d2a"
EASY_CHIP_FG = "#2ecc71"
MEDIUM_CHIP_BG = "#3a2f14"
MEDIUM_CHIP_FG = "#f6c343"
HARD_CHIP_BG = "#3d1f1a"
HARD_CHIP_FG = "#e67e22"

SIDEBAR_ACTIVE = "#2b2418"
SIDEBAR_IDLE = BG_PANEL

CALENDAR_DAY_BG = BG_PANEL_SECONDARY
CALENDAR_EMPTY_BG = BG_PANEL
CALENDAR_TODAY_BG = "#2b2418"

# Brighter gold used for S/SS/SSS-tier ranks so they feel more prestigious
# than the base amber accent, while staying in the same warm color family.
RANK_SPECIAL_COLOR = "#fff3c4"

# --- Fonts ---

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 18, "bold")
FONT_SUBHEADING = ("Segoe UI", 13, "bold")
FONT_BRAND = ("Segoe UI", 22, "bold")
FONT_TAGLINE = ("Segoe UI", 10)
FONT_STAT_VALUE = ("Segoe UI", 24, "bold")
FONT_STAT_LABEL = ("Segoe UI", 9)
FONT_TIMER = ("Consolas", 48, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SMALL = ("Consolas", 9)
FONT_CALENDAR_DAY = ("Segoe UI", 9, "bold")
FONT_CALENDAR_GRADE = ("Segoe UI", 10, "bold")
FONT_RANK_VALUE = ("Segoe UI", 34, "bold")


def get_rank_accent_color(rank):
    """S/SS/SSS-tier ranks get a brighter gold; everything else uses the normal amber."""
    if rank.startswith("S"):
        return RANK_SPECIAL_COLOR
    return ACCENT_AMBER


def apply_app_theme(root):
    """Apply the dark dashboard look to the main window and ttk widgets."""
    root.configure(bg=BG_APP)

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG_APP, foreground=TEXT_PRIMARY, font=FONT_UI)
    style.configure("TFrame", background=BG_APP)
    style.configure("Card.TFrame", background=BG_PANEL)
    style.configure("TLabel", background=BG_APP, foreground=TEXT_PRIMARY)
    style.configure(
        "Secondary.TLabel",
        background=BG_APP,
        foreground=TEXT_SECONDARY,
        font=FONT_UI,
    )
    style.configure(
        "Card.TLabel",
        background=BG_PANEL,
        foreground=TEXT_PRIMARY,
    )
    style.configure(
        "CardSecondary.TLabel",
        background=BG_PANEL,
        foreground=TEXT_SECONDARY,
    )
    style.configure(
        "TEntry",
        fieldbackground=BG_PANEL_SECONDARY,
        foreground=TEXT_PRIMARY,
        insertcolor=TEXT_PRIMARY,
        bordercolor=BORDER_SOFT,
    )
    style.configure(
        "TCombobox",
        fieldbackground=BG_PANEL_SECONDARY,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_SOFT,
        arrowcolor=ACCENT_AMBER,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG_PANEL_SECONDARY)],
        foreground=[("readonly", TEXT_PRIMARY)],
    )
    style.configure(
        "TCheckbutton",
        background=BG_PANEL,
        foreground=TEXT_PRIMARY,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_PANEL)],
        foreground=[("active", TEXT_PRIMARY)],
    )
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=BG_PANEL_SECONDARY,
        background=ACCENT_AMBER,
        bordercolor=BORDER_SOFT,
        lightcolor=ACCENT_AMBER,
        darkcolor=ACCENT_BRONZE,
    )


def create_card(parent, padding=14):
    """Dark panel with a thin amber border."""
    card = tk.Frame(
        parent,
        bg=BG_PANEL,
        highlightbackground=BORDER_MUTED,
        highlightthickness=1,
        bd=0,
    )
    inner = tk.Frame(card, bg=BG_PANEL, padx=padding, pady=padding)
    inner.pack(fill="both", expand=True)
    return card, inner


def create_header(parent):
    """
    Top header inspired by the fromfacade portfolio.

    The height is not hardcoded: the frame sizes itself to fit the brand
    text, so it does not clip on different fonts, DPI settings, or screens.
    """
    header = tk.Frame(parent, bg=BG_PANEL)
    header.pack(fill="x")

    inner = tk.Frame(header, bg=BG_PANEL, padx=20, pady=14)
    inner.pack(fill="both", expand=True)

    brand = tk.Label(
        inner,
        text="fromfacade",
        font=FONT_BRAND,
        fg=ACCENT_AMBER,
        bg=BG_PANEL,
    )
    brand.pack(anchor="w")

    title = tk.Label(
        inner,
        text="To-Do Grader",
        font=FONT_SUBHEADING,
        fg=TEXT_PRIMARY,
        bg=BG_PANEL,
    )
    title.pack(anchor="w", pady=(2, 0))

    tagline = tk.Label(
        inner,
        text="Plan. Focus. Grade your day.",
        font=FONT_TAGLINE,
        fg=TEXT_SECONDARY,
        bg=BG_PANEL,
    )
    tagline.pack(anchor="w", pady=(2, 0))

    divider = tk.Frame(parent, bg=BORDER_MUTED, height=1)
    divider.pack(fill="x")

    return header


def create_hero(parent, title, subtitle):
    """Small hero block for a section."""
    card, inner = create_card(parent, padding=16)

    heading = tk.Label(
        inner,
        text=title,
        font=FONT_HEADING,
        fg=TEXT_PRIMARY,
        bg=BG_PANEL,
    )
    heading.pack(anchor="w")

    sub = tk.Label(
        inner,
        text=subtitle,
        font=FONT_UI,
        fg=TEXT_SECONDARY,
        bg=BG_PANEL,
    )
    sub.pack(anchor="w", pady=(4, 0))

    return card


def create_stat_card(parent, label, value, width=170):
    """Compact dashboard stat card with a large number."""
    card, inner = create_card(parent, padding=12)
    card.configure(width=width)
    card.pack_propagate(False)

    value_label = tk.Label(
        inner,
        text=value,
        font=FONT_STAT_VALUE,
        fg=ACCENT_AMBER,
        bg=BG_PANEL,
    )
    value_label.pack(anchor="w")

    name_label = tk.Label(
        inner,
        text=label,
        font=FONT_STAT_LABEL,
        fg=TEXT_SECONDARY,
        bg=BG_PANEL,
    )
    name_label.pack(anchor="w", pady=(4, 0))

    return card, value_label


def create_rank_card(parent):
    """
    Prominent card for the Stats tab showing the user's rank/EXP progress.
    Returns (card, rank_value_label, exp_label, next_rank_label,
    progress_bar) so app.py can update the text/values from
    progression.get_rank_progress() without rebuilding any widgets.
    """
    card, inner = create_card(parent, padding=18)

    tk.Label(
        inner,
        text="Rank",
        font=FONT_SUBHEADING,
        fg=TEXT_SECONDARY,
        bg=BG_PANEL,
    ).pack(anchor="w")

    rank_value_label = tk.Label(
        inner,
        text="F-",
        font=FONT_RANK_VALUE,
        fg=ACCENT_AMBER,
        bg=BG_PANEL,
    )
    rank_value_label.pack(anchor="w", pady=(2, 8))

    exp_label = tk.Label(
        inner,
        text="Total EXP: 0",
        font=FONT_UI_BOLD,
        fg=TEXT_PRIMARY,
        bg=BG_PANEL,
    )
    exp_label.pack(anchor="w")

    next_rank_label = tk.Label(
        inner,
        text="",
        font=FONT_UI,
        fg=TEXT_SECONDARY,
        bg=BG_PANEL,
    )
    next_rank_label.pack(anchor="w", pady=(2, 10))

    progress_bar = ttk.Progressbar(
        inner,
        orient="horizontal",
        mode="determinate",
        maximum=100,
    )
    progress_bar.pack(fill="x")

    return card, rank_value_label, exp_label, next_rank_label, progress_bar


def create_sidebar_button(parent, text, command):
    """Navigation button for the left sidebar."""
    button = tk.Button(
        parent,
        text=text,
        font=FONT_UI_BOLD,
        fg=TEXT_SECONDARY,
        bg=SIDEBAR_IDLE,
        activebackground=SIDEBAR_ACTIVE,
        activeforeground=ACCENT_AMBER,
        relief="flat",
        bd=0,
        padx=16,
        pady=12,
        anchor="w",
        cursor="hand2",
        command=command,
    )
    button.pack(fill="x", pady=4)
    return button


def set_sidebar_button_active(button, active):
    """Highlight the selected sidebar section."""
    if active:
        button.configure(
            bg=SIDEBAR_ACTIVE,
            fg=ACCENT_AMBER,
            highlightbackground=ACCENT_BRONZE,
            highlightthickness=1,
        )
    else:
        button.configure(
            bg=SIDEBAR_IDLE,
            fg=TEXT_SECONDARY,
            highlightthickness=0,
        )


def create_primary_button(parent, text, command):
    """Amber/bronze action button with a soft glow-like border."""
    return tk.Button(
        parent,
        text=text,
        font=FONT_UI_BOLD,
        fg=BG_APP,
        bg=ACCENT_AMBER,
        activebackground=ACCENT_BRONZE,
        activeforeground=TEXT_PRIMARY,
        relief="flat",
        bd=0,
        padx=16,
        pady=8,
        cursor="hand2",
        highlightbackground=ACCENT_BRONZE,
        highlightthickness=2,
        command=command,
    )


def create_secondary_button(parent, text, command):
    """Neutral dark button for secondary actions."""
    return tk.Button(
        parent,
        text=text,
        font=FONT_UI,
        fg=TEXT_PRIMARY,
        bg=BG_PANEL_SECONDARY,
        activebackground=BORDER_SOFT,
        activeforeground=ACCENT_AMBER,
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        cursor="hand2",
        command=command,
    )


def create_danger_button(parent, text, command):
    """Small red-toned button for delete actions."""
    return tk.Button(
        parent,
        text=text,
        font=FONT_UI,
        fg=TEXT_PRIMARY,
        bg="#4a1f1f",
        activebackground=DANGER,
        activeforeground=TEXT_PRIMARY,
        relief="flat",
        bd=0,
        padx=10,
        pady=6,
        cursor="hand2",
        command=command,
    )


def create_difficulty_chip(parent, difficulty):
    """Small colored badge for easy / medium / hard."""
    styles = {
        "easy": (EASY_CHIP_BG, EASY_CHIP_FG),
        "medium": (MEDIUM_CHIP_BG, MEDIUM_CHIP_FG),
        "hard": (HARD_CHIP_BG, HARD_CHIP_FG),
    }
    bg_color, fg_color = styles.get(difficulty, (MEDIUM_CHIP_BG, MEDIUM_CHIP_FG))

    chip = tk.Label(
        parent,
        text=difficulty.capitalize(),
        font=("Segoe UI", 8, "bold"),
        fg=fg_color,
        bg=bg_color,
        padx=8,
        pady=2,
    )
    return chip


def create_scrollable_frame(parent, bg=BG_APP):
    """Scrollable area for long task or habit lists."""
    container = tk.Frame(parent, bg=bg)
    # width/height=1 keeps the canvas's own requested size tiny so it is
    # sized purely by the available space from pack(fill="both", expand=True)
    # instead of growing to fit whatever is inside it (which would stop the
    # whole card from ever shrinking back down when the window gets smaller).
    canvas = tk.Canvas(container, bg=bg, highlightthickness=0, bd=0, width=1, height=1)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=bg)

    scroll_frame.bind(
        "<Configure>",
        lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Without this, scroll_frame keeps its own natural width instead of
    # matching the canvas, so cards inside it look too narrow or too wide
    # whenever the window is resized.
    def _match_scroll_frame_width(event):
        canvas.itemconfig(window_id, width=event.width)

    canvas.bind("<Configure>", _match_scroll_frame_width)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_mousewheel(_event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_mousewheel(_event):
        canvas.unbind_all("<MouseWheel>")

    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)

    return container, scroll_frame


def create_terminal_panel(parent):
    """
    Terminal-inspired activity log.
    Returns the outer frame and a function to append log lines.
    """
    outer = tk.Frame(parent, bg=BG_APP)
    outer.pack(fill="x", padx=16, pady=(0, 12))

    panel = tk.Frame(
        outer,
        bg=BG_TERMINAL,
        highlightbackground=BORDER_SOFT,
        highlightthickness=1,
    )
    panel.pack(fill="both", expand=True)

    title_bar = tk.Frame(panel, bg=BG_TERMINAL_TITLE, height=28)
    title_bar.pack(fill="x")
    title_bar.pack_propagate(False)

    dots = tk.Frame(title_bar, bg=BG_TERMINAL_TITLE)
    dots.pack(side="left", padx=10, pady=6)

    for color in ("#ff5f57", "#febc2e", "#28c840"):
        tk.Label(
            dots,
            text="●",
            fg=color,
            bg=BG_TERMINAL_TITLE,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=2)

    tk.Label(
        title_bar,
        text="activity.log",
        font=FONT_MONO_SMALL,
        fg=TEXT_SECONDARY,
        bg=BG_TERMINAL_TITLE,
    ).pack(side="left", padx=8)

    text_widget = tk.Text(
        panel,
        height=6,
        bg=BG_TERMINAL,
        fg=SUCCESS,
        insertbackground=SUCCESS,
        font=FONT_MONO,
        relief="flat",
        bd=0,
        padx=10,
        pady=8,
        wrap="word",
    )
    text_widget.pack(fill="both", expand=True)
    text_widget.configure(state="disabled")

    def log_activity(message):
        text_widget.configure(state="normal")
        text_widget.insert("end", f"> {message}\n")
        text_widget.see("end")
        text_widget.configure(state="disabled")

    log_activity("dashboard ready")

    return outer, log_activity


def style_toplevel(dialog):
    """Apply dark styling to popup windows."""
    dialog.configure(bg=BG_PANEL)
    dialog.resizable(False, False)
