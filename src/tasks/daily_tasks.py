import time
from pathlib import Path

from src.device.base import DeviceController
from src.game.actions import close_popup, scroll_screen, tap_template
from src.game.state import GameState
from src.tasks.base import Task, TaskConfig, TaskResult
from src.utils.helpers import sleep_random
from src.utils.logger import logger
from src.vision.matcher import find_all_templates

# Template paths
DAILY_TASKS_BTN = "assets/templates/buttons/daily_tasks_btn.png"
CLAIM_BTN = "assets/templates/buttons/claim_btn.png"
CHECKIN_BTN = "assets/templates/buttons/checkin_btn.png"
CLAIM_ALL_BTN = "assets/templates/buttons/claim_all_btn.png"

# Seconds in a day
DAY_SECONDS = 86400


class DailyTasksTask(Task):
    """Automatically complete daily check-ins and claim task rewards."""

    def __init__(self, config: TaskConfig | None = None):
        super().__init__(
            "daily_tasks",
            config or TaskConfig(priority=4, cooldown=DAY_SECONDS),
        )

    def should_run(self, game_state: GameState) -> bool:
        if not super().should_run(game_state):
            return False

        # Only run if daily tasks haven't been completed today
        if game_state.daily_tasks_completed:
            time_since_reset = time.time() - game_state.last_daily_reset
            if time_since_reset < DAY_SECONDS:
                return False
            # New day, reset the flag
            game_state.daily_tasks_completed = False

        return True

    def execute(self, device: DeviceController, game_state: GameState) -> TaskResult:
        logger.info("Starting daily tasks")

        claimed = 0

        # Try daily check-in first
        claimed += self._do_checkin(device)

        # Open daily tasks screen
        if not tap_template(device, DAILY_TASKS_BTN, timeout=5.0):
            logger.warning("Could not open daily tasks screen")
            return TaskResult.FAILURE if claimed == 0 else TaskResult.SUCCESS

        sleep_random(1.0)

        # Try "claim all" button first
        if Path(CLAIM_ALL_BTN).exists():
            screen = device.screenshot()
            from src.vision.matcher import find_template
            if find_template(screen, CLAIM_ALL_BTN, threshold=0.8):
                tap_template(device, CLAIM_ALL_BTN, timeout=2.0)
                claimed += 1
                sleep_random(0.5)

        # Scan for individual claim buttons
        for scroll_attempt in range(3):
            screen = device.screenshot()
            claim_buttons = find_all_templates(screen, CLAIM_BTN, threshold=0.8)

            for btn_x, btn_y, confidence in claim_buttons:
                device.tap(btn_x, btn_y)
                sleep_random(0.5)
                # Close any reward popup
                close_popup(device)
                sleep_random(0.3)
                claimed += 1

            if not claim_buttons and scroll_attempt < 2:
                scroll_screen(device, direction="down", distance=200)
                sleep_random(0.5)
            elif not claim_buttons:
                break

        # Close daily tasks screen
        close_popup(device)

        if claimed > 0:
            logger.info("Claimed %d daily rewards", claimed)
            game_state.daily_tasks_completed = True
            game_state.last_daily_reset = time.time()
            return TaskResult.SUCCESS

        logger.info("No daily rewards available to claim")
        return TaskResult.SKIPPED

    def _do_checkin(self, device: DeviceController) -> int:
        """Attempt daily check-in."""
        if not Path(CHECKIN_BTN).exists():
            return 0

        if tap_template(device, CHECKIN_BTN, timeout=3.0):
            logger.info("Daily check-in completed")
            sleep_random(0.5)
            close_popup(device)
            return 1

        return 0
