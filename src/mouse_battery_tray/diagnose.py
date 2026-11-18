"""`--diagnose`: a report of the HID devices and the raw frames a receiver sends, so other mice can be supported.

The report is meant to be pasted into a public issue, so it holds ids, usage pages, names and frames only: no serial
numbers or device paths.
"""

import faulthandler
import os
import platform
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

import hid

from mouse_battery_tray.device import PID_WIRED, VID
from mouse_battery_tray.protocol import parse_frame

LISTEN_SECONDS = 15
READ_TIMEOUT_MS = 200
HANG_EXIT_SECONDS = LISTEN_SECONDS + 30
SKIPPED_PAGES = {0x0001, 0x000C}  # mouse, keyboard and media-key collections: owned by Windows, not battery data
MAX_FRAMES_PER_COLLECTION = 20
DEVICE_ID = re.compile(r"([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})")

Emit = Callable[[str], None]


def parse_device_id(text: str) -> tuple[int, int]:
    """Parse "1d57:fa60" (hex VID:PID) into (0x1D57, 0xFA60)."""
    match = DEVICE_ID.fullmatch(text)
    if match is None:
        raise ValueError(f"expected VID:PID in hex, like 1d57:fa60, got {text!r}")
    return int(match[1], 16), int(match[2], 16)


def run(report_path: Path, target: tuple[int, int] | None) -> None:
    """Write the report to report_path, echoing it to stdout, or open it in Notepad when there is no console."""
    with open(report_path, "w", encoding="utf-8") as report:

        def emit(line: str) -> None:
            report.write(line + "\n")
            report.flush()
            if sys.stdout is not None:
                print(line, flush=True)

        # A HID call once blocked for over 90 seconds; without a console a hang would leave an invisible process.
        faulthandler.dump_traceback_later(HANG_EXIT_SECONDS, exit=True, file=report)
        try:
            _write_report(emit, target)
        finally:
            faulthandler.cancel_dump_traceback_later()
    if sys.stdout is None:  # the windowed exe or pythonw
        os.startfile(report_path)
    else:
        print(f"saved to {report_path}")


def _write_report(emit: Emit, target: tuple[int, int] | None) -> None:
    emit("mouse-battery-tray diagnose")
    emit(f"Windows: {platform.platform()}")
    emit(f"Python: {platform.python_version()}, exe: {getattr(sys, 'frozen', False)}")
    devices = hid.enumerate()
    emit("")
    emit("HID devices (VID:PID, interface, usage page, usage | manufacturer | product):")
    for row in sorted({f"{_collection_name(d)} usage=0x{d['usage']:02X} | {_names(d)}" for d in devices}):
        emit(f"  {row}")
    emit("")
    scope = f"{target[0]:04x}:{target[1]:04x}" if target else f"{VID:04x}:*"
    emit(f"Listening for {LISTEN_SECONDS} s on {scope} (use the mouse, don't type):")
    _listen(emit, [d for d in devices if _wanted(d, target)])


def _wanted(info: dict, target: tuple[int, int] | None) -> bool:
    ids = (info["vendor_id"], info["product_id"])
    if ids == (VID, PID_WIRED) or info["usage_page"] in SKIPPED_PAGES:
        return False  # the wired mouse is never opened: see BatteryMonitor
    return ids == target if target else info["vendor_id"] == VID


def _listen(emit: Emit, collections: list[dict]) -> None:
    handles: list[tuple[str, hid.device]] = []
    for info in collections:
        name = _collection_name(info)
        device = hid.device()
        try:
            device.open_path(info["path"])
        except OSError as error:
            emit(f"  {name}: can't open ({error})")
            continue
        handles.append((name, device))
    if not handles:
        emit("  nothing to listen on")
        return
    seen: dict[str, set[bytes]] = {name: set() for name, _ in handles}
    total = 0
    start = time.monotonic()
    try:
        while handles and time.monotonic() - start < LISTEN_SECONDS:
            for name, device in list(handles):
                try:
                    frame = device.read(64, timeout_ms=READ_TIMEOUT_MS)
                except OSError as error:
                    emit(f"  {name}: read error ({error}), stopped listening to it")
                    handles.remove((name, device))
                    device.close()
                    continue
                if not frame:
                    continue
                total += 1
                data = bytes(frame)
                if data in seen[name] or len(seen[name]) >= MAX_FRAMES_PER_COLLECTION:
                    continue
                seen[name].add(data)
                emit(f"  t={time.monotonic() - start:4.1f}s {name}: {data.hex(' ')}{_meaning(data)}")
    finally:
        for _, device in handles:
            device.close()
    emit(f"done: {total} frames, {sum(len(frames) for frames in seen.values())} distinct")


def _meaning(data: bytes) -> str:
    reading = parse_frame(data)
    if reading is None:
        return ""
    return f"  -> battery {reading.percent}%" + (" charging" if reading.charging else "")


def _collection_name(info: dict) -> str:
    return (
        f"{info['vendor_id']:04x}:{info['product_id']:04x} iface={info['interface_number']} "
        f"page=0x{info['usage_page']:04X}"
    )


def _names(info: dict) -> str:
    return f"{info['manufacturer_string'] or '-'} | {info['product_string'] or '-'}"
