"""Path utilities for PyInstaller compatibility.

When packaged as an exe, data files are extracted to a temp folder.
This module provides the correct base path for accessing config/assets.
"""

import os
import sys
from pathlib import Path


def get_base_path() -> Path:
    """Get the base directory for resource files.

    Returns the correct path whether running from source or as a packaged exe.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running from source
        return Path.cwd()


def get_data_path() -> Path:
    """Get the writable data directory.

    Config and state files need to be writable, so when packaged,
    use the directory where the exe is located instead of the temp folder.
    """
    if getattr(sys, 'frozen', False):
        return Path(os.path.dirname(sys.executable))
    else:
        return Path.cwd()


def resource_path(relative_path: str) -> str:
    """Convert a relative path to an absolute path that works in both dev and packaged mode."""
    # First check writable data dir (for user-created templates, configs)
    data_path = get_data_path() / relative_path
    if data_path.exists():
        return str(data_path)

    # Fall back to bundled resources
    base_path = get_base_path() / relative_path
    return str(base_path)
