from mouse_battery_tray.status import MouseStatus

LOW_PERCENT = 20


class LowBatteryAlert:
    """Warns once per discharge when the level drops to the threshold; charging re-arms it."""

    def __init__(self, threshold: int = LOW_PERCENT) -> None:
        self._threshold = threshold
        self._armed = True

    def should_notify(self, status: MouseStatus) -> bool:
        if status.charging:
            self._armed = True
            return False
        if status.percent is None or status.percent > self._threshold or not self._armed:
            return False
        self._armed = False
        return True
