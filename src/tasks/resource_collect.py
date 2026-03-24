from pathlib import Path

from src.device.base import DeviceController
from src.game.actions import close_popup, scroll_screen, tap_template
from src.game.state import GameState
from src.tasks.base import Task, TaskConfig, TaskResult
from src.utils.helpers import sleep_random
from src.utils.logger import logger
from src.vision.matcher import find_all_templates, find_template

# Template paths
WORLD_MAP_BTN = "assets/templates/buttons/world_map_btn.png"
GATHER_BTN = "assets/templates/buttons/gather_btn.png"
MARCH_BTN = "assets/templates/buttons/march_btn.png"
MARCH_CONFIRM_BTN = "assets/templates/buttons/march_confirm_btn.png"

# Resource node templates
RESOURCE_TEMPLATES = [
    "assets/templates/icons/food_node.png",
    "assets/templates/icons/wood_node.png",
    "assets/templates/icons/iron_node.png",
    "assets/templates/icons/gold_node.png",
]


class ResourceCollectTask(Task):
    """Automatically find and collect resources on the world map."""

    def __init__(self, config: TaskConfig | None = None, max_marches: int = 3):
        super().__init__(
            "resource_collect",
            config or TaskConfig(priority=3, cooldown=300),
        )
        self.max_marches = max_marches

    def execute(self, device: DeviceController, game_state: GameState) -> TaskResult:
        logger.info("Starting resource collection")

        # Navigate to world map
        if not tap_template(device, WORLD_MAP_BTN, timeout=5.0):
            logger.warning("Could not navigate to world map")
            return TaskResult.FAILURE

        sleep_random(1.5)
        collected = 0

        for attempt in range(self.max_marches):
            # Scan for resource nodes
            node_pos = self._find_resource_node(device)

            if node_pos is None:
                # Scroll around to find resources
                scroll_screen(device, direction="right", distance=250)
                sleep_random(1.0)
                node_pos = self._find_resource_node(device)

            if node_pos is None:
                logger.info("No resource nodes found")
                break

            # Tap the resource node
            x, y = node_pos
            device.tap(x, y)
            sleep_random(0.8)

            # Tap gather/march button
            if not tap_template(device, GATHER_BTN, timeout=3.0):
                logger.warning("Gather button not found")
                close_popup(device)
                continue

            sleep_random(0.5)

            # Confirm march
            if tap_template(device, MARCH_BTN, timeout=3.0):
                sleep_random(0.3)
                # Some games have a second confirmation
                tap_template(device, MARCH_CONFIRM_BTN, timeout=2.0)

                collected += 1
                game_state.resources_collected += 1
                logger.info("Dispatched march %d/%d to collect resources", collected, self.max_marches)
                sleep_random(1.0)
            else:
                logger.warning("March button not found (march slots may be full)")
                close_popup(device)
                break

        if collected > 0:
            logger.info("Resource collection complete: %d marches dispatched", collected)
            return TaskResult.SUCCESS

        return TaskResult.SKIPPED

    def _find_resource_node(self, device: DeviceController) -> tuple[int, int] | None:
        """Find the best resource node on the current screen."""
        screen = device.screenshot()

        for tpl_path in RESOURCE_TEMPLATES:
            if not Path(tpl_path).exists():
                continue

            nodes = find_all_templates(screen, tpl_path, threshold=0.75, max_results=5)
            if nodes:
                # Return the highest confidence match
                best = max(nodes, key=lambda n: n[2])
                logger.debug("Found resource node at (%d, %d)", best[0], best[1])
                return best[0], best[1]

        return None
