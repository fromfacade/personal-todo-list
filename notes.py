"""
Notes tab logic for To-Do Grader: a single free-text daily notepad entry
per date, plus the note-date lookup used by the Notes calendar's per-day
indicator.

Storage access (raw SQL) lives in storage.py; this file turns those rows
into the shapes the Notes tab UI needs, the same way habits.py and focus.py
sit on top of storage.py for their own areas.
"""

import calendar as calendar_module

from storage import (
    get_daily_note_row,
    get_note_dates_between_dates,
    get_today_key,
    save_daily_note_row,
)


def get_daily_note(conn, date_key=None):
    """Return the saved notepad row for date_key, or None if nothing's been saved yet."""
    if date_key is None:
        date_key = get_today_key()

    return get_daily_note_row(conn, date_key)


def save_daily_note(conn, date_key, body):
    """
    Create or update the single notepad entry for date_key. There is at
    most one row per date_key (enforced by the UNIQUE constraint on
    daily_notes.date_key) - editing the same date again updates that row
    in place rather than creating a duplicate, so its id stays stable.
    """
    return save_daily_note_row(conn, date_key, body)


def get_note_dates_for_month(conn, year, month):
    """Return the set of date_keys in the given month that have a saved (non-empty) note."""
    start_date_key = f"{year:04d}-{month:02d}-01"
    last_day = calendar_module.monthrange(year, month)[1]
    end_date_key = f"{year:04d}-{month:02d}-{last_day:02d}"

    return get_note_dates_between_dates(conn, start_date_key, end_date_key)
