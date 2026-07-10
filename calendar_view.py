"""
Monthly calendar component for the Daily Planner dashboard.

Each day box shows the day number and that day's letter grade.
Clicking a day box selects that date. This is kept in its own file
so app.py does not get too large.
"""

import calendar as calendar_module
import tkinter as tk
from datetime import date

from theme import (
    ACCENT_AMBER,
    BG_PANEL,
    BORDER_MUTED,
    CALENDAR_DAY_BG,
    CALENDAR_EMPTY_BG,
    CALENDAR_TODAY_BG,
    FONT_CALENDAR_DAY,
    FONT_CALENDAR_GRADE,
    FONT_SUBHEADING,
    FONT_UI,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_card,
    create_secondary_button,
)

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_BOX_WIDTH = 74
# Kept fairly compact vertically since a month can span up to 6 rows and
# this whole calendar sits above the task list on the same page.
DAY_BOX_HEIGHT = 46


class CalendarGradeView:
    """
    A monthly calendar grid that shows a letter grade for each day.

    get_month_grades(year, month) must return {date_key: grade_dict}.
    on_day_selected(date_key) is called whenever the user clicks a day box.
    """

    def __init__(self, parent, get_month_grades, on_day_selected, initial_date_key):
        self.get_month_grades = get_month_grades
        self.on_day_selected = on_day_selected
        self.selected_date_key = initial_date_key

        selected_date = date.fromisoformat(initial_date_key)
        self.displayed_year = selected_date.year
        self.displayed_month = selected_date.month

        self.card, self.inner = create_card(parent, padding=14)

        self._build_header()
        self._build_weekday_row()

        self.grid_frame = tk.Frame(self.inner, bg=BG_PANEL)
        self.grid_frame.pack(fill="both", expand=True)

        self.render()

    def get_widget(self):
        """Return the outer card frame so app.py can pack/grid it."""
        return self.card

    def set_selected_date(self, date_key):
        """Move to the month containing date_key and select that day."""
        self.selected_date_key = date_key
        selected_date = date.fromisoformat(date_key)
        self.displayed_year = selected_date.year
        self.displayed_month = selected_date.month
        self.render()

    def go_previous_month(self):
        self.displayed_month -= 1
        if self.displayed_month == 0:
            self.displayed_month = 12
            self.displayed_year -= 1
        self.render()

    def go_next_month(self):
        self.displayed_month += 1
        if self.displayed_month == 13:
            self.displayed_month = 1
            self.displayed_year += 1
        self.render()

    def render(self):
        """Redraw the header and the full day grid for the displayed month."""
        self.month_label.config(
            text=f"{calendar_module.month_name[self.displayed_month]} {self.displayed_year}"
        )

        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        grades_by_date = self.get_month_grades(self.displayed_year, self.displayed_month)
        today_key = str(date.today())

        month_weeks = calendar_module.Calendar(firstweekday=0).monthdayscalendar(
            self.displayed_year, self.displayed_month
        )

        # Equal weights on every column and row let the whole grid stretch
        # evenly as the window is resized, instead of only growing sideways.
        for column in range(7):
            self.grid_frame.grid_columnconfigure(column, weight=1)

        for row_index in range(len(month_weeks)):
            self.grid_frame.grid_rowconfigure(row_index, weight=1)

        for row_index, week in enumerate(month_weeks):
            for column_index, day_number in enumerate(week):
                if day_number == 0:
                    self._build_empty_cell(row_index, column_index)
                    continue

                date_key = (
                    f"{self.displayed_year:04d}-"
                    f"{self.displayed_month:02d}-{day_number:02d}"
                )
                grade = grades_by_date.get(date_key)
                self._build_day_cell(
                    row_index, column_index, date_key, day_number, grade, today_key
                )

    def _build_header(self):
        header = tk.Frame(self.inner, bg=BG_PANEL)
        header.pack(fill="x", pady=(0, 10))

        create_secondary_button(header, "<", self.go_previous_month).pack(side="left")

        self.month_label = tk.Label(
            header,
            text="",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        )
        self.month_label.pack(side="left", expand=True)

        create_secondary_button(header, ">", self.go_next_month).pack(side="right")

    def _build_weekday_row(self):
        row = tk.Frame(self.inner, bg=BG_PANEL)
        row.pack(fill="x")

        for column, label in enumerate(WEEKDAY_LABELS):
            tk.Label(
                row,
                text=label,
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_PANEL,
                width=6,
            ).grid(row=0, column=column, sticky="nsew", padx=2, pady=(0, 6))
            row.grid_columnconfigure(column, weight=1)

    def _build_empty_cell(self, row, column):
        """Blank box for days outside the displayed month, to keep grid aligned."""
        empty_box = tk.Frame(
            self.grid_frame,
            bg=CALENDAR_EMPTY_BG,
            width=DAY_BOX_WIDTH,
            height=DAY_BOX_HEIGHT,
        )
        empty_box.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)

    def _build_day_cell(self, row, column, date_key, day_number, grade, today_key):
        is_selected = date_key == self.selected_date_key
        is_today = date_key == today_key

        box_bg = CALENDAR_TODAY_BG if is_today else CALENDAR_DAY_BG
        border_color = ACCENT_AMBER if is_selected else BORDER_MUTED
        border_width = 2 if is_selected else 1

        box = tk.Frame(
            self.grid_frame,
            bg=box_bg,
            width=DAY_BOX_WIDTH,
            height=DAY_BOX_HEIGHT,
            highlightbackground=border_color,
            highlightthickness=border_width,
            cursor="hand2",
        )
        box.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
        box.pack_propagate(False)

        day_label = tk.Label(
            box,
            text=str(day_number),
            font=FONT_CALENDAR_DAY,
            fg=ACCENT_AMBER if is_today else TEXT_PRIMARY,
            bg=box_bg,
        )
        day_label.pack(anchor="w", padx=6, pady=(4, 0))

        grade_text = grade["letter"] if grade else "--"
        grade_label = tk.Label(
            box,
            text=grade_text,
            font=FONT_CALENDAR_GRADE,
            fg=ACCENT_AMBER if grade else TEXT_SECONDARY,
            bg=box_bg,
            wraplength=DAY_BOX_WIDTH - 12,
            justify="left",
        )
        grade_label.pack(anchor="w", padx=6, pady=(0, 4))

        # Re-wrap the grade text whenever the box is resized, so it never
        # overflows the box at smaller window sizes or gets stuck tiny at
        # larger ones.
        box.bind(
            "<Configure>",
            lambda event, label=grade_label: label.config(
                wraplength=max(event.width - 12, 30)
            ),
        )

        # Clicking anywhere on the box or its labels selects that day.
        for widget in (box, day_label, grade_label):
            widget.bind("<Button-1>", lambda event, key=date_key: self._select_day(key))

    def _select_day(self, date_key):
        self.selected_date_key = date_key
        self.render()
        self.on_day_selected(date_key)
