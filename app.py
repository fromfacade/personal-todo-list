import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from calendar_view import CalendarGradeView, FocusCalendarView
from focus import (
    BREAK_MINUTES,
    FOCUS_GOAL_PRESETS,
    FOCUS_MINUTES,
    PomodoroTimer,
    format_studied_time,
    get_daily_focus_summary,
    get_focus_goal_preset_label,
    get_focus_goal_preset_minutes,
    get_month_focus_summary,
    get_study_goal,
    record_focus_session,
    set_study_goal,
)
from grading import calculate_grade
from habits import (
    WEEKDAY_SHORT_NAMES,
    create_habit,
    edit_habit,
    format_weekday_schedule,
    get_habits_for_date,
    list_habits,
    remove_habit,
    toggle_habit_on_date,
)
from progression import (
    MAX_RANK,
    award_daily_grade_bonus,
    award_focus_goal_bonus,
    award_habit_exp,
    award_task_exp,
    get_rank_progress,
    has_reached_max_rank,
    prestige,
    reset_rank,
)
from stats import calculate_weekly_focus_stats, calculate_weekly_stats, get_month_grades
from storage import (
    add_task_to_date,
    delete_task_at_index,
    get_day_grade_items,
    get_tasks_for_date,
    get_today_key,
    get_user_progress,
    load_data,
    rollover_unfinished_tasks,
    save_data,
    set_task_completed,
    update_task,
)
from theme import (
    ACCENT_AMBER,
    ASSETS_DIR,
    BG_APP,
    BG_PANEL,
    BG_PANEL_SECONDARY,
    BORDER_MUTED,
    FONT_HEADING,
    FONT_MONO,
    FONT_SUBHEADING,
    FONT_TIMER,
    FONT_UI,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    apply_app_theme,
    create_card,
    create_danger_button,
    create_difficulty_accent_bar,
    create_difficulty_chip,
    create_header,
    create_hero,
    create_primary_button,
    create_rank_card,
    create_scrollable_frame,
    create_secondary_button,
    create_sidebar_button,
    create_sidebar_rank_badge,
    create_stat_card,
    create_status_badge,
    create_terminal_panel,
    get_rank_accent_color,
    set_sidebar_button_active,
    style_toplevel,
)


def _load_app_icon(root):
    """
    Set the window/taskbar icon from assets/app_icon.ico (Windows) and
    assets/app_icon.png (all platforms), without ever crashing the app if
    the asset files are missing or a platform can't load one of the
    formats - the window just falls back to Tk's default icon.
    """
    ico_path = os.path.join(ASSETS_DIR, "app_icon.ico")
    png_path = os.path.join(ASSETS_DIR, "app_icon.png")

    if sys.platform == "win32" and os.path.exists(ico_path):
        try:
            root.iconbitmap(default=ico_path)
        except tk.TclError:
            pass

    if os.path.exists(png_path):
        try:
            icon_image = tk.PhotoImage(file=png_path)
            root.iconphoto(True, icon_image)
            # Keep a reference alive on the root window - otherwise Python
            # garbage-collects the image and the taskbar icon can vanish.
            root._todo_grader_icon_image = icon_image
        except tk.TclError:
            pass


class TodoGraderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("fromfacade To-Do Grader")
        self.root.geometry("1100x820")
        self.root.minsize(960, 700)

        _load_app_icon(root)

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

        # Pinned to the bottom of the sidebar (packed with side="bottom")
        # so the rank/EXP readout stays glanceable on every tab, not just
        # on the Stats tab, without scrolling away with the main content.
        (
            self.sidebar_rank_badge,
            self.sidebar_rank_label,
            self.sidebar_exp_label,
        ) = create_sidebar_rank_badge(sidebar)
        self.sidebar_rank_badge.pack(side="bottom", fill="x", padx=12, pady=12)

        nav_wrap = tk.Frame(sidebar, bg=BG_PANEL, padx=12, pady=16)
        nav_wrap.pack(fill="both", expand=True)

        tk.Label(
            nav_wrap,
            text="MENU",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 4))

        tk.Frame(nav_wrap, bg=BORDER_MUTED, height=1).pack(fill="x", pady=(0, 12))

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
        # The whole main content area (right of the sidebar) scrolls as one
        # unit so cards/boxes are never clipped when a tab's natural content
        # is taller than the window - the user can just scroll to reach the
        # rest instead of it being cut off. The sidebar and terminal panel
        # live outside this container, so they stay fixed and always visible.
        content_scroll_container, content_scroll_host = create_scrollable_frame(
            parent, bg=BG_APP
        )
        content_scroll_container.pack(side="right", fill="both", expand=True)

        self.content_area = tk.Frame(content_scroll_host, bg=BG_APP, padx=18, pady=16)
        self.content_area.pack(fill="both", expand=True)

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
        elif section_name == "planner":
            # Habits may have been added/edited/deleted from the Habits tab
            # since the planner was last shown.
            self.refresh_scheduled_habits()
            self.refresh_summary_cards()
        elif section_name == "focus":
            # Covers the app being left open across midnight, so "today's
            # goal" always reflects the actual current date.
            self.refresh_focus_goal_card()
            self.refresh_focus_calendar()

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
        # Plain pack, top to bottom: header -> summary cards -> calendar ->
        # add-task form -> scheduled habits -> task list. Nothing here is
        # height-constrained or independently scrollable - the whole tab
        # just grows to fit its content, and the main content area's own
        # scrolling (see _build_content_area) handles the page getting
        # taller than the window.
        tk.Label(
            self.planner_section,
            text="Daily Planner",
            font=FONT_HEADING,
            fg=TEXT_PRIMARY,
            bg=BG_APP,
        ).pack(anchor="w", pady=(0, 12))

        summary_row = tk.Frame(self.planner_section, bg=BG_APP)
        summary_row.pack(fill="x", pady=(0, 12))

        cards = [
            ("grade", "Grade"),
            ("completed", "Completed Items"),
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
        self.calendar_view.get_widget().pack(fill="x", pady=(0, 12))

        input_card, input_inner = create_card(self.planner_section, padding=14)
        input_card.pack(fill="x", pady=(0, 12))

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

        # Habits scheduled for the selected day show up right in the
        # planner, next to the normal task list, instead of only living in
        # their own separate tab.
        habits_card, habits_inner = create_card(self.planner_section, padding=10)
        habits_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            habits_inner,
            text="Scheduled Habits",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 8))

        self.planner_habits_frame = tk.Frame(habits_inner, bg=BG_PANEL)
        self.planner_habits_frame.pack(fill="both", expand=True)

        # A plain (non-scrollable) card that grows to fit every task card in
        # full - no inner scrollbar competing with the main page scroll.
        list_card, list_inner = create_card(self.planner_section, padding=12)
        list_card.pack(fill="both", expand=True)

        tk.Label(
            list_inner,
            text="Task List",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 10))

        self.tasks_frame = tk.Frame(list_inner, bg=BG_PANEL)
        self.tasks_frame.pack(fill="both", expand=True)

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
        tasks = get_tasks_for_date(self.data, date_key)
        task = tasks[index] if 0 <= index < len(tasks) else None
        is_completed = completed_value.get()

        set_task_completed(
            self.data,
            index,
            is_completed,
            date_key=date_key,
        )
        save_data(self.data)
        self.refresh_tasks()

        if is_completed:
            self.log_activity("task completed")

            if task is not None:
                self._award_and_log_exp(
                    award_task_exp(
                        self.data,
                        task["id"],
                        date_key,
                        task["difficulty"],
                        description=f"Completed task: {task['title']}",
                    ),
                    difficulty=task["difficulty"],
                    kind="task",
                )
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
        else:
            for index, task in enumerate(tasks):
                self._build_task_card(index, task)

        self.refresh_scheduled_habits()
        self.refresh_summary_cards()

    def _build_task_card(self, index, task):
        completed = task["completed"]
        card_bg = "#171512" if completed else BG_PANEL_SECONDARY

        card = tk.Frame(
            self.tasks_frame,
            bg=card_bg,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=6, padx=4)

        # Left accent bar shows the task's difficulty at a glance, like a
        # status indicator on a dashboard card.
        create_difficulty_accent_bar(card, task["difficulty"]).pack(side="left", fill="y")

        content = tk.Frame(card, bg=card_bg, padx=12, pady=10)
        content.pack(side="left", fill="both", expand=True)

        top_row = tk.Frame(content, bg=card_bg)
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

        bottom_row = tk.Frame(content, bg=card_bg)
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
            create_status_badge(bottom_row, "Completed").pack(side="left", padx=(12, 0))

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

    def _award_and_log_exp(self, award_result, difficulty, kind):
        """
        Log an EXP/rank-up terminal message and refresh the rank card.
        award_result is whatever progression.award_*_exp() returned - None
        means no EXP was granted (already awarded, or bonus not earned).
        """
        if award_result is None:
            return

        if difficulty is not None:
            message = f"+{award_result['exp_amount']} EXP from completing {difficulty.capitalize()} {kind}"
        else:
            message = f"+{award_result['exp_amount']} EXP from {kind}"

        self.log_activity(message)

        if award_result["ranked_up"]:
            self.log_activity(f"rank updated: {award_result['old_rank']} \u2192 {award_result['new_rank']}")

        self.refresh_rank_card()

    def refresh_summary_cards(self):
        # Combines normal tasks with any habits scheduled for this day so the
        # grade and points reflect both, without double-counting either one.
        date_key = self.get_selected_date_key()
        items = get_day_grade_items(self.data, date_key)
        grade = calculate_grade(items)

        completed_count = sum(1 for item in items if item["completed"])
        total_count = len(items)

        if not items:
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

        # Safe to call every refresh: award_daily_grade_bonus only grants EXP
        # once per date_key, so re-checking here just no-ops after the first time.
        self._award_and_log_exp(
            award_daily_grade_bonus(self.data, date_key, grade["percentage"]),
            difficulty=None,
            kind="daily grade bonus",
        )

    # --- Scheduled Habits (inside the Daily Planner) ---

    def refresh_scheduled_habits(self):
        for widget in self.planner_habits_frame.winfo_children():
            widget.destroy()

        date_key = self.get_selected_date_key()
        habits_today = get_habits_for_date(self.data, date_key)

        if not habits_today:
            tk.Label(
                self.planner_habits_frame,
                text="No habits scheduled for this day.",
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_PANEL,
            ).pack(anchor="w", padx=4, pady=4)
            return

        for habit_item in habits_today:
            self._build_planner_habit_card(habit_item)

    def _build_planner_habit_card(self, habit_item):
        completed = habit_item["completed"]
        card_bg = "#171512" if completed else BG_PANEL_SECONDARY

        card = tk.Frame(
            self.planner_habits_frame,
            bg=card_bg,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=6, padx=4)

        create_difficulty_accent_bar(card, habit_item["difficulty"]).pack(side="left", fill="y")

        content = tk.Frame(card, bg=card_bg, padx=12, pady=10)
        content.pack(side="left", fill="both", expand=True)

        top_row = tk.Frame(content, bg=card_bg)
        top_row.pack(fill="x")

        title_font = ("Segoe UI", 11, "overstrike") if completed else ("Segoe UI", 11, "bold")
        title_color = TEXT_SECONDARY if completed else TEXT_PRIMARY

        tk.Label(
            top_row,
            text=habit_item["title"],
            font=title_font,
            fg=title_color,
            bg=card_bg,
        ).pack(side="left")

        bottom_row = tk.Frame(content, bg=card_bg)
        bottom_row.pack(fill="x", pady=(8, 0))

        create_difficulty_chip(bottom_row, habit_item["difficulty"]).pack(side="left")

        tk.Label(
            bottom_row,
            text=f"{habit_item['points']} pts",
            font=FONT_UI,
            fg=ACCENT_AMBER,
            bg=card_bg,
        ).pack(side="left", padx=(10, 0))

        if completed:
            create_status_badge(bottom_row, "Completed").pack(side="left", padx=(12, 0))

        habit_id = habit_item["habit_id"]
        toggle_button = create_secondary_button if completed else create_primary_button
        toggle_label = "Mark Incomplete" if completed else "Mark Complete"

        toggle_button(
            bottom_row,
            toggle_label,
            lambda h=habit_id, mark_completed=not completed: self.toggle_scheduled_habit(
                h, mark_completed
            ),
        ).pack(side="right")

    def toggle_scheduled_habit(self, habit_id, completed):
        date_key = self.get_selected_date_key()
        habits_today = get_habits_for_date(self.data, date_key)
        habit_item = next((h for h in habits_today if h["habit_id"] == habit_id), None)

        toggle_habit_on_date(self.data, habit_id, completed, date_key=date_key)
        save_data(self.data)

        self.refresh_scheduled_habits()
        self.refresh_summary_cards()

        if completed:
            self.log_activity("habit completed")

            if habit_item is not None:
                self._award_and_log_exp(
                    award_habit_exp(
                        self.data,
                        habit_id,
                        date_key,
                        habit_item["difficulty"],
                        description=f"Completed habit: {habit_item['title']}",
                    ),
                    difficulty=habit_item["difficulty"],
                    kind="habit",
                )
        else:
            self.log_activity("habit marked incomplete")

    # --- Habits ---

    def _build_habits_tab(self):
        # Plain pack, top to bottom: hero -> add-habit form -> habit list.
        # The habit list card is NOT height-constrained or independently
        # scrollable here - it just grows to fit every habit card, and the
        # main content area's own scrolling (see _build_content_area) is
        # what handles the page getting taller than the window.
        create_hero(
            self.habits_section,
            "Daily Habits",
            "Small routines that keep the system running.",
        ).pack(fill="x", pady=(0, 12))

        input_card, input_inner = create_card(self.habits_section, padding=14)
        input_card.pack(fill="x", pady=(0, 12))

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

        tk.Label(
            input_inner,
            text="Scheduled days",
            font=FONT_UI,
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(10, 4))

        _, self.habit_weekday_vars = self._build_weekday_checkboxes(input_inner)

        # A plain (non-scrollable) card that grows to fit every habit card in
        # full - no inner scrollbar competing with the main page scroll.
        list_card, list_inner = create_card(self.habits_section, padding=12)
        list_card.pack(fill="both", expand=True)

        tk.Label(
            list_inner,
            text="Your Habits",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(anchor="w", pady=(0, 10))

        self.habits_frame = tk.Frame(list_inner, bg=BG_PANEL)
        self.habits_frame.pack(fill="both", expand=True)

    def _build_weekday_checkboxes(self, parent):
        """Row of 7 weekday checkboxes. Returns (row_frame, {weekday_index: BooleanVar})."""
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x")

        weekday_vars = {}
        for index, label in enumerate(WEEKDAY_SHORT_NAMES):
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(row, text=label, variable=var).pack(side="left", padx=(0, 10))
            weekday_vars[index] = var

        return row, weekday_vars

    def add_habit(self):
        title = self.habit_entry.get().strip()
        difficulty = self.habit_difficulty_box.get()
        weekdays = [day for day, var in self.habit_weekday_vars.items() if var.get()]

        if not title:
            messagebox.showwarning("Empty Habit", "Habit title can't be empty.")
            return

        try:
            create_habit(self.data, title, difficulty, weekdays=weekdays)
            save_data(self.data)
        except ValueError as error:
            messagebox.showerror("Add Habit Failed", str(error))
            return

        self.habit_entry.delete(0, tk.END)
        for var in self.habit_weekday_vars.values():
            var.set(False)

        self.refresh_habits()
        self.refresh_scheduled_habits()
        self.refresh_summary_cards()
        self.log_activity(f"habit added: {title}")

    def edit_habit_ui(self, habit):
        self.open_edit_habit_dialog(
            habit["id"], habit["title"], habit["difficulty"], habit["weekdays"]
        )

    def open_edit_habit_dialog(self, habit_id, current_title, current_difficulty, current_weekdays):
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Habit")
        dialog.transient(self.root)
        dialog.grab_set()
        style_toplevel(dialog)

        tk.Label(
            dialog,
            text="Habit title",
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

        tk.Label(
            dialog,
            text="Scheduled days",
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=2, column=0, padx=12, pady=10, sticky="nw")

        # _build_weekday_checkboxes packs its row into whatever parent it is
        # given, but this dialog places everything else with grid - and
        # Tkinter does not allow mixing pack and grid for children of the
        # very same parent. Wrapping in a plain container frame (itself
        # placed with grid) gives the checkbox row its own parent to pack
        # into, so the two geometry managers never collide.
        weekday_container = tk.Frame(dialog, bg=BG_PANEL)
        weekday_container.grid(row=2, column=1, padx=12, pady=10, sticky="w")

        _, weekday_vars = self._build_weekday_checkboxes(weekday_container)

        for day, var in weekday_vars.items():
            var.set(day in current_weekdays)

        button_frame = tk.Frame(dialog, bg=BG_PANEL)
        button_frame.grid(row=3, column=0, columnspan=2, pady=14)

        def save_changes():
            new_title = title_entry.get().strip()
            new_difficulty = difficulty_box.get()
            new_weekdays = [day for day, var in weekday_vars.items() if var.get()]

            if not new_title:
                messagebox.showwarning("Empty Habit", "Habit title can't be empty.")
                return

            try:
                edit_habit(
                    self.data,
                    habit_id,
                    title=new_title,
                    difficulty=new_difficulty,
                    weekdays=new_weekdays,
                )
                save_data(self.data)
            except ValueError as error:
                messagebox.showerror("Edit Failed", str(error))
                return

            dialog.destroy()
            self.refresh_habits()
            self.refresh_scheduled_habits()
            self.refresh_summary_cards()
            self.log_activity(f"habit updated: {new_title}")

        create_primary_button(button_frame, "Save", save_changes).pack(side="left", padx=6)
        create_secondary_button(button_frame, "Cancel", dialog.destroy).pack(side="left", padx=6)

    def delete_habit(self, habit_id):
        remove_habit(self.data, habit_id)
        save_data(self.data)
        self.refresh_habits()
        self.refresh_scheduled_habits()
        self.refresh_summary_cards()
        self.log_activity("habit deleted")

    def refresh_habits(self):
        for widget in self.habits_frame.winfo_children():
            widget.destroy()

        habits = list_habits(self.data)

        if not habits:
            tk.Label(
                self.habits_frame,
                text="No habits yet. Add one to build a daily routine.",
                font=FONT_UI,
                fg=TEXT_SECONDARY,
                bg=BG_PANEL,
            ).pack(pady=24, padx=8)
            return

        for habit in habits:
            self._build_habit_card(habit)

    def _build_habit_card(self, habit):
        card_bg = BG_PANEL_SECONDARY

        card = tk.Frame(
            self.habits_frame,
            bg=card_bg,
            highlightbackground=BORDER_MUTED,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=6, padx=4)

        create_difficulty_accent_bar(card, habit["difficulty"]).pack(side="left", fill="y")

        content = tk.Frame(card, bg=card_bg, padx=12, pady=10)
        content.pack(side="left", fill="both", expand=True)

        top_row = tk.Frame(content, bg=card_bg)
        top_row.pack(fill="x")

        tk.Label(
            top_row,
            text=habit["title"],
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_PRIMARY,
            bg=card_bg,
        ).pack(side="left")

        bottom_row = tk.Frame(content, bg=card_bg)
        bottom_row.pack(fill="x", pady=(8, 0))

        create_difficulty_chip(bottom_row, habit["difficulty"]).pack(side="left")
        tk.Label(
            bottom_row,
            text=f"{habit['points']} pts",
            font=FONT_UI,
            fg=ACCENT_AMBER,
            bg=card_bg,
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            bottom_row,
            text=format_weekday_schedule(habit["weekdays"]),
            font=FONT_UI,
            fg=TEXT_SECONDARY,
            bg=card_bg,
        ).pack(side="left", padx=(12, 0))

        actions = tk.Frame(bottom_row, bg=card_bg)
        actions.pack(side="right")

        create_secondary_button(
            actions,
            "Edit",
            lambda h=habit: self.edit_habit_ui(h),
        ).pack(side="left", padx=(0, 6))

        create_danger_button(
            actions,
            "Delete",
            lambda h=habit["id"]: self.delete_habit(h),
        ).pack(side="left")

    # --- Stats ---

    def _build_stats_tab(self):
        create_hero(
            self.stats_section,
            "Performance Dashboard",
            "Track your weekly momentum and consistency.",
        ).pack(fill="x", pady=(0, 12))

        (
            rank_card,
            self.rank_value_label,
            self.rank_exp_label,
            self.rank_next_label,
            self.rank_progress,
            self.rank_prestige_label,
            self.reset_rank_button,
            self.prestige_button,
            self.prestige_hint_label,
        ) = create_rank_card(
            self.stats_section,
            on_reset_rank=self.reset_rank_ui,
            on_prestige=self.prestige_ui,
        )
        rank_card.pack(fill="x", pady=(0, 12))

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

        tk.Label(
            self.stats_section,
            text="Focus & Study",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_APP,
        ).pack(anchor="w", pady=(0, 8))

        focus_stats_row = tk.Frame(self.stats_section, bg=BG_APP)
        focus_stats_row.pack(fill="x", pady=(0, 12))

        focus_stat_defs = [
            ("focus_total", "Studied This Week"),
            ("focus_goal_rate", "Goal Success Rate"),
            ("focus_best_day", "Best Focus Day"),
        ]

        for column, (key, label) in enumerate(focus_stat_defs):
            card, value_label = create_stat_card(focus_stats_row, label, "--", width=190)
            card.grid(row=0, column=column, sticky="nsew", padx=6)
            focus_stats_row.grid_columnconfigure(column, weight=1)
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

    def refresh_rank_card(self):
        progress = get_user_progress(self.data)
        rank_info = get_rank_progress(progress["total_exp"])
        rank_color = get_rank_accent_color(rank_info["current_rank"])

        self.rank_value_label.config(
            text=rank_info["current_rank"],
            fg=rank_color,
        )
        self.rank_exp_label.config(text=f"Total EXP: {progress['total_exp']}")

        if rank_info["next_rank"] is None:
            self.rank_next_label.config(text="Max rank reached!")
        else:
            self.rank_next_label.config(
                text=(
                    f"Next rank: {rank_info['next_rank']} "
                    f"({rank_info['exp_needed_for_next_rank']} EXP needed)"
                )
            )

        self.rank_progress["value"] = rank_info["progress_percentage"]

        self.rank_prestige_label.config(text=f"Prestige: {progress['prestige_count']}")

        # Prestige only ever unlocks once the player has actually reached
        # the max rank - keep the button disabled (with an explanatory
        # hint) the rest of the time instead of hiding it, so the layout
        # never jumps around as EXP is earned.
        if has_reached_max_rank(rank_info["current_rank"]):
            self.prestige_button.config(state="normal")
            self.prestige_hint_label.config(text="")
        else:
            self.prestige_button.config(state="disabled")
            self.prestige_hint_label.config(text=f"Reach {MAX_RANK} to prestige.")

        # Keep the always-visible sidebar badge in sync with the same numbers
        # shown on the full rank card in the Stats tab.
        self.sidebar_rank_label.config(text=rank_info["current_rank"], fg=rank_color)
        self.sidebar_exp_label.config(text=f"{progress['total_exp']} EXP")

    def reset_rank_ui(self):
        confirmed = messagebox.askyesno(
            "Reset Rank",
            "Are you sure you want to reset your rank and EXP? Your tasks, "
            "habits, and focus history will stay, but your progression "
            "will restart at F-. This cannot be undone.",
        )

        if not confirmed:
            return

        reset_rank(self.data)
        save_data(self.data)
        self.refresh_rank_card()
        self.log_activity("rank reset to F-")

    def prestige_ui(self):
        progress = get_user_progress(self.data)

        if not has_reached_max_rank(progress["current_rank"]):
            messagebox.showinfo("Prestige Locked", f"Reach {MAX_RANK} to prestige.")
            return

        confirmed = messagebox.askyesno(
            "Prestige",
            "Prestiging resets your rank and EXP back to F- and adds 1 to "
            "your prestige count. Your tasks, habits, and focus history "
            "will stay. This cannot be undone.",
        )

        if not confirmed:
            return

        try:
            result = prestige(self.data)
        except ValueError as error:
            messagebox.showinfo("Prestige Locked", str(error))
            return

        save_data(self.data)
        self.refresh_rank_card()
        self.log_activity("prestige activated")
        self.log_activity(f"prestige level increased to {result['prestige_count']}")

    def refresh_stats(self):
        self.refresh_rank_card()

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

        focus_stats = calculate_weekly_focus_stats(self.data)
        focus_best_day = focus_stats["best_day"]

        self.stat_card_labels["focus_total"].config(
            text=format_studied_time(focus_stats["total_studied_minutes"])
        )
        self.stat_card_labels["focus_goal_rate"].config(
            text=f"{focus_stats['goal_success_rate']}%"
        )

        if focus_best_day["date_key"] is None:
            self.stat_card_labels["focus_best_day"].config(text="--")
        else:
            self.stat_card_labels["focus_best_day"].config(
                text=format_studied_time(focus_best_day["studied_minutes"])
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
        # Grid (not pack) so the calendar keeps a usable minimum height
        # instead of being squeezed out on shorter windows, matching the
        # Daily Planner / Habits tabs.
        self.focus_section.grid_columnconfigure(0, weight=1)
        self.focus_section.grid_rowconfigure(3, weight=1, minsize=200)

        create_hero(
            self.focus_section,
            "Focus Session",
            f"{FOCUS_MINUTES} minute focus blocks - track your study time and hit your daily goal.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._build_focus_goal_card()
        self.focus_goal_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._build_focus_timer_card()
        self.focus_timer_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self._build_focus_calendar_section()

        self.focus_timer = PomodoroTimer(on_tick=self.on_focus_tick)

        self.refresh_focus_goal_card()

    # --- Focus: study goal card ---

    def _build_focus_goal_card(self):
        self.focus_goal_card, goal_inner = create_card(self.focus_section, padding=16)

        header_row = tk.Frame(goal_inner, bg=BG_PANEL)
        header_row.pack(fill="x")

        tk.Label(
            header_row,
            text="Today's Study Goal",
            font=FONT_SUBHEADING,
            fg=TEXT_PRIMARY,
            bg=BG_PANEL,
        ).pack(side="left")

        self.focus_goal_button = create_secondary_button(
            header_row, "Set Goal", self.open_set_focus_goal_dialog
        )
        self.focus_goal_button.pack(side="right")

        self.focus_goal_label = tk.Label(
            goal_inner,
            text="No goal set for today.",
            font=FONT_UI,
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            justify="left",
        )
        self.focus_goal_label.pack(anchor="w", pady=(10, 4))

        self.focus_goal_progress = ttk.Progressbar(
            goal_inner,
            orient="horizontal",
            mode="determinate",
            maximum=100,
        )
        self.focus_goal_progress.pack(fill="x", pady=(4, 0))

    def refresh_focus_goal_card(self):
        date_key = get_today_key()
        summary = get_daily_focus_summary(self.data, date_key)

        self.focus_goal_button.config(text="Edit Goal" if summary["goal_minutes"] else "Set Goal")

        if summary["goal_minutes"] is None:
            studied_text = format_studied_time(summary["studied_minutes"])
            self.focus_goal_label.config(
                text=f"No goal set for today. Studied so far: {studied_text}",
                fg=TEXT_SECONDARY,
            )
            self.focus_goal_progress["value"] = 0
            return

        percentage = min(
            round((summary["studied_minutes"] / summary["goal_minutes"]) * 100), 100
        )
        self.focus_goal_progress["value"] = percentage

        progress_text = f"Studied {summary['studied_minutes']} / {summary['goal_minutes']} min"

        if summary["goal_met"]:
            self.focus_goal_label.config(text=f"{progress_text} - Goal met!", fg=SUCCESS)
        else:
            self.focus_goal_label.config(text=progress_text, fg=TEXT_SECONDARY)

    def open_set_focus_goal_dialog(self):
        date_key = get_today_key()
        current_goal = get_study_goal(self.data, date_key)
        current_preset_label = (
            get_focus_goal_preset_label(current_goal) if current_goal else None
        )
        # If the saved goal isn't one of the presets, start on "Custom" with
        # its exact minute value pre-filled instead of losing that value.
        custom_prefill = str(current_goal) if (current_goal and current_preset_label is None) else ""

        dialog = tk.Toplevel(self.root)
        dialog.title("Set Study Goal")
        dialog.transient(self.root)
        dialog.grab_set()
        style_toplevel(dialog)

        current_text = (
            f"Current goal: {format_studied_time(current_goal)}"
            if current_goal
            else "No goal set for today yet."
        )
        tk.Label(
            dialog,
            text=current_text,
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 10), sticky="w")

        tk.Label(
            dialog,
            text="Quick select",
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=1, column=0, padx=12, pady=6, sticky="w")

        preset_var = tk.StringVar(value=current_preset_label or "Custom")
        preset_box = ttk.Combobox(
            dialog,
            values=[label for label, _minutes in FOCUS_GOAL_PRESETS],
            textvariable=preset_var,
            state="readonly",
            width=14,
        )
        preset_box.grid(row=1, column=1, padx=12, pady=6, sticky="w")

        tk.Label(
            dialog,
            text="Custom minutes",
            fg=TEXT_SECONDARY,
            bg=BG_PANEL,
            font=FONT_UI,
        ).grid(row=2, column=0, padx=12, pady=(6, 12), sticky="w")

        goal_entry = ttk.Entry(dialog, width=12)
        goal_entry.grid(row=2, column=1, padx=12, pady=(6, 12), sticky="w")

        def sync_goal_entry_to_preset(*_args):
            """
            Keep the minutes entry matching whatever is picked in "Quick
            select" - locked to the preset's fixed value normally, only
            editable once "Custom" is chosen (see requirement: typing a
            custom number only counts while Custom is selected).
            """
            preset_minutes = get_focus_goal_preset_minutes(preset_var.get())

            goal_entry.config(state="normal")
            goal_entry.delete(0, tk.END)

            if preset_minutes is None:
                goal_entry.insert(0, custom_prefill)
            else:
                goal_entry.insert(0, str(preset_minutes))
                goal_entry.config(state="disabled")

        preset_box.bind("<<ComboboxSelected>>", sync_goal_entry_to_preset)
        sync_goal_entry_to_preset()

        button_frame = tk.Frame(dialog, bg=BG_PANEL)
        button_frame.grid(row=3, column=0, columnspan=2, pady=14)

        def save_goal():
            preset_minutes = get_focus_goal_preset_minutes(preset_var.get())

            if preset_minutes is not None:
                goal_minutes = preset_minutes
            else:
                raw_value = goal_entry.get().strip()

                if not raw_value.isdigit() or int(raw_value) <= 0:
                    messagebox.showwarning(
                        "Invalid Goal", "Enter a whole number of minutes greater than 0."
                    )
                    return

                goal_minutes = int(raw_value)

            set_study_goal(self.data, goal_minutes, date_key=date_key)
            save_data(self.data)

            dialog.destroy()
            self.refresh_focus_goal_card()
            self.refresh_focus_calendar()
            self.log_activity(f"goal set: {goal_minutes} min")
            self._check_focus_goal_bonus(date_key)

        create_primary_button(button_frame, "Save Goal", save_goal).pack(side="left", padx=6)
        create_secondary_button(button_frame, "Cancel", dialog.destroy).pack(side="left", padx=6)

    # --- Focus: Pomodoro timer card ---

    def _build_focus_timer_card(self):
        self.focus_timer_card, timer_inner = create_card(self.focus_section, padding=24)

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
            fg=SUCCESS,
            bg=BG_PANEL,
            justify="left",
        )
        self.focus_status_label.pack(anchor="w", pady=(18, 0))

    def on_focus_tick(self, timer, finished=False):
        self.focus_mode_label.config(text=f"Mode: {timer.get_mode_label()}")
        self.focus_time_label.config(text=timer.format_time())

        if finished:
            # timer.mode is already the NEW mode by the time we get here, so
            # "just switched to break" means a focus block was just finished.
            just_finished_focus_block = timer.mode == "break"
            next_label = "break mode activated" if just_finished_focus_block else "focus mode activated"

            if just_finished_focus_block:
                date_key = get_today_key()
                record_focus_session(self.data, FOCUS_MINUTES, date_key=date_key)
                save_data(self.data)

                self.log_activity("focus session completed")
                self.refresh_focus_goal_card()
                self.refresh_focus_calendar()
                self._check_focus_goal_bonus(date_key)

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

    def _check_focus_goal_bonus(self, date_key):
        """
        Award the once-per-day study goal bonus if today's studied minutes
        have reached the goal. Safe to call any time the goal or studied
        minutes change - award_focus_goal_bonus only grants EXP once per
        date, so this silently does nothing after the first success.
        """
        summary = get_daily_focus_summary(self.data, date_key)

        if not summary["goal_met"]:
            return

        award_result = award_focus_goal_bonus(self.data, date_key)

        if award_result is None:
            return

        self.log_activity("study goal reached")
        self.log_activity(f"+{award_result['exp_amount']} bonus EXP awarded")

        if award_result["ranked_up"]:
            self.log_activity(f"rank updated: {award_result['old_rank']} \u2192 {award_result['new_rank']}")

        self.refresh_rank_card()

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

    # --- Focus: monthly calendar ---

    def _build_focus_calendar_section(self):
        self.focus_calendar = FocusCalendarView(
            self.focus_section,
            get_month_focus_summary=lambda year, month: get_month_focus_summary(
                self.data, year, month
            ),
            initial_date_key=get_today_key(),
        )
        self.focus_calendar.get_widget().grid(row=3, column=0, sticky="nsew")

    def refresh_focus_calendar(self):
        self.focus_calendar.render()


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
