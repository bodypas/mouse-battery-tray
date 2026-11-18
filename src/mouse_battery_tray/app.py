"""Tray wiring: status updates from the monitor become icon, tooltip, menu and notification changes."""

import argparse
import itertools
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import TextIO

import pystray

from mouse_battery_tray import app_identity, autostart, diagnose, single_instance, tray
from mouse_battery_tray.alerts import LowBatteryAlert
from mouse_battery_tray.device import BatteryMonitor
from mouse_battery_tray.icon import SPINNER_FRAMES, render_icon, render_spinner
from mouse_battery_tray.status import MouseStatus

logger = logging.getLogger(__name__)


SPIN_SECONDS = 0.16
SPIN_LIMIT_SECONDS = 20  # each frame change writes a temp .ico, so a long wait (receiver unplugged) stops spinning


class TrayApp:
    def __init__(self, hang_log: TextIO) -> None:
        self._status = MouseStatus()
        self._shown: tuple[int | None, bool] | None = None
        self._waiting_since = time.monotonic()
        self._icon_lock = threading.Lock()  # the spinner and status updates both set the icon
        self._closing = threading.Event()
        self._size = tray.icon_size()
        self._spinner = [render_spinner(frame, self._size) for frame in range(SPINNER_FRAMES)]
        self._alert = LowBatteryAlert()
        self._icon = tray.TrayIcon(
            "mouse-battery-tray",
            icon=render_icon(self._status, self._size),
            title=describe(self._status),
            menu=pystray.Menu(
                pystray.MenuItem(lambda _item: describe(self._status), None, enabled=False),
                pystray.MenuItem(
                    "Start with Windows", self._toggle_autostart, checked=lambda _item: autostart.is_enabled()
                ),
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        self._monitor = BatteryMonitor(self._on_status, hang_log)

    def run(self) -> None:
        self._icon.run(setup=self._start)

    def _start(self, icon: pystray.Icon) -> None:
        icon.visible = True
        self._monitor.start()
        threading.Thread(target=self._spin, name="spinner", daemon=True).start()

    def _on_status(self, status: MouseStatus) -> None:
        with self._icon_lock:
            if status.waiting and not self._status.waiting:
                self._waiting_since = time.monotonic()
            self._status = status
            if (status.percent, status.charging) != self._shown:
                self._shown = (status.percent, status.charging)
                self._icon.icon = render_icon(status, self._size)
        self._icon.title = describe(status)
        self._icon.update_menu()
        if self._alert.should_notify(status):
            self._icon.notify(
                f"Mouse battery is at about {status.percent}%. Plug in the charging cable.", "Mouse battery low"
            )

    def _spin(self) -> None:
        frames = itertools.cycle(self._spinner)
        while not self._closing.wait(SPIN_SECONDS):
            with self._icon_lock:
                if self._status.waiting and time.monotonic() - self._waiting_since < SPIN_LIMIT_SECONDS:
                    self._icon.icon = next(frames)

    def _toggle_autostart(self) -> None:
        autostart.set_enabled(not autostart.is_enabled())

    def _quit(self, icon: pystray.Icon) -> None:
        self._closing.set()
        self._monitor.stop()
        icon.stop()


def describe(status: MouseStatus) -> str:
    if status.cable:
        return "Mouse charging (cable connected)"
    if status.percent is None:
        return "Mouse battery: waiting for the mouse..."
    state = "charging" if status.charging else "battery"
    as_of = time.strftime("%H:%M", time.localtime(status.updated_at))
    return f"Mouse {state}: about {status.percent}% (as of {as_of})"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mouse-battery-tray", description="Tray icon with the battery level of an Attack Shark X3 mouse."
    )
    parser.add_argument(
        "--diagnose",
        nargs="?",
        const="",
        metavar="VID:PID",
        help="list HID devices and the frames a receiver sends (default: every 1d57 device), save a report and exit",
    )
    args = parser.parse_args()
    log_dir = Path(os.environ["LOCALAPPDATA"]) / "mouse-battery-tray"
    log_dir.mkdir(parents=True, exist_ok=True)
    if args.diagnose is not None:  # before the single-instance check, so it also works while the tray app runs
        try:
            target = diagnose.parse_device_id(args.diagnose) if args.diagnose else None
        except ValueError as error:
            parser.error(str(error))
        diagnose.run(log_dir / "diagnose.txt", target)
        return
    _run_tray(log_dir)


def _run_tray(log_dir: Path) -> None:
    handlers: list[logging.Handler] = [logging.FileHandler(log_dir / "app.log", encoding="utf-8")]
    if sys.stderr is not None:  # None under pythonw
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)

    mutex = single_instance.acquire()
    if mutex is None:
        logger.info("already running, exiting")
        return
    logger.info("started")
    if not tray.enable_dpi_awareness():
        logger.warning("Windows refused DPI awareness; the icon will be stretched and blurry")
    logger.info("tray icon size: %d px", tray.icon_size())
    app_identity.register(log_dir)
    with open(log_dir / "hang.log", "a", encoding="utf-8") as hang_log:
        try:
            TrayApp(hang_log).run()
        except Exception:
            logger.exception("tray app crashed")
            raise
    logger.info("stopped")
