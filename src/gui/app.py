"""Main desktop GUI application window."""

import threading
import time
import tkinter as tk
from tkinter import ttk

from src.gui.canvas_panel import CanvasPanel
from src.gui.task_panel import TaskPanel
from src.gui.match_panel import MatchPanel
from src.gui.region_panel import RegionPanel
from src.gui.state_panel import StatePanel
from src.utils.logger import logger


class App(tk.Tk):
    """Main application window."""

    def __init__(self, device, scheduler):
        super().__init__()
        self.device = device
        self.scheduler = scheduler

        self.title("Last War Automation")
        self.geometry("1280x780")
        self.minsize(960, 600)
        self.configure(bg="#1a1a2e")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_styles()
        self._build_ui()

        # Auto-refresh screenshot
        self._refresh_running = True
        self._refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._refresh_thread.start()

    # ── Styles ───────────────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        bg = "#1a1a2e"
        panel_bg = "#16213e"
        fg = "#e0e0e0"
        accent = "#e94560"
        border = "#0f3460"
        entry_bg = "#0d1117"

        style.configure(".", background=bg, foreground=fg, bordercolor=border, troughcolor=entry_bg)
        style.configure("TFrame", background=panel_bg)
        style.configure("TLabel", background=panel_bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TLabelframe", background=panel_bg, foreground=accent, font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe.Label", background=panel_bg, foreground=accent)
        style.configure("TButton", background=accent, foreground="white", font=("Segoe UI", 9), padding=4)
        style.map("TButton", background=[("active", "#c73550")])
        style.configure("TCheckbutton", background=panel_bg, foreground=fg)
        style.configure("TScale", background=panel_bg, troughcolor=entry_bg)
        style.configure("TEntry", fieldbackground=entry_bg, foreground=fg)
        style.configure("TSpinbox", fieldbackground=entry_bg, foreground=fg, arrowcolor=fg)
        style.configure("TCombobox", fieldbackground=entry_bg, foreground=fg)
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=accent, background=panel_bg)
        style.configure("Status.TLabel", font=("Segoe UI", 9), background=panel_bg)
        style.configure("Small.TLabel", font=("Segoe UI", 9), background=panel_bg, foreground="#888888")
        style.configure("Accent.TButton", background=accent, foreground="white")
        style.configure("Tool.TButton", padding=2, font=("Segoe UI", 9))
        style.configure("Active.Tool.TButton", background=accent, foreground="white")

        # Notebook (tabs)
        style.configure("TNotebook", background=panel_bg, bordercolor=border)
        style.configure("TNotebook.Tab", background=bg, foreground=fg, padding=[10, 4])
        style.map("TNotebook.Tab", background=[("selected", panel_bg)], foreground=[("selected", accent)])

    # ── UI Layout ────────────────────────────────────────────────────

    def _build_ui(self):
        # Top status bar
        self._build_status_bar()

        # Main content: left = canvas, right = control tabs
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.rowconfigure(0, weight=1)

        # Left: screenshot canvas
        self.canvas_panel = CanvasPanel(content, self.device)
        self.canvas_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Right: tabbed control panels
        right_frame = ttk.Frame(content, width=340)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.grid_propagate(False)

        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.task_panel = TaskPanel(notebook, self.scheduler)
        notebook.add(self.task_panel, text="Tasks")

        self.match_panel = MatchPanel(notebook, self.device, self.canvas_panel)
        notebook.add(self.match_panel, text="Match")

        self.region_panel = RegionPanel(notebook, self.canvas_panel)
        notebook.add(self.region_panel, text="Regions")

        self.state_panel = StatePanel(notebook, self.scheduler)
        notebook.add(self.state_panel, text="State")

    def _build_status_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(bar, text="Last War Automation", style="Header.TLabel").pack(side=tk.LEFT)

        self._status_var = tk.StringVar(value="Running")
        self._status_label = ttk.Label(bar, textvariable=self._status_var, style="Status.TLabel")
        self._status_label.pack(side=tk.RIGHT, padx=8)

        self._fps_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._fps_var, style="Small.TLabel").pack(side=tk.RIGHT, padx=8)

    # ── Auto refresh ─────────────────────────────────────────────────

    def _auto_refresh_loop(self):
        frame_count = 0
        last_time = time.time()
        while self._refresh_running:
            try:
                self.canvas_panel.refresh()
                frame_count += 1
                now = time.time()
                if now - last_time >= 1.0:
                    fps = frame_count / (now - last_time)
                    self._fps_var.set(f"{fps:.1f} FPS")
                    frame_count = 0
                    last_time = now
            except tk.TclError:
                break
            except Exception as e:
                logger.debug("Refresh error: %s", e)
            time.sleep(0.5)

    def _on_close(self):
        self._refresh_running = False
        if self.scheduler:
            self.scheduler.stop()
        self.destroy()
