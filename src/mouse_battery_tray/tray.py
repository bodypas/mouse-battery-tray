"""A sharp tray icon on Windows: per-monitor DPI awareness, and the icon loaded at exactly the tray's size.

Without DPI awareness Windows hands the app 100%-scaling sizes and stretches the result, and pystray loads its icon at
the large-icon size, which the tray then shrinks to the small-icon size; both blur small digits.
"""

import ctypes
import os
import tempfile
from typing import BinaryIO

import pystray
from PIL import Image
from pystray._util import win32

SM_CXSMICON = 49
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
PROCESS_PER_MONITOR_DPI_AWARE = 2
S_OK = 0


def enable_dpi_awareness() -> bool:
    """Use real pixels for the tray icon size and the menu. Call before any window exists; False if Windows refused."""
    try:
        context = ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        return bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(context))
    except AttributeError:  # before Windows 10 1703
        return ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE) == S_OK


def icon_size() -> int:
    """The tray's icon size in pixels: 16 at 100% scaling, 24 at 150%, 32 at 200%."""
    return ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON)


def save_ico(image: Image.Image, file: BinaryIO) -> None:
    """One frame at the image's own size: Pillow's default frames skip 20 px (125%) and 28 px (175%)."""
    image.save(file, format="ICO", sizes=[image.size])


class TrayIcon(pystray.Icon):
    """pystray's Windows icon, loaded at the tray's size instead of the large-icon size."""

    def _assert_icon_handle(self) -> None:
        # Replaces pystray 0.19.5's version, which saves Pillow's default frames and loads with LR_DEFAULTSIZE (the
        # large-icon size, 32 px at 100%), so the tray shrinks it.
        if self._icon_handle:
            return
        size = icon_size()
        fd, path = tempfile.mkstemp(".ico")
        try:
            with os.fdopen(fd, "wb") as file:
                save_ico(self.icon, file)
            self._icon_handle = win32.LoadImage(None, path, win32.IMAGE_ICON, size, size, win32.LR_LOADFROMFILE)
        finally:
            os.unlink(path)
