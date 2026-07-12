"""
Monthly calendar components used by the Daily Planner and Focus tabs.

CalendarGradeView shows a letter grade per day and lets the user click a
day to select it. FocusCalendarView shows studied minutes/goal progress per
day as a read-only history view. Both share the same header/weekday-row/
empty-cell building blocks so the layout code is not duplicated.
"""

import calendar as calendar_module
import tkinter as tk
from datetime import date

from focus import format_focus_day_cell_text
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
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_card,
    create_secondary_button,
)

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_BOX_WIDTH = 74
# Kept fairly compact vertically since a month can span up to 6 rows and
# this whole calendar sits above other content on the same page.
DAY_BOX_HEIGHT = 46


def _build_month_nav_header(parent, go_previous, go_next):
    """Card header with < month name > navigation. Returns the month label."""
    header = tk.Frame(parent, bg=BG_PANEL)
    header.pack(fill="x", pady=(0, 10))

    create_secondary_button(header, "<", go_previous).pack(side="left")

    month_label = tk.Label(
        header,
        text="",
        font=FONT_SUBHEADING,
        fg=TEXT_PRIMARY,
        bg=BG_PANEL,
    )
    month_label.pack(side="left", expand=True)

    create_secondary_button(header, ">", go_next).pack(side="right")

    return month_label


def _build_weekday_header_row(parent):
    """Row of Mon..Sun labels above the day grid."""
    row = tk.Frame(parent, bg=BG_PANEL)
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


def _build_empty_day_cell(grid_frame, row, column):
    """Blank box for days outside the displayed month, to keep the grid aligned."""
    empty_box = tk.Frame(
        grid_frame,
        bg=CALENDAR_EMPTY_BG,
        width=DAY_BOX_WIDTH,
        height=DAY_BOX_HEIGHT,
    )
    empty_box.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)


