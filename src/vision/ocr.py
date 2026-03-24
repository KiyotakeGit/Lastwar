import re
from datetime import timedelta

import cv2
import numpy as np
import pytesseract

from src.utils.logger import logger


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Preprocess an image region for better OCR accuracy.

    Pipeline: grayscale -> bilateral filter -> Otsu threshold -> invert if needed.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Bilateral filter to reduce noise while keeping edges
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)

    # Otsu's binarization
    _, binary = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # If background is dark (game timer text is usually light on dark),
    # invert so text is black on white for Tesseract
    if np.mean(binary) > 127:
        binary = cv2.bitwise_not(binary)

    return binary


def read_timer(screen: np.ndarray, region: tuple[int, int, int, int]) -> timedelta | None:
    """Read a timer value from a screen region.

    Args:
        screen: Full BGR screen image.
        region: (x, y, width, height) of the timer area.

    Returns:
        timedelta if successfully parsed, else None.
    """
    x, y, w, h = region
    cropped = screen[y:y + h, x:x + w]

    if cropped.size == 0:
        return None

    processed = preprocess_for_ocr(cropped)

    # Scale up for better OCR accuracy
    scaled = cv2.resize(processed, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    text = pytesseract.image_to_string(
        scaled,
        config="--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789:",
    ).strip()

    return _parse_timer_text(text)


def _parse_timer_text(text: str) -> timedelta | None:
    """Parse timer text in formats like HH:MM:SS, MM:SS, or SS."""
    text = text.replace(" ", "").replace(".", ":")

    # Match HH:MM:SS
    match = re.match(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return timedelta(hours=h, minutes=m, seconds=s)

    # Match MM:SS
    match = re.match(r"(\d{1,2}):(\d{2})", text)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return timedelta(minutes=m, seconds=s)

    # Match plain seconds
    match = re.match(r"(\d+)", text)
    if match:
        return timedelta(seconds=int(match.group(1)))

    logger.warning("Could not parse timer text: '%s'", text)
    return None


def read_text(
    screen: np.ndarray,
    region: tuple[int, int, int, int],
    whitelist: str | None = None,
) -> str:
    """Read text from a screen region using OCR.

    Args:
        screen: Full BGR screen image.
        region: (x, y, width, height) of the text area.
        whitelist: Optional character whitelist for Tesseract.

    Returns:
        Recognized text string.
    """
    x, y, w, h = region
    cropped = screen[y:y + h, x:x + w]

    if cropped.size == 0:
        return ""

    processed = preprocess_for_ocr(cropped)
    scaled = cv2.resize(processed, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    config = "--psm 7 --oem 3"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"

    text = pytesseract.image_to_string(scaled, config=config).strip()
    return text
