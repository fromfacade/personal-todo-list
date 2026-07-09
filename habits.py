"""
Habit-related logic for To-Do Grader.

Habits are stored in the habits table. Completing a habit for a day
creates or updates a normal task row linked by recurring_task_id.
That keeps habits compatible with grading and stats.
"""

from storage import (
    add_habit,
    delete_habit,
    get_all_habits,
    get_habit_by_id,
    get_habit_task_for_date,
    get_today_key,
    set_habit_completion_for_date,
)


def create_habit(conn, title, difficulty="medium"):
    """Add a new active habit."""
    return add_habit(conn, title, difficulty)


def remove_habit(conn, habit_id):
    """Soft-delete a habit without removing its past completion records."""
    delete_habit(conn, habit_id)


def list_habits(conn):
    """Return all active habits."""
    return get_all_habits(conn, active_only=True)


def is_habit_completed_on_date(conn, habit_id, date_key=None):
    """Check whether a habit has a completed task record for the given date."""
    if date_key is None:
        date_key = get_today_key()

    task = get_habit_task_for_date(conn, habit_id, date_key)

    if task is None:
        return False

    return task["completed"]


def complete_habit_on_date(conn, habit_id, date_key=None):
    """Mark a habit complete for a date by syncing to the tasks table."""
    if date_key is None:
        date_key = get_today_key()

    habit = get_habit_by_id(conn, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    set_habit_completion_for_date(conn, habit_id, date_key, completed=True)


def uncomplete_habit_on_date(conn, habit_id, date_key=None):
    """Mark a habit incomplete for a date."""
    if date_key is None:
        date_key = get_today_key()

    habit = get_habit_by_id(conn, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    set_habit_completion_for_date(conn, habit_id, date_key, completed=False)


def toggle_habit_on_date(conn, habit_id, completed, date_key=None):
    """Set a habit's completion state for a specific date."""
    if completed:
        complete_habit_on_date(conn, habit_id, date_key)
    else:
        uncomplete_habit_on_date(conn, habit_id, date_key)
