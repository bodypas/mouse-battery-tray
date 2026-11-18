import sys

import pytest

from mouse_battery_tray.autostart import launch_command


@pytest.mark.parametrize(
    ("frozen", "executable", "expected"),
    [
        (True, r"C:\Apps\MouseBatteryTray.exe", r'"C:\Apps\MouseBatteryTray.exe"'),
        (False, r"C:\proj\.venv\Scripts\python.exe", r'"C:\proj\.venv\Scripts\pythonw.exe" -m mouse_battery_tray'),
    ],
)
def test_start_with_windows_launches_the_running_app(
    monkeypatch: pytest.MonkeyPatch, frozen: bool, executable: str, expected: str
) -> None:
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(sys, "executable", executable)
    assert launch_command() == expected, "the Run entry must start this exe, or pythonw for a source install"
