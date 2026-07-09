import tkinter as tk
from tkinter import ttk, messagebox

from tkcalendar import DateEntry

from focus import BREAK_MINUTES, FOCUS_MINUTES, PomodoroTimer
from grading import calculate_grade
from habits import (
    create_habit,
    is_habit_completed_on_date,
    list_habits,
    remove_habit,
    toggle_habit_on_date,
)
from stats import calculate_weekly_stats, format_weekly_stats_summary
from storage import (
    add_task_to_date,
    delete_task_at_index,
    get_tasks_for_date,
    get_today_key,
    load_data,
    rollover_unfinished_tasks,
    save_data,
    set_task_completed,
    update_task,
)


class TodoGraderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do Grader")
        self.root.geometry("800x700")

        self.data = load_data()
        self.selected_date_key = get_today_key()

        self.title_label = ttk.Label(
            root,
            text="To-Do Grader",
            font=("Arial", 18, "bold"),
        )
        self.title_label.pack(pady=10)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self.planner_tab = ttk.Frame(self.notebook)
        self.habits_tab = ttk.Frame(self.notebook)
        self.stats_tab = ttk.Frame(self.notebook)
        self.focus_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.planner_tab, text="Daily Planner")
        self.notebook.add(self.habits_tab, text="Habits")
        self.notebook.add(self.stats_tab, text="Stats")
        self.notebook.add(self.focus_tab, text="Focus")

        self._build_planner_tab()
        self._build_habits_tab()
        self._build_stats_tab()
        self._build_focus_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.refresh_tasks()
        self.refresh_habits()
        self.refresh_stats()

    def get_selected_date_key(self):
        """Return the planner date as an ISO string (YYYY-MM-DD)."""
        selected_date = self.date_picker.get_date()
        return str(selected_date)

    def on_date_changed(self, _event=None):
        self.selected_date_key = self.get_selected_date_key()
        self.refresh_tasks()

    def on_tab_changed(self, _event=None):
        current_tab = self.notebook.index(self.notebook.select())

        if current_tab == 1:
            self.refresh_habits()
        elif current_tab == 2:
            self.refresh_stats()

    # --- Daily Planner tab ---

    def _build_planner_tab(self):
        top_frame = ttk.Frame(self.planner_tab)
        top_frame.pack(fill="x", padx=15, pady=10)

        ttk.Label(top_frame, text="Date:").pack(side="left")

        self.date_picker = DateEntry(
            top_frame,
            width=12,
            background="darkblue",
            foreground="white",
            borderwidth=2,
            date_pattern="yyyy-mm-dd",
        )
        self.date_picker.pack(side="left", padx=8)
        self.date_picker.bind("<<DateEntrySelected>>", self.on_date_changed)

        self.rollover_button = ttk.Button(
            top_frame,
            text="Rollover unfinished tasks to today",
            command=self.rollover_tasks,
        )
        self.rollover_button.pack(side="right")

        self.input_frame = ttk.Frame(self.planner_tab)
        self.input_frame.pack(pady=10)

        self.task_entry = ttk.Entry(self.input_frame, width=35)
        self.task_entry.grid(row=0, column=0, padx=5)

        self.difficulty_box = ttk.Combobox(
            self.input_frame,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=10,
        )
        self.difficulty_box.set("medium")
        self.difficulty_box.grid(row=0, column=1, padx=5)

        self.add_button = ttk.Button(
            self.input_frame,
            text="Add Task",
            command=self.add_task,
        )
        self.add_button.grid(row=0, column=2, padx=5)

        self.tasks_frame = ttk.Frame(self.planner_tab)
        self.tasks_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.grade_label = ttk.Label(
            self.planner_tab,
            text="Grade: Nothing yet...",
            font=("Arial", 14, "bold"),
        )
        self.grade_label.pack(pady=10)

    def add_task(self):
        title = self.task_entry.get().strip()
        difficulty = self.difficulty_box.get()
        date_key = self.get_selected_date_key()

        if not title:
            messagebox.showwarning("Empty Task", "Task can't be empty.")
            return

        add_task_to_date(self.data, title, difficulty, date_key=date_key)
        save_data(self.data)

        self.task_entry.delete(0, tk.END)
        self.refresh_tasks()

    def toggle_task(self, index, completed_value):
        date_key = self.get_selected_date_key()
        set_task_completed(
            self.data,
            index,
            completed_value.get(),
            date_key=date_key,
        )
        save_data(self.data)
        self.refresh_grade()

    def delete_task(self, index):
        date_key = self.get_selected_date_key()
        delete_task_at_index(self.data, index, date_key=date_key)
        save_data(self.data)
        self.refresh_tasks()

    def edit_task(self, index):
        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)

        if index < 0 or index >= len(tasks):
            return

        task = tasks[index]
        self.open_edit_task_dialog(task["id"], task["title"], task["difficulty"])

    def open_edit_task_dialog(self, task_id, current_title, current_difficulty):
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Task")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Task title:").grid(row=0, column=0, padx=10, pady=8)
        title_entry = ttk.Entry(dialog, width=35)
        title_entry.grid(row=0, column=1, padx=10, pady=8)
        title_entry.insert(0, current_title)

        ttk.Label(dialog, text="Difficulty:").grid(row=1, column=0, padx=10, pady=8)
        difficulty_box = ttk.Combobox(
            dialog,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=12,
        )
        difficulty_box.set(current_difficulty)
        difficulty_box.grid(row=1, column=1, padx=10, pady=8)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=12)

        def save_changes():
            new_title = title_entry.get().strip()
            new_difficulty = difficulty_box.get()

            if not new_title:
                messagebox.showwarning("Empty Task", "Task can't be empty.")
                return

            try:
                update_task(
                    self.data,
                    task_id,
                    title=new_title,
                    difficulty=new_difficulty,
                )
                save_data(self.data)
            except ValueError as error:
                messagebox.showerror("Edit Failed", str(error))
                return

            dialog.destroy()
            self.refresh_tasks()

        ttk.Button(button_frame, text="Save", command=save_changes).pack(
            side="left", padx=5
        )
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="left", padx=5)

    def rollover_tasks(self):
        today_key = get_today_key()
        rolled_count = rollover_unfinished_tasks(self.data, target_date_key=today_key)
        save_data(self.data)

        if rolled_count == 0:
            messagebox.showinfo(
                "Rollover",
                "No new unfinished tasks to roll over from yesterday.",
            )
        else:
            messagebox.showinfo(
                "Rollover",
                f"Rolled over {rolled_count} unfinished task(s) to today.",
            )

        # Jump to today so the user can see the copied tasks.
        self.date_picker.set_date(today_key)
        self.selected_date_key = today_key
        self.refresh_tasks()

    def refresh_tasks(self):
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()

        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)

        if not tasks:
            empty_label = ttk.Label(
                self.tasks_frame,
                text="No tasks for this date. Add something to get started.",
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
                command=lambda i=index, var=completed_var: self.toggle_task(i, var),
            )
            checkbox.pack(side="left")

            rolled_text = ""
            if task["rolled_over_from"] is not None:
                rolled_text = " [rolled over]"

            task_text = (
                f"{task['title']} ({task['difficulty']}, "
                f"{task['points']} pts){rolled_text}"
            )

            task_label = ttk.Label(row, text=task_text)
            task_label.pack(side="left", padx=10)

            edit_button = ttk.Button(
                row,
                text="Edit",
                command=lambda i=index: self.edit_task(i),
            )
            edit_button.pack(side="right", padx=5)

            delete_button = ttk.Button(
                row,
                text="Delete",
                command=lambda i=index: self.delete_task(i),
            )
            delete_button.pack(side="right")

        self.refresh_grade()

    def refresh_grade(self):
        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)
        grade = calculate_grade(tasks)

        if not tasks:
            self.grade_label.config(text="Grade: No tasks for this date yet")
            return

        self.grade_label.config(
            text=(
                f"Grade: {grade['letter']} | "
                f"{grade['percentage']}% | "
                f"{grade['completed_points']} / {grade['total_points']} pts"
            )
        )

    # --- Habits tab ---

    def _build_habits_tab(self):
        intro = ttk.Label(
            self.habits_tab,
            text="Recurring habits for today. Completing one adds a task for grading.",
        )
        intro.pack(pady=10)

        input_frame = ttk.Frame(self.habits_tab)
        input_frame.pack(pady=5)

        self.habit_entry = ttk.Entry(input_frame, width=35)
        self.habit_entry.grid(row=0, column=0, padx=5)

        self.habit_difficulty_box = ttk.Combobox(
            input_frame,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=10,
        )
        self.habit_difficulty_box.set("medium")
        self.habit_difficulty_box.grid(row=0, column=1, padx=5)

        ttk.Button(
            input_frame,
            text="Add Habit",
            command=self.add_habit,
        ).grid(row=0, column=2, padx=5)

        self.habits_frame = ttk.Frame(self.habits_tab)
        self.habits_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def add_habit(self):
        title = self.habit_entry.get().strip()
        difficulty = self.habit_difficulty_box.get()

        if not title:
            messagebox.showwarning("Empty Habit", "Habit title can't be empty.")
            return

        try:
            create_habit(self.data, title, difficulty)
            save_data(self.data)
        except ValueError as error:
            messagebox.showerror("Add Habit Failed", str(error))
            return

        self.habit_entry.delete(0, tk.END)
        self.refresh_habits()

    def toggle_habit(self, habit_id, completed_value):
        toggle_habit_on_date(
            self.data,
            habit_id,
            completed_value.get(),
            date_key=get_today_key(),
        )
        save_data(self.data)

        # Habit completions become tasks, so refresh planner grade if viewing today.
        if self.get_selected_date_key() == get_today_key():
            self.refresh_grade()

    def delete_habit(self, habit_id):
        remove_habit(self.data, habit_id)
        save_data(self.data)
        self.refresh_habits()

    def refresh_habits(self):
        for widget in self.habits_frame.winfo_children():
            widget.destroy()

        habits = list_habits(self.data)
        today_key = get_today_key()

        if not habits:
            ttk.Label(
                self.habits_frame,
                text="No habits yet. Add one to build a daily routine.",
            ).pack(pady=20)
            return

        ttk.Label(
            self.habits_frame,
            text=f"Today: {today_key}",
            font=("Arial", 11, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        for habit in habits:
            row = ttk.Frame(self.habits_frame)
            row.pack(fill="x", pady=5)

            completed_var = tk.BooleanVar(
                value=is_habit_completed_on_date(self.data, habit["id"], today_key)
            )

            ttk.Checkbutton(
                row,
                variable=completed_var,
                command=lambda h=habit["id"], var=completed_var: self.toggle_habit(
                    h, var
                ),
            ).pack(side="left")

            habit_text = (
                f"{habit['title']} ({habit['difficulty']}, {habit['points']} pts)"
            )
            ttk.Label(row, text=habit_text).pack(side="left", padx=10)

            ttk.Button(
                row,
                text="Delete",
                command=lambda h=habit["id"]: self.delete_habit(h),
            ).pack(side="right")

    # --- Stats tab ---

    def _build_stats_tab(self):
        header = ttk.Label(
            self.stats_tab,
            text="Weekly progress (from your saved tasks)",
            font=("Arial", 12, "bold"),
        )
        header.pack(pady=10)

        ttk.Button(
            self.stats_tab,
            text="Refresh Stats",
            command=self.refresh_stats,
        ).pack(pady=5)

        self.stats_frame = ttk.Frame(self.stats_tab)
        self.stats_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def refresh_stats(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        stats = calculate_weekly_stats(self.data)
        lines = format_weekly_stats_summary(stats)

        for line in lines:
            ttk.Label(self.stats_frame, text=line, font=("Arial", 11)).pack(
                anchor="w", pady=4
            )

    # --- Focus tab ---

    def _build_focus_tab(self):
        intro = ttk.Label(
            self.focus_tab,
            text=(
                f"Pomodoro timer: {FOCUS_MINUTES} min focus, "
                f"{BREAK_MINUTES} min break"
            ),
        )
        intro.pack(pady=10)

        self.focus_mode_label = ttk.Label(
            self.focus_tab,
            text="Mode: Focus",
            font=("Arial", 12),
        )
        self.focus_mode_label.pack(pady=5)

        self.focus_time_label = ttk.Label(
            self.focus_tab,
            text="25:00",
            font=("Arial", 36, "bold"),
        )
        self.focus_time_label.pack(pady=15)

        button_frame = ttk.Frame(self.focus_tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Start", command=self.start_focus_timer).pack(
            side="left", padx=5
        )
        ttk.Button(button_frame, text="Pause", command=self.pause_focus_timer).pack(
            side="left", padx=5
        )
        ttk.Button(button_frame, text="Reset", command=self.reset_focus_timer).pack(
            side="left", padx=5
        )

        mode_frame = ttk.Frame(self.focus_tab)
        mode_frame.pack(pady=10)

        ttk.Button(
            mode_frame,
            text="Focus Mode",
            command=lambda: self.set_focus_mode("focus"),
        ).pack(side="left", padx=5)
        ttk.Button(
            mode_frame,
            text="Break Mode",
            command=lambda: self.set_focus_mode("break"),
        ).pack(side="left", padx=5)

        self.focus_timer = PomodoroTimer(on_tick=self.on_focus_tick)

    def on_focus_tick(self, timer, finished=False):
        self.focus_mode_label.config(text=f"Mode: {timer.get_mode_label()}")
        self.focus_time_label.config(text=timer.format_time())

        if finished:
            next_label = "Break" if timer.mode == "break" else "Focus"
            messagebox.showinfo("Focus Timer", f"Time is up. Switching to {next_label}.")

    def start_focus_timer(self):
        self.focus_timer.start(self.root)

    def pause_focus_timer(self):
        self.focus_timer.pause()

    def reset_focus_timer(self):
        self.focus_timer.reset()

    def set_focus_mode(self, mode):
        self.focus_timer.switch_mode(mode)
        self.on_focus_tick(self.focus_timer)


if __name__ == "__main__":
    root = tk.Tk()
    app = TodoGraderApp(root)
    root.mainloop()
