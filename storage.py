import json
import os
import sqlite3
from datetime import date, timedelta

DB_FILE = "todo_grader.db"
OLD_JSON_FILE = "tasks.json"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table_name):
    """Return True if a table already exists in the database."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(conn, table_name, column_name):
    """Return True if a column exists on a table (used for safe migrations)."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cursor.fetchall())


def ensure_column(conn, table_name, column_name, column_definition):
    """
    Add a missing column without recreating the table.
    This keeps existing rows and avoids wiping user data.
    """
    if not column_exists(conn, table_name, column_name):
        cursor = conn.cursor()
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
        conn.commit()


def run_migrations(conn):
    """
    Apply safe schema updates for older databases.
    New installs get the full schema from CREATE TABLE statements.
    """
    # Extra task columns for older databases that predate rollover/habits support.
    if table_exists(conn, "tasks"):
        ensure_column(conn, "tasks", "rolled_over_from", "INTEGER")
        ensure_column(conn, "tasks", "recurring_task_id", "INTEGER")

    # Older databases used to store habit completions as task rows linked by
    # recurring_task_id. Copy those into the new habit_completions table so
    # old history is not lost, then the tasks side is ignored going forward
    # (see get_tasks_for_date/get_tasks_between_dates) to avoid double-counting.
    if table_exists(conn, "tasks") and table_exists(conn, "habit_completions"):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habit_completions (habit_id, date_key, completed, completed_at)
            SELECT recurring_task_id, date_key, completed, created_at
            FROM tasks
            WHERE recurring_task_id IS NOT NULL
            ON CONFLICT(habit_id, date_key) DO NOTHING
        """)
        conn.commit()

    # Rank reset / prestige support: extra user_progress columns for older
    # databases. All additive (ALTER TABLE ADD COLUMN) so existing
    # total_exp/current_rank and every other table are left untouched.
    if table_exists(conn, "user_progress"):
        ensure_column(conn, "user_progress", "prestige_count", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "user_progress", "progression_epoch", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "user_progress", "last_reset_at", "TEXT")
        ensure_column(conn, "user_progress", "last_prestige_at", "TEXT")

    # exp_events needs progression_epoch folded into its UNIQUE constraint
    # (not just a new column) so a rank reset/prestige can let the same
    # task/habit/date grant EXP again without deleting the old event row.
    # SQLite can only change a table's constraints by rebuilding it, so
    # this copies every existing row across untouched (tagged epoch 0) -
    # it only runs once, the first time an older database is opened after
    # this update, and skips entirely on already-migrated or brand-new DBs.
    if table_exists(conn, "exp_events") and not column_exists(conn, "exp_events", "progression_epoch"):
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE exp_events RENAME TO exp_events_pre_epoch")
        cursor.execute("""
            CREATE TABLE exp_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_key TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL DEFAULT 0,
                exp_amount INTEGER NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                progression_epoch INTEGER NOT NULL DEFAULT 0,
                UNIQUE(source_type, source_id, date_key, progression_epoch)
            )
        """)
        cursor.execute("""
            INSERT INTO exp_events (
                id, date_key, source_type, source_id, exp_amount,
                description, created_at, progression_epoch
            )
            SELECT id, date_key, source_type, source_id, exp_amount,
                   description, created_at, 0
            FROM exp_events_pre_epoch
        """)
        cursor.execute("DROP TABLE exp_events_pre_epoch")
        conn.commit()


def initialize_database(conn):
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date_key TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            points INTEGER NOT NULL DEFAULT 2,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            rolled_over_from INTEGER,
            recurring_task_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'medium',
            points INTEGER NOT NULL DEFAULT 2,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Which weekdays a habit is scheduled for. weekday matches Python's
    # date.weekday(): 0 = Monday ... 6 = Sunday.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            UNIQUE(habit_id, weekday)
        )
    """)

    # One row per habit per day it was marked complete/incomplete. Kept
    # separate from tasks so scheduled-but-not-yet-completed habits can still
    # count as "possible points" for a day without needing a task row.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            date_key TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            UNIQUE(habit_id, date_key)
        )
    """)

    # Single-row table holding the user's overall EXP/rank progress.
    # id is always 1 - there is only ever one row. prestige_count and
    # progression_epoch support the rank-reset/prestige feature:
    # progression_epoch increases each time the user resets or prestiges,
    # so old exp_events stay in the table as history without counting
    # toward whether a task/habit/date can grant EXP again.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY,
            total_exp INTEGER NOT NULL DEFAULT 0,
            current_rank TEXT NOT NULL DEFAULT 'F-',
            prestige_count INTEGER NOT NULL DEFAULT 0,
            progression_epoch INTEGER NOT NULL DEFAULT 0,
            last_reset_at TEXT,
            last_prestige_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # One row per EXP grant. The UNIQUE constraint is what stops the same
    # completion from granting EXP more than once: source_id is the task or
    # habit id (or 0 for day-level bonuses not tied to a specific row), and
    # source_type distinguishes task/habit/focus_goal_bonus/daily_grade_bonus.
    # progression_epoch is part of that constraint too, so a rank
    # reset/prestige (which bumps the epoch) lets the same source grant EXP
    # again under the new epoch, while its old event row stays as history.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL DEFAULT 0,
            exp_amount INTEGER NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            progression_epoch INTEGER NOT NULL DEFAULT 0,
            UNIQUE(source_type, source_id, date_key, progression_epoch)
        )
    """)

    # One study-minutes goal per day. UNIQUE(date_key) keeps "set the goal
    # again" an update instead of a second row.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS focus_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key TEXT NOT NULL UNIQUE,
            goal_minutes INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # One row per completed focus block. Studied time for a day is just the
    # sum of duration_minutes for that date_key - no separate running total
    # to keep in sync.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            started_at TEXT,
            ended_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # A single free-text daily notepad entry per date. UNIQUE(date_key) is
    # what keeps this "one note per day" - saving the same date again
    # updates that row (see save_daily_note_row's upsert) instead of
    # creating a duplicate, and also gives this column its own index for
    # free. AUTOINCREMENT keeps id stable and never reused even after an
    # update, which is what would let a future feature reference one note
    # from another without ids shifting around.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key TEXT NOT NULL UNIQUE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_date
        ON tasks(date_key)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_focus_sessions_date
        ON focus_sessions(date_key)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_rollover
        ON tasks(date_key, rolled_over_from)
    """)

    conn.commit()
    run_migrations(conn)


def get_metadata(conn, key):
    cursor = conn.cursor()

    cursor.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (key,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return row["value"]


def set_metadata(conn, key, value):
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO app_metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))

    conn.commit()


def migrate_json_to_sqlite(conn):
    already_migrated = get_metadata(conn, "json_migrated")

    if already_migrated == "true":
        return

    if not os.path.exists(OLD_JSON_FILE):
        set_metadata(conn, "json_migrated", "true")
        return

    try:
        with open(OLD_JSON_FILE, "r") as file:
            old_data = json.load(file)
    except json.JSONDecodeError:
        print("Warning: tasks.json exists, but it could not be read.")
        set_metadata(conn, "json_migrated", "true")
        return

    cursor = conn.cursor()

    for date_key, tasks in old_data.items():
        if not isinstance(tasks, list):
            continue

        for task in tasks:
            title = task.get("title", "").strip()

            if not title:
                continue

            difficulty = task.get("difficulty", "medium")
            points = task.get("points", get_points(difficulty))
            completed = 1 if task.get("completed", False) else 0

            cursor.execute("""
                INSERT INTO tasks (
                    title,
                    date_key,
                    difficulty,
                    points,
                    completed
                )
                VALUES (?, ?, ?, ?, ?)
            """, (title, date_key, difficulty, points, completed))

    conn.commit()
    set_metadata(conn, "json_migrated", "true")

    print("Migrated tasks.json into todo_grader.db")


def load_data():
    conn = get_connection()
    initialize_database(conn)
    migrate_json_to_sqlite(conn)
    return conn


def save_data(data):
    data.commit()


def get_today_key():
    return str(date.today())


def get_previous_date_key(date_key):
    """Return the ISO date string for the day before date_key."""
    current = date.fromisoformat(date_key)
    return str(current - timedelta(days=1))


def get_points(difficulty):
    if difficulty == "easy":
        return 1
    elif difficulty == "medium":
        return 2
    elif difficulty == "hard":
        return 3

    return 2


def _row_to_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "date_key": row["date_key"],
        "difficulty": row["difficulty"],
        "points": row["points"],
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
        "rolled_over_from": row["rolled_over_from"],
        "recurring_task_id": row["recurring_task_id"],
    }


def get_tasks_for_date(data, date_key=None):
    if date_key is None:
        date_key = get_today_key()

    cursor = data.cursor()

    # recurring_task_id IS NULL excludes old-style habit rows: those are
    # migrated into habit_completions and shown via the habits helpers
    # instead, so including them here would double-count them.
    cursor.execute("""
        SELECT
            id,
            title,
            date_key,
            difficulty,
            points,
            completed,
            created_at,
            rolled_over_from,
            recurring_task_id
        FROM tasks
        WHERE date_key = ? AND recurring_task_id IS NULL
        ORDER BY id
    """, (date_key,))

    return [_row_to_task(row) for row in cursor.fetchall()]


def get_task_by_id(data, task_id):
    cursor = data.cursor()

    cursor.execute("""
        SELECT
            id,
            title,
            date_key,
            difficulty,
            points,
            completed,
            created_at,
            rolled_over_from,
            recurring_task_id
        FROM tasks
        WHERE id = ?
    """, (task_id,))

    row = cursor.fetchone()

    if row is None:
        return None

    return _row_to_task(row)


def add_task_to_date(data, title, difficulty="medium", date_key=None):
    if date_key is None:
        date_key = get_today_key()

    title = title.strip()

    if not title:
        raise ValueError("Task title cannot be empty.")

    if difficulty not in ["easy", "medium", "hard"]:
        difficulty = "medium"

    points = get_points(difficulty)

    cursor = data.cursor()

    cursor.execute("""
        INSERT INTO tasks (
            title,
            date_key,
            difficulty,
            points,
            completed
        )
        VALUES (?, ?, ?, ?, ?)
    """, (title, date_key, difficulty, points, 0))

    data.commit()

    task_id = cursor.lastrowid

    return {
        "id": task_id,
        "title": title,
        "date_key": date_key,
        "difficulty": difficulty,
        "points": points,
        "completed": False,
    }


def get_task_id_by_index(data, task_index, date_key=None):
    tasks = get_tasks_for_date(data, date_key)

    if task_index < 0 or task_index >= len(tasks):
        raise IndexError("Invalid task index.")

    return tasks[task_index]["id"]


def update_task(data, task_id, title=None, difficulty=None):
    """Update a task title and/or difficulty, recalculating points when needed."""
    task = get_task_by_id(data, task_id)

    if task is None:
        raise ValueError("Task not found.")

    new_title = title.strip() if title is not None else task["title"]
    new_difficulty = difficulty if difficulty is not None else task["difficulty"]

    if not new_title:
        raise ValueError("Task title cannot be empty.")

    if new_difficulty not in ["easy", "medium", "hard"]:
        new_difficulty = task["difficulty"]

    new_points = get_points(new_difficulty)

    cursor = data.cursor()

    cursor.execute("""
        UPDATE tasks
        SET title = ?, difficulty = ?, points = ?
        WHERE id = ?
    """, (new_title, new_difficulty, new_points, task_id))

    data.commit()

    return get_task_by_id(data, task_id)


def set_task_completed(data, task_index, completed, date_key=None):
    task_id = get_task_id_by_index(data, task_index, date_key)

    cursor = data.cursor()

    cursor.execute("""
        UPDATE tasks
        SET completed = ?
        WHERE id = ?
    """, (1 if completed else 0, task_id))

    data.commit()


def delete_task_at_index(data, task_index, date_key=None):
    task_id = get_task_id_by_index(data, task_index, date_key)

    cursor = data.cursor()

    cursor.execute("""
        DELETE FROM tasks
        WHERE id = ?
    """, (task_id,))

    data.commit()


def rollover_unfinished_tasks(data, target_date_key=None):
    """
    Copy incomplete tasks from the previous day into the target day.
    Uses rolled_over_from so the same source task is not copied twice.
    """
    if target_date_key is None:
        target_date_key = get_today_key()

    previous_date_key = get_previous_date_key(target_date_key)
    cursor = data.cursor()

    cursor.execute("""
        SELECT id, title, difficulty, points, recurring_task_id
        FROM tasks
        WHERE date_key = ? AND completed = 0 AND recurring_task_id IS NULL
    """, (previous_date_key,))

    source_tasks = cursor.fetchall()
    rolled_count = 0

    for source in source_tasks:
        # Skip if this exact source task was already rolled into the target day.
        cursor.execute("""
            SELECT id
            FROM tasks
            WHERE date_key = ? AND rolled_over_from = ?
        """, (target_date_key, source["id"]))

        if cursor.fetchone() is not None:
            continue

        cursor.execute("""
            INSERT INTO tasks (
                title,
                date_key,
                difficulty,
                points,
                completed,
                rolled_over_from,
                recurring_task_id
            )
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (
            source["title"],
            target_date_key,
            source["difficulty"],
            source["points"],
            source["id"],
            source["recurring_task_id"],
        ))

        rolled_count += 1

    data.commit()
    return rolled_count


