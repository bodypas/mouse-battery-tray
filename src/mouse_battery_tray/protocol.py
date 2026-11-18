"""Decode the battery frames that the Attack Shark 2.4 GHz receiver (Xenta 1d57:fa60) pushes on its own."""

from dataclasses import dataclass

REPORT_ID = 0x03
BATTERY_KIND = 0x40
STATE_CHARGING = 0x03  # 0x01 means running on battery
MAX_LEVEL = 10  # this mouse reports 0-10; it sat at 10 after a long charge


@dataclass(frozen=True)
class BatteryReading:
    percent: int  # level * 10, so it moves in 10% steps
    charging: bool


def parse_frame(data: bytes | list[int]) -> BatteryReading | None:
    """Return the reading in a `03 xx 40 <state> <level>` frame, or None for anything else.

    Byte 1 is ignored; it is 10 on this mouse. Frames with another byte 2, such as `03 E5 01 00 00`, are not battery
    data and would otherwise read as 0%. Other models that send 0-100 here (as the Linux KDE project describes) are
    not supported: their levels above 10 are rejected.
    """
    if len(data) < 5 or data[0] != REPORT_ID or data[2] != BATTERY_KIND:
        return None
    level = data[4]
    if level > MAX_LEVEL:
        return None
    return BatteryReading(percent=level * 10, charging=data[3] == STATE_CHARGING)


class SteadyReadings:
    """Passes a reading on only once the same value arrives twice in a row.

    Right after the cable is unplugged the mouse sends one frame at level 7 before settling at its real level.
    """

    def __init__(self) -> None:
        self._last: BatteryReading | None = None

    def feed(self, reading: BatteryReading) -> BatteryReading | None:
        steady = reading == self._last
        self._last = reading
        return reading if steady else None
