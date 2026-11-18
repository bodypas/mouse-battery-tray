"""Background thread that follows the mouse battery through the receiver's vendor HID collection."""

import faulthandler
import logging
import threading
import time
from collections.abc import Callable
from typing import TextIO

import hid

from mouse_battery_tray.protocol import SteadyReadings, parse_frame
from mouse_battery_tray.status import MouseStatus

logger = logging.getLogger(__name__)

VID = 0x1D57
PID_RECEIVER = 0xFA60
PID_WIRED = 0xFA61  # the mouse itself shows up under this id while the charging cable is plugged in
VENDOR_USAGE_PAGE = 0x000A  # the receiver collection that pushes battery frames
READ_TIMEOUT_MS = 1000
CABLE_CHECK_SECONDS = 3.0
RETRY_SECONDS = 3.0
HANG_DUMP_SECONDS = 30


class BatteryMonitor:
    """Reads battery frames on a daemon thread and passes every status update to `on_status`.

    Only the receiver is ever opened. The wired mouse is only looked up in the device list: opening every collection
    right after an unplug once blocked for over 90 seconds, and the cause is not known yet.
    """

    def __init__(self, on_status: Callable[[MouseStatus], None], hang_log: TextIO) -> None:
        self._on_status = on_status
        self._hang_log = hang_log
        self._status = MouseStatus()
        self._receiver_missing = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="battery-monitor", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._arm_hang_dump()
            try:
                self._cycle()
            except Exception:
                logger.exception("battery read failed, retrying in %ss", RETRY_SECONDS)
            self._stop.wait(RETRY_SECONDS)
        faulthandler.cancel_dump_traceback_later()

    def _cycle(self) -> None:
        if _cable_connected():
            self._publish(MouseStatus(cable=True))
            return
        if self._status.cable:
            self._publish(MouseStatus())  # just unplugged: the level from before charging is stale
        path = _receiver_path()
        if path is None:
            if not self._receiver_missing:
                logger.info("receiver %04x:%04x not found", VID, PID_RECEIVER)
                self._receiver_missing = True
            self._publish(MouseStatus())  # no receiver: the last level can't be trusted
            return
        if self._receiver_missing:
            logger.info("receiver found")
            self._receiver_missing = False
        device = hid.device()
        device.open_path(path)
        try:
            self._read_frames(device)
        finally:
            device.close()

    def _read_frames(self, device: hid.device) -> None:
        next_cable_check = time.monotonic() + CABLE_CHECK_SECONDS
        last_frame: list[int] = []
        steady = SteadyReadings()
        while not self._stop.is_set():
            self._arm_hang_dump()
            frame = device.read(64, timeout_ms=READ_TIMEOUT_MS)
            if frame and frame != last_frame:
                logger.info("frame: %s", bytes(frame).hex(" "))
                last_frame = frame
            reading = parse_frame(frame)
            if reading is not None:
                reading = steady.feed(reading)
            if reading is not None:
                self._publish(MouseStatus(reading.percent, reading.charging, updated_at=time.time()))
            if time.monotonic() >= next_cable_check:
                if _cable_connected():
                    return
                next_cable_check = time.monotonic() + CABLE_CHECK_SECONDS

    def _publish(self, status: MouseStatus) -> None:
        previous, self._status = self._status, status
        if (previous.percent, previous.charging) != (status.percent, status.charging):
            logger.info("status: percent=%s charging=%s cable=%s", status.percent, status.charging, status.cable)
        self._on_status(status)

    def _arm_hang_dump(self) -> None:
        # If a HID call blocks, every thread's stack goes to the hang log so the blocking call can be identified.
        faulthandler.dump_traceback_later(HANG_DUMP_SECONDS, file=self._hang_log)


def _cable_connected() -> bool:
    return bool(hid.enumerate(VID, PID_WIRED))


def _receiver_path() -> bytes | None:
    for info in hid.enumerate(VID, PID_RECEIVER):
        if info["usage_page"] == VENDOR_USAGE_PAGE:
            return info["path"]
    return None
