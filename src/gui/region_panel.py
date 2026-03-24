"""Region editor panel - adjust timer regions and coordinates visually."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import yaml

from src.utils.logger import logger


class RegionPanel(ttk.Frame):
    """Panel for editing coordinate regions with visual preview."""

    def __init__(self, parent, canvas_panel):
        super().__init__(parent)
        self.canvas_panel = canvas_panel
        self._coords_data: dict = {}
        self._region_widgets: dict[str, dict] = {}

        self._build_ui()
        self._load_coords()

    def _build_ui(self):
        pad = dict(padx=6, pady=2)

        ttk.Label(self, text="Timer Regions", style="Header.TLabel").pack(anchor=tk.W, **pad, pady=(6, 4))

        # Show overlay toggle
        self._show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self, text="Show regions on screenshot",
            variable=self._show_var, command=self._toggle_overlay,
        ).pack(anchor=tk.W, **pad)

        # Scrollable region list
        self._list_frame = ttk.Frame(self)
        self._list_frame.pack(fill=tk.BOTH, expand=True, **pad)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, **pad, pady=(4, 4))
        ttk.Button(btn_frame, text="Reload", command=self._load_coords).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Save", command=self._save_coords).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Add Region", command=self._add_region).pack(side=tk.LEFT, padx=2)

        # Use selection button
        sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=6)
        ttk.Label(self, text="Quick Set", style="Header.TLabel").pack(anchor=tk.W, **pad)
        ttk.Label(
            self,
            text='Select a region on canvas with "Select Region"\nmode, then click a region name to set it.',
            style="Small.TLabel",
        ).pack(anchor=tk.W, **pad)

    def _load_coords(self):
        try:
            with open("config/coordinates.yaml", "r", encoding="utf-8") as f:
                self._coords_data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            self._coords_data = {"timers": {}}

        self._rebuild_region_list()

    def _rebuild_region_list(self):
        # Clear existing
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._region_widgets.clear()

        timers = self._coords_data.get("timers", {})
        for name, cfg in timers.items():
            region = cfg.get("region", [0, 0, 100, 30])
            self._build_region_row(name, region)

        self._update_overlay()

    def _build_region_row(self, name: str, region: list):
        card = ttk.LabelFrame(self._list_frame, text=name)
        card.pack(fill=tk.X, pady=3)

        row = ttk.Frame(card)
        row.pack(fill=tk.X, padx=6, pady=4)

        vars_ = {}
        for i, label in enumerate(["X:", "Y:", "W:", "H:"]):
            ttk.Label(row, text=label, width=2).pack(side=tk.LEFT)
            var = tk.IntVar(value=region[i] if i < len(region) else 0)
            spin = ttk.Spinbox(
                row, from_=0, to=9999, textvariable=var, width=5,
                command=lambda: self._on_region_edited(),
            )
            spin.pack(side=tk.LEFT, padx=(0, 6))
            vars_[("x", "y", "w", "h")[i]] = var

        # "Set from canvas" button
        ttk.Button(
            row, text="<- Canvas",
            command=lambda n=name: self._set_from_canvas(n),
        ).pack(side=tk.RIGHT, padx=2)

        # Delete button
        ttk.Button(
            row, text="X",
            command=lambda n=name: self._delete_region(n),
        ).pack(side=tk.RIGHT, padx=2)

        self._region_widgets[name] = vars_

    def _on_region_edited(self):
        self._sync_to_data()
        self._update_overlay()

    def _sync_to_data(self):
        """Sync widget values back to coords_data."""
        timers = self._coords_data.setdefault("timers", {})
        for name, vars_ in self._region_widgets.items():
            try:
                region = [vars_["x"].get(), vars_["y"].get(), vars_["w"].get(), vars_["h"].get()]
            except tk.TclError:
                continue
            if name not in timers:
                timers[name] = {}
            timers[name]["region"] = region

    def _update_overlay(self):
        if not self._show_var.get():
            self.canvas_panel.set_region_overlays([])
            return

        regions = []
        for name, vars_ in self._region_widgets.items():
            try:
                regions.append({
                    "name": name,
                    "x": vars_["x"].get(),
                    "y": vars_["y"].get(),
                    "w": vars_["w"].get(),
                    "h": vars_["h"].get(),
                })
            except tk.TclError:
                continue

        self.canvas_panel.set_region_overlays(regions)

    def _toggle_overlay(self):
        self._update_overlay()

    def _set_from_canvas(self, name: str):
        """Set a region from the current canvas selection."""
        sel = self.canvas_panel.selection_rect
        if not sel:
            messagebox.showinfo("Info", "Please select a region on the canvas first\n(use Select Region mode)")
            return

        x, y, w, h = sel
        vars_ = self._region_widgets.get(name)
        if vars_:
            vars_["x"].set(x)
            vars_["y"].set(y)
            vars_["w"].set(w)
            vars_["h"].set(h)
            self._on_region_edited()
            logger.info("Region '%s' set to (%d, %d, %d, %d)", name, x, y, w, h)

    def _add_region(self):
        """Add a new timer region."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Region")
        dialog.geometry("250x100")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Region name:").pack(padx=10, pady=(10, 4))
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var)
        entry.pack(padx=10, fill=tk.X)
        entry.focus()

        def do_add():
            name = name_var.get().strip()
            if not name:
                return
            timers = self._coords_data.setdefault("timers", {})
            timers[name] = {
                "region": [0, 0, 100, 30],
                "action_template": f"assets/templates/buttons/{name}_btn.png",
            }
            dialog.destroy()
            self._rebuild_region_list()

        ttk.Button(dialog, text="Add", command=do_add).pack(pady=8)
        dialog.bind("<Return>", lambda e: do_add())

    def _delete_region(self, name: str):
        timers = self._coords_data.get("timers", {})
        if name in timers:
            del timers[name]
        self._rebuild_region_list()

    def _save_coords(self):
        self._sync_to_data()
        try:
            with open("config/coordinates.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self._coords_data, f, default_flow_style=False, allow_unicode=True)
            logger.info("Coordinates saved")
            messagebox.showinfo("Saved", "Coordinates saved to config/coordinates.yaml")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
