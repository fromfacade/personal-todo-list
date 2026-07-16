"""
Habit rotation logic for To-Do Grader.

A "rotation" is a cycle-based routine (e.g. a 4-day workout split: Chest,
Back and Biceps, Legs, Rest) that repeats forever from an anchor date,
instead of being tied to specific weekdays like habits.py's weekday
schedule. Both systems can be active at the same time - see habits.py for
the weekday version.

Cycle math: for any date, the applicable cycle item is

    days_since_anchor = date - anchor_date
    cycle_index = days_since_anchor % cycle_length

item #1 in the list lands exactly on the anchor date, item #2 the day
after, and so on, wrapping back to item #1 once the cycle finishes. This
also works for dates before the anchor, since Python's modulo of a
negative day count still returns a value in [0, cycle_length). See
storage.get_cycle_index for the implementation.

Rest days: a cycle item flagged is_rest_day is always stored with
points = 0, regardless of its difficulty. That makes a rest day show up
and stay completable (for the user's own tracking) without it ever
counting against the day's grade or breaking a streak - see
storage.get_daily_completion_status, which excludes zero-point items from
its "all completed" check.
"""

from datetime import date, timedelta

from storage import (
    add_habit_rotation,
    delete_habit_rotation,
    get_active_habit_rotations,
    get_cycle_index,
    get_habit_rotation_by_id,
    get_habit_rotation_items,
    get_points,
    get_today_key,
    set_habit_rotation_completion,
    set_habit_rotation_items,
    update_habit_rotation,
)

WEEKDAY_SHORT_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# How many days ahead the Habits tab preview shows by default.
DEFAULT_PREVIEW_DAYS = 14


def _prepare_rotation_item(item):
    """Normalize one cycle-item dict and derive its points from difficulty,
    forcing rest days to 0 points (see module docstring)."""
    title = (item.get("title") or "").strip()

    if not title:
        raise ValueError("Every cycle day needs a title.")

    is_rest_day = bool(item.get("is_rest_day"))
    difficulty = item.get("difficulty") or "medium"

    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    points = 0 if is_rest_day else get_points(difficulty)

    return {
        "title": title,
        "difficulty": difficulty,
        "points": points,
        "is_rest_day": is_rest_day,
    }


def create_rotation(conn, name, anchor_date, items):
    """
    Create a new rotation. items is an ordered list of dicts:
    {title, difficulty, is_rest_day}. Raises ValueError on bad input.
    """
    if not items:
        raise ValueError("A rotation needs at least one cycle day.")

    prepared_items = [_prepare_rotation_item(item) for item in items]
    rotation = add_habit_rotation(conn, name, anchor_date)
    set_habit_rotation_items(conn, rotation["id"], prepared_items)

    return get_rotation_with_items(conn, rotation["id"])


def edit_rotation(conn, rotation_id, name=None, anchor_date=None, items=None):
    """Update a rotation's name/anchor date and, if given, replace its cycle items."""
    update_habit_rotation(conn, rotation_id, name=name, anchor_date=anchor_date)

    if items is not None:
        if not items:
            raise ValueError("A rotation needs at least one cycle day.")

        prepared_items = [_prepare_rotation_item(item) for item in items]
        set_habit_rotation_items(conn, rotation_id, prepared_items)

    return get_rotation_with_items(conn, rotation_id)


def remove_rotation(conn, rotation_id):
    """Soft-delete a rotation without removing its past completion records."""
    delete_habit_rotation(conn, rotation_id)


def list_rotations(conn):
    """Return all active rotations, each including its ordered cycle items."""
    return [
        get_rotation_with_items(conn, rotation["id"])
        for rotation in get_active_habit_rotations(conn)
    ]


def get_rotation_with_items(conn, rotation_id):
    """Return one rotation dict with an "items" list attached, or None."""
    rotation = get_habit_rotation_by_id(conn, rotation_id)

    if rotation is None:
        return None

    rotation["items"] = get_habit_rotation_items(conn, rotation_id)
    return rotation


def get_rotation_item_for_date(rotation_items, anchor_date, date_key):
    """Return whichever cycle item applies to date_key (see module docstring)."""
    if not rotation_items:
        return None

    cycle_index = get_cycle_index(anchor_date, date_key, len(rotation_items))
    return rotation_items[cycle_index]


def get_upcoming_rotation_schedule(rotation, num_days=DEFAULT_PREVIEW_DAYS, start_date_key=None):
    """
    Preview a rotation's schedule for num_days starting at start_date_key
    (today by default). Each entry has date_key, weekday_short,
    display_date ("Jul 13"), title, and is_rest_day - ready for the Habits
    tab's upcoming-schedule preview.
    """
    if start_date_key is None:
        start_date_key = get_today_key()

    start_date = date.fromisoformat(start_date_key)
    schedule = []

    for offset in range(num_days):
        day = start_date + timedelta(days=offset)
        day_key = str(day)
        item = get_rotation_item_for_date(rotation["items"], rotation["anchor_date"], day_key)

        schedule.append({
            "date_key": day_key,
            "weekday_short": WEEKDAY_SHORT_NAMES[day.weekday()],
            "display_date": day.strftime("%b %d"),
            "title": item["title"] if item else "--",
            "is_rest_day": item["is_rest_day"] if item else False,
        })

    return schedule


def toggle_rotation_item_on_date(conn, rotation_id, rotation_item_id, completed, date_key=None):
    """Set a rotation's completion state for whichever item applies on date_key."""
    if date_key is None:
        date_key = get_today_key()

    set_habit_rotation_completion(conn, rotation_id, rotation_item_id, date_key, completed)
