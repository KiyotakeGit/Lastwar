"""Template matching test panel with visual overlay."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import cv2

from src.device.base import DeviceController
from src.utils.logger import logger
from src.vision.matcher import find_all_templates, _template_cache


class MatchPanel(ttk.Frame):
    """Panel for testing template matching and capturing new templates."""

    def __init__(self, parent, device: DeviceController, canvas_panel):
        super().__init__(parent)
        self.device = device
        self.canvas_panel = canvas_panel
        self._build_ui()
        self._load_templates()

        # Register selection callback for template capture
        self.canvas_panel.set_on_selection(self._on_region_selected)

    def _build_ui(self):
        pad = dict(padx=6, pady=2)

        # ── Match Test Section ───────────────────────────────────────
        ttk.Label(self, text="Template Match Test", style="Header.TLabel").pack(anchor=tk.W, **pad, pady=(6, 4))

        # Template selector
        sel_frame = ttk.Frame(self)
        sel_frame.pack(fill=tk.X, **pad)

        self._tpl_var = tk.StringVar()
        self._tpl_combo = ttk.Combobox(sel_frame, textvariable=self._tpl_var, state="readonly")
        self._tpl_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(sel_frame, text="Reload", command=self._load_templates).pack(side=tk.RIGHT, padx=(4, 0))

        # Threshold slider
        thr_frame = ttk.Frame(self)
        thr_frame.pack(fill=tk.X, **pad)

        ttk.Label(thr_frame, text="Threshold:").pack(side=tk.LEFT)
        self._threshold_var = tk.DoubleVar(value=0.80)
        self._threshold_scale = ttk.Scale(
            thr_frame, from_=0.3, to=1.0, variable=self._threshold_var,
            orient=tk.HORIZONTAL, command=self._on_threshold_change,
        )
        self._threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._thr_label = ttk.Label(thr_frame, text="0.80", width=5)
        self._thr_label.pack(side=tk.RIGHT)

        # Test button
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, **pad)
        ttk.Button(btn_frame, text="Test Match", command=self._test_match).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Clear Overlay", command=self._clear_overlay).pack(side=tk.LEFT, padx=4)

        # Results
        self._results_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._results_var, style="Small.TLabel", wraplength=300).pack(
            anchor=tk.W, **pad,
        )

        # ── Capture Section ──────────────────────────────────────────
        sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=8)

        ttk.Label(self, text="Capture Template", style="Header.TLabel").pack(anchor=tk.W, **pad)
        ttk.Label(
            self,
            text='Use "Capture Template" mode on the canvas,\nthen fill in the details below.',
            style="Small.TLabel",
        ).pack(anchor=tk.W, **pad)

        # Selection display
        sel_info = ttk.Frame(self)
        sel_info.pack(fill=tk.X, **pad)
        self._sel_var = tk.StringVar(value="No selection")
        ttk.Label(sel_info, textvariable=self._sel_var, style="Small.TLabel").pack(side=tk.LEFT)

        # Name and category
        name_frame = ttk.Frame(self)
        name_frame.pack(fill=tk.X, **pad)
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self._name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self._name_var, width=16).pack(side=tk.LEFT, padx=4)
        ttk.Label(name_frame, text="Category:").pack(side=tk.LEFT, padx=(8, 0))
        self._cat_var = tk.StringVar(value="buttons")
        cat_combo = ttk.Combobox(
            name_frame, textvariable=self._cat_var, width=10,
            values=["buttons", "icons", "screens"], state="readonly",
        )
        cat_combo.pack(side=tk.LEFT, padx=4)

        ttk.Button(self, text="Save Template", command=self._save_template).pack(anchor=tk.W, **pad)

        # Template preview
        self._preview_label = ttk.Label(self)
        self._preview_label.pack(anchor=tk.W, **pad)
        self._preview_photo = None

    def _load_templates(self):
        templates_dir = Path("assets/templates")
        templates = []
        for png in sorted(templates_dir.rglob("*.png")):
            templates.append(str(png))
        self._tpl_combo["values"] = templates
        if templates:
            self._tpl_combo.current(0)

    def _on_threshold_change(self, _=None):
        val = self._threshold_var.get()
        self._thr_label.config(text=f"{val:.2f}")

    def _test_match(self):
        tpl_path = self._tpl_var.get()
        if not tpl_path or not Path(tpl_path).exists():
            self._results_var.set("Please select a valid template")
            return

        self.canvas_panel.force_refresh()
        screen = self.canvas_panel.last_frame
        if screen is None:
            self._results_var.set("No screenshot available")
            return

        threshold = self._threshold_var.get()
        matches = find_all_templates(screen, tpl_path, threshold=threshold)

        tpl_img = cv2.imread(tpl_path)
        if tpl_img is None:
            self._results_var.set("Failed to load template image")
            return

        th, tw = tpl_img.shape[:2]

        overlays = []
        for mx, my, conf in matches:
            overlays.append({
                "x": mx - tw // 2,
                "y": my - th // 2,
                "w": tw,
                "h": th,
                "conf": conf,
            })

        self.canvas_panel.set_match_overlays(overlays)

        if matches:
            lines = [f"Found {len(matches)} match(es):"]
            for i, (mx, my, conf) in enumerate(matches, 1):
                lines.append(f"  #{i}: ({mx}, {my}) conf={conf:.4f}")
            self._results_var.set("\n".join(lines))
        else:
            self._results_var.set(f"No matches (threshold={threshold:.2f})")

    def _clear_overlay(self):
        self.canvas_panel.clear_match_overlays()
        self._results_var.set("")

    def _on_region_selected(self, x, y, w, h):
        """Called when user selects a region on canvas in capture mode."""
        self._selection = (x, y, w, h)
        self._sel_var.set(f"Region: ({x}, {y}) {w}x{h}")

        # Show preview
        screen = self.canvas_panel.last_frame
        if screen is not None:
            cropped = screen[y:y + h, x:x + w]
            if cropped.size > 0:
                from PIL import Image, ImageTk
                rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                # Scale preview to fit
                max_dim = 150
                scale = min(max_dim / max(rgb.shape[1], 1), max_dim / max(rgb.shape[0], 1), 1.0)
                if scale < 1.0:
                    new_w = int(rgb.shape[1] * scale)
                    new_h = int(rgb.shape[0] * scale)
                    rgb = cv2.resize(rgb, (new_w, new_h))
                pil = Image.fromarray(rgb)
                self._preview_photo = ImageTk.PhotoImage(pil)
                self._preview_label.config(image=self._preview_photo)

    def _save_template(self):
        if not hasattr(self, "_selection") or not self._selection:
            messagebox.showwarning("Warning", "Please select a region on the canvas first")
            return

        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a template name")
            return

        x, y, w, h = self._selection
        screen = self.canvas_panel.last_frame
        if screen is None:
            messagebox.showerror("Error", "No screenshot available")
            return

        cropped = screen[y:y + h, x:x + w]
        if cropped.size == 0:
            messagebox.showerror("Error", "Invalid region")
            return

        category = self._cat_var.get()
        save_dir = Path(f"assets/templates/{category}")
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{name}.png"

        cv2.imwrite(str(save_path), cropped)
        _template_cache.pop(str(save_path), None)

        logger.info("Template saved: %s (%dx%d)", save_path, w, h)
        messagebox.showinfo("Saved", f"Template saved:\n{save_path}\nSize: {w}x{h}")
        self._load_templates()
