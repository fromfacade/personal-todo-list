"""
Simple Pomodoro timer logic for the Focus tab.
"""


FOCUS_MINUTES = 25
BREAK_MINUTES = 5
FOCUS_SECONDS = FOCUS_MINUTES * 60
BREAK_SECONDS = BREAK_MINUTES * 60


class PomodoroTimer:
    """A small countdown timer with focus and break modes."""

    def __init__(self, on_tick=None):
        self.on_tick = on_tick
        self.mode = "focus"
        self.remaining_seconds = FOCUS_SECONDS
        self.running = False
        self._after_id = None
        self._root = None

    def get_mode_label(self):
        if self.mode == "focus":
            return "Focus"
        return "Break"

    def format_time(self):
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def start(self, root):
        """Start or resume the countdown."""
        self._root = root

        if self.running:
            return

        self.running = True
        self._schedule_tick()

    def pause(self):
        """Pause the countdown."""
        self.running = False

        if self._root is not None and self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None

    def reset(self):
        """Reset the timer back to the default for the current mode."""
        self.pause()
        self.remaining_seconds = (
            FOCUS_SECONDS if self.mode == "focus" else BREAK_SECONDS
        )
        self._notify()

    def switch_mode(self, mode):
        """Switch between focus and break modes."""
        if mode not in ("focus", "break"):
            return

        self.pause()
        self.mode = mode
        self.remaining_seconds = (
            FOCUS_SECONDS if mode == "focus" else BREAK_SECONDS
        )
        self._notify()

    def _schedule_tick(self):
        if self._root is None:
            return

        self._after_id = self._root.after(1000, self._tick)

    def _tick(self):
        if not self.running:
            return

        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._notify()
            self._schedule_tick()
            return

        # Timer finished: automatically switch to the next mode.
        self.running = False
        next_mode = "break" if self.mode == "focus" else "focus"
        self.switch_mode(next_mode)
        self._notify(finished=True)

    def _notify(self, finished=False):
        if self.on_tick is not None:
            self.on_tick(self, finished)
