import sys
import tkinter as tk
from tkinter import ttk, messagebox

from calendar_view import CalendarGradeView
from focus import BREAK_MINUTES, FOCUS_MINUTES, PomodoroTimer
from grading import calculate_grade
from habits import (
    create_habit,
    is_habit_completed_on_date,
    list_habits,
    remove_habit,
    toggle_habit_on_date,
)
from stats import calculate_weekly_stats, get_month_grades
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
from theme import (
    ACCENT_AMBER,
    BG_APP,
    BG_PANEL,
    BG_PANEL_SECONDARY,
    BORDER_MUTED,
    FONT_HEADING,
    FONT_MONO,
    FONT_SUBHEADING,
    FONT_TIMER,
    FONT_UI,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    apply_app_theme,
    create_card,
    create_danger_button,
    create_difficulty_chip,
    create_header,
    create_hero,
    create_primary_button,
    create_scrollable_frame,
    create_secondary_button,
    create_sidebar_button,
    create_stat_card,
    create_terminal_panel,
    set_sidebar_button_active,
    style_toplevel,
)


class TodoGraderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("fromfacade To-Do Grader")
        self.root.geometry("1100x820")
        self.root.minsize(960, 700)

        apply_app_theme(root)

        self.data = load_data()
        self.selected_date_key = get_today_key()
        self.sidebar_buttons = {}
        self.summary_labels = {}
        self.stat_card_labels = {}

        create_header(root)

        body = tk.Frame(root, bg=BG_APP)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_content_area(body)

        _, self.log_activity = create_terminal_panel(root)

        self.show_section("planner")

        self.refresh_tasks()
        self.refresh_habits()
        self.refresh_stats()

    # --- Navigation ---

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(
            parent,
            bg=BG_PANEL,
            width=210,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        nav_wrap = tk.Frame(sidebar, bg=BG_PANEL, padx=12, pady=16)
        nav_wrap.pack(fill="both", expand=True)

        tk.Label(
            nav_wrap,
            text="Navigation",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 12))

        sections = [
            ("planner", "Daily Planner"),
            ("habits", "Habits"),
            ("stats", "Stats"),
            ("focus", "Focus"),
        ]

        for key, label in sections:
            button = create_sidebar_button(
                nav_wrap,
                label,
                command=lambda section=key: self.show_section(section),
            )
            self.sidebar_buttons[key] = button

    def _build_content_area(self, parent):
        self.content_area = tk.Frame(parent, bg=BG_APP, padx=18, pady=16)
        self.content_area.pack(side="right", fill="both", expand=True)

        self.planner_section = tk.Frame(self.content_area, bg=BG_APP)
        self.habits_section = tk.Frame(self.content_area, bg=BG_APP)
        self.stats_section = tk.Frame(self.content_area, bg=BG_APP)
        self.focus_section = tk.Frame(self.content_area, bg=BG_APP)

        self.sections = {
            "planner": self.planner_section,
            "habits": self.habits_section,
            "stats": self.stats_section,
            "focus": self.focus_section,
        }

        self._build_planner_tab()
        self._build_habits_tab()
        self._build_stats_tab()
        self._build_focus_tab()

    def show_section(self, section_name):
        for name, frame in self.sections.items():
            frame.pack_forget()

        self.sections[section_name].pack(fill="both", expand=True)

        for name, button in self.sidebar_buttons.items():
            set_sidebar_button_active(button, name == section_name)

        if section_name == "habits":
            self.refresh_habits()
        elif section_name == "stats":
            self.refresh_stats()

        self.log_activity(f"opened {section_name.replace('_', ' ')} section")

    def get_selected_date_key(self):
        """The calendar is the single source of truth for the active date."""
        return self.selected_date_key

    def on_calendar_day_selected(self, date_key):
        """Called when the user clicks a day box on the monthly calendar."""
        self.selected_date_key = date_key
        self.refresh_tasks()
        self.log_activity(f"viewing plan for {date_key}")

    # --- Daily Planner ---

    def _build_planner_tab(self):
        # The whole tab uses grid (not pack) so we can guarantee the task
        # list row always keeps a usable minimum height. With plain pack,
        # once the header/calendar/input card need more height than the
        # window has, pack can shrink the task list all the way to zero
        # and hide it completely instead of just scrolling its contents.
        self.planner_section.grid_columnconfigure(0, weight=1)
        self.planner_section.grid_rowconfigure(4, weight=1, minsize=160)

        tk.Label(
            self.planner_section,
            text="Daily Planner",
            font=FONT_HEADING,
            fg=TEXT_PRIMARY,
            bg=BG_APP,
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        summary_row = tk.Frame(self.planner_section, bg=BG_APP)
        summary_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        cards = [
            ("grade", "Grade"),
            ("completed", "Completed Tasks"),
            ("earned", "Earned Points"),
            ("total", "Total Points"),
        ]

        # Equal-weight grid columns let the cards stretch evenly with the
        # window instead of staying stuck at one fixed pixel width.
        for column, (key, label) in enumerate(cards):
            card, value_label = create_stat_card(summary_row, label, "--")
            card.grid(row=0, column=column, sticky="nsew", padx=6)
            summary_row.grid_columnconfigure(column, weight=1)
            self.summary_labels[key] = value_label

        # Monthly calendar: each day box shows that day's letter grade.
        self.calendar_view = CalendarGradeView(
            self.planner_section,
            get_month_grades=lambda year, month: get_month_grades(self.data, year, month),
            on_day_selected=self.on_calendar_day_selected,
            initial_date_key=self.selected_date_key,
        )
        self.calendar_view.get_widget().grid(row=2, column=0, sticky="ew", pady=(0, 12))

        input_card, input_inner = create_card(self.planner_section, padding=14)
        input_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))

        tk.Label(
            input_inner,
            text="Add a new task",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 10))

        input_row = tk.Frame(input_inner, bg=BG_PANEL)
        input_row.pack(fill="x")

        self.task_entry = ttk.Entry(input_row, width=42)
        self.task_entry.pack(side="left", padx=(0, 8))

        self.difficulty_box = ttk.Combobox(
            input_row,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=12,
        )
        self.difficulty_box.set("medium")
        self.difficulty_box.pack(side="left", padx=(0, 8))

        create_primary_button(input_row, "Add Task", self.add_task).pack(side="left")

        rollover_row = tk.Frame(input_inner, bg=BG_PANEL)
        rollover_row.pack(fill="x", pady=(10, 0))

        create_secondary_button(
            rollover_row,
            "Rollover unfinished tasks to today",
            self.rollover_tasks,
        ).pack(side="right")

        list_card, list_inner = create_card(self.planner_section, padding=10)
        list_card.grid(row=4, column=0, sticky="nsew")

        tk.Label(
            list_inner,
            text="Task List",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 8))

        scroll_container, self.tasks_frame = create_scrollable_frame(list_inner, bg=BG_PANEL)
        scroll_container.pack(fill="both", expand=True)

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
        self.log_activity(f"task added: {title}")

    def toggle_task(self, index, completed_value):
        date_key = self.get_selected_date_key()
        set_task_completed(
            self.data,
            index,
            completed_value.get(),
            date_key=date_key,
        )
        save_data(self.data)
        self.refresh_tasks()

        if completed_value.get():
            self.log_activity("task completed")
        else:
            self.log_activity("task marked incomplete")

        self.log_activity("grade recalculated")

    def delete_task(self, index):
        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)
        title = tasks[index]["title"] if index < len(tasks) else "task"

        delete_task_at_index(self.data, index, date_key=date_key)
        save_data(self.data)
        self.refresh_tasks()
        self.log_activity(f"task deleted: {title}")

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
        style_toplevel(dialog)

        tk.Label(
            dialog,
            text="Task title",
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=0, column=0, padx=12, pady=10, sticky="w")

        title_entry = ttk.Entry(dialog, width=36)
        title_entry.grid(row=0, column=1, padx=12, pady=10)
        title_entry.insert(0, current_title)

        tk.Label(
            dialog,
            text="Difficulty",
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=1, column=0, padx=12, pady=10, sticky="w")

        difficulty_box = ttk.Combobox(
            dialog,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=14,
        )
        difficulty_box.set(current_difficulty)
        difficulty_box.grid(row=1, column=1, padx=12, pady=10)

        button_frame = tk.Frame(dialog, bg=BG_PANEL)
        button_frame.grid(row=2, column=0, columnspan=2, pady=14)

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
            self.log_activity(f"task updated: {new_title}")

        create_primary_button(button_frame, "Save", save_changes).pack(side="left", padx=6)
        create_secondary_button(button_frame, "Cancel", dialog.destroy).pack(side="left", padx=6)

    def rollover_tasks(self):
        today_key = get_today_key()
        rolled_count = rollover_unfinished_tasks(self.data, target_date_key=today_key)
        save_data(self.data)

        if rolled_count == 0:
            messagebox.showinfo(
                "Rollover",
                "No new unfinished tasks to roll over from yesterday.",
            )
            self.log_activity("rollover found no new tasks")
        else:
            messagebox.showinfo(
                "Rollover",
                f"Rolled over {rolled_count} unfinished task(s) to today.",
            )
            self.log_activity(f"rolled over {rolled_count} task(s) to today")

        self.selected_date_key = today_key
        self.calendar_view.set_selected_date(today_key)
        self.refresh_tasks()

    def refresh_tasks(self):
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()

        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)

        if not tasks:
            tk.Label(
                self.tasks_frame,
                text="No tasks for this date. Add something to get started.",
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_PANEL,
            ).pack(pady=24, padx=8)
            self.refresh_summary_cards()
            return

        for index, task in enumerate(tasks):
            self._build_task_card(index, task)

        self.refresh_summary_cards()

    def _build_task_card(self, index, task):
        completed = task["completed"]
        card_bg = "#171512" if completed else BG_PANEL_SECONDARY

        card = tk.Frame(
            self.tasks_frame,
            bg=card_bg,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        card.pack(fill="x", pady=6, padx=4)

        top_row = tk.Frame(card, bg=card_bg)
        top_row.pack(fill="x")

        completed_var = tk.BooleanVar(value=completed)
        ttk.Checkbutton(
            top_row,
            variable=completed_var,
            command=lambda i=index, var=completed_var: self.toggle_task(i, var),
        ).pack(side="left")

        title_font = ("Segoe UI", 11, "overstrike") if completed else ("Segoe UI", 11, "bold")
        title_color = TEXT_SECONDARY if completed else TEXT_PRIMARY

        title_text = task["title"]
        if task["rolled_over_from"] is not None:
            title_text += "  [rolled over]"

        tk.Label(
            top_row,
            text=title_text,
            font=title_font,
            fg=title_color,
            bg=card_bg,
        ).pack(side="left", padx=(8, 10))

        bottom_row = tk.Frame(card, bg=card_bg)
        bottom_row.pack(fill="x", pady=(8, 0))

        create_difficulty_chip(bottom_row, task["difficulty"]).pack(side="left")

        tk.Label(
            bottom_row,
            text=f"{task['points']} pts",
            font=FONT_UI,
            fg=ACCENT_AMBER,
            bg=card_bg,
        ).pack(side="left", padx=(10, 0))

        if completed:
            tk.Label(
                bottom_row,
                text="Completed",
                font=FONT_UI,
                fg="#2ecc71",
                bg=card_bg,
            ).pack(side="left", padx=(12, 0))

        actions = tk.Frame(bottom_row, bg=card_bg)
        actions.pack(side="right")

        create_secondary_button(
            actions,
            "Edit",
            lambda i=index: self.edit_task(i),
        ).pack(side="left", padx=(0, 6))

        create_danger_button(
            actions,
            "Delete",
            lambda i=index: self.delete_task(i),
        ).pack(side="left")

    def refresh_summary_cards(self):
        date_key = self.get_selected_date_key()
        tasks = get_tasks_for_date(self.data, date_key)
        grade = calculate_grade(tasks)

        completed_count = sum(1 for task in tasks if task["completed"])
        total_count = len(tasks)

        if not tasks:
            self.summary_labels["grade"].config(text="--")
            self.summary_labels["completed"].config(text="0 / 0")
            self.summary_labels["earned"].config(text="0")
            self.summary_labels["total"].config(text="0")
            self.calendar_view.render()
            return

        self.summary_labels["grade"].config(text=grade["letter"])
        self.summary_labels["completed"].config(text=f"{completed_count} / {total_count}")
        self.summary_labels["earned"].config(text=str(grade["completed_points"]))
        self.summary_labels["total"].config(text=str(grade["total_points"]))
        self.calendar_view.render()

    # --- Habits ---

    def _build_habits_tab(self):
        # Grid (not pack) so the habit list always keeps a usable minimum
        # height instead of being squeezed out of view on shorter windows.
        self.habits_section.grid_columnconfigure(0, weight=1)
        self.habits_section.grid_rowconfigure(2, weight=1, minsize=160)

        create_hero(
            self.habits_section,
            "Daily Habits",
            "Small routines that keep the system running.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        input_card, input_inner = create_card(self.habits_section, padding=14)
        input_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        input_row = tk.Frame(input_inner, bg=BG_PANEL)
        input_row.pack(fill="x")

        self.habit_entry = ttk.Entry(input_row, width=36)
        self.habit_entry.pack(side="left", padx=(0, 8))

        self.habit_difficulty_box = ttk.Combobox(
            input_row,
            values=["easy", "medium", "hard"],
            state="readonly",
            width=12,
        )
        self.habit_difficulty_box.set("medium")
        self.habit_difficulty_box.pack(side="left", padx=(0, 8))

        create_primary_button(input_row, "Add Habit", self.add_habit).pack(side="left")

        list_card, list_inner = create_card(self.habits_section, padding=10)
        list_card.grid(row=2, column=0, sticky="nsew")

        scroll_container, self.habits_frame = create_scrollable_frame(
            list_inner, bg=BG_PANEL
        )
        scroll_container.pack(fill="both", expand=True)

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
        self.log_activity(f"habit added: {title}")

    def toggle_habit(self, habit_id, completed_value):
        toggle_habit_on_date(
            self.data,
            habit_id,
            completed_value.get(),
            date_key=get_today_key(),
        )
        save_data(self.data)
        self.refresh_habits()
        self.calendar_view.render()

        if self.get_selected_date_key() == get_today_key():
            self.refresh_summary_cards()

        if completed_value.get():
            self.log_activity("habit completed")
        else:
            self.log_activity("habit marked incomplete")

    def delete_habit(self, habit_id):
        remove_habit(self.data, habit_id)
        save_data(self.data)
        self.refresh_habits()
        self.log_activity("habit deleted")

    def refresh_habits(self):
        for widget in self.habits_frame.winfo_children():
            widget.destroy()

        habits = list_habits(self.data)
        today_key = get_today_key()

        if not habits:
            tk.Label(
                self.habits_frame,
                text="No habits yet. Add one to build a daily routine.",
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_PANEL,
            ).pack(pady=24, padx=8)
            return

        tk.Label(
            self.habits_frame,
            text=f"Today: {today_key}",
            font=FONT_SUBHEADING,
            fg=ACCENT_AMBER,
            bg=BG_PANEL,
        ).pack(anchor="w", padx=4, pady=(0, 8))

        for habit in habits:
            self._build_habit_card(habit, today_key)

    def _build_habit_card(self, habit, today_key):
        completed = is_habit_completed_on_date(self.data, habit["id"], today_key)
        card_bg = "#171512" if completed else BG_PANEL_SECONDARY

        card = tk.Frame(
            self.habits_frame,
            bg=card_bg,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        card.pack(fill="x", pady=6, padx=4)

        top_row = tk.Frame(card, bg=card_bg)
        top_row.pack(fill="x")

        completed_var = tk.BooleanVar(value=completed)
        ttk.Checkbutton(
            top_row,
            variable=completed_var,
            command=lambda h=habit["id"], var=completed_var: self.toggle_habit(h, var),
        ).pack(side="left")

        tk.Label(
            top_row,
            text=habit["title"],
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_SECONDARY if completed else TEXT_PRIMARY,
            bg=card_bg,
        ).pack(side="left", padx=(8, 10))

        bottom_row = tk.Frame(card, bg=card_bg)
        bottom_row.pack(fill="x", pady=(8, 0))

        create_difficulty_chip(bottom_row, habit["difficulty"]).pack(side="left")
        tk.Label(
            bottom_row,
            text=f"{habit['points']} pts",
            font=FONT_UI,
            fg=ACCENT_AMBER,
            bg=card_bg,
        ).pack(side="left", padx=(10, 0))

        status_text = "Done today" if completed else "Not done yet"
        status_color = "#2ecc71" if completed else TEXT_SECONDARY
        tk.Label(
            bottom_row,
            text=status_text,
            font=FONT_UI,
            fg=status_color,
            bg=card_bg,
        ).pack(side="left", padx=(12, 0))

        create_danger_button(
            bottom_row,
            "Delete",
            lambda h=habit["id"]: self.delete_habit(h),
        ).pack(side="right")

    # --- Stats ---

    def _build_stats_tab(self):
        create_hero(
            self.stats_section,
            "Performance Dashboard",
            "Track your weekly momentum and consistency.",
        ).pack(fill="x", pady=(0, 12))

        top_row = tk.Frame(self.stats_section, bg=BG_APP)
        top_row.pack(fill="x", pady=(0, 12))

        stat_defs = [
            ("weekly", "Weekly Completion"),
            ("streak", "Current Streak"),
            ("best_day", "Best Day"),
            ("points", "Completed Points"),
        ]

        # Equal-weight grid columns let the cards stretch evenly with the
        # window instead of staying stuck at one fixed pixel width.
        for column, (key, label) in enumerate(stat_defs):
            card, value_label = create_stat_card(top_row, label, "--", width=190)
            card.grid(row=0, column=column, sticky="nsew", padx=6)
            top_row.grid_columnconfigure(column, weight=1)
            self.stat_card_labels[key] = value_label

        progress_card, progress_inner = create_card(self.stats_section, padding=14)
        progress_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            progress_inner,
            text="Weekly Progress",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w")

        self.stats_progress = ttk.Progressbar(
            progress_inner,
            orient="horizontal",
            length=500,
            mode="determinate",
            maximum=100,
        )
        self.stats_progress.pack(anchor="w", pady=(10, 4))

        self.stats_progress_label = tk.Label(
            progress_inner,
            text="0%",
            font=FONT_UI,
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
        )
        self.stats_progress_label.pack(anchor="w")

        footer = tk.Frame(self.stats_section, bg=BG_APP)
        footer.pack(fill="x")

        create_secondary_button(footer, "Refresh Stats", self.refresh_stats).pack(
            anchor="w"
        )

        self.stats_detail_frame = tk.Frame(self.stats_section, bg=BG_APP)
        self.stats_detail_frame.pack(fill="both", expand=True, pady=(12, 0))

    def refresh_stats(self):
        stats = calculate_weekly_stats(self.data)
        best_day = stats["best_day"]

        self.stat_card_labels["weekly"].config(
            text=f"{stats['completion_percentage']}%"
        )
        self.stat_card_labels["streak"].config(
            text=f"{stats['current_streak']} days"
        )

        if best_day["date_key"] is None:
            self.stat_card_labels["best_day"].config(text="--")
        else:
            self.stat_card_labels["best_day"].config(
                text=f"{best_day['completed_points']} pts"
            )

        self.stat_card_labels["points"].config(
            text=f"{stats['completed_points']} / {stats['total_points']}"
        )

        self.stats_progress["value"] = stats["completion_percentage"]
        self.stats_progress_label.config(
            text=(
                f"{stats['completion_percentage']}% complete this week "
                f"({stats['week_start']} to {stats['week_end']})"
            )
        )

        for widget in self.stats_detail_frame.winfo_children():
            widget.destroy()

        if best_day["date_key"] is None:
            best_day_text = "No completed points yet this week"
        else:
            best_day_text = (
                f"{best_day['date_key']} with {best_day['completed_points']} points"
            )

        details = [
            f"Best day: {best_day_text}",
            f"Current streak: {stats['current_streak']} day(s)",
            (
                f"Completed points: {stats['completed_points']} / "
                f"{stats['total_points']}"
            ),
        ]

        for line in details:
            tk.Label(
                self.stats_detail_frame,
                text=line,
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_APP,
            ).pack(anchor="w", pady=3)

        self.log_activity("stats refreshed")

    # --- Focus ---

    def _build_focus_tab(self):
        create_hero(
            self.focus_section,
            "Focus Session",
            f"{FOCUS_MINUTES} minute focus blocks with {BREAK_MINUTES} minute breaks.",
        ).pack(fill="x", pady=(0, 12))

        timer_card, timer_inner = create_card(self.focus_section, padding=24)
        timer_card.pack(fill="both", expand=True)

        self.focus_mode_label = tk.Label(
            timer_inner,
            text="Mode: Focus",
            font=FONT_SUBHEADING,
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
        )
        self.focus_mode_label.pack(pady=(0, 8))

        self.focus_time_label = tk.Label(
            timer_inner,
            text="25:00",
            font=FONT_TIMER,
            fg=ACCENT_AMBER,
            bg=BG_PANEL,
        )
        self.focus_time_label.pack(pady=12)

        button_frame = tk.Frame(timer_inner, bg=BG_PANEL)
        button_frame.pack(pady=10)

        create_primary_button(button_frame, "Start", self.start_focus_timer).pack(
            side="left", padx=6
        )
        create_secondary_button(button_frame, "Pause", self.pause_focus_timer).pack(
            side="left", padx=6
        )
        create_secondary_button(button_frame, "Reset", self.reset_focus_timer).pack(
            side="left", padx=6
        )

        mode_frame = tk.Frame(timer_inner, bg=BG_PANEL)
        mode_frame.pack(pady=10)

        create_secondary_button(
            mode_frame,
            "Focus Mode",
            lambda: self.set_focus_mode("focus"),
        ).pack(side="left", padx=6)
        create_secondary_button(
            mode_frame,
            "Break Mode",
            lambda: self.set_focus_mode("break"),
        ).pack(side="left", padx=6)

        self.focus_status_label = tk.Label(
            timer_inner,
            text="> focus session ready",
            font=FONT_MONO,
            fg="#2ecc71",
            bg=BG_PANEL,
            justify="left",
        )
        self.focus_status_label.pack(anchor="w", pady=(18, 0))

        self.focus_timer = PomodoroTimer(on_tick=self.on_focus_tick)

    def on_focus_tick(self, timer, finished=False):
        self.focus_mode_label.config(text=f"Mode: {timer.get_mode_label()}")
        self.focus_time_label.config(text=timer.format_time())

        if finished:
            next_label = "break mode activated" if timer.mode == "break" else "focus mode activated"
            self.focus_status_label.config(text=f"> {next_label}")
            self.log_activity(next_label)
            messagebox.showinfo(
                "Focus Timer",
                f"Time is up. Switching to {timer.get_mode_label()}.",
            )
            return

        if timer.running:
            self.focus_status_label.config(text="> timer running...")
        else:
            self.focus_status_label.config(text="> focus session paused")

    def start_focus_timer(self):
        self.focus_timer.start(self.root)
        self.focus_status_label.config(text="> timer started")
        self.log_activity("focus session started")

    def pause_focus_timer(self):
        self.focus_timer.pause()
        self.focus_status_label.config(text="> timer paused")
        self.log_activity("focus session paused")

    def reset_focus_timer(self):
        self.focus_timer.reset()
        self.focus_status_label.config(text="> focus session ready")
        self.log_activity("focus session reset")

    def set_focus_mode(self, mode):
        self.focus_timer.switch_mode(mode)
        self.on_focus_tick(self.focus_timer)
        self.focus_status_label.config(text=f"> {mode} mode selected")
        self.log_activity(f"{mode} mode selected")


def _enable_windows_dpi_awareness():
    """
    Tell Windows not to bitmap-scale this app's window.

    Without this, Windows display scaling (125%, 150%, etc.) stretches the
    whole window like a blurry photo, which is why the same layout can look
    fine on one screen and cramped/misaligned on another.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


if __name__ == "__main__":
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    app = TodoGraderApp(root)
    root.mainloop()
