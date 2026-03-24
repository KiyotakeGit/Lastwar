import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2

from src.device.base import DeviceController
from src.game.actions import close_popup
from src.game.state import GameState
from src.tasks.base import Task, TaskResult
from src.utils.helpers import sleep_random
from src.utils.logger import logger


class Scheduler:
    """Main task scheduler that orchestrates automation tasks."""

    def __init__(
        self,
        device: DeviceController,
        tasks: list[Task],
        poll_interval: float = 2.0,
        max_errors: int = 10,
    ):
        self.device = device
        self.tasks = sorted(tasks, key=lambda t: t.config.priority)
        self.poll_interval = poll_interval
        self.max_errors = max_errors
        self.game_state = GameState.load()
        self._running = False
        self._error_count = 0

    def run(self) -> None:
        """Start the main automation loop."""
        self._running = True
        enabled = [t for t in self.tasks if t.config.enabled]
        logger.info(
            "Scheduler started with %d tasks: %s",
            len(enabled),
            ", ".join(t.name for t in enabled),
        )

        try:
            while self._running:
                self._tick()
                sleep_random(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self.game_state.save()
            logger.info("Game state saved")

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        self._running = False

    def _tick(self) -> None:
        """Execute one cycle of task checks."""
        for task in self.tasks:
            if not task.config.enabled:
                continue

            if not task.should_run(self.game_state):
                continue

            logger.info("--- Running task: %s ---", task.name)
            result = self._safe_execute(task)
            task.on_complete(result, self.game_state)

            if result == TaskResult.SUCCESS:
                logger.info("Task '%s' completed successfully", task.name)
                self._error_count = 0
            elif result == TaskResult.FAILURE:
                logger.warning("Task '%s' failed", task.name)
                self._error_count += 1

            # Periodically save state
            self.game_state.save()

            if self._error_count >= self.max_errors:
                logger.error("Too many consecutive errors (%d), pausing...", self._error_count)
                self._recover()
                self._error_count = 0
                time.sleep(30)

    def _safe_execute(self, task: Task) -> TaskResult:
        """Execute a task with error handling."""
        try:
            return task.execute(self.device, self.game_state)
        except Exception as e:
            logger.error("Task '%s' crashed: %s", task.name, e)
            logger.debug(traceback.format_exc())
            self.game_state.errors += 1
            self.game_state.last_error = str(e)
            self._save_error_screenshot(task.name)
            self._recover()
            return TaskResult.FAILURE

    def _recover(self) -> None:
        """Try to recover to a known good state after an error."""
        logger.info("Attempting recovery...")
        try:
            # Try closing any popups
            for _ in range(3):
                if not close_popup(self.device):
                    break
                sleep_random(0.5)
        except Exception as e:
            logger.error("Recovery failed: %s", e)

    def _save_error_screenshot(self, task_name: str) -> None:
        """Save a screenshot for debugging when a task crashes."""
        try:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = screenshots_dir / f"error_{task_name}_{timestamp}.png"
            screen = self.device.screenshot()
            cv2.imwrite(str(filename), screen)
            logger.info("Error screenshot saved: %s", filename)
        except Exception:
            pass