# --- Habit storage helpers ---


def _row_to_habit(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "difficulty": row["difficulty"],
        "points": row["points"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
    }


def get_all_habits(data, active_only=True):
    cursor = data.cursor()

    if active_only:
        cursor.execute("""
            SELECT id, title, difficulty, points, active, created_at
            FROM habits
            WHERE active = 1
            ORDER BY id
        """)
    else:
        cursor.execute("""
            SELECT id, title, difficulty, points, active, created_at
            FROM habits
            ORDER BY id
        """)

    habits = [_row_to_habit(row) for row in cursor.fetchall()]

    for habit in habits:
        habit["weekdays"] = get_habit_schedule(data, habit["id"])

    return habits


def get_habit_by_id(data, habit_id):
    cursor = data.cursor()

    cursor.execute("""
        SELECT id, title, difficulty, points, active, created_at
        FROM habits
        WHERE id = ?
    """, (habit_id,))

    row = cursor.fetchone()

    if row is None:
        return None

    return _row_to_habit(row)


def add_habit(data, title, difficulty="medium"):
    title = title.strip()

    if not title:
        raise ValueError("Habit title cannot be empty.")

    if difficulty not in ["easy", "medium", "hard"]:
        difficulty = "medium"

    points = get_points(difficulty)
    cursor = data.cursor()

    cursor.execute("""
        INSERT INTO habits (title, difficulty, points, active)
        VALUES (?, ?, ?, 1)
    """, (title, difficulty, points))

    data.commit()
    return get_habit_by_id(data, cursor.lastrowid)


def delete_habit(data, habit_id):
    """Soft-delete a habit so old completion records stay linked."""
    cursor = data.cursor()

    cursor.execute("""
        UPDATE habits
        SET active = 0
        WHERE id = ?
    """, (habit_id,))

    data.commit()


def update_habit(data, habit_id, title=None, difficulty=None):
    """Update a habit's title and/or difficulty, recalculating points if needed."""
    habit = get_habit_by_id(data, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    new_title = title.strip() if title is not None else habit["title"]
    new_difficulty = difficulty if difficulty is not None else habit["difficulty"]

    if not new_title:
        raise ValueError("Habit title cannot be empty.")

    if new_difficulty not in ["easy", "medium", "hard"]:
        new_difficulty = habit["difficulty"]

    new_points = get_points(new_difficulty)

    cursor = data.cursor()
    cursor.execute("""
        UPDATE habits
        SET title = ?, difficulty = ?, points = ?
        WHERE id = ?
    """, (new_title, new_difficulty, new_points, habit_id))

    data.commit()
    return get_habit_by_id(data, habit_id)


# --- Habit schedule (which weekdays a habit is active on) ---


def get_habit_schedule(data, habit_id):
    """Return the sorted list of weekdays (0=Monday..6=Sunday) for a habit."""
    cursor = data.cursor()

    cursor.execute("""
        SELECT weekday
        FROM habit_schedule
        WHERE habit_id = ?
        ORDER BY weekday
    """, (habit_id,))

    return [row["weekday"] for row in cursor.fetchall()]


def set_habit_schedule(data, habit_id, weekdays):
    """Replace a habit's scheduled weekdays with the given list of ints (0-6)."""
    cleaned_weekdays = sorted({w for w in weekdays if 0 <= w <= 6})

    cursor = data.cursor()
    cursor.execute("DELETE FROM habit_schedule WHERE habit_id = ?", (habit_id,))

    for weekday in cleaned_weekdays:
        cursor.execute("""
            INSERT INTO habit_schedule (habit_id, weekday)
            VALUES (?, ?)
        """, (habit_id, weekday))

    data.commit()


# --- Habit completions (per-date, replaces the old task-row approach) ---


def get_habit_completion(data, habit_id, date_key):
    """Return the completion row for a habit on a date, or None."""
    cursor = data.cursor()

    cursor.execute("""
        SELECT habit_id, date_key, completed, completed_at
        FROM habit_completions
        WHERE habit_id = ? AND date_key = ?
    """, (habit_id, date_key))

    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "habit_id": row["habit_id"],
        "date_key": row["date_key"],
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
    }


def set_habit_completion(data, habit_id, date_key, completed):
    """Create or update a habit's completion state for a specific date."""
    cursor = data.cursor()

    cursor.execute("""
        INSERT INTO habit_completions (habit_id, date_key, completed, completed_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(habit_id, date_key) DO UPDATE SET
            completed = excluded.completed,
            completed_at = excluded.completed_at
    """, (habit_id, date_key, 1 if completed else 0))

    data.commit()


def get_scheduled_habits_for_date(data, date_key):
    """
    Return active habits scheduled for date_key's weekday, shaped like a
    grade-countable item (has "points"/"completed") plus habit identity
    fields, so app.py can render them like task cards.
    """
    weekday = date.fromisoformat(date_key).weekday()
    cursor = data.cursor()

    cursor.execute("""
        SELECT h.id, h.title, h.difficulty, h.points
        FROM habits h
        JOIN habit_schedule hs ON hs.habit_id = h.id
        WHERE h.active = 1 AND hs.weekday = ?
        ORDER BY h.id
    """, (weekday,))

    items = []
    for row in cursor.fetchall():
        completion = get_habit_completion(data, row["id"], date_key)
        items.append({
            "habit_id": row["id"],
            "title": row["title"],
            "difficulty": row["difficulty"],
            "points": row["points"],
            "completed": bool(completion["completed"]) if completion else False,
            "date_key": date_key,
        })

    return items


def get_scheduled_habits_between_dates(data, start_date_key, end_date_key):
    """
    Return {date_key: [habit_item, ...]} for every day in the range that has
    at least one scheduled habit. Used for weekly/monthly grade rollups.
    """
    start = date.fromisoformat(start_date_key)
    end = date.fromisoformat(end_date_key)

    result = {}
    current = start
    while current <= end:
        date_key = str(current)
        habits_today = get_scheduled_habits_for_date(data, date_key)

        if habits_today:
            result[date_key] = habits_today

        current += timedelta(days=1)

    return result


def get_day_grade_items(data, date_key):
    """Tasks plus scheduled habits for one date, ready for calculate_grade."""
    return get_tasks_for_date(data, date_key) + get_scheduled_habits_for_date(data, date_key)


# --- Stats query helpers (raw data for stats.py) ---


def get_tasks_between_dates(data, start_date_key, end_date_key):
    """Return all tasks between two ISO date strings, inclusive."""
    cursor = data.cursor()

    # See get_tasks_for_date for why recurring_task_id rows are excluded.
    cursor.execute("""
        SELECT
            id,
            title,
            date_key,
            difficulty,
            points,
            completed,
            created_at,
            rolled_over_from,
            recurring_task_id
        FROM tasks
        WHERE date_key >= ? AND date_key <= ? AND recurring_task_id IS NULL
        ORDER BY date_key, id
    """, (start_date_key, end_date_key))

    return [_row_to_task(row) for row in cursor.fetchall()]


def get_completed_points_by_date(data, start_date_key, end_date_key):
    """Return {date_key: completed_points} for each day in the range, including
    points from scheduled habits that were completed that day."""
    tasks = get_tasks_between_dates(data, start_date_key, end_date_key)
    points_by_date = {}

    for task in tasks:
        date_key = task["date_key"]
        if date_key not in points_by_date:
            points_by_date[date_key] = 0

        if task["completed"]:
            points_by_date[date_key] += task["points"]

    habits_by_date = get_scheduled_habits_between_dates(data, start_date_key, end_date_key)
    for date_key, habit_items in habits_by_date.items():
        points_by_date.setdefault(date_key, 0)
        for item in habit_items:
            if item["completed"]:
                points_by_date[date_key] += item["points"]

    return points_by_date


def get_daily_completion_status(data, date_key):
    """
    Return completion info for one day, combining tasks and any habits
    scheduled for that weekday. A day counts as fully complete only when it
    has at least one item (task or scheduled habit) and all are done.
    """
    items = get_day_grade_items(data, date_key)

    if not items:
        return {
            "date_key": date_key,
            "has_tasks": False,
            "all_completed": False,
            "total_points": 0,
            "completed_points": 0,
            "completion_percentage": 0,
        }

    total_points = sum(item["points"] for item in items)
    completed_points = sum(
        item["points"] for item in items if item["completed"]
    )

    percentage = round((completed_points / total_points) * 100) if total_points else 0

    return {
        "date_key": date_key,
        "has_tasks": True,
        "all_completed": all(item["completed"] for item in items),
        "total_points": total_points,
        "completed_points": completed_points,
        "completion_percentage": percentage,
    }


# --- EXP / rank progress storage ---
# Rank math itself lives in progression.py; this file only reads/writes the
# raw rows so progression.py stays free of any SQL.


def get_user_progress(data):
    """Return the single user_progress row, creating a default one if missing."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT id, total_exp, current_rank, prestige_count, progression_epoch,
               last_reset_at, last_prestige_at, updated_at
        FROM user_progress
        WHERE id = 1
    """)
    row = cursor.fetchone()

    if row is None:
        cursor.execute("""
            INSERT INTO user_progress (id, total_exp, current_rank)
            VALUES (1, 0, 'F-')
        """)
        data.commit()
        return {
            "total_exp": 0,
            "current_rank": "F-",
            "prestige_count": 0,
            "progression_epoch": 0,
            "last_reset_at": None,
            "last_prestige_at": None,
            "updated_at": None,
        }

    return {
        "total_exp": row["total_exp"],
        "current_rank": row["current_rank"],
        "prestige_count": row["prestige_count"],
        "progression_epoch": row["progression_epoch"],
        "last_reset_at": row["last_reset_at"],
        "last_prestige_at": row["last_prestige_at"],
        "updated_at": row["updated_at"],
    }


