from collections import deque
from pathlib import Path

from src.device.base import DeviceController
from src.game.actions import tap_template
from src.utils.helpers import sleep_random
from src.utils.logger import logger
from src.vision.screen import ScreenState, detect_current_screen


class Transition:
    """A transition between two screen states."""

    def __init__(self, from_state: ScreenState, to_state: ScreenState, template_path: str):
        self.from_state = from_state
        self.to_state = to_state
        self.template_path = template_path


class Navigator:
    """Navigate between game screens using a transition graph."""

    def __init__(self):
        self._transitions: list[Transition] = []
        self._adjacency: dict[ScreenState, list[Transition]] = {}

    def register_transition(
        self, from_state: ScreenState, to_state: ScreenState, template_path: str,
    ) -> None:
        """Register a navigation transition.

        Args:
            from_state: Starting screen state.
            to_state: Target screen state after tapping.
            template_path: Button template to tap to trigger transition.
        """
        t = Transition(from_state, to_state, template_path)
        self._transitions.append(t)
        self._adjacency.setdefault(from_state, []).append(t)

    def navigate_to(
        self,
        device: DeviceController,
        target: ScreenState,
        max_steps: int = 10,
    ) -> bool:
        """Navigate from the current screen to the target screen.

        Uses BFS to find the shortest path through the transition graph.

        Returns:
            True if navigation succeeded.
        """
        screen = device.screenshot()
        current = detect_current_screen(screen)

        if current == target:
            logger.debug("Already on screen: %s", target.name)
            return True

        if current == ScreenState.UNKNOWN:
            logger.warning("Cannot determine current screen, navigation may fail")
            return False

        # BFS to find path
        path = self._find_path(current, target)
        if path is None:
            logger.error("No path from %s to %s", current.name, target.name)
            return False

        logger.info("Navigating: %s", " -> ".join(t.to_state.name for t in path))

        for transition in path:
            if not Path(transition.template_path).exists():
                logger.error("Transition template missing: %s", transition.template_path)
                return False

            if not tap_template(device, transition.template_path, timeout=5.0):
                logger.error("Failed to tap transition button: %s", transition.template_path)
                return False

            sleep_random(1.0)

            # Verify we reached the expected screen
            screen = device.screenshot()
            reached = detect_current_screen(screen)
            if reached != transition.to_state:
                logger.warning(
                    "Expected %s but got %s after transition",
                    transition.to_state.name, reached.name,
                )

        return True

    def _find_path(
        self, start: ScreenState, target: ScreenState,
    ) -> list[Transition] | None:
        """BFS to find shortest transition path."""
        if start == target:
            return []

        visited = {start}
        queue: deque[tuple[ScreenState, list[Transition]]] = deque()
        queue.append((start, []))

        while queue:
            current, path = queue.popleft()
            for transition in self._adjacency.get(current, []):
                if transition.to_state in visited:
                    continue
                new_path = path + [transition]
                if transition.to_state == target:
                    return new_path
                visited.add(transition.to_state)
                queue.append((transition.to_state, new_path))

        return None
