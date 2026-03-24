"""Last War Game Automation Script - Entry Point."""

import argparse
import sys
import threading
from pathlib import Path

import yaml

from src.device.base import DeviceController
from src.scheduler.engine import Scheduler
from src.tasks.auto_join_team import AutoJoinTeamTask
from src.tasks.base import TaskConfig
from src.tasks.daily_tasks import DailyTasksTask
from src.tasks.resource_collect import ResourceCollectTask
from src.tasks.timer_monitor import TimerMonitorTask
from src.utils.logger import logger, setup_logger
from src.utils.paths import resource_path


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load configuration from YAML file."""
    try:
        resolved = resource_path(config_path)
        with open(resolved, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning("Config file not found: %s, using defaults", config_path)
        return {}


def create_device(config: dict) -> DeviceController:
    """Create the appropriate device controller based on config."""
    platform = config.get("platform", "pc")

    if platform == "pc":
        from src.device.pc import PCController
        pc_config = config.get("pc", {})
        region = pc_config.get("game_region")
        if region:
            region = tuple(region)
        return PCController(game_region=region)

    elif platform == "android":
        from src.device.android import AndroidController
        android_config = config.get("android", {})
        serial = android_config.get("serial")
        return AndroidController(serial=serial)

    else:
        raise ValueError(f"Unknown platform: {platform}")


def create_tasks(config: dict) -> list:
    """Create task instances based on config."""
    tasks_config = config.get("tasks", {})
    tasks = []

    task_classes = {
        "auto_join_team": AutoJoinTeamTask,
        "timer_monitor": TimerMonitorTask,
        "resource_collect": ResourceCollectTask,
        "daily_tasks": DailyTasksTask,
    }

    for task_name, task_cls in task_classes.items():
        tc = tasks_config.get(task_name, {})
        task_config = TaskConfig(
            enabled=tc.get("enabled", True),
            priority=tc.get("priority", 5),
            cooldown=tc.get("cooldown", 60),
        )
        tasks.append(task_cls(config=task_config))

    return tasks


def main():
    parser = argparse.ArgumentParser(description="Last War Game Automation")
    parser.add_argument(
        "--platform", choices=["pc", "android"],
        help="Override platform setting from config",
    )
    parser.add_argument(
        "--config", default="config/settings.yaml",
        help="Path to config file (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--log-file", default=None,
        help="Log file path (optional)",
    )
    parser.add_argument(
        "--no-gui", action="store_true",
        help="Run in headless mode without GUI (terminal only)",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logger(level=args.log_level, log_file=args.log_file)

    logger.info("=== Last War Automation Script ===")
    logger.info("Config: %s", args.config)

    # Load config
    config = load_config(args.config)
    if args.platform:
        config["platform"] = args.platform

    logger.info("Platform: %s", config.get("platform", "pc"))

    # Check templates directory
    templates_dir = Path("assets/templates")
    if not any(templates_dir.rglob("*.png")):
        logger.warning(
            "No template images found in %s. "
            "Use the GUI to capture template screenshots from the game.",
            templates_dir,
        )

    # Create device and tasks
    try:
        device = create_device(config)
    except Exception as e:
        logger.error("Failed to initialize device: %s", e)
        sys.exit(1)

    tasks = create_tasks(config)
    poll_interval = config.get("screenshot_interval", 2.0)

    # Create scheduler
    scheduler = Scheduler(
        device=device,
        tasks=tasks,
        poll_interval=poll_interval,
    )

    if args.no_gui:
        # Headless mode - run scheduler directly
        logger.info("Running in headless mode. Press Ctrl+C to stop.")
        scheduler.run()
    else:
        # GUI mode - run scheduler in background thread, GUI in main thread
        from src.gui.app import App

        scheduler_thread = threading.Thread(target=scheduler.run, daemon=True)
        scheduler_thread.start()

        app = App(device, scheduler)
        app.mainloop()


if __name__ == "__main__":
    main()