def set_user_progress(data, total_exp, current_rank):
    """Overwrite the total EXP/rank on the single user_progress row.

    Only touches total_exp/current_rank - prestige_count and
    progression_epoch (see reset_user_progress/prestige_user_progress)
    are left exactly as they were, since a normal EXP gain should never
    change either of those.
    """
    cursor = data.cursor()
    cursor.execute("""
        INSERT INTO user_progress (id, total_exp, current_rank, updated_at)
        VALUES (1, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            total_exp = excluded.total_exp,
            current_rank = excluded.current_rank,
            updated_at = excluded.updated_at
    """, (total_exp, current_rank))
    data.commit()


def reset_user_progress(data):
    """
    Reset rank/EXP back to the starting point (F-, 0 EXP) without touching
    prestige_count or any other table (tasks, habits, focus, etc. are
    untouched). Bumps progression_epoch so exp_events recorded before the
    reset stay in the table as history but no longer block the same
    task/habit/date from granting EXP again under the new epoch.
    """
    get_user_progress(data)  # make sure the row exists first
    cursor = data.cursor()
    cursor.execute("""
        UPDATE user_progress
        SET total_exp = 0,
            current_rank = 'F-',
            progression_epoch = progression_epoch + 1,
            last_reset_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """)
    data.commit()


