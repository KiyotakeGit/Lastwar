from pathlib import Path

import cv2
import numpy as np

from src.device.base import DeviceController
from src.utils.logger import logger

# Cache loaded template images
_template_cache: dict[str, np.ndarray] = {}


def _load_template(template_path: str) -> np.ndarray:
    """Load and cache a template image."""
    if template_path not in _template_cache:
        tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if tpl is None:
            raise FileNotFoundError(f"Template not found: {template_path}")
        _template_cache[template_path] = tpl
    return _template_cache[template_path]


def find_template(
    screen: np.ndarray,
    template_path: str,
    threshold: float = 0.8,
    use_multiscale: bool = False,
) -> tuple[int, int, float] | None:
    """Find a template in the screen image.

    Args:
        screen: BGR screen image.
        template_path: Path to the template image file.
        threshold: Minimum match confidence (0-1).
        use_multiscale: Try matching at multiple scales for robustness.

    Returns:
        (center_x, center_y, confidence) if found, else None.
    """
    template = _load_template(template_path)
    scales = [0.9, 1.0, 1.1] if use_multiscale else [1.0]

    best_match = None
    best_confidence = 0.0

    for scale in scales:
        if scale != 1.0:
            w = int(template.shape[1] * scale)
            h = int(template.shape[0] * scale)
            tpl = cv2.resize(template, (w, h))
        else:
            tpl = template

        if tpl.shape[0] > screen.shape[0] or tpl.shape[1] > screen.shape[1]:
            continue

        result = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > best_confidence:
            best_confidence = max_val
            th, tw = tpl.shape[:2]
            center_x = max_loc[0] + tw // 2
            center_y = max_loc[1] + th // 2
            best_match = (center_x, center_y, max_val)

    if best_match and best_match[2] >= threshold:
        logger.debug(
            "Template %s found at (%d, %d) confidence=%.3f",
            Path(template_path).name, best_match[0], best_match[1], best_match[2],
        )
        return best_match

    return None


def find_all_templates(
    screen: np.ndarray,
    template_path: str,
    threshold: float = 0.8,
    max_results: int = 20,
) -> list[tuple[int, int, float]]:
    """Find all occurrences of a template in the screen.

    Uses non-maximum suppression to avoid overlapping detections.

    Returns:
        List of (center_x, center_y, confidence) tuples.
    """
    template = _load_template(template_path)
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    th, tw = template.shape[:2]

    locations = []
    result_copy = result.copy()

    for _ in range(max_results):
        _, max_val, _, max_loc = cv2.minMaxLoc(result_copy)
        if max_val < threshold:
            break

        center_x = max_loc[0] + tw // 2
        center_y = max_loc[1] + th // 2
        locations.append((center_x, center_y, max_val))

        # Suppress the area around this detection
        x_start = max(0, max_loc[0] - tw // 2)
        y_start = max(0, max_loc[1] - th // 2)
        x_end = min(result_copy.shape[1], max_loc[0] + tw // 2 + 1)
        y_end = min(result_copy.shape[0], max_loc[1] + th // 2 + 1)
        result_copy[y_start:y_end, x_start:x_end] = 0

    return locations


def wait_for_template(
    device: DeviceController,
    template_path: str,
    timeout: float = 10.0,
    interval: float = 0.5,
    threshold: float = 0.8,
) -> tuple[int, int] | None:
    """Poll the screen until a template appears or timeout is reached.

    Returns:
        (center_x, center_y) if found, else None.
    """
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = device.screenshot()
        match = find_template(screen, template_path, threshold=threshold)
        if match:
            return match[0], match[1]
        time.sleep(interval)

    logger.warning("Timeout waiting for template: %s", Path(template_path).name)
    return None
