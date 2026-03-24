import numpy as np
import cv2
import mss
import pyautogui

from src.device.base import DeviceController
from src.utils.helpers import sleep_random
from src.utils.logger import logger

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class PCController(DeviceController):
    """PC device controller using mss for screenshots and pyautogui for input."""

    def __init__(self, game_region: tuple[int, int, int, int] | None = None):
        """Initialize PC controller.

        Args:
            game_region: (x, y, width, height) of the game window area.
                         If None, captures the entire primary monitor.
        """
        self._sct = mss.mss()
        self._game_region = game_region
        self._size: tuple[int, int] | None = None
        logger.info("PC controller initialized (region=%s)", game_region)

    def screenshot(self) -> np.ndarray:
        if self._game_region:
            x, y, w, h = self._game_region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = self._sct.monitors[1]

        img = self._sct.grab(monitor)
        frame = np.array(img)
        # mss returns BGRA, convert to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        self._size = (frame.shape[1], frame.shape[0])
        return frame

    def tap(self, x: int, y: int) -> None:
        abs_x, abs_y = self._to_absolute(x, y)
        pyautogui.click(abs_x, abs_y)
        sleep_random(0.1)
        logger.debug("Tap at (%d, %d) -> absolute (%d, %d)", x, y, abs_x, abs_y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        abs_x1, abs_y1 = self._to_absolute(x1, y1)
        abs_x2, abs_y2 = self._to_absolute(x2, y2)
        pyautogui.moveTo(abs_x1, abs_y1)
        pyautogui.drag(
            abs_x2 - abs_x1,
            abs_y2 - abs_y1,
            duration=duration_ms / 1000.0,
        )
        sleep_random(0.15)

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        abs_x, abs_y = self._to_absolute(x, y)
        pyautogui.mouseDown(abs_x, abs_y)
        sleep_random(duration_ms / 1000.0, jitter=0.1)
        pyautogui.mouseUp()

    def screen_size(self) -> tuple[int, int]:
        if self._size:
            return self._size
        if self._game_region:
            return self._game_region[2], self._game_region[3]
        mon = self._sct.monitors[1]
        return mon["width"], mon["height"]

    def _to_absolute(self, x: int, y: int) -> tuple[int, int]:
        """Convert game-relative coordinates to absolute screen coordinates."""
        if self._game_region:
            return x + self._game_region[0], y + self._game_region[1]
        return x, y
