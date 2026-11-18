import pytest

from mouse_battery_tray.protocol import BatteryReading, SteadyReadings, parse_frame


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        pytest.param("03 10 40 01 09", BatteryReading(90, charging=False), id="on-battery frame, level 9 of 10"),
        pytest.param("03 10 40 01 0a", BatteryReading(100, charging=False), id="full"),
        pytest.param("03 10 40 03 05", BatteryReading(50, charging=True), id="charging state"),
        pytest.param("03 10 40 01 0b", None, id="level above 10"),
        pytest.param("03 e5 01 00 00", None, id="non-battery frame must not read as 0%"),
        pytest.param("03 10 40 01", None, id="short frame"),
        pytest.param("", None, id="read timeout"),
    ],
)
def test_parse_frame(frame: str, expected: BatteryReading | None) -> None:
    # device.read() returns a list of ints, so feed the parser the same shape
    assert parse_frame(list(bytes.fromhex(frame))) == expected, (
        "only `03 xx 40 <state> <level 0-10>` frames are battery readings, reported as level * 10 percent"
    )


def test_first_reading_after_unplug_is_held_until_repeated() -> None:
    # Seen on every unplug after a long charge: one frame at level 7, then 10 from then on.
    steady = SteadyReadings()
    readings = [BatteryReading(70, False), BatteryReading(100, False), BatteryReading(100, False)]

    passed = [steady.feed(reading) for reading in readings]

    assert passed == [None, None, BatteryReading(100, False)], (
        "a reading is only passed on once the same value arrives twice in a row"
    )
