"""Task control panel - enable/disable tasks, adjust cooldown in real-time."""

import threading
import time
import tkinter as tk
from tkinter import ttk

from src.utils.logger import logger


class TaskPanel(ttk.Frame):
    """Panel to control automation tasks at runtime."""

    def __init__(self, parent, scheduler):
        super().__init__(parent)
        self.scheduler = scheduler
        self._widgets: dict[str, dict] = {}
        self._build_ui()
        self._start_refresh()

    def _build_ui(self):
        # Scrollable area
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        ttk.Label(container, text="Task Control", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 8))

        if not self.scheduler:
            ttk.Label(container, text="Scheduler not started").pack()
            return

        for task in self.scheduler.tasks:
            self._build_task_card(container, task)

        # Scheduler controls
        sep = ttk.Separator(container, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=10)

        ttk.Label(container, text="Scheduler", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 4))

        ctrl_row = ttk.Frame(container)
        ctrl_row.pack(fill=tk.X, pady=2)

        self._running_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ctrl_row, text="Running", variable=self._running_var,
            command=self._toggle_scheduler,
        ).pack(side=tk.LEFT)

        ttk.Label(ctrl_row, text="Poll interval:").pack(side=tk.LEFT, padx=(16, 4))
        self._poll_var = tk.DoubleVar(value=self.scheduler.poll_interval)
        poll_spin = ttk.Spinbox(
            ctrl_row, from_=0.5, to=30.0, increment=0.5,
            textvariable=self._poll_var, width=6,
            command=self._update_poll_interval,
        )
        poll_spin.pack(side=tk.LEFT)
        ttk.Label(ctrl_row, text="s").pack(side=tk.LEFT)

    def _build_task_card(self, parent, task):
        card = ttk.LabelFrame(parent, text=task.name)
        card.pack(fill=tk.X, pady=4)

        # Enable toggle
        row1 = ttk.Frame(card)
        row1.pack(fill=tk.X, padx=8, pady=4)

        enabled_var = tk.BooleanVar(value=task.config.enabled)
        ttk.Checkbutton(
            row1, text="Enabled", variable=enabled_var,
            command=lambda t=task, v=enabled_var: self._set_enabled(t, v),
        ).pack(side=tk.LEFT)

        priority_label = ttk.Label(row1, text=f"Priority: {task.config.priority}", style="Small.TLabel")
        priority_label.pack(side=tk.RIGHT)

        # Cooldown
        row2 = ttk.Frame(card)
        row2.pack(fill=tk.X, padx=8, pady=(0, 4))

        ttk.Label(row2, text="Cooldown:").pack(side=tk.LEFT)
        cooldown_var = tk.DoubleVar(value=task.config.cooldown)
        cooldown_spin = ttk.Spinbox(
            row2, from_=1, to=86400, increment=1,
            textvariable=cooldown_var, width=8,
            command=lambda t=task, v=cooldown_var: self._set_cooldown(t, v),
        )
        cooldown_spin.pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="s").pack(side=tk.LEFT)

        # Stats
        stats_var = tk.StringVar(value="Runs: 0 | Fails: 0 | Last: never")
        stats_label = ttk.Label(card, textvariable=stats_var, style="Small.TLabel")
        stats_label.pack(anchor=tk.W, padx=8, pady=(0, 4))

        self._widgets[task.name] = {
            "enabled_var": enabled_var,
            "cooldown_var": cooldown_var,
            "stats_var": stats_var,
        }

    def _set_enabled(self, task, var):
        task.config.enabled = var.get()
        logger.info("Task '%s' %s", task.name, "enabled" if var.get() else "disabled")

    def _set_cooldown(self, task, var):
        try:
            task.config.cooldown = var.get()
            logger.info("Task '%s' cooldown set to %.1fs", task.name, var.get())
        except (tk.TclError, ValueError):
            pass

    def _toggle_scheduler(self):
        if self._running_var.get():
            logger.info("Scheduler resumed")
        else:
            logger.info("Scheduler paused")
        # The scheduler checks _running flag
        if self.scheduler:
            self.scheduler._running = self._running_var.get()

    def _update_poll_interval(self):
        try:
            val = self._poll_var.get()
            if self.scheduler:
                self.scheduler.poll_interval = val
        except (tk.TclError, ValueError):
            pass

    def _refresh_stats(self):
        if not self.scheduler:
            return
        for task in self.scheduler.tasks:
            w = self._widgets.get(task.name)
            if not w:
                continue
            elapsed = time.time() - task.last_run if task.last_run > 0 else -1
            last_str = f"{int(elapsed)}s ago" if elapsed >= 0 else "never"
            w["stats_var"].set(f"Runs: {task.run_count} | Fails: {task.fail_count} | Last: {last_str}")

    def _start_refresh(self):
        def loop():
            while True:
                try:
                    self._refresh_stats()
                except (tk.TclError, RuntimeError):
                    break
                time.sleep(2)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
