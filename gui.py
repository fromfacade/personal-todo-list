import tkinter as tk
from tkinter import ttk, messagebox

from storage import (
    load_data,
    save_data,
    get_tasks_for_date,
    add_task_to_date,
    set_task_completed,
    delete_task_at_index
)

from grading import calculate_grade

class TodoGraderApp:
  def __init__(self, root):
    self.root = root
    self.root.title("To-do Grader")
    self.root.geometry("600x500")

    self.data = load_data()

    self.title_label = ttk.Label(
      root,
      text="What do you gotta do today?",
      font=("Arial", 18, "bold")
    )
    self.title_label.pack(pady=15)

    self.input_frame = ttk.Frame(root)
    self.input_frame.pack(pady=10)

    self.task_entry = ttk.Entry(self.input_frame, width=35)
    self.task_entry.grid(row=0, column=0, padx=5)

    self.difficulty_box = ttk.Combobox(
      self.input_frame,
      values=["easy", "medium", "hard"],
      state="readonly",
      width=10
    )
    self.difficulty_box.set("medium")
    self.difficulty_box.grid(row=0, column=1, padx=5)

    self.add_button = ttk.Button(
      self.input_frame,
      text="Add Task",
      command=self.add_task
    )
    self.add_button.grid(row=0, column=2, padx=5)

    self.tasks_frame = ttk.Frame(root)
    self.tasks_frame.pack(fill="both", expand=True, padx=20, pady=10)

    self.grade_label = ttk.Label(
      root,
      text="Grade: Nothing yet...",
      font = ("Arial", 14, "bold")
    )
    self.grade_label.pack(pady=10)

    self.refresh_tasks()
  
  def add_task(self):
    title = self.task_entry.get().strip()
    difficulty = self.difficulty_box.get()

    if not title:
        messagebox.showwarning("Empty Task", "Task can't be empty gang")
        return

    add_task_to_date(self.data, title, difficulty)

    save_data(self.data)

    self.task_entry.delete(0, tk.END)
    self.refresh_tasks()

  def toggle_task(self, index, completed_value):
    set_task_completed(self.data, index, completed_value.get())

    save_data(self.data)
    self.refresh_grade()

  def delete_task(self, index):
    delete_task_at_index(self.data, index)

    save_data(self.data)
    self.refresh_tasks()

  def refresh_tasks(self):
    for widget in self.tasks_frame.winfo_children():
      widget.destroy()
    
    tasks = get_tasks_for_date(self.data)

    if not tasks:
      empty_label = ttk.Label(
        self.tasks_frame,
        text="No tasks rn, add something to lock in"
      )
      empty_label.pack(pady=20)
      self.refresh_grade()
      return
    
    for index, task in enumerate(tasks):
      row = ttk.Frame(self.tasks_frame)
      row.pack(fill="x", pady=5)

      completed_var = tk.BooleanVar(value=task["completed"])

      checkbox = ttk.Checkbutton(
        row,
        variable=completed_var,
        command=lambda i=index, var=completed_var: self.toggle_task(i, var)
      )
      checkbox.pack(side="left")

      task_text = f"{task['title']} ({task['difficulty']}, {task['points']} pts)"

      task_label = ttk.Label(row, text=task_text)
      task_label.pack(side="left", padx=10)

      delete_button = ttk.Button(
        row,
        text="Delete",
        command=lambda i=index: self.delete_task(i)
      )
      delete_button.pack(side="right")

    self.refresh_grade()

  def refresh_grade(self):
    tasks = get_tasks_for_date(self.data)
    grade = calculate_grade(tasks)

    if not tasks:
        self.grade_label.config(text="Grade: uhh nothing yet lmao")
        return

    self.grade_label.config(
        text=(
            f"Grade: {grade['letter']} | "
            f"{grade['percentage']}% | "
            f"{grade['completed_points']} / {grade['total_points']} pts"
        )
    )

if __name__ == "__main__":
  root = tk.Tk()
  app = TodoGraderApp(root)
  root.mainloop()