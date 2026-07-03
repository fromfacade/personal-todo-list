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
    json.dump(data,file, indent=4)

def get_today_key():
  return str(date.today())

def get_today_tasks(data):
  today = get_today_key()

  if today not in data:
    data[today] = []

  return data[today]

def add_task(data):
  title = input("What do you gotta work on gang? ").strip()

  if not title:
    print("Task can't be empty.")
    return
  
  difficulty = input("Difficulty? easy/medium/hard: ").strip().lower()

  if difficulty == "easy":
    points = 1
  elif difficulty == "medium":
    points = 2
  elif difficulty == "hard":
    points = 3
  
  else:
    print("Invalid - put in a valid difficulty")
    difficulty = "medium"
    points = 2

  task = {
    "title": title,
    "difficulty": difficulty,
    "points": points,
    "completed": False
  }

  tasks = get_today_tasks(data)
  tasks.append(task)

  print(f"Added: {title}")

def view_tasks(data):
  tasks = get_today_tasks(data)

  if not tasks:
    print("No tasks for today - gotta fix that.")
    return
  
  print("\nToday's Tasks:")

  for index, task in enumerate(tasks, start=1):
    status = "DONE." if task['completed'] else "pending..."
    print(f"{index}. {status} {task['title']} ({task['difficulty']}, {task['points']} pts)")

  print()

def complete_task(data):
  tasks = get_today_tasks(data)

  if not tasks:
    print("Nothing yet...")
    return
  
  view_tasks(data)

  try:
    choice = int(input("Which task did you complete? (Enter it's number): "))
  except ValueError:
    print("Please enter a valid number...")
    return

  if choice < 1 or choice > len(tasks):
    print("Invalid task number.")
    return
  
  tasks[choice - 1]["completed"] = True
  print(f"Completed: {tasks[choice - 1]['title']}")

def calculate_grade(data):
  tasks = get_today_tasks(data)

  if not tasks:
    print("No tasks added today, so no grade yet.")
    return 
  
  total_points = sum(task["points"] for task in tasks)
  completed_points = sum(task["points"] for task in tasks if task["completed"])

  percentage = round((completed_points / total_points) * 100)

  if percentage == 100:
    letter = 'A+++++'
  elif percentage >= 90:
    letter = 'A'
  elif percentage >= 80:
    letter = 'B'
  elif percentage >= 70:
    letter = 'C'
  elif percentage >= 60:
    letter = 'D'
  else:
    letter = 'F--- (you suck)'

  print("\nand your Daily Grade is...")
  print(f"Completed Points: {completed_points} / {total_points}")
  print(f"Score: {percentage}%")
  print(f"Grade: {letter}\n")

def main():
  data = load_data()

  print("Welcome man, lock in.")
  print("What do you gotta do today?")

  while True:
    print("""
          \nMenu:
          1. Add Task
          2. View Tasks
          3. Complete Tasks
          4. View Grade
          5. Exit
          """)

    choice = input("What's it gonna be? (choose number):").strip()

    if choice == '1':
      add_task(data)
      save_data(data)
    elif choice == '2':
      view_tasks(data)
    elif choice == '3':
      complete_task(data)
      save_data(data)
    elif choice == '4':
      calculate_grade(data)
    elif choice == '5':
      save_data(data)
      print("Cya man.")
      break

    else:
      print("Not an option, choose an actual one por favor.")

if __name__ == "__main__":
  main()