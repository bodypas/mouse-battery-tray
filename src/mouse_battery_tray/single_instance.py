"""Named mutex so autostart plus a manual launch don't put two icons in the tray."""

import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\MouseBatteryTray"


def acquire() -> int | None:
    """Return the mutex handle (keep it referenced for the process lifetime), or None if another instance runs."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle
