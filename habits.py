"""
Habit-related logic for To-Do Grader.

Habits are stored in the habits table. Which days a habit is active on is
stored in habit_schedule (0=Monday..6=Sunday, same as Python's date.weekday()).
Completing a habit for a day is stored in habit_completions, keyed by
(habit_id, date_key), so a scheduled-but-not-done habit can still count as
"possible points" for a day even before it is ever completed.
"""

from storage import (
    add_habit,
    delete_habit,
    get_all_habits,
    get_habit_by_id,
    get_habit_completion,
    get_scheduled_habits_for_date,
    get_today_key,
    set_habit_completion,
    set_habit_schedule,
    update_habit,
)

WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
WEEKDAY_SHORT_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_weekday_schedule(weekdays):
    """Turn a list of weekday ints (0=Monday..6=Sunday) into 'Mon, Wed, Fri'."""
    if not weekdays:
        return "No days scheduled"

    return ", ".join(WEEKDAY_SHORT_NAMES[day] for day in sorted(weekdays))


def create_habit(conn, title, difficulty="medium", weekdays=None):
    """Add a new active habit and set its scheduled weekdays (if any)."""
    habit = add_habit(conn, title, difficulty)

    if weekdays:
        set_habit_schedule(conn, habit["id"], weekdays)
        habit["weekdays"] = sorted(set(weekdays))
    else:
        habit["weekdays"] = []

    return habit


def edit_habit(conn, habit_id, title=None, difficulty=None, weekdays=None):
    """Update a habit's title/difficulty and, if given, its scheduled weekdays."""
    habit = update_habit(conn, habit_id, title=title, difficulty=difficulty)

    if weekdays is not None:
        set_habit_schedule(conn, habit_id, weekdays)

    return habit


def remove_habit(conn, habit_id):
    """Soft-delete a habit without removing its past completion records."""
    delete_habit(conn, habit_id)


def list_habits(conn):
    """Return all active habits, each including its scheduled weekdays."""
    return get_all_habits(conn, active_only=True)


def get_habits_for_date(conn, date_key=None):
    """Return active habits scheduled for date_key's weekday, with completion status."""
    if date_key is None:
        date_key = get_today_key()

    return get_scheduled_habits_for_date(conn, date_key)


def is_habit_completed_on_date(conn, habit_id, date_key=None):
    """Check whether a habit has a completion record marked done for the date."""
    if date_key is None:
        date_key = get_today_key()

    completion = get_habit_completion(conn, habit_id, date_key)

    if completion is None:
        return False

    return completion["completed"]


def complete_habit_on_date(conn, habit_id, date_key=None):
    """Mark a habit complete for a date."""
    if date_key is None:
        date_key = get_today_key()

    habit = get_habit_by_id(conn, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    set_habit_completion(conn, habit_id, date_key, completed=True)


def uncomplete_habit_on_date(conn, habit_id, date_key=None):
    """Mark a habit incomplete for a date."""
    if date_key is None:
        date_key = get_today_key()

    habit = get_habit_by_id(conn, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    set_habit_completion(conn, habit_id, date_key, completed=False)


def toggle_habit_on_date(conn, habit_id, completed, date_key=None):
    """Set a habit's completion state for a specific date."""
    if completed:
        complete_habit_on_date(conn, habit_id, date_key)
    else:
        uncomplete_habit_on_date(conn, habit_id, date_key)
