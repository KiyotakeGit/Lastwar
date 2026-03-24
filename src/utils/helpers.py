import random
import time


def sleep_random(base: float, jitter: float = 0.3) -> None:
    """Sleep for a random duration around base seconds.

    Args:
        base: Base sleep time in seconds.
        jitter: Maximum fraction of base to add/subtract (e.g., 0.3 = +/-30%).
    """
    offset = base * jitter * (2 * random.random() - 1)
    time.sleep(max(0.05, base + offset))


def scale_coords(
    x: int, y: int, from_res: tuple[int, int], to_res: tuple[int, int]
) -> tuple[int, int]:
    """Scale coordinates from one resolution to another.

    Args:
        x, y: Original coordinates.
        from_res: Reference resolution (width, height).
        to_res: Target resolution (width, height).

    Returns:
        Scaled (x, y) coordinates.
    """
    scale_x = to_res[0] / from_res[0]
    scale_y = to_res[1] / from_res[1]
    return int(x * scale_x), int(y * scale_y)


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp a value to [min_val, max_val]."""
    return max(min_val, min(value, max_val))


def random_offset(x: int, y: int, radius: int = 5) -> tuple[int, int]:
    """Add a small random offset to coordinates to appear more human-like."""
    dx = random.randint(-radius, radius)
    dy = random.randint(-radius, radius)
    return x + dx, y + dy
