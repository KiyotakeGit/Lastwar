"""模板匹配测试面板 —— 在截图上进行模板匹配并以可视化叠加层显示结果。"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import cv2

from src.device.base import DeviceController
from src.utils.logger import logger
from src.vision.matcher import find_all_templates, _template_cache


class MatchPanel(ttk.Frame):
    """模板匹配面板：支持测试匹配和截取新模板两大功能。"""

    def __init__(self, parent, device: DeviceController, canvas_panel):
        super().__init__(parent)
        self.device = device              # 设备控制器，用于获取截图
        self.canvas_panel = canvas_panel  # 画布面板，用于显示截图和叠加层
        self._build_ui()                  # 构建界面组件
        self._load_templates()            # 加载 assets/templates 目录下的所有模板

        # 当用户在画布上框选区域时，调用 _on_region_selected 回调
        self.canvas_panel.set_on_selection(self._on_region_selected)

    # ================================================================
    #  界面构建
    # ================================================================
    def _build_ui(self):
        # 通用内边距（水平 6px，垂直 2px）
        pad = dict(padx=6, pady=2)

        # ── 模板匹配测试区域 ──────────────────────────────────────
        # 标题标签，使用单独的 pady 避免与 pad 字典中的 pady 冲突
        ttk.Label(self, text="Template Match Test", style="Header.TLabel").pack(anchor=tk.W, padx=6, pady=(6, 4))

        # --- 模板选择下拉框 + 刷新按钮 ---
        sel_frame = ttk.Frame(self)
        sel_frame.pack(fill=tk.X, **pad)

        self._tpl_var = tk.StringVar()  # 当前选中的模板路径
        self._tpl_combo = ttk.Combobox(sel_frame, textvariable=self._tpl_var, state="readonly")
        self._tpl_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 点击刷新按钮重新扫描模板目录
        ttk.Button(sel_frame, text="Reload", command=self._load_templates).pack(side=tk.RIGHT, padx=(4, 0))

        # --- 匹配阈值滑块 ---
        thr_frame = ttk.Frame(self)
        thr_frame.pack(fill=tk.X, **pad)

        ttk.Label(thr_frame, text="Threshold:").pack(side=tk.LEFT)
        self._threshold_var = tk.DoubleVar(value=0.80)  # 默认阈值 0.80
        self._threshold_scale = ttk.Scale(
            thr_frame, from_=0.3, to=1.0, variable=self._threshold_var,
            orient=tk.HORIZONTAL, command=self._on_threshold_change,
        )
        self._threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._thr_label = ttk.Label(thr_frame, text="0.80", width=5)  # 显示当前阈值数值
        self._thr_label.pack(side=tk.RIGHT)

        # --- 测试按钮 & 清除按钮 ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, **pad)
        ttk.Button(btn_frame, text="Test Match", command=self._test_match).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Clear Overlay", command=self._clear_overlay).pack(side=tk.LEFT, padx=4)

        # --- 匹配结果文字显示 ---
        self._results_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._results_var, style="Small.TLabel", wraplength=300).pack(
            anchor=tk.W, **pad,
        )

        # ── 模板截取区域 ─────────────────────────────────────────
        sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=8)  # 分隔线

        ttk.Label(self, text="Capture Template", style="Header.TLabel").pack(anchor=tk.W, **pad)
        ttk.Label(
            self,
            text='Use "Capture Template" mode on the canvas,\nthen fill in the details below.',
            style="Small.TLabel",
        ).pack(anchor=tk.W, **pad)

        # --- 框选区域信息 ---
        sel_info = ttk.Frame(self)
        sel_info.pack(fill=tk.X, **pad)
        self._sel_var = tk.StringVar(value="No selection")  # 显示当前框选坐标
        ttk.Label(sel_info, textvariable=self._sel_var, style="Small.TLabel").pack(side=tk.LEFT)

        # --- 模板名称 & 分类输入 ---
        name_frame = ttk.Frame(self)
        name_frame.pack(fill=tk.X, **pad)
        ttk.Label(name_frame, text="Name:").pack(side=tk.LEFT)
        self._name_var = tk.StringVar()  # 模板文件名（不含扩展名）
        ttk.Entry(name_frame, textvariable=self._name_var, width=16).pack(side=tk.LEFT, padx=4)
        ttk.Label(name_frame, text="Category:").pack(side=tk.LEFT, padx=(8, 0))
        self._cat_var = tk.StringVar(value="buttons")  # 模板分类，决定保存子目录
        cat_combo = ttk.Combobox(
            name_frame, textvariable=self._cat_var, width=10,
            values=["buttons", "icons", "screens"], state="readonly",
        )
        cat_combo.pack(side=tk.LEFT, padx=4)

        # 保存模板按钮
        ttk.Button(self, text="Save Template", command=self._save_template).pack(anchor=tk.W, **pad)

        # --- 模板预览图 ---
        self._preview_label = ttk.Label(self)
        self._preview_label.pack(anchor=tk.W, **pad)
        self._preview_photo = None  # 持有 PhotoImage 引用，防止被垃圾回收

    # ================================================================
    #  模板加载
    # ================================================================
    def _load_templates(self):
        """扫描 assets/templates 目录，把所有 .png 文件填入下拉框。"""
        templates_dir = Path("assets/templates")
        templates = []
        for png in sorted(templates_dir.rglob("*.png")):
            templates.append(str(png))
        self._tpl_combo["values"] = templates
        if templates:
            self._tpl_combo.current(0)  # 默认选中第一个

    # ================================================================
    #  阈值滑块回调
    # ================================================================
    def _on_threshold_change(self, _=None):
        """滑块拖动时实时更新右侧数值标签。"""
        val = self._threshold_var.get()
        self._thr_label.config(text=f"{val:.2f}")

    # ================================================================
    #  执行模板匹配
    # ================================================================
    def _test_match(self):
        """读取当前截图，用选中的模板进行匹配，并在画布上绘制矩形叠加层。"""
        tpl_path = self._tpl_var.get()
        if not tpl_path or not Path(tpl_path).exists():
            self._results_var.set("Please select a valid template")
            return

        # 强制刷新截图，确保拿到最新画面
        self.canvas_panel.force_refresh()
        screen = self.canvas_panel.last_frame
        if screen is None:
            self._results_var.set("No screenshot available")
            return

        # 调用视觉匹配函数，返回所有匹配位置
        threshold = self._threshold_var.get()
        matches = find_all_templates(screen, tpl_path, threshold=threshold)

        # 读取模板图片以获取尺寸（宽高）
        tpl_img = cv2.imread(tpl_path)
        if tpl_img is None:
            self._results_var.set("Failed to load template image")
            return

        th, tw = tpl_img.shape[:2]  # 模板高度、宽度

        # 将匹配结果转换为叠加层矩形（左上角坐标 + 宽高 + 置信度）
        overlays = []
        for mx, my, conf in matches:
            overlays.append({
                "x": mx - tw // 2,   # 匹配中心点转为左上角 x
                "y": my - th // 2,   # 匹配中心点转为左上角 y
                "w": tw,
                "h": th,
                "conf": conf,        # 匹配置信度
            })

        # 在画布上绘制匹配框
        self.canvas_panel.set_match_overlays(overlays)

        # 更新结果文字
        if matches:
            lines = [f"Found {len(matches)} match(es):"]
            for i, (mx, my, conf) in enumerate(matches, 1):
                lines.append(f"  #{i}: ({mx}, {my}) conf={conf:.4f}")
            self._results_var.set("\n".join(lines))
        else:
            self._results_var.set(f"No matches (threshold={threshold:.2f})")

    # ================================================================
    #  清除叠加层
    # ================================================================
    def _clear_overlay(self):
        """清除画布上的所有匹配叠加框，并清空结果文字。"""
        self.canvas_panel.clear_match_overlays()
        self._results_var.set("")

    # ================================================================
    #  框选区域回调（用于截取新模板）
    # ================================================================
    def _on_region_selected(self, x, y, w, h):
        """用户在画布上框选一块区域后触发，保存坐标并显示预览图。"""
        self._selection = (x, y, w, h)
        self._sel_var.set(f"Region: ({x}, {y}) {w}x{h}")

        # 从当前截图中裁剪出选中区域，生成预览
        screen = self.canvas_panel.last_frame
        if screen is not None:
            cropped = screen[y:y + h, x:x + w]
            if cropped.size > 0:
                from PIL import Image, ImageTk
                rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                # 等比缩放预览图，最大边不超过 150px
                max_dim = 150
                scale = min(max_dim / max(rgb.shape[1], 1), max_dim / max(rgb.shape[0], 1), 1.0)
                if scale < 1.0:
                    new_w = int(rgb.shape[1] * scale)
                    new_h = int(rgb.shape[0] * scale)
                    rgb = cv2.resize(rgb, (new_w, new_h))
                pil = Image.fromarray(rgb)
                self._preview_photo = ImageTk.PhotoImage(pil)
                self._preview_label.config(image=self._preview_photo)

    # ================================================================
    #  保存模板
    # ================================================================
    def _save_template(self):
        """将框选区域保存为 PNG 模板文件到 assets/templates/<分类>/ 目录。"""
        # 检查是否已框选区域
        if not hasattr(self, "_selection") or not self._selection:
            messagebox.showwarning("Warning", "Please select a region on the canvas first")
            return

        # 检查模板名称
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a template name")
            return

        # 从截图裁剪框选区域
        x, y, w, h = self._selection
        screen = self.canvas_panel.last_frame
        if screen is None:
            messagebox.showerror("Error", "No screenshot available")
            return

        cropped = screen[y:y + h, x:x + w]
        if cropped.size == 0:
            messagebox.showerror("Error", "Invalid region")
            return

        # 按分类创建目录并保存 PNG
        category = self._cat_var.get()
        save_dir = Path(f"assets/templates/{category}")
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{name}.png"

        cv2.imwrite(str(save_path), cropped)
        # 清除缓存，确保下次匹配时使用最新模板
        _template_cache.pop(str(save_path), None)

        logger.info("Template saved: %s (%dx%d)", save_path, w, h)
        messagebox.showinfo("Saved", f"Template saved:\n{save_path}\nSize: {w}x{h}")
        self._load_templates()  # 刷新下拉框
