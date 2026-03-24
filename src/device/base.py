from abc import ABC, abstractmethod

import numpy as np

REFERENCE_RESOLUTION = (1280, 720)


class DeviceController(ABC):
    """Abstract base class for device interaction."""

    @abstractmethod
    def screenshot(self) -> np.ndarray:
        """Capture the current screen.

        Returns:
            BGR numpy array of the screen image.
        """

    @abstractmethod
    def tap(self, x: int, y: int) -> None:
        """Tap at the given screen coordinates."""

    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """Perform a swipe gesture from (x1,y1) to (x2,y2)."""

    @abstractmethod
    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long press at the given coordinates."""

    @abstractmethod
    def screen_size(self) -> tuple[int, int]:
        """Return the screen size as (width, height)."""

    def scale_from_reference(self, x: int, y: int) -> tuple[int, int]:
        """Scale coordinates from reference resolution to actual screen size."""
        w, h = self.screen_size()
        scale_x = w / REFERENCE_RESOLUTION[0]
        scale_y = h / REFERENCE_RESOLUTION[1]
        return int(x * scale_x), int(y * scale_y)
