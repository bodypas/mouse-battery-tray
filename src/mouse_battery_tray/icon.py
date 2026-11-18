"""Draws the tray icon: an oval mouse that fills from the bottom like a battery, with the percent in white.

Everything is drawn at SUPERSAMPLE times the requested size and box-reduced, so the edges are smooth and the result is
exactly the tray's pixel size (tray.TrayIcon loads it unscaled). Every number uses one digit size: the largest at which
"100" keeps CLEARANCE tray pixels between the digits and the mouse's outline. Digits are placed on whole tray pixels,
so all numbers come out the same height.
"""

from dataclasses import dataclass
from functools import cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

from mouse_battery_tray.alerts import LOW_PERCENT
from mouse_battery_tray.status import MouseStatus

SUPERSAMPLE = 4
DESIGN = 96  # the geometry below is in a 96-unit square, scaled to the drawing canvas
BODY = (9, 0, 86, 95)
BODY_RADIUS = 36
OUTLINE = 5
WHEEL = (43, 11, 52, 28)
WHEEL_RADIUS = 4
DIGITS_TOP = WHEEL[3] + 6  # digits, bolt and spinner stay below the wheel
DIGIT_CENTRES = range(48, 70, 2)  # candidate heights for the digits; the oval is widest in the middle
PREFERRED_CENTRE = 58
CLEARANCE = 1  # tray pixels between the digits and the outline

GREEN = (46, 157, 79)
AMBER = (217, 138, 0)
RED = (209, 52, 56)
GREY = (110, 110, 110)
EMPTY = (48, 48, 52)  # the part of the mouse above the battery level
TRACK = (110, 110, 116)  # the spinner's faint ring
WHITE = (255, 255, 255)
MID_PERCENT = 40

BOLT = [(38, 4), (14, 36), (30, 36), (24, 60), (50, 26), (34, 26), (42, 4)]  # in a 64-unit square, 56 units tall
BOLT_HEIGHT = 56
SPINNER_FRAMES = 8
APP_ICON_SIZE = 256


@dataclass(frozen=True)
class _Digits:
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    centre: tuple[float, float]
    top: int  # canvas row of the digits' top, the same for every number
    height: int


def render_icon(status: MouseStatus, size: int) -> Image.Image:
    """The icon for a status at size x size pixels."""
    if status.waiting:
        return render_spinner(0, size)
    canvas = size * SUPERSAMPLE
    if status.percent is None:  # charging cable in: no level is reported
        image, draw = _mouse(canvas, GREEN, 100)
        _bolt(draw, _digits(size))
    else:
        image, draw = _mouse(canvas, GREEN if status.charging else _level_colour(status.percent), status.percent)
        _number(image, str(status.percent), _digits(size))
    return image.reduce(SUPERSAMPLE)


def render_spinner(frame: int, size: int) -> Image.Image:
    """One frame of a faint ring with a bright 110-degree arc that moves 45 degrees per frame."""
    image, draw = _mouse(size * SUPERSAMPLE, GREY, 0)
    digits = _digits(size)
    cx, cy = digits.centre
    radius, width = digits.height / 2, max(SUPERSAMPLE, round(digits.height / 5))
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    start = frame % SPINNER_FRAMES * 360 / SPINNER_FRAMES
    draw.ellipse(box, outline=TRACK, width=width)
    draw.arc(box, start, start + 110, fill=WHITE, width=width)
    return image.reduce(SUPERSAMPLE)


def render_app_icon() -> Image.Image:
    """Logo for the notification header and the exe: the full green mouse without a number."""
    image, _ = _mouse(APP_ICON_SIZE * SUPERSAMPLE, GREEN, 100)
    return image.reduce(SUPERSAMPLE)


def _mouse(canvas: int, colour: tuple[int, int, int], level: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Oval body with an outline in the level colour, dark inside, filled from the bottom up to level percent."""
    k = canvas / DESIGN
    outline = max(1, round(OUTLINE * k))
    body = _scaled(BODY, k)
    inner = (body[0] + outline, body[1] + outline, body[2] - outline, body[3] - outline)
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(body, radius=BODY_RADIUS * k, fill=colour)
    draw.rounded_rectangle(inner, radius=BODY_RADIUS * k - outline, fill=EMPTY)
    fill = _mask(canvas, inner, BODY_RADIUS * k - outline)
    surface = round(inner[3] - (inner[3] - inner[1]) * level / 100)
    ImageDraw.Draw(fill).rectangle((0, 0, canvas, surface), fill=0)
    image.paste(colour, (0, 0), fill)
    draw.line((canvas / 2 - 0.5, 0, canvas / 2 - 0.5, WHEEL[3] * k), fill=colour, width=outline)
    draw.rounded_rectangle(_scaled(WHEEL, k), radius=WHEEL_RADIUS * k, fill=WHITE)
    return image, draw


def _number(image: Image.Image, text: str, digits: _Digits) -> None:
    glyphs = _glyph_mask(text, digits.font)
    left = _snap(digits.centre[0] - glyphs.width / 2)
    image.paste(WHITE, (left, digits.top, left + glyphs.width, digits.top + glyphs.height), glyphs)


def _bolt(draw: ImageDraw.ImageDraw, digits: _Digits) -> None:
    (cx, cy), k = digits.centre, digits.height / BOLT_HEIGHT
    draw.polygon([(cx + (x - 32) * k, cy + (y - 32) * k) for x, y in BOLT], fill=WHITE)


@cache
def _digits(size: int) -> _Digits:
    """The font size and position at which "100" is largest while keeping CLEARANCE from the outline."""
    canvas = size * SUPERSAMPLE
    k = canvas / DESIGN
    margin = max(1, round(OUTLINE * k)) + CLEARANCE * SUPERSAMPLE
    body = _scaled(BODY, k)
    allowed = _mask(
        canvas, (body[0] + margin, body[1] + margin, body[2] - margin, body[3] - margin), BODY_RADIUS * k - margin
    )
    ImageDraw.Draw(allowed).rectangle((0, 0, canvas, round(DIGITS_TOP * k)), fill=0)
    best: tuple[int, float, _Digits] | None = None
    for centre_y in DIGIT_CENTRES:
        centre = (canvas / 2, centre_y * k)
        for font_size in range(round(canvas * 0.7), 3, -1):
            font = _font(font_size)
            glyphs = _glyph_mask("100", font)
            top = _snap(centre[1] - glyphs.height / 2)
            if _fits(glyphs, (_snap(centre[0] - glyphs.width / 2), top), allowed):
                candidate = (font_size, -abs(centre_y - PREFERRED_CENTRE), _Digits(font, centre, top, glyphs.height))
                best = max(best, candidate, key=lambda c: c[:2]) if best else candidate
                break
    if best is None:
        raise ValueError(f"no font size fits the digits in a {size} px icon")
    return best[2]


def _fits(glyphs: Image.Image, at: tuple[int, int], allowed: Image.Image) -> bool:
    placed = Image.new("L", allowed.size, 0)
    placed.paste(glyphs.point(lambda v: 255 if v else 0), at)
    return ImageChops.subtract(placed, allowed).getbbox() is None


def _mask(canvas: int, box: tuple[float, float, float, float], radius: float) -> Image.Image:
    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def _scaled(box: tuple[int, int, int, int], k: float) -> tuple[float, float, float, float]:
    return box[0] * k, box[1] * k, (box[2] + 1) * k - 1, (box[3] + 1) * k - 1


def _snap(value: float) -> int:
    """Round to a whole tray pixel, so every number lands on the pixel grid the same way."""
    return round(value / SUPERSAMPLE) * SUPERSAMPLE


def _level_colour(percent: int | None) -> tuple[int, int, int]:
    if percent is None or percent > MID_PERCENT:
        return GREEN
    if percent <= LOW_PERCENT:
        return RED
    return AMBER


def _glyph_mask(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> Image.Image:
    """The text's rendered pixels, cropped: Pillow's text box includes side bearings, so centring uses the ink."""
    size = round(font.size * 3) if hasattr(font, "size") else 256
    canvas = Image.new("L", (size * 2, size), 0)
    ImageDraw.Draw(canvas).text((size // 2, size // 4), text, font=font, fill=255)
    return canvas.crop(canvas.getbbox())


@cache
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Bahnschrift Bold Condensed (Windows 10 1709+): narrow digits let "100" be as tall as "90"."""
    try:
        font = ImageFont.truetype("bahnschrift.ttf", size)
        font.set_variation_by_name("Bold Condensed")
        return font
    except OSError, ValueError:
        pass
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        return ImageFont.load_default(size)
