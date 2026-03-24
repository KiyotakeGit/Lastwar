from src.device.base import DeviceController
from src.game.actions import close_popup, scroll_screen, tap_template
from src.game.state import GameState
from src.tasks.base import Task, TaskConfig, TaskResult
from src.utils.helpers import sleep_random
from src.utils.logger import logger
from src.vision.matcher import find_all_templates

# Template paths
RALLY_LIST_BTN = "assets/templates/buttons/rally_list_btn.png"
JOIN_BTN = "assets/templates/buttons/join_btn.png"
CONFIRM_BTN = "assets/templates/buttons/confirm_btn.png"


class AutoJoinTeamTask(Task):
    """Automatically detect and join available team rallies."""

    def __init__(self, config: TaskConfig | None = None):
        super().__init__("auto_join_team", config or TaskConfig(priority=1, cooldown=30))
        self.max_scroll_attempts = 3

    def execute(self, device: DeviceController, game_state: GameState) -> TaskResult:
        logger.info("Starting auto join team task")

        # Try to open rally/team list
        if not tap_template(device, RALLY_LIST_BTN, timeout=5.0):
            logger.warning("Could not find rally list button")
            return TaskResult.FAILURE

        sleep_random(1.0)
        joined = False

        for scroll_attempt in range(self.max_scroll_attempts):
            # Look for join buttons on current view
            screen = device.screenshot()
            join_buttons = find_all_templates(screen, JOIN_BTN, threshold=0.8)

            if join_buttons:
                # Tap the first available join button
                x, y, confidence = join_buttons[0]
                logger.info(
                    "Found join button at (%d, %d) confidence=%.3f",
                    x, y, confidence,
                )
                device.tap(x, y)
                sleep_random(0.5)

                # Confirm join
                if tap_template(device, CONFIRM_BTN, timeout=3.0):
                    logger.info("Successfully joined a team rally")
                    game_state.teams_joined += 1
                    joined = True
                    sleep_random(0.5)
                    break
                else:
                    logger.warning("Join confirmation failed")

            # Scroll down to find more
            if scroll_attempt < self.max_scroll_attempts - 1:
                scroll_screen(device, direction="down", distance=200)
                sleep_random(0.5)

        # Close the rally list
        close_popup(device)

        if joined:
            return TaskResult.SUCCESS

        logger.info("No teams available to join")
        return TaskResult.SKIPPED
