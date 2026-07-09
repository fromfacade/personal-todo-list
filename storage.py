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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_date
        ON tasks(date_key)
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
        WHERE date_key = ?
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
        WHERE date_key = ? AND completed = 0
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

    return [_row_to_habit(row) for row in cursor.fetchall()]


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


def get_habit_task_for_date(data, habit_id, date_key):
    """Find the task record created for a habit on a specific date."""
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
        WHERE date_key = ? AND recurring_task_id = ?
        LIMIT 1
    """, (date_key, habit_id))

    row = cursor.fetchone()

    if row is None:
        return None

    return _row_to_task(row)


def set_habit_completion_for_date(data, habit_id, date_key, completed):
    """
    Create or update a task row that represents habit completion for a date.
    Habit tasks use recurring_task_id to link back to the habit definition.
    """
    habit = get_habit_by_id(data, habit_id)

    if habit is None:
        raise ValueError("Habit not found.")

    existing_task = get_habit_task_for_date(data, habit_id, date_key)
    cursor = data.cursor()

    if existing_task is None:
        cursor.execute("""
            INSERT INTO tasks (
                title,
                date_key,
                difficulty,
                points,
                completed,
                recurring_task_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            habit["title"],
            date_key,
            habit["difficulty"],
            habit["points"],
            1 if completed else 0,
            habit_id,
        ))
    else:
        cursor.execute("""
            UPDATE tasks
            SET completed = ?
            WHERE id = ?
        """, (1 if completed else 0, existing_task["id"]))

    data.commit()


# --- Stats query helpers (raw data for stats.py) ---


def get_tasks_between_dates(data, start_date_key, end_date_key):
    """Return all tasks between two ISO date strings, inclusive."""
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
        WHERE date_key >= ? AND date_key <= ?
        ORDER BY date_key, id
    """, (start_date_key, end_date_key))

    return [_row_to_task(row) for row in cursor.fetchall()]


def get_completed_points_by_date(data, start_date_key, end_date_key):
    """Return {date_key: completed_points} for each day in the range."""
    tasks = get_tasks_between_dates(data, start_date_key, end_date_key)
    points_by_date = {}

    for task in tasks:
        date_key = task["date_key"]
        if date_key not in points_by_date:
            points_by_date[date_key] = 0

        if task["completed"]:
            points_by_date[date_key] += task["points"]

    return points_by_date


def get_daily_completion_status(data, date_key):
    """
    Return completion info for one day.
    A day counts as fully complete only when it has tasks and all are done.
    """
    tasks = get_tasks_for_date(data, date_key)

    if not tasks:
        return {
            "date_key": date_key,
            "has_tasks": False,
            "all_completed": False,
            "total_points": 0,
            "completed_points": 0,
            "completion_percentage": 0,
        }

    total_points = sum(task["points"] for task in tasks)
    completed_points = sum(
        task["points"] for task in tasks if task["completed"]
    )

    percentage = round((completed_points / total_points) * 100) if total_points else 0

    return {
        "date_key": date_key,
        "has_tasks": True,
        "all_completed": all(task["completed"] for task in tasks),
        "total_points": total_points,
        "completed_points": completed_points,
        "completion_percentage": percentage,
    }
