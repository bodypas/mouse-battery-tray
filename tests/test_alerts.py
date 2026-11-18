from mouse_battery_tray.alerts import LowBatteryAlert
from mouse_battery_tray.status import MouseStatus


def test_low_battery_warns_once_per_discharge() -> None:
    alert = LowBatteryAlert(threshold=15)
    steps = [
        (MouseStatus(percent=40), False),
        (MouseStatus(percent=15), True),
        (MouseStatus(percent=14), False),  # already warned during this discharge
        (MouseStatus(cable=True), False),  # charging re-arms the warning
        (MouseStatus(percent=12), True),
    ]

    fired = [alert.should_notify(status) for status, _ in steps]

    assert fired == [expected for _, expected in steps], (
        "low-battery warning must fire once per discharge and re-arm after charging"
    )
