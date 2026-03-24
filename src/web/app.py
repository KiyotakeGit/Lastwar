"""Web dashboard for real-time monitoring and parameter adjustment."""

import base64
import json
import time
import threading
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request

from src.device.base import DeviceController
from src.utils.logger import logger
from src.vision.matcher import find_template, find_all_templates, _template_cache

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# Shared state - set by the main app before starting
_device: DeviceController | None = None
_scheduler = None  # Will hold reference to Scheduler
_last_screenshot: np.ndarray | None = None
_screenshot_lock = threading.Lock()


def init_dashboard(device: DeviceController, scheduler=None):
    """Initialize the dashboard with device and scheduler references."""
    global _device, _scheduler
    _device = device
    _scheduler = scheduler


def _capture_screenshot() -> np.ndarray | None:
    """Capture a fresh screenshot from the device."""
    global _last_screenshot
    if _device is None:
        return None
    try:
        with _screenshot_lock:
            _last_screenshot = _device.screenshot()
        return _last_screenshot
    except Exception as e:
        logger.error("Dashboard screenshot failed: %s", e)
        return _last_screenshot


def _encode_image(image: np.ndarray, quality: int = 80) -> str:
    """Encode image as base64 JPEG string."""
    params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode(".jpg", image, params)
    return base64.b64encode(buffer).decode("utf-8")


# ── Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/screenshot")
def api_screenshot():
    """Get current screenshot as base64 JPEG."""
    screen = _capture_screenshot()
    if screen is None:
        return jsonify({"error": "No device connected"}), 503

    # Check if we should draw match overlay
    template_path = request.args.get("match_template")
    threshold = float(request.args.get("threshold", 0.8))

    display = screen.copy()

    if template_path and Path(template_path).exists():
        matches = find_all_templates(screen, template_path, threshold=threshold, max_results=10)
        tpl = cv2.imread(template_path)
        if tpl is not None:
            th, tw = tpl.shape[:2]
            for mx, my, conf in matches:
                x1 = mx - tw // 2
                y1 = my - th // 2
                cv2.rectangle(display, (x1, y1), (x1 + tw, y1 + th), (0, 255, 0), 2)
                cv2.putText(
                    display, f"{conf:.2f}",
                    (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                )

    # Draw any coordinate regions being edited
    regions_json = request.args.get("highlight_regions")
    if regions_json:
        try:
            regions = json.loads(regions_json)
            for region in regions:
                x, y, w, h = region["x"], region["y"], region["w"], region["h"]
                color = (0, 200, 255)  # Orange
                cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
                if "name" in region:
                    cv2.putText(
                        display, region["name"],
                        (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
                    )
        except (json.JSONDecodeError, KeyError):
            pass

    img_b64 = _encode_image(display)
    h, w = display.shape[:2]
    return jsonify({"image": img_b64, "width": w, "height": h})


@app.route("/api/screenshot/stream")
def api_screenshot_stream():
    """MJPEG stream of screenshots."""
    def generate():
        while True:
            screen = _capture_screenshot()
            if screen is not None:
                _, buffer = cv2.imencode(".jpg", screen, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame = buffer.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.5)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/match_test", methods=["POST"])
def api_match_test():
    """Test template matching on current screenshot."""
    data = request.get_json()
    template_path = data.get("template_path", "")
    threshold = float(data.get("threshold", 0.8))

    if not Path(template_path).exists():
        return jsonify({"error": f"Template not found: {template_path}"}), 404

    screen = _capture_screenshot()
    if screen is None:
        return jsonify({"error": "No device connected"}), 503

    matches = find_all_templates(screen, template_path, threshold=threshold)

    # Create annotated image
    display = screen.copy()
    tpl = cv2.imread(template_path)
    results = []
    if tpl is not None:
        th, tw = tpl.shape[:2]
        for mx, my, conf in matches:
            x1 = mx - tw // 2
            y1 = my - th // 2
            cv2.rectangle(display, (x1, y1), (x1 + tw, y1 + th), (0, 255, 0), 2)
            cv2.putText(
                display, f"{conf:.2f}",
                (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
            results.append({"x": mx, "y": my, "confidence": round(conf, 4)})

    return jsonify({
        "image": _encode_image(display),
        "matches": results,
        "template": template_path,
        "threshold": threshold,
    })


@app.route("/api/capture_template", methods=["POST"])
def api_capture_template():
    """Capture a region of the current screenshot as a template."""
    data = request.get_json()
    x = int(data["x"])
    y = int(data["y"])
    w = int(data["w"])
    h = int(data["h"])
    name = data.get("name", f"template_{int(time.time())}")
    category = data.get("category", "buttons")

    screen = _capture_screenshot()
    if screen is None:
        return jsonify({"error": "No device connected"}), 503

    # Crop the region
    cropped = screen[y:y + h, x:x + w]
    if cropped.size == 0:
        return jsonify({"error": "Invalid region"}), 400

    # Save template
    save_dir = Path(f"assets/templates/{category}")
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}.png"
    save_path = save_dir / filename
    cv2.imwrite(str(save_path), cropped)

    # Clear template cache so new template is picked up
    _template_cache.pop(str(save_path), None)

    logger.info("Captured template: %s (%dx%d)", save_path, w, h)
    return jsonify({
        "path": str(save_path),
        "preview": _encode_image(cropped),
        "width": w,
        "height": h,
    })


@app.route("/api/templates")
def api_templates():
    """List all available template images."""
    templates_dir = Path("assets/templates")
    templates = []
    for png in sorted(templates_dir.rglob("*.png")):
        rel = str(png.relative_to("."))
        img = cv2.imread(str(png))
        h, w = (0, 0) if img is None else img.shape[:2]
        templates.append({
            "path": rel,
            "name": png.stem,
            "category": png.parent.name,
            "width": w,
            "height": h,
        })
    return jsonify(templates)


@app.route("/api/tasks")
def api_tasks():
    """Get current task states."""
    if _scheduler is None:
        return jsonify({"error": "Scheduler not running"}), 503

    tasks = []
    for task in _scheduler.tasks:
        elapsed = time.time() - task.last_run if task.last_run > 0 else -1
        tasks.append({
            "name": task.name,
            "enabled": task.config.enabled,
            "priority": task.config.priority,
            "cooldown": task.config.cooldown,
            "last_run": elapsed,
            "run_count": task.run_count,
            "fail_count": task.fail_count,
        })
    return jsonify(tasks)


@app.route("/api/tasks/<task_name>", methods=["PATCH"])
def api_update_task(task_name: str):
    """Update task configuration at runtime."""
    if _scheduler is None:
        return jsonify({"error": "Scheduler not running"}), 503

    data = request.get_json()
    for task in _scheduler.tasks:
        if task.name == task_name:
            if "enabled" in data:
                task.config.enabled = bool(data["enabled"])
            if "cooldown" in data:
                task.config.cooldown = float(data["cooldown"])
            if "priority" in data:
                task.config.priority = int(data["priority"])
            logger.info("Task '%s' updated: %s", task_name, data)
            return jsonify({"ok": True, "task": task_name, "updated": data})

    return jsonify({"error": f"Task not found: {task_name}"}), 404


@app.route("/api/state")
def api_state():
    """Get current game state."""
    if _scheduler is None:
        return jsonify({"error": "Scheduler not running"}), 503

    state = _scheduler.game_state
    return jsonify({
        "current_screen": state.current_screen,
        "resources_collected": state.resources_collected,
        "teams_joined": state.teams_joined,
        "daily_tasks_completed": state.daily_tasks_completed,
        "timers_checked": state.timers_checked,
        "errors": state.errors,
        "last_error": state.last_error,
    })


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """Get or update runtime configuration."""
    if request.method == "GET":
        import yaml
        try:
            with open("config/settings.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return jsonify(config)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # POST - update config
    data = request.get_json()
    import yaml
    try:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # Deep merge
        _deep_update(config, data)

        with open("config/settings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info("Config updated via dashboard: %s", list(data.keys()))
        return jsonify({"ok": True, "config": config})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/coordinates", methods=["GET", "POST"])
def api_coordinates():
    """Get or update coordinate configuration."""
    import yaml
    if request.method == "GET":
        try:
            with open("config/coordinates.yaml", "r", encoding="utf-8") as f:
                coords = yaml.safe_load(f) or {}
            return jsonify(coords)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    data = request.get_json()
    try:
        with open("config/coordinates.yaml", "r", encoding="utf-8") as f:
            coords = yaml.safe_load(f) or {}

        _deep_update(coords, data)

        with open("config/coordinates.yaml", "w", encoding="utf-8") as f:
            yaml.dump(coords, f, default_flow_style=False, allow_unicode=True)

        # Reload timer monitor if scheduler is running
        if _scheduler:
            for task in _scheduler.tasks:
                if task.name == "timer_monitor":
                    task._load_timers()
                    break

        logger.info("Coordinates updated via dashboard")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _deep_update(base: dict, updates: dict) -> None:
    """Recursively update a dict."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def run_dashboard(host: str = "0.0.0.0", port: int = 5000):
    """Start the dashboard web server in a background thread."""
    def _run():
        app.run(host=host, port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info("Dashboard running at http://%s:%d", host, port)
    return thread
