"""Game state monitoring panel."""

import threading
import time
import tkinter as tk
from tkinter import ttk

from src.utils.logger import logger


class StatePanel(ttk.Frame):
    """Panel showing current game state and recent logs."""

    def __init__(self, parent, scheduler):
        super().__init__(parent)
        self.scheduler = scheduler
        self._build_ui()
        self._start_refresh()

    def _build_ui(self):
        pad = dict(padx=6, pady=2)

        ttk.Label(self, text="Game State", style="Header.TLabel").pack(anchor=tk.W, **pad, pady=(6, 4))

        # State display
        self._state_frame = ttk.Frame(self)
        self._state_frame.pack(fill=tk.X, **pad)

        self._state_vars = {}
        fields = [
            ("resources_collected", "Resources Collected"),
            ("teams_joined", "Teams Joined"),
            ("timers_checked", "Timers Checked"),
            ("daily_tasks_completed", "Daily Completed"),
            ("errors", "Errors"),
            ("last_error", "Last Error"),
        ]

        for key, label in fields:
            row = ttk.Frame(self._state_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=label, width=20, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value="--")
            ttk.Label(row, textvariable=var, foreground="#4fc3f7").pack(side=tk.RIGHT)
            self._state_vars[key] = var

        # Log display
        sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=8)

        ttk.Label(self, text="Recent Activity", style="Header.TLabel").pack(anchor=tk.W, **pad)

        self._log_text = tk.Text(
            self, height=15, bg="#0d1117", fg="#e0e0e0",
            font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
        )
        self._log_text.pack(fill=tk.BOTH, expand=True, **pad)

        # Add a log handler to capture logs
        self._setup_log_handler()

    def _setup_log_handler(self):
        """Add a logging handler that writes to the text widget."""
        import logging

        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                try:
                    self.text_widget.config(state=tk.NORMAL)
                    self.text_widget.insert(tk.END, msg + "\n")
                    # Keep only last 200 lines
                    lines = int(self.text_widget.index("end-1c").split(".")[0])
                    if lines > 200:
                        self.text_widget.delete("1.0", f"{lines - 200}.0")
                    self.text_widget.see(tk.END)
                    self.text_widget.config(state=tk.DISABLED)
                except tk.TclError:
                    pass

        handler = TextHandler(self._log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("lastwar").addHandler(handler)

    def _refresh_state(self):
        if not self.scheduler:
            return

        state = self.scheduler.game_state
        self._state_vars["resources_collected"].set(str(state.resources_collected))
        self._state_vars["teams_joined"].set(str(state.teams_joined))
        self._state_vars["timers_checked"].set(str(state.timers_checked))
        self._state_vars["daily_tasks_completed"].set("Yes" if state.daily_tasks_completed else "No")
        self._state_vars["errors"].set(str(state.errors))
        self._state_vars["last_error"].set(state.last_error or "--")

    def _start_refresh(self):
        def loop():
            while True:
                try:
                    self._refresh_state()
                except (tk.TclError, RuntimeError):
                    break
                time.sleep(2)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