def prestige_user_progress(data):
    """
    Reset rank/EXP back to the starting point (like reset_user_progress)
    and add 1 to prestige_count. Returns the new prestige_count.
    """
    get_user_progress(data)  # make sure the row exists first
    cursor = data.cursor()
    cursor.execute("""
        UPDATE user_progress
        SET total_exp = 0,
            current_rank = 'F-',
            prestige_count = prestige_count + 1,
            progression_epoch = progression_epoch + 1,
            last_prestige_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """)
    data.commit()

    return get_user_progress(data)["prestige_count"]


def add_exp_event(
    data, date_key, source_type, source_id, exp_amount, description=None, progression_epoch=0
):
    """
    Record an EXP grant for (source_type, source_id, date_key, progression_epoch).

    Returns True if this was a new grant, or False if an event already
    existed for that exact combination - this is what stops completing and
    un-completing the same task/habit from farming EXP more than once
    within the same progression epoch. Resetting/prestiging bumps the
    epoch, so a task/habit that already granted EXP before a reset can
    grant it again afterwards without touching its old (now-historical)
    event row.
    """
    cursor = data.cursor()
    cursor.execute("""
        INSERT INTO exp_events (
            date_key, source_type, source_id, exp_amount, description, progression_epoch
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, source_id, date_key, progression_epoch) DO NOTHING
    """, (date_key, source_type, source_id, exp_amount, description, progression_epoch))
    data.commit()
    return cursor.rowcount > 0