def _configure_grid_weights(grid_frame, week_count):
    """Equal column/row weights so the grid stretches evenly when resized."""
    for column in range(7):
        grid_frame.grid_columnconfigure(column, weight=1)

    for row_index in range(week_count):
        grid_frame.grid_rowconfigure(row_index, weight=1)


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

        self.month_label = _build_month_nav_header(
            self.inner, self.go_previous_month, self.go_next_month
        )
        _build_weekday_header_row(self.inner)

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

        _configure_grid_weights(self.grid_frame, len(month_weeks))

        for row_index, week in enumerate(month_weeks):
            for column_index, day_number in enumerate(week):
                if day_number == 0:
                    _build_empty_day_cell(self.grid_frame, row_index, column_index)
                    continue

                date_key = (
                    f"{self.displayed_year:04d}-"
                    f"{self.displayed_month:02d}-{day_number:02d}"
                )
                grade = grades_by_date.get(date_key)
                self._build_day_cell(
                    row_index, column_index, date_key, day_number, grade, today_key
                )

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

        grade_text, grade_color = self._get_grade_cell_text_and_color(date_key, today_key, grade)
        grade_label = tk.Label(
            box,
            text=grade_text,
            font=FONT_CALENDAR_GRADE,
            fg=grade_color,
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

    def _get_grade_cell_text_and_color(self, date_key, today_key, grade):
        """
        Decide what the day box's grade line should show.

        Only days that have fully passed show a final letter grade. Future
        dates have no completed history yet, and today is still in progress
        (tasks/habits can still be checked off), so neither should display a
        misleading final grade - only the actual calendar date (via real
        date objects, not string comparison) decides which case applies.
        """
        day_date = date.fromisoformat(date_key)
        today_date = date.fromisoformat(today_key)

        if day_date > today_date:
            return "--", TEXT_SECONDARY

        if day_date == today_date:
            return "Today", TEXT_SECONDARY

        grade_text = grade["letter"] if grade else "--"
        grade_color = ACCENT_AMBER if grade else TEXT_SECONDARY
        return grade_text, grade_color

    def _select_day(self, date_key):
        self.selected_date_key = date_key
        self.render()
        self.on_day_selected(date_key)


class FocusCalendarView:
    """
    A read-only monthly calendar showing studied minutes and goal progress
    for each day. Unlike CalendarGradeView, days are not clickable - this
    is a history/overview panel for the Focus tab, not a date picker.
    """

    def __init__(self, parent, get_month_focus_summary, initial_date_key):
        self.get_month_focus_summary = get_month_focus_summary

        initial_date = date.fromisoformat(initial_date_key)
        self.displayed_year = initial_date.year
        self.displayed_month = initial_date.month

        self.card, self.inner = create_card(parent, padding=14)

        self.month_label = _build_month_nav_header(
            self.inner, self.go_previous_month, self.go_next_month
        )
        _build_weekday_header_row(self.inner)

        self.grid_frame = tk.Frame(self.inner, bg=BG_PANEL)
        self.grid_frame.pack(fill="both", expand=True)

        self.render()

    def get_widget(self):
        return self.card

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

        summary_by_date = self.get_month_focus_summary(self.displayed_year, self.displayed_month)
        today_key = str(date.today())

        month_weeks = calendar_module.Calendar(firstweekday=0).monthdayscalendar(
            self.displayed_year, self.displayed_month
        )

        _configure_grid_weights(self.grid_frame, len(month_weeks))

        for row_index, week in enumerate(month_weeks):
            for column_index, day_number in enumerate(week):
                if day_number == 0:
                    _build_empty_day_cell(self.grid_frame, row_index, column_index)
                    continue

                date_key = (
                    f"{self.displayed_year:04d}-"
                    f"{self.displayed_month:02d}-{day_number:02d}"
                )
                day_summary = summary_by_date.get(date_key)
                self._build_day_cell(
                    row_index, column_index, date_key, day_number, day_summary, today_key
                )

    def _build_day_cell(self, row, column, date_key, day_number, day_summary, today_key):
        is_today = date_key == today_key
        goal_met = day_summary is not None and day_summary["goal_met"]
        has_activity = day_summary is not None and day_summary["studied_minutes"] > 0

        if goal_met:
            box_bg = "#1a3d1a"
            border_color = SUCCESS
            border_width = 2
        elif is_today:
            box_bg = CALENDAR_TODAY_BG
            border_color = BORDER_MUTED
            border_width = 1
        else:
            box_bg = CALENDAR_DAY_BG if has_activity else CALENDAR_EMPTY_BG
            border_color = BORDER_MUTED
            border_width = 1

        box = tk.Frame(
            self.grid_frame,
            bg=box_bg,
            width=DAY_BOX_WIDTH,
            height=DAY_BOX_HEIGHT,
            highlightbackground=border_color,
            highlightthickness=border_width,
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

        cell_text = format_focus_day_cell_text(day_summary)
        if goal_met:
            text_color = SUCCESS
        elif has_activity:
            text_color = ACCENT_AMBER
        else:
            text_color = TEXT_SECONDARY

        info_label = tk.Label(
            box,
            text=cell_text,
            font=FONT_CALENDAR_GRADE,
            fg=text_color,
            bg=box_bg,
            wraplength=DAY_BOX_WIDTH - 12,
            justify="left",
        )
        info_label.pack(anchor="w", padx=6, pady=(0, 4))

        box.bind(
            "<Configure>",
            lambda event, label=info_label: label.config(
                wraplength=max(event.width - 12, 30)
            ),
        )


class NotesCalendarView:
    """
    A monthly calendar grid for the Notes tab's daily notepad. Clicking a
    day selects it (like CalendarGradeView), and each day shows a small
    amber "Note" mark if a notepad entry has been saved for it - there is
    at most one note per day, so this is just a has-note indicator, not a
    count.

    get_month_note_dates(year, month) must return a collection (set/list/
    dict) of date_keys that have a saved note for that month.
    on_day_selected(date_key) is called whenever the user clicks a day box.
    """

    def __init__(self, parent, get_month_note_dates, on_day_selected, initial_date_key):
        self.get_month_note_dates = get_month_note_dates
        self.on_day_selected = on_day_selected
        self.selected_date_key = initial_date_key

        selected_date = date.fromisoformat(initial_date_key)
        self.displayed_year = selected_date.year
        self.displayed_month = selected_date.month

        self.card, self.inner = create_card(parent, padding=14)

        self.month_label = _build_month_nav_header(
            self.inner, self.go_previous_month, self.go_next_month
        )
        _build_weekday_header_row(self.inner)

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

        note_dates = self.get_month_note_dates(self.displayed_year, self.displayed_month)
        today_key = str(date.today())

        month_weeks = calendar_module.Calendar(firstweekday=0).monthdayscalendar(
            self.displayed_year, self.displayed_month
        )

        _configure_grid_weights(self.grid_frame, len(month_weeks))

        for row_index, week in enumerate(month_weeks):
            for column_index, day_number in enumerate(week):
                if day_number == 0:
                    _build_empty_day_cell(self.grid_frame, row_index, column_index)
                    continue

                date_key = (
                    f"{self.displayed_year:04d}-"
                    f"{self.displayed_month:02d}-{day_number:02d}"
                )
                has_note = date_key in note_dates
                self._build_day_cell(
                    row_index, column_index, date_key, day_number, has_note, today_key
                )

    def _build_day_cell(self, row, column, date_key, day_number, has_note, today_key):
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

        if has_note:
            note_text = "\u25cf Note"
            note_color = ACCENT_AMBER
        else:
            note_text = "--"
            note_color = TEXT_SECONDARY

        note_label = tk.Label(
            box,
            text=note_text,
            font=FONT_CALENDAR_GRADE,
            fg=note_color,
            bg=box_bg,
            wraplength=DAY_BOX_WIDTH - 12,
            justify="left",
        )
        note_label.pack(anchor="w", padx=6, pady=(0, 4))

        box.bind(
            "<Configure>",
            lambda event, label=note_label: label.config(
                wraplength=max(event.width - 12, 30)
            ),
        )

        for widget in (box, day_label, note_label):
            widget.bind("<Button-1>", lambda event, key=date_key: self._select_day(key))

    def _select_day(self, date_key):
        self.selected_date_key = date_key
        self.render()
        self.on_day_selected(date_key)
