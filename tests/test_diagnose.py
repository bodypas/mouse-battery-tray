import pytest

from mouse_battery_tray.diagnose import parse_device_id


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1d57:fa60", (0x1D57, 0xFA60)), ("1D57:FA60", (0x1D57, 0xFA60)), ("248a:5b4", (0x248A, 0x05B4))],
)
def test_parse_device_id(text: str, expected: tuple[int, int]) -> None:
    assert parse_device_id(text) == expected, "--diagnose VID:PID must take hex ids"


@pytest.mark.parametrize("text", ["1d57", "1d57:fa60:1", "12345:fa60", "0x1d:fa60", "xyz:fa60", " 1d57:fa60"])
def test_parse_device_id_rejects_malformed_ids(text: str) -> None:
    with pytest.raises(ValueError):
        parse_device_id(text)