# --- Focus / study tracking storage ---
# Business logic (formatting, "what counts as goal met") lives in focus.py;
# this file only reads/writes the raw goal and session rows.


def get_focus_goal(data, date_key):
    """Return {date_key, goal_minutes} for a date, or None if no goal was set."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT date_key, goal_minutes
        FROM focus_goals
        WHERE date_key = ?
    """, (date_key,))
    row = cursor.fetchone()

    if row is None:
        return None

    return {"date_key": row["date_key"], "goal_minutes": row["goal_minutes"]}


def set_focus_goal(data, date_key, goal_minutes):
    """Create or update the study goal (in minutes) for a date."""
    cursor = data.cursor()
    cursor.execute("""
        INSERT INTO focus_goals (date_key, goal_minutes, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(date_key) DO UPDATE SET
            goal_minutes = excluded.goal_minutes,
            updated_at = excluded.updated_at
    """, (date_key, goal_minutes))
    data.commit()


def get_focus_goals_between_dates(data, start_date_key, end_date_key):
    """Return {date_key: goal_minutes} for every day in the range that has a goal."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT date_key, goal_minutes
        FROM focus_goals
        WHERE date_key >= ? AND date_key <= ?
    """, (start_date_key, end_date_key))
    return {row["date_key"]: row["goal_minutes"] for row in cursor.fetchall()}


