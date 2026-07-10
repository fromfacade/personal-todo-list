"""
Focus tab logic for To-Do Grader: the Pomodoro timer, daily study goals,
and studied-time tracking.

Storage access (raw SQL) lives in storage.py; this file turns those rows
into the shapes the Focus tab UI actually needs, the same way habits.py and
stats.py sit on top of storage.py for their own areas.
"""

import calendar as calendar_module
from datetime import datetime, timedelta

from storage import (
    add_focus_session,
    get_focus_goal,
    get_focus_goals_between_dates,
    get_studied_minutes_between_dates,
    get_studied_minutes_for_date,
    get_today_key,
    set_focus_goal,
)

FOCUS_MINUTES = 25
BREAK_MINUTES = 5
FOCUS_SECONDS = FOCUS_MINUTES * 60
BREAK_SECONDS = BREAK_MINUTES * 60


class PomodoroTimer:
    """A small countdown timer with focus and break modes."""

    def __init__(self, on_tick=None):
        self.on_tick = on_tick
        self.mode = "focus"
        self.remaining_seconds = FOCUS_SECONDS
        self.running = False
        self._after_id = None
        self._root = None

    def get_mode_label(self):
        if self.mode == "focus":
            return "Focus"
        return "Break"

    def format_time(self):
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def start(self, root):
        """Start or resume the countdown."""
        self._root = root

        if self.running:
            return

        self.running = True
        self._schedule_tick()

    def pause(self):
        """Pause the countdown."""
        self.running = False

        if self._root is not None and self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None

    def reset(self):
        """Reset the timer back to the default for the current mode."""
        self.pause()
        self.remaining_seconds = (
            FOCUS_SECONDS if self.mode == "focus" else BREAK_SECONDS
        )
        self._notify()

    def switch_mode(self, mode):
        """Switch between focus and break modes."""
        if mode not in ("focus", "break"):
            return

        self.pause()
        self.mode = mode
        self.remaining_seconds = (
            FOCUS_SECONDS if mode == "focus" else BREAK_SECONDS
        )
        self._notify()

    def _schedule_tick(self):
        if self._root is None:
            return

        self._after_id = self._root.after(1000, self._tick)

    def _tick(self):
        if not self.running:
            return

        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._notify()
            self._schedule_tick()
            return

        # Timer finished: automatically switch to the next mode.
        self.running = False
        next_mode = "break" if self.mode == "focus" else "focus"
        self.switch_mode(next_mode)
        self._notify(finished=True)

    def _notify(self, finished=False):
        if self.on_tick is not None:
            self.on_tick(self, finished)


# --- Study goals ---


def set_study_goal(conn, goal_minutes, date_key=None):
    """Set (or replace) the study goal, in minutes, for a date."""
    if date_key is None:
        date_key = get_today_key()

    if goal_minutes <= 0:
        raise ValueError("Study goal must be a whole number of minutes greater than 0.")

    set_focus_goal(conn, date_key, goal_minutes)


def get_study_goal(conn, date_key=None):
    """Return the goal_minutes for a date, or None if no goal was set."""
    if date_key is None:
        date_key = get_today_key()

    goal = get_focus_goal(conn, date_key)
    return goal["goal_minutes"] if goal else None


# --- Sessions / studied time ---


def record_focus_session(conn, duration_minutes, date_key=None):
    """Log a completed focus block's minutes toward that day's studied time."""
    if date_key is None:
        date_key = get_today_key()

    now = datetime.now()
    started_at = (now - timedelta(minutes=duration_minutes)).isoformat(timespec="seconds")
    ended_at = now.isoformat(timespec="seconds")

    return add_focus_session(
        conn, date_key, duration_minutes, started_at=started_at, ended_at=ended_at
    )


def get_daily_focus_summary(conn, date_key=None):
    """Studied minutes, goal, and whether the goal was met for one day."""
    if date_key is None:
        date_key = get_today_key()

    studied_minutes = get_studied_minutes_for_date(conn, date_key)
    goal_minutes = get_study_goal(conn, date_key)
    goal_met = goal_minutes is not None and studied_minutes >= goal_minutes

    return {
        "date_key": date_key,
        "studied_minutes": studied_minutes,
        "goal_minutes": goal_minutes,
        "goal_met": goal_met,
    }


def get_month_focus_summary(conn, year, month):
    """
    Return {date_key: {studied_minutes, goal_minutes, goal_met}} for every
    day in the given month that has either a goal or at least one session.
    Used by the Focus calendar so it does not need to query day-by-day.
    """
    start_date_key = f"{year:04d}-{month:02d}-01"
    last_day = calendar_module.monthrange(year, month)[1]
    end_date_key = f"{year:04d}-{month:02d}-{last_day:02d}"

    studied_by_date = get_studied_minutes_between_dates(conn, start_date_key, end_date_key)
    goals_by_date = get_focus_goals_between_dates(conn, start_date_key, end_date_key)

    all_date_keys = set(studied_by_date) | set(goals_by_date)
    summary = {}

    for date_key in all_date_keys:
        studied_minutes = studied_by_date.get(date_key, 0)
        goal_minutes = goals_by_date.get(date_key)
        summary[date_key] = {
            "studied_minutes": studied_minutes,
            "goal_minutes": goal_minutes,
            "goal_met": goal_minutes is not None and studied_minutes >= goal_minutes,
        }

    return summary


# --- Display formatting ---


def format_studied_time(minutes):
    """Human-friendly studied time, e.g. '45 min' or '2.0h'."""
    if minutes >= 60:
        return f"{minutes / 60:.1f}h"

    return f"{minutes} min"


def format_focus_day_cell_text(day_summary):
    """Compact text for one Focus calendar day box."""
    if day_summary is None:
        return "--"

    studied_minutes = day_summary["studied_minutes"]
    goal_minutes = day_summary["goal_minutes"]

    if goal_minutes is None:
        if studied_minutes <= 0:
            return "--"
        return format_studied_time(studied_minutes)

    if day_summary["goal_met"]:
        return "Goal met"

    return f"{studied_minutes}/{goal_minutes}m"
