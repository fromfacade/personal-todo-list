import json
import os
import sqlite3
from datetime import date

DB_FILE = "todo_grader.db"
OLD_JSON_FILE = "tasks.json"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


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
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_date
        ON tasks(date_key)
    """)

    conn.commit()


def get_metadata(conn, key):
    cursor = conn.cursor()

    cursor.execute(
        "SELECT value FROM app_metadata WHERE key = ?",
        (key,)
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


def get_points(difficulty):
    if difficulty == "easy":
        return 1
    elif difficulty == "medium":
        return 2
    elif difficulty == "hard":
        return 3

    return 2


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

    rows = cursor.fetchall()

    tasks = []

    for row in rows:
        tasks.append({
            "id": row["id"],
            "title": row["title"],
            "date_key": row["date_key"],
            "difficulty": row["difficulty"],
            "points": row["points"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
            "rolled_over_from": row["rolled_over_from"],
            "recurring_task_id": row["recurring_task_id"]
        })

    return tasks


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
        "completed": False
    }


def get_task_id_by_index(data, task_index, date_key=None):
    tasks = get_tasks_for_date(data, date_key)

    if task_index < 0 or task_index >= len(tasks):
        raise IndexError("Invalid task index.")

    return tasks[task_index]["id"]


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