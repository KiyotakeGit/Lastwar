from pathlib import Path

from src.device.base import DeviceController
from src.utils.helpers import random_offset, sleep_random
from src.utils.logger import logger
from src.vision.matcher import find_template, wait_for_template


def tap_template(
    device: DeviceController,
    template_path: str,
    timeout: float = 10.0,
    threshold: float = 0.8,
    offset_radius: int = 3,
) -> bool:
    """Wait for a template to appear and tap it.

    Returns:
        True if the template was found and tapped, False on timeout.
    """
    pos = wait_for_template(device, template_path, timeout=timeout, threshold=threshold)
    if pos is None:
        logger.warning("tap_template: template not found: %s", Path(template_path).name)
        return False

    x, y = random_offset(pos[0], pos[1], radius=offset_radius)
    device.tap(x, y)
    sleep_random(0.3)
    return True


def tap_and_confirm(
    device: DeviceController,
    button_template: str,
    confirm_template: str,
    timeout: float = 10.0,
) -> bool:
    """Tap a button, then wait for and tap a confirmation dialog.

    Returns:
        True if both taps succeeded.
    """
    if not tap_template(device, button_template, timeout=timeout):
        return False

    sleep_random(0.5)
    return tap_template(device, confirm_template, timeout=5.0)


def tap_if_visible(
    device: DeviceController,
    template_path: str,
    threshold: float = 0.8,
) -> bool:
    """Tap a template if it's currently visible (no waiting).

    Returns:
        True if tapped, False if not visible.
    """
    screen = device.screenshot()
    match = find_template(screen, template_path, threshold=threshold)
    if match:
        x, y = random_offset(match[0], match[1], radius=3)
        device.tap(x, y)
        sleep_random(0.2)
        return True
    return False


def close_popup(device: DeviceController, close_templates: list[str] | None = None) -> bool:
    """Try to close any popup by looking for common close/X buttons.

    Args:
        close_templates: List of template paths for close buttons.
                         Defaults to common close button templates.

    Returns:
        True if a close button was found and tapped.
    """
    if close_templates is None:
        close_templates = [
            "assets/templates/buttons/close_btn.png",
            "assets/templates/buttons/x_btn.png",
        ]

    for tpl in close_templates:
        if Path(tpl).exists() and tap_if_visible(device, tpl):
            logger.debug("Closed popup using: %s", Path(tpl).name)
            return True

    return False


def scroll_screen(
    device: DeviceController,
    direction: str = "down",
    distance: int = 300,
) -> None:
    """Scroll the game screen in a direction.

    Args:
        direction: 'up', 'down', 'left', or 'right'.
        distance: Scroll distance in pixels.
    """
    w, h = device.screen_size()
    cx, cy = w // 2, h // 2

    directions = {
        "up": (cx, cy, cx, cy - distance),
        "down": (cx, cy, cx, cy + distance),
        "left": (cx, cy, cx - distance, cy),
        "right": (cx, cy, cx + distance, cy),
    }

    if direction not in directions:
        logger.warning("Unknown scroll direction: %s", direction)
        return

    x1, y1, x2, y2 = directions[direction]
    device.swipe(x1, y1, x2, y2, duration_ms=400)
    sleep_random(0.3)