def add_focus_session(data, date_key, duration_minutes, started_at=None, ended_at=None):
    """Record one completed focus block's minutes toward a date's studied time."""
    cursor = data.cursor()
    cursor.execute("""
        INSERT INTO focus_sessions (date_key, duration_minutes, started_at, ended_at)
        VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
    """, (date_key, duration_minutes, started_at, ended_at))
    data.commit()

    return {
        "id": cursor.lastrowid,
        "date_key": date_key,
        "duration_minutes": duration_minutes,
    }


def get_studied_minutes_for_date(data, date_key):
    """Total studied minutes for one date, summed from focus_sessions."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(duration_minutes), 0) AS total
        FROM focus_sessions
        WHERE date_key = ?
    """, (date_key,))
    return cursor.fetchone()["total"]


def get_studied_minutes_between_dates(data, start_date_key, end_date_key):
    """Return {date_key: total_studied_minutes} for every day with at least one session."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT date_key, SUM(duration_minutes) AS total
        FROM focus_sessions
        WHERE date_key >= ? AND date_key <= ?
        GROUP BY date_key
    """, (start_date_key, end_date_key))
    return {row["date_key"]: row["total"] for row in cursor.fetchall()}


# --- Notes ---


def _row_to_daily_note(row):
    return {
        "id": row["id"],
        "date_key": row["date_key"],
        "body": row["body"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_daily_note_row(data, date_key):
    """The single notepad entry for a date, or None if nothing's been saved yet."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT id, date_key, body, created_at, updated_at
        FROM daily_notes
        WHERE date_key = ?
    """, (date_key,))
    row = cursor.fetchone()
    return _row_to_daily_note(row) if row else None


def save_daily_note_row(data, date_key, body):
    """
    Create or update the one notepad entry for date_key. The UNIQUE
    constraint on daily_notes.date_key makes this an upsert: editing the
    same date again updates that row in place (keeping its id and
    created_at) instead of inserting a duplicate.
    """
    cursor = data.cursor()
    cursor.execute("""
        INSERT INTO daily_notes (date_key, body, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(date_key) DO UPDATE SET
            body = excluded.body,
            updated_at = excluded.updated_at
    """, (date_key, body))
    data.commit()

    return get_daily_note_row(data, date_key)


def get_note_dates_between_dates(data, start_date_key, end_date_key):
    """Return the set of date_keys in range that have a saved, non-empty note."""
    cursor = data.cursor()
    cursor.execute("""
        SELECT date_key
        FROM daily_notes
        WHERE date_key >= ? AND date_key <= ? AND TRIM(body) <> ''
    """, (start_date_key, end_date_key))
    return {row["date_key"] for row in cursor.fetchall()}
