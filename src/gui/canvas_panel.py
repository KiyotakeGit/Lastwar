"""Interactive screenshot canvas with coordinate picking and region selection."""

import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from src.device.base import DeviceController
from src.utils.logger import logger


class CanvasPanel(ttk.Frame):
    """Live screenshot display with interactive tools."""

    MODE_VIEW = "view"
    MODE_PICK = "pick"
    MODE_REGION = "region"
    MODE_CAPTURE = "capture"

    def __init__(self, parent, device: DeviceController):
        super().__init__(parent)
        self.device = device

        self._mode = self.MODE_VIEW
        self._photo_image = None
        self._last_frame: np.ndarray | None = None
        self._scale = 1.0
        self._picked_coords: list[tuple[int, int]] = []
        self._drag_start: tuple[int, int] | None = None
        self._selection_rect: tuple[int, int, int, int] | None = None  # x, y, w, h in image coords
        self._overlay_regions: list[dict] = []  # [{name, x, y, w, h, color}]
        self._match_overlays: list[dict] = []   # [{x, y, w, h, conf}]

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 4))

        self._mode_var = tk.StringVar(value=self.MODE_VIEW)
        modes = [
            ("View", self.MODE_VIEW),
            ("Pick Coords", self.MODE_PICK),
            ("Select Region", self.MODE_REGION),
            ("Capture Template", self.MODE_CAPTURE),
        ]
        for text, mode in modes:
            rb = ttk.Radiobutton(
                toolbar, text=text, variable=self._mode_var, value=mode,
                command=self._on_mode_change,
            )
            rb.pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT, padx=2)

        self._auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Auto", variable=self._auto_refresh_var).pack(side=tk.RIGHT, padx=2)

        # Canvas
        self._canvas = tk.Canvas(self, bg="#0d1117", cursor="crosshair", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._canvas.bind("<Motion>", self._on_mouse_move)
        self._canvas.bind("<Button-1>", self._on_mouse_down)
        self._canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._canvas.bind("<Configure>", lambda e: self._redraw())

        # Bottom info bar
        info_bar = ttk.Frame(self)
        info_bar.pack(fill=tk.X, pady=(4, 0))

        self._pos_var = tk.StringVar(value="X: 0  Y: 0")
        ttk.Label(info_bar, textvariable=self._pos_var, style="Small.TLabel").pack(side=tk.LEFT)

        self._sel_var = tk.StringVar(value="")
        ttk.Label(info_bar, textvariable=self._sel_var, style="Small.TLabel").pack(side=tk.LEFT, padx=16)

        self._mode_label_var = tk.StringVar(value="Mode: View")
        ttk.Label(info_bar, textvariable=self._mode_label_var, style="Small.TLabel").pack(side=tk.RIGHT)

        # Picked coords display (hidden by default)
        self._coords_frame = ttk.Frame(self)
        self._coords_text = tk.Text(
            self._coords_frame, height=3, bg="#0d1117", fg="#e0e0e0",
            font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED,
        )
        self._coords_text.pack(fill=tk.X, padx=2)
        btn_row = ttk.Frame(self._coords_frame)
        btn_row.pack(fill=tk.X, pady=2)
        ttk.Button(btn_row, text="Clear", command=self._clear_coords).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Copy", command=self._copy_coords).pack(side=tk.LEFT, padx=2)

    # ── Public API ───────────────────────────────────────────────────

    @property
    def auto_refresh(self) -> bool:
        return self._auto_refresh_var.get()

    @property
    def last_frame(self) -> np.ndarray | None:
        return self._last_frame

    @property
    def selection_rect(self) -> tuple[int, int, int, int] | None:
        return self._selection_rect

    def refresh(self):
        """Capture a new screenshot and display it."""
        if not self._auto_refresh_var.get() and self._last_frame is not None:
            return
        try:
            self._last_frame = self.device.screenshot()
            self._redraw()
        except Exception as e:
            logger.debug("Screenshot failed: %s", e)

    def force_refresh(self):
        """Force a screenshot even if auto-refresh is off."""
        try:
            self._last_frame = self.device.screenshot()
            self._redraw()
        except Exception as e:
            logger.debug("Screenshot failed: %s", e)

    def set_match_overlays(self, overlays: list[dict]):
        """Set template match overlays to display on canvas.
        Each dict: {x, y, w, h, conf}
        """
        self._match_overlays = overlays
        self._redraw()

    def clear_match_overlays(self):
        self._match_overlays = []
        self._redraw()

    def set_region_overlays(self, regions: list[dict]):
        """Set region overlays. Each dict: {name, x, y, w, h, color?}"""
        self._overlay_regions = regions
        self._redraw()

    # ── Drawing ──────────────────────────────────────────────────────

    def _redraw(self):
        if self._last_frame is None:
            return

        canvas_w = self._canvas.winfo_width()
        canvas_h = self._canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            return

        img_h, img_w = self._last_frame.shape[:2]
        self._scale = min(canvas_w / img_w, canvas_h / img_h, 1.0)

        disp_w = int(img_w * self._scale)
        disp_h = int(img_h * self._scale)

        # Convert BGR to RGB and resize
        rgb = cv2.cvtColor(self._last_frame, cv2.COLOR_BGR2RGB)
        if self._scale != 1.0:
            rgb = cv2.resize(rgb, (disp_w, disp_h))

        pil_img = Image.fromarray(rgb)
        self._photo_image = ImageTk.PhotoImage(pil_img)

        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor=tk.NW, image=self._photo_image)

        # Draw match overlays (green rectangles)
        for m in self._match_overlays:
            x1 = int(m["x"] * self._scale)
            y1 = int(m["y"] * self._scale)
            x2 = int((m["x"] + m["w"]) * self._scale)
            y2 = int((m["y"] + m["h"]) * self._scale)
            self._canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff00", width=2)
            self._canvas.create_text(
                x1, y1 - 4, text=f'{m.get("conf", 0):.2f}',
                fill="#00ff00", anchor=tk.SW, font=("Consolas", 9),
            )

        # Draw region overlays (yellow rectangles)
        for r in self._overlay_regions:
            x1 = int(r["x"] * self._scale)
            y1 = int(r["y"] * self._scale)
            x2 = int((r["x"] + r["w"]) * self._scale)
            y2 = int((r["y"] + r["h"]) * self._scale)
            color = r.get("color", "#ffd600")
            self._canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, dash=(4, 2))
            self._canvas.create_text(
                x1, y1 - 4, text=r.get("name", ""),
                fill=color, anchor=tk.SW, font=("Consolas", 9),
            )

        # Draw picked coords (red dots)
        for px, py in self._picked_coords:
            sx, sy = int(px * self._scale), int(py * self._scale)
            self._canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, fill="#e94560", outline="")
            self._canvas.create_text(
                sx + 8, sy - 4, text=f"({px},{py})",
                fill="#ffffff", anchor=tk.W, font=("Consolas", 9),
            )

        # Draw selection rectangle (green dashed)
        if self._selection_rect:
            rx, ry, rw, rh = self._selection_rect
            x1 = int(rx * self._scale)
            y1 = int(ry * self._scale)
            x2 = int((rx + rw) * self._scale)
            y2 = int((ry + rh) * self._scale)
            self._canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff88", width=2, dash=(5, 3))
            self._canvas.create_text(
                x1, y1 - 4, text=f"{rw}x{rh}",
                fill="#00ff88", anchor=tk.SW, font=("Consolas", 9),
            )

    # ── Mouse events ─────────────────────────────────────────────────

    def _canvas_to_image(self, cx: int, cy: int) -> tuple[int, int]:
        """Convert canvas pixel coordinates to image coordinates."""
        if self._scale == 0:
            return 0, 0
        return int(cx / self._scale), int(cy / self._scale)

    def _on_mode_change(self):
        self._mode = self._mode_var.get()
        self._mode_label_var.set(f"Mode: {self._mode.capitalize()}")
        self._selection_rect = None
        self._sel_var.set("")

        if self._mode == self.MODE_PICK:
            self._coords_frame.pack(fill=tk.X, pady=(4, 0))
        else:
            self._coords_frame.pack_forget()

        self._redraw()

    def _on_mouse_move(self, event):
        ix, iy = self._canvas_to_image(event.x, event.y)
        self._pos_var.set(f"X: {ix}  Y: {iy}")

        if self._drag_start and self._mode in (self.MODE_REGION, self.MODE_CAPTURE):
            sx, sy = self._drag_start
            x = min(sx, ix)
            y = min(sy, iy)
            w = abs(ix - sx)
            h = abs(iy - sy)
            self._selection_rect = (x, y, w, h)
            self._sel_var.set(f"Selection: {x},{y} {w}x{h}")
            self._redraw()

    def _on_mouse_down(self, event):
        ix, iy = self._canvas_to_image(event.x, event.y)

        if self._mode == self.MODE_PICK:
            self._picked_coords.append((ix, iy))
            self._update_coords_text()
            self._redraw()
        elif self._mode in (self.MODE_REGION, self.MODE_CAPTURE):
            self._drag_start = (ix, iy)
            self._selection_rect = None

    def _on_mouse_drag(self, event):
        self._on_mouse_move(event)

    def _on_mouse_up(self, event):
        if self._drag_start and self._mode in (self.MODE_REGION, self.MODE_CAPTURE):
            ix, iy = self._canvas_to_image(event.x, event.y)
            sx, sy = self._drag_start
            x = min(sx, ix)
            y = min(sy, iy)
            w = abs(ix - sx)
            h = abs(iy - sy)
            if w > 3 and h > 3:
                self._selection_rect = (x, y, w, h)
                self._sel_var.set(f"Selection: {x},{y} {w}x{h}")
                # Notify callbacks
                if hasattr(self, "_on_selection_callback") and self._on_selection_callback:
                    self._on_selection_callback(x, y, w, h)
            self._drag_start = None
            self._redraw()

    def set_on_selection(self, callback):
        """Register a callback for when a region is selected: callback(x, y, w, h)."""
        self._on_selection_callback = callback

    # ── Picked coords helpers ────────────────────────────────────────

    def _update_coords_text(self):
        self._coords_text.config(state=tk.NORMAL)
        self._coords_text.delete("1.0", tk.END)
        lines = [f"({x}, {y})" for x, y in self._picked_coords]
        self._coords_text.insert("1.0", "  ".join(lines))
        self._coords_text.config(state=tk.DISABLED)

    def _clear_coords(self):
        self._picked_coords.clear()
        self._update_coords_text()
        self._redraw()

    def _copy_coords(self):
        text = ", ".join(f"[{x}, {y}]" for x, y in self._picked_coords)
        self.clipboard_clear()
        self.clipboard_append(text)
