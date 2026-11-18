from dataclasses import dataclass


@dataclass(frozen=True)
class MouseStatus:
    percent: int | None = None  # None until a battery frame arrives, and while the cable is plugged in
    frame_charging: bool = False  # the frame's own charging state (never seen yet on this mouse)
    cable: bool = False  # the mouse is plugged in by cable, which charges it
    updated_at: float | None = None  # wall-clock time of the last battery frame

    @property
    def charging(self) -> bool:
        return self.cable or self.frame_charging

    @property
    def waiting(self) -> bool:
        """Nothing to show yet: no reading and not on the cable."""
        return self.percent is None and not self.charging
