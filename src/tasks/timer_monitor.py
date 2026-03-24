from datetime import timedelta

import yaml

from src.device.base import DeviceController
from src.game.actions import tap_if_visible
from src.game.state import GameState
from src.tasks.base import Task, TaskConfig, TaskResult
from src.utils.helpers import sleep_random
from src.utils.logger import logger
from src.vision.ocr import read_timer


class TimerEntry:
    """A monitored in-game timer."""

    def __init__(self, name: str, region: tuple[int, int, int, int], action_template: str):
        """
        Args:
            name: Display name for logging.
            region: (x, y, w, h) screen region where the timer is displayed.
            action_template: Template path for the button to tap when timer reaches zero.
        """
        self.name = name
        self.region = region
        self.action_template = action_template


class TimerMonitorTask(Task):
    """Monitor in-game timers and click when they reach zero."""

    def __init__(self, config: TaskConfig | None = None):
        super().__init__("timer_monitor", config or TaskConfig(priority=2, cooldown=10))
        self.timers: list[TimerEntry] = []
        self._load_timers()

    def _load_timers(self) -> None:
        """Load timer definitions from coordinates config."""
        try:
            with open("config/coordinates.yaml", "r", encoding="utf-8") as f:
                coords = yaml.safe_load(f) or {}

            timer_defs = coords.get("timers", {})
            for name, cfg in timer_defs.items():
                self.timers.append(TimerEntry(
                    name=name,
                    region=tuple(cfg["region"]),
                    action_template=cfg["action_template"],
                ))
            logger.info("Loaded %d timer definitions", len(self.timers))
        except FileNotFoundError:
            logger.warning("coordinates.yaml not found, no timers configured")
        except Exception as e:
            logger.error("Failed to load timer config: %s", e)

    def execute(self, device: DeviceController, game_state: GameState) -> TaskResult:
        logger.info("Checking timers...")

        if not self.timers:
            logger.debug("No timers configured")
            return TaskResult.SKIPPED

        screen = device.screenshot()
        actions_taken = 0

        for timer in self.timers:
            # Scale region to actual resolution
            sx, sy = device.scale_from_reference(timer.region[0], timer.region[1])
            sw, sh = device.scale_from_reference(
                timer.region[0] + timer.region[2],
                timer.region[1] + timer.region[3],
            )
            scaled_region = (sx, sy, sw - sx, sh - sy)

            remaining = read_timer(screen, scaled_region)

            if remaining is None:
                logger.debug("Timer '%s': could not read", timer.name)
                continue

            logger.info("Timer '%s': %s remaining", timer.name, remaining)

            if remaining <= timedelta(seconds=1):
                logger.info("Timer '%s' completed! Tapping action button", timer.name)
                if tap_if_visible(device, timer.action_template):
                    actions_taken += 1
                    sleep_random(0.5)
                else:
                    logger.warning("Action button not visible for timer '%s'", timer.name)

        game_state.timers_checked += 1

        if actions_taken > 0:
            logger.info("Completed %d timer actions", actions_taken)
            return TaskResult.SUCCESS

        return TaskResult.SKIPPED
