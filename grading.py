def get_letter_grade(percentage):
    if percentage == 100:
        return "A++++++"
    elif percentage >= 90:
        return "A"
    elif percentage >= 80:
        return "B"
    elif percentage >= 70:
        return "C"
    elif percentage >= 60:
        return "D"
    else:
        return "F"


def calculate_grade(tasks):
    if not tasks:
        return {
            "total_points": 0,
            "completed_points": 0,
            "percentage": 0,
            "letter": "No grade yet"
        }

    total_points = sum(task["points"] for task in tasks)
    completed_points = sum(
        task["points"] for task in tasks if task["completed"]
    )

    if total_points == 0:
        # Everything scheduled for this day is worth 0 points (e.g. only a
        # rest-day rotation item, nothing else). There's nothing to divide
        # by and nothing that should count against the grade either way,
        # so treat it as a perfect day rather than crashing or showing 0%.
        percentage = 100
    else:
        percentage = round((completed_points / total_points) * 100)

    letter = get_letter_grade(percentage)

    return {
        "total_points": total_points,
        "completed_points": completed_points,
        "percentage": percentage,
        "letter": letter
    }