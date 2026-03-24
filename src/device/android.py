import subprocess

import cv2
import numpy as np

from src.device.base import DeviceController
from src.utils.helpers import sleep_random
from src.utils.logger import logger


class AndroidController(DeviceController):
    """Android device controller using ADB."""

    def __init__(self, serial: str | None = None):
        """Initialize Android controller.

        Args:
            serial: ADB device serial (e.g., 'emulator-5554').
                    If None, uses the first connected device.
        """
        self._serial = serial
        self._size: tuple[int, int] | None = None
        self._verify_connection()
        logger.info("Android controller initialized (serial=%s)", serial)

    def _adb_cmd(self, *args: str) -> list[str]:
        """Build an ADB command with optional serial."""
        cmd = ["adb"]
        if self._serial:
            cmd.extend(["-s", self._serial])
        cmd.extend(args)
        return cmd

    def _verify_connection(self) -> None:
        """Verify ADB connection to device."""
        result = subprocess.run(
            self._adb_cmd("devices"),
            capture_output=True, text=True, timeout=10,
        )
        if self._serial and self._serial not in result.stdout:
            raise ConnectionError(f"Device {self._serial} not found. Output: {result.stdout}")
        logger.debug("ADB devices: %s", result.stdout.strip())

    def screenshot(self) -> np.ndarray:
        result = subprocess.run(
            self._adb_cmd("exec-out", "screencap", "-p"),
            capture_output=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"screencap failed: {result.stderr.decode()}")

        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Failed to decode screenshot")

        self._size = (frame.shape[1], frame.shape[0])
        return frame

    def tap(self, x: int, y: int) -> None:
        subprocess.run(
            self._adb_cmd("shell", "input", "tap", str(x), str(y)),
            capture_output=True, timeout=10,
        )
        sleep_random(0.15)
        logger.debug("Tap at (%d, %d)", x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        subprocess.run(
            self._adb_cmd(
                "shell", "input", "swipe",
                str(x1), str(y1), str(x2), str(y2), str(duration_ms),
            ),
            capture_output=True, timeout=10,
        )
        sleep_random(0.2)

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        # ADB long press is a swipe from same point to same point
        subprocess.run(
            self._adb_cmd(
                "shell", "input", "swipe",
                str(x), str(y), str(x), str(y), str(duration_ms),
            ),
            capture_output=True, timeout=10,
        )
        sleep_random(0.1)

    def screen_size(self) -> tuple[int, int]:
        if self._size:
            return self._size
        result = subprocess.run(
            self._adb_cmd("shell", "wm", "size"),
            capture_output=True, text=True, timeout=10,
        )
        # Output: "Physical size: 1280x720"
        parts = result.stdout.strip().split()[-1].split("x")
        self._size = (int(parts[0]), int(parts[1]))
        return self._size
