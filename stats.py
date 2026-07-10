"""
Stats calculations for To-Do Grader.

All stats are calculated from SQLite data, not from temporary GUI state.
"""

import calendar as calendar_module
from datetime import date, timedelta

from grading import calculate_grade
from storage import (
    get_completed_points_by_date,
    get_daily_completion_status,
    get_focus_goals_between_dates,
    get_scheduled_habits_between_dates,
    get_studied_minutes_between_dates,
    get_tasks_between_dates,
    get_today_key,
)


def _flatten_habit_items(habits_by_date):
    """Turn {date_key: [habit_item, ...]} into one flat list of habit items."""
    all_items = []
    for items in habits_by_date.values():
        all_items.extend(items)
    return all_items


def get_week_start(reference_date=None):
    """Return the Monday of the week that contains reference_date."""
    if reference_date is None:
        reference_date = date.today()

    return reference_date - timedelta(days=reference_date.weekday())


def get_week_date_keys(reference_date=None):
    """Return the seven ISO date strings for the current week (Mon-Sun)."""
    week_start = get_week_start(reference_date)
    return [str(week_start + timedelta(days=offset)) for offset in range(7)]


def get_week_range(reference_date=None):
    """Return (start_date_key, end_date_key) for the current week."""
    week_dates = get_week_date_keys(reference_date)
    return week_dates[0], week_dates[-1]


def calculate_weekly_stats(conn, reference_date=None):
    """
    Build weekly stats from tasks stored in SQLite.
    Returns completion percentage, total completed points, streak, and best day.
    """
    start_key, end_key = get_week_range(reference_date)
    week_tasks = get_tasks_between_dates(conn, start_key, end_key)
    week_habits_by_date = get_scheduled_habits_between_dates(conn, start_key, end_key)
    week_grade = calculate_grade(week_tasks + _flatten_habit_items(week_habits_by_date))

    total_points = week_grade["total_points"]
    completed_points = week_grade["completed_points"]

    if total_points == 0:
        completion_percentage = 0
    else:
        completion_percentage = week_grade["percentage"]

    points_by_date = get_completed_points_by_date(conn, start_key, end_key)
    best_day = _get_best_day(points_by_date)

    return {
        "week_start": start_key,
        "week_end": end_key,
        "completion_percentage": completion_percentage,
        "completed_points": completed_points,
        "total_points": total_points,
        "current_streak": calculate_current_streak(conn),
        "best_day": best_day,
    }


def calculate_current_streak(conn, reference_date=None):
    """
    Count consecutive days (ending yesterday or today) where every task
    for that day was completed. Days with no tasks are skipped.
    """
    if reference_date is None:
        current_day = date.today()
    else:
        current_day = reference_date

    streak = 0

    while True:
        date_key = str(current_day)
        day_status = get_daily_completion_status(conn, date_key)

        if not day_status["has_tasks"]:
            # Empty days do not add to the streak, but also do not break it.
            current_day -= timedelta(days=1)
            continue

        if day_status["all_completed"]:
            streak += 1
            current_day -= timedelta(days=1)
            continue

        # Today can be incomplete without breaking a streak that starts yesterday.
        if current_day == date.today():
            current_day -= timedelta(days=1)
            continue

        break

    return streak


def _get_best_day(points_by_date):
    """Return the date with the most completed points this week."""
    if not points_by_date:
        return {
            "date_key": None,
            "completed_points": 0,
        }

    best_date_key = max(points_by_date, key=points_by_date.get)

    return {
        "date_key": best_date_key,
        "completed_points": points_by_date[best_date_key],
    }


def get_month_grades(conn, year, month):
    """
    Return {date_key: grade_dict} for every day in the given month that has
    tasks and/or scheduled habits.

    This reuses calculate_grade so the grading logic itself is not duplicated.
    A day with only scheduled habits (no normal tasks) still gets a grade,
    since we combine both lists before grading.
    """
    start_key = f"{year:04d}-{month:02d}-01"
    last_day_of_month = calendar_module.monthrange(year, month)[1]
    end_key = f"{year:04d}-{month:02d}-{last_day_of_month:02d}"

    month_tasks = get_tasks_between_dates(conn, start_key, end_key)
    habits_by_date = get_scheduled_habits_between_dates(conn, start_key, end_key)

    tasks_by_date = {}
    for task in month_tasks:
        tasks_by_date.setdefault(task["date_key"], []).append(task)

    all_date_keys = set(tasks_by_date) | set(habits_by_date)

    return {
        date_key: calculate_grade(
            tasks_by_date.get(date_key, []) + habits_by_date.get(date_key, [])
        )
        for date_key in all_date_keys
    }


def calculate_weekly_focus_stats(conn, reference_date=None):
    """
    Weekly study stats: total studied minutes, what fraction of days that
    had a goal actually hit it, and the single best focus day.
    """
    start_key, end_key = get_week_range(reference_date)
    studied_by_date = get_studied_minutes_between_dates(conn, start_key, end_key)
    goals_by_date = get_focus_goals_between_dates(conn, start_key, end_key)

    total_studied_minutes = sum(studied_by_date.values())

    days_with_goals = list(goals_by_date.keys())
    days_goal_met = [
        date_key
        for date_key in days_with_goals
        if studied_by_date.get(date_key, 0) >= goals_by_date[date_key]
    ]

    if days_with_goals:
        goal_success_rate = round((len(days_goal_met) / len(days_with_goals)) * 100)
    else:
        goal_success_rate = 0

    return {
        "week_start": start_key,
        "week_end": end_key,
        "total_studied_minutes": total_studied_minutes,
        "goal_success_rate": goal_success_rate,
        "days_with_goals": len(days_with_goals),
        "days_goal_met": len(days_goal_met),
        "best_day": _get_best_focus_day(studied_by_date),
    }


def _get_best_focus_day(studied_by_date):
    """Return the date with the most studied minutes this week."""
    if not studied_by_date or max(studied_by_date.values()) <= 0:
        return {"date_key": None, "studied_minutes": 0}

    best_date_key = max(studied_by_date, key=studied_by_date.get)

    return {
        "date_key": best_date_key,
        "studied_minutes": studied_by_date[best_date_key],
    }


def format_weekly_stats_summary(stats):
    """Turn weekly stats into readable lines for the Stats tab."""
    best_day = stats["best_day"]

    if best_day["date_key"] is None:
        best_day_text = "No completed points yet this week"
    else:
        best_day_text = (
            f"{best_day['date_key']} ({best_day['completed_points']} pts)"
        )

    return [
        f"Week: {stats['week_start']} to {stats['week_end']}",
        f"Weekly completion: {stats['completion_percentage']}%",
        (
            f"Completed points this week: "
            f"{stats['completed_points']} / {stats['total_points']}"
        ),
        f"Current streak: {stats['current_streak']} day(s)",
        f"Best day this week: {best_day_text}",
    ]
