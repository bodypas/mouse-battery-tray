import io

import pystray
import pytest
from PIL import Image, ImageChops, ImageFilter

from mouse_battery_tray.icon import DESIGN, DIGITS_TOP, render_icon
from mouse_battery_tray.status import MouseStatus
from mouse_battery_tray.tray import TrayIcon, save_ico


def _digit_pixels(icon: Image.Image) -> Image.Image:
    """White, opaque pixels below the wheel: the number."""
    r, g, b, a = icon.split()
    white = ImageChops.darker(ImageChops.darker(r, g), b).point(lambda v: 255 if v >= 200 else 0)
    white = ImageChops.multiply(white, a.point(lambda v: 255 if v == 255 else 0))
    white.paste(0, (0, 0, icon.width, round(DIGITS_TOP * icon.height / DESIGN)))
    return white


@pytest.mark.parametrize("size", [16, 20, 24, 32])  # tray icon size at 100%, 125%, 150% and 200% scaling
def test_every_number_has_the_same_digit_height_and_clears_the_edge(size: int) -> None:
    heights = {}
    for percent in range(0, 101, 10):
        icon = render_icon(MouseStatus(percent=percent), size)
        digits = _digit_pixels(icon)
        top, bottom = digits.getbbox()[1], digits.getbbox()[3]
        heights[percent] = bottom - top
        # Digits must never reach the icon's outer edge. The 1 px gap to the outline itself is built into icon._digits:
        # at these sizes the 1.25 px outline blends into its neighbours, so pixels can't tell it apart reliably.
        outside = icon.getchannel("A").point(lambda v: 255 if v < 255 else 0)
        touching = ImageChops.multiply(digits.filter(ImageFilter.MaxFilter(3)), outside)
        assert touching.getbbox() is None, f"the digits of {percent}% touch the icon's edge at {size} px"
    # One font size and one top for all numbers. Up to 1 px apart only because flat-edged digits (2, 7) fully cover an
    # edge row that the round 0 covers partly; fitting each number on its own made "100" 2-3 px shorter than "90".
    assert max(heights.values()) - min(heights.values()) <= 1, (
        f"numbers must share one digit size at {size} px: {heights}"
    )


@pytest.mark.parametrize("size", [16, 20, 24, 28, 32])
def test_tray_ico_holds_a_frame_at_the_exact_tray_size(size: int) -> None:
    buffer = io.BytesIO()
    save_ico(render_icon(MouseStatus(percent=100), size), buffer)
    sizes = Image.open(buffer).info["sizes"]
    assert (size, size) in sizes, f"no {size} px frame ({sizes}), so Windows would stretch a smaller one"


def test_tray_icon_still_overrides_pystray_icon_loading() -> None:
    assert "_assert_icon_handle" in vars(pystray.Icon), (
        "pystray no longer has _assert_icon_handle, so TrayIcon's sharp-icon loading is never called"
    )
    assert "_assert_icon_handle" in vars(TrayIcon)
