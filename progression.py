"""
EXP and rank progression for To-Do Grader.

This file owns all rank-threshold math and "how much EXP does this action
give" rules, kept separate from both the GUI (app.py) and raw storage
(storage.py) - the same pattern grading.py already uses for grades.

app.py should only ever call the small award_*_exp() functions here; it
should never compute EXP amounts or rank thresholds itself.
"""

from storage import (
    add_exp_event,
    get_user_progress,
    set_user_progress,
)

RANKS = [
    "F-", "F", "F+",
    "D-", "D", "D+",
    "C-", "C", "C+",
    "B-", "B", "B+",
    "A-", "A", "A+",
    "S-", "S", "S+",
    "SS-", "SS", "SS+",
    "SSS-", "SSS", "SSS+",
]

# Total EXP required to REACH each rank, index-aligned with RANKS. The gaps
# grow steadily larger so later ranks take meaningfully longer, but it is
# just a plain list, so retuning the pace later only means editing numbers
# here - no other file needs to change.
RANK_THRESHOLDS = [
    0,      # F-
    20,     # F
    45,     # F+
    75,     # D-
    110,    # D
    150,    # D+
    200,    # C-
    260,    # C
    330,    # C+
    410,    # B-
    500,    # B
    600,    # B+
    720,    # A-
    850,    # A
    1000,   # A+
    1180,   # S-
    1380,   # S
    1600,   # S+
    1850,   # SS-
    2120,   # SS
    2420,   # SS+
    2750,   # SSS-
    3120,   # SSS
    3550,   # SSS+
]

# Base EXP for completing one task or habit, by difficulty.
EXP_BY_DIFFICULTY = {
    "easy": 10,
    "medium": 15,
    "hard": 25,
}

# Bonus EXP for reaching the day's study goal (once per date).
FOCUS_GOAL_BONUS_EXP = 50

# Bonus EXP for a day's completion percentage, checked from the highest
# threshold down. A day under 80% earns no bonus.
DAILY_GRADE_BONUS_EXP = {
    100: 50,
    90: 25,
    80: 10,
}


def get_exp_for_difficulty(difficulty):
    """EXP for completing one task/habit of a given difficulty."""
    return EXP_BY_DIFFICULTY.get(difficulty, EXP_BY_DIFFICULTY["medium"])


def get_daily_grade_bonus_exp(percentage):
    """Bonus EXP for a day's completion percentage, or 0 if none earned."""
    for threshold in sorted(DAILY_GRADE_BONUS_EXP, reverse=True):
        if percentage >= threshold:
            return DAILY_GRADE_BONUS_EXP[threshold]

    return 0


def get_rank_for_exp(total_exp):
    """Return the highest rank whose threshold is <= total_exp."""
    rank = RANKS[0]

    for index, threshold in enumerate(RANK_THRESHOLDS):
        if total_exp >= threshold:
            rank = RANKS[index]
        else:
            break

    return rank


def get_rank_progress(total_exp):
    """
    Return progress towards the next rank:
        current_rank, next_rank (None at max rank), exp_into_current_rank,
        exp_needed_for_next_rank (None at max rank), progress_percentage.
    """
    current_rank = get_rank_for_exp(total_exp)
    current_index = RANKS.index(current_rank)
    current_threshold = RANK_THRESHOLDS[current_index]

    if current_index == len(RANKS) - 1:
        return {
            "current_rank": current_rank,
            "next_rank": None,
            "exp_into_current_rank": total_exp - current_threshold,
            "exp_needed_for_next_rank": None,
            "progress_percentage": 100,
        }

    next_rank = RANKS[current_index + 1]
    next_threshold = RANK_THRESHOLDS[current_index + 1]

    exp_into_current_rank = total_exp - current_threshold
    exp_span = next_threshold - current_threshold
    progress_percentage = round((exp_into_current_rank / exp_span) * 100) if exp_span else 100

    return {
        "current_rank": current_rank,
        "next_rank": next_rank,
        "exp_into_current_rank": exp_into_current_rank,
        "exp_needed_for_next_rank": next_threshold - total_exp,
        "progress_percentage": progress_percentage,
    }


def _apply_exp_gain(data, exp_amount):
    """Add exp_amount to the stored total, recompute rank, and persist both."""
    progress = get_user_progress(data)
    old_rank = progress["current_rank"]
    new_total_exp = progress["total_exp"] + exp_amount
    new_rank = get_rank_for_exp(new_total_exp)

    set_user_progress(data, new_total_exp, new_rank)

    return {
        "exp_amount": exp_amount,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "total_exp": new_total_exp,
        "ranked_up": old_rank != new_rank,
    }


def award_task_exp(data, task_id, date_key, difficulty, description=None):
    """Award EXP for completing a task, once per task. Returns an award dict, or None if already granted."""
    exp_amount = get_exp_for_difficulty(difficulty)
    was_awarded = add_exp_event(
        data,
        date_key=date_key,
        source_type="task",
        source_id=task_id,
        exp_amount=exp_amount,
        description=description,
    )

    if not was_awarded:
        return None

    return _apply_exp_gain(data, exp_amount)


def award_habit_exp(data, habit_id, date_key, difficulty, description=None):
    """Award EXP for completing a habit on a date, once per habit per date."""
    exp_amount = get_exp_for_difficulty(difficulty)
    was_awarded = add_exp_event(
        data,
        date_key=date_key,
        source_type="habit",
        source_id=habit_id,
        exp_amount=exp_amount,
        description=description,
    )

    if not was_awarded:
        return None

    return _apply_exp_gain(data, exp_amount)


def award_focus_goal_bonus(data, date_key, description="Daily study goal reached"):
    """
    Award a once-per-day bonus for reaching that day's study goal. Safe to
    call every time studied minutes are recalculated - source_id is fixed
    at 0, so only the first call for a given date actually grants EXP.
    """
    exp_amount = FOCUS_GOAL_BONUS_EXP

    was_awarded = add_exp_event(
        data,
        date_key=date_key,
        source_type="focus_goal_bonus",
        source_id=0,
        exp_amount=exp_amount,
        description=description,
    )

    if not was_awarded:
        return None

    return _apply_exp_gain(data, exp_amount)


def award_daily_grade_bonus(data, date_key, percentage):
    """
    Award a once-per-day bonus when a day's completion percentage is high
    enough. Safe to call repeatedly (e.g. every time the grade is
    recalculated) since source_id=0 plus date_key keeps it to one grant.
    """
    exp_amount = get_daily_grade_bonus_exp(percentage)

    if exp_amount <= 0:
        return None

    was_awarded = add_exp_event(
        data,
        date_key=date_key,
        source_type="daily_grade_bonus",
        source_id=0,
        exp_amount=exp_amount,
        description=f"Daily grade bonus ({percentage}%)",
    )

    if not was_awarded:
        return None

    return _apply_exp_gain(data, exp_amount)
