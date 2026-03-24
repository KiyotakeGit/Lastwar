from enum import Enum, auto
from pathlib import Path

import numpy as np

from src.vision.matcher import find_template
from src.utils.logger import logger


class ScreenState(Enum):
    """Known game screen states."""
    UNKNOWN = auto()
    CITY_VIEW = auto()
    WORLD_MAP = auto()
    RALLY_LIST = auto()
    TROOP_SELECT = auto()
    DAILY_TASKS = auto()
    RESOURCE_NODE = auto()
    MARCH_CONFIRM = auto()
    POPUP_DIALOG = auto()


# Mapping of screen state to signature template image paths
# These templates should be small, distinctive UI elements unique to each screen
_SCREEN_SIGNATURES: dict[ScreenState, str] = {}

TEMPLATES_DIR = Path("assets/templates/screens")


def register_screen_signature(state: ScreenState, template_filename: str) -> None:
    """Register a template image as the signature for a screen state.

    Args:
        state: The screen state this template identifies.
        template_filename: Filename within assets/templates/screens/.
    """
    path = str(TEMPLATES_DIR / template_filename)
    _SCREEN_SIGNATURES[state] = path
    logger.debug("Registered screen signature: %s -> %s", state.name, path)


def detect_current_screen(
    screen: np.ndarray,
    threshold: float = 0.75,
) -> ScreenState:
    """Detect which game screen is currently displayed.

    Checks the screen against all registered screen signatures.

    Returns:
        The detected ScreenState, or ScreenState.UNKNOWN if no match.
    """
    best_state = ScreenState.UNKNOWN
    best_confidence = 0.0

    for state, template_path in _SCREEN_SIGNATURES.items():
        if not Path(template_path).exists():
            continue

        match = find_template(screen, template_path, threshold=threshold)
        if match and match[2] > best_confidence:
            best_confidence = match[2]
            best_state = state

    if best_state != ScreenState.UNKNOWN:
        logger.debug("Detected screen: %s (confidence=%.3f)", best_state.name, best_confidence)

    return best_state


def _init_default_signatures() -> None:
    """Register default screen signatures if template files exist."""
    defaults = {
        ScreenState.CITY_VIEW: "city_view.png",
        ScreenState.WORLD_MAP: "world_map.png",
        ScreenState.RALLY_LIST: "rally_list.png",
        ScreenState.DAILY_TASKS: "daily_tasks.png",
    }
    for state, filename in defaults.items():
        if (TEMPLATES_DIR / filename).exists():
            register_screen_signature(state, filename)


_init_default_signatures()
