"""Names the app in Windows notifications ("Mouse Battery" instead of "Python") through a registered AppUserModelID."""

import ctypes
import logging
import winreg
from pathlib import Path

from mouse_battery_tray.icon import render_app_icon

logger = logging.getLogger(__name__)

APP_ID = "MouseBatteryTray"
DISPLAY_NAME = "Mouse Battery"


def register(data_dir: Path) -> None:
    """Write the display name and logo under HKCU and adopt the app id; call before the tray icon is created."""
    icon_path = data_dir / "app-icon.png"
    render_app_icon().save(icon_path)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{APP_ID}") as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, DISPLAY_NAME)
        winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(icon_path))
    result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    if result != 0:
        logger.warning("could not set the app id (HRESULT %#x); notifications will say Python", result & 0xFFFFFFFF)
