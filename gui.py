import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar

from storage import (
    load_data,
    save_data,
    get_today_key,
    get_tasks_for_date,
    add_task_to_date,
    set_task_completed,
    delete_task_at_index
)

from grading import calculate_grade


class TodoGraderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do Grader")
        self.root.geometry("850x550")

        self.data = load_data()
        self.selected_date = get_today_key()

        self.setup_layout()
        self.refresh_tasks()

    def setup_layout(self):
        # Top: app title
        self.title_label = ttk.Label(
            self.root,
            text="To-Do Grader",
            font=("Arial", 22, "bold")
        )
        self.title_label.pack(side="top", pady=(15, 5))

        # Bottom: grade label for selected date
        self.grade_label = ttk.Label(
            self.root,
            text="Grade: Nothing yet...",
            font=("Arial", 14, "bold")
        )
        self.grade_label.pack(side="bottom", pady=(5, 15))

        # Center: Main Frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(side="top", fill="both", expand=True, padx=15, pady=(5, 5))

        # Left side: calendar/date selector
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=(0, 15))

        self.calendar_label = ttk.Label(
            self.left_frame,
            text="Pick a day",
            font=("Arial", 14, "bold")
        )
        self.calendar_label.pack(pady=(0, 10))

        self.calendar = Calendar(
            self.left_frame,
            selectmode="day",
            date_pattern="yyyy-mm-dd"
        )
        self.calendar.pack()

        self.calendar.bind("<<CalendarSelected>>", self.on_date_selected)

        # Right side: task input, difficulty dropdown, Add Task button, and task list
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.selected_date_label = ttk.Label(
            self.right_frame,
            text=f"Planning for: {self.selected_date}",
            font=("Arial", 18, "bold")
        )
        self.selected_date_label.pack(pady=(0, 15))

        self.input_frame = ttk.Frame(self.right_frame)
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

        self.tasks_frame = ttk.Frame(self.right_frame)
        self.tasks_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def on_date_selected(self, event=None):
        self.selected_date = self.calendar.get_date()
        self.selected_date_label.config(text=f"Planning for: {self.selected_date}")
        self.refresh_tasks()

    def add_task(self):
        title = self.task_entry.get().strip()
        difficulty = self.difficulty_box.get()

        if not title:
            messagebox.showwarning("Empty Task", "Task can't be empty.")
            return

        add_task_to_date(
            self.data,
            title,
            difficulty,
            self.selected_date
        )

        save_data(self.data)

        self.task_entry.delete(0, tk.END)
        self.refresh_tasks()

    def toggle_task(self, index, completed_value):
        set_task_completed(
            self.data,
            index,
            completed_value.get(),
            self.selected_date
        )

        save_data(self.data)
        self.refresh_grade()

    def delete_task(self, index):
        delete_task_at_index(
            self.data,
            index,
            self.selected_date
        )

        save_data(self.data)
        self.refresh_tasks()

    def refresh_tasks(self):
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()

        tasks = get_tasks_for_date(self.data, self.selected_date)

        if not tasks:
            empty_label = ttk.Label(
                self.tasks_frame,
                text="No tasks for this day yet. Add something to lock in."
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

            task_text = (
                f"{task['title']} "
                f"({task['difficulty']}, {task['points']} pts)"
            )

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
        tasks = get_tasks_for_date(self.data, self.selected_date)
        grade = calculate_grade(tasks)

        from datetime import datetime
        try:
            dt = datetime.strptime(self.selected_date, "%Y-%m-%d")
            formatted_date = dt.strftime("%B ") + str(dt.day) + dt.strftime(", %Y")
        except Exception:
            formatted_date = self.selected_date

        if not tasks:
            self.grade_label.config(text=f"{formatted_date} Grade: No tasks yet")
            return

        self.grade_label.config(
            text=(
                f"{formatted_date} Grade: {grade['letter']} | "
                f"{grade['percentage']}% | "
                f"{grade['completed_points']} / {grade['total_points']} pts"
            )
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoGraderApp(root)
    root.mainloop()