import json
import os
from datetime import date

DATA_FILE = "tasks.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r") as file:
        return json.load(file)


def save_data(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def get_today_key():
    return str(date.today())


def get_tasks_for_date(data, date_key=None):
    if date_key is None:
        date_key = get_today_key()

    if date_key not in data:
        data[date_key] = []

    return data[date_key]


def get_points(difficulty):
    if difficulty == "easy":
        return 1
    elif difficulty == "medium":
        return 2
    elif difficulty == "hard":
        return 3

    return 2


def add_task_to_date(data, title, difficulty="medium", date_key=None):
    title = title.strip()

    if not title:
        raise ValueError("Task title cannot be empty.")

    points = get_points(difficulty)

    task = {
        "title": title,
        "difficulty": difficulty,
        "points": points,
        "completed": False
    }

    tasks = get_tasks_for_date(data, date_key)
    tasks.append(task)

    return task


def set_task_completed(data, task_index, completed, date_key=None):
    tasks = get_tasks_for_date(data, date_key)

    if task_index < 0 or task_index >= len(tasks):
        raise IndexError("Invalid task index.")

    tasks[task_index]["completed"] = completed


def delete_task_at_index(data, task_index, date_key=None):
    tasks = get_tasks_for_date(data, date_key)

    if task_index < 0 or task_index >= len(tasks):
        raise IndexError("Invalid task index.")

    return tasks.pop(task_index)