"""Draws the tray icon: a mouse silhouette coloured by level with the percent, a bolt while charging, or a spinner."""

from PIL import Image, ImageDraw, ImageFont

from mouse_battery_tray.alerts import LOW_PERCENT
from mouse_battery_tray.status import MouseStatus

SIZE = 64
MAX_FONT_SIZE = 54
GREEN = (46, 157, 79)
AMBER = (217, 138, 0)
RED = (209, 52, 56)
GREY = (110, 110, 110)
WHITE = (255, 255, 255)
BUTTON_SPLIT = (0, 0, 0, 90)
MID_PERCENT = 40

BODY_BOX = (6, 0, SIZE - 7, SIZE - 1)
BODY_RADIUS = 24
WHEEL_BOX = (28, 8, 35, 20)
LOWER_BOX = (11, 25, SIZE - 11, SIZE - 5)  # below the wheel: holds the number, bolt or spinner
LOWER_CENTRE = ((LOWER_BOX[0] + LOWER_BOX[2]) / 2, (LOWER_BOX[1] + LOWER_BOX[3]) / 2)

_FULL_BOLT = [(38, 4), (14, 36), (30, 36), (24, 60), (50, 26), (34, 26), (42, 4)]  # drawn for a 64 px square
BOLT = [(LOWER_CENTRE[0] + (x - 32) * 0.6, LOWER_CENTRE[1] + (y - 32) * 0.6) for x, y in _FULL_BOLT]

SPINNER_FRAMES = 8
SPINNER_RADIUS = 12
SPINNER_BOX = (
    LOWER_CENTRE[0] - SPINNER_RADIUS,
    LOWER_CENTRE[1] - SPINNER_RADIUS,
    LOWER_CENTRE[0] + SPINNER_RADIUS,
    LOWER_CENTRE[1] + SPINNER_RADIUS,
)
SPINNER_TRACK = (150, 150, 150)


def render_icon(status: MouseStatus) -> Image.Image:
    if status.waiting:
        return render_spinner(0)
    image, draw = _mouse(GREEN if status.charging else _level_colour(status.percent))
    if status.percent is None:
        draw.polygon(BOLT, fill=WHITE)
    else:
        _centred_text(image, str(status.percent), LOWER_BOX)
    return image


def render_spinner(frame: int) -> Image.Image:
    """One frame of a faint ring with a bright 110-degree arc that moves 45 degrees per frame.

    A single long arc read as the letter "C" at tray size; the faint track keeps it looking like a spinner.
    """
    image, draw = _mouse(GREY)
    start = frame % SPINNER_FRAMES * 360 / SPINNER_FRAMES
    draw.ellipse(SPINNER_BOX, outline=SPINNER_TRACK, width=6)
    draw.arc(SPINNER_BOX, start, start + 110, fill=WHITE, width=6)
    return image


def render_app_icon() -> Image.Image:
    """Logo for the notification header: the mouse silhouette on its own."""
    image, _ = _mouse(GREEN)
    return image


def _mouse(colour: tuple[int, int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Mouse silhouette: rounded body in the level colour, a faint split between the buttons, a white wheel."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(BODY_BOX, radius=BODY_RADIUS, fill=colour)
    draw.line((SIZE / 2 - 0.5, 0, SIZE / 2 - 0.5, WHEEL_BOX[3]), fill=BUTTON_SPLIT, width=3)
    draw.rounded_rectangle(WHEEL_BOX, radius=3, fill=WHITE)
    return image, draw


def _level_colour(percent: int | None) -> tuple[int, int, int]:
    if percent is None or percent > MID_PERCENT:
        return GREEN
    if percent <= LOW_PERCENT:
        return RED
    return AMBER


def _centred_text(image: Image.Image, text: str, box: tuple[float, float, float, float]) -> None:
    """Draw the text as large as fits in the box, centred on its rendered pixels.

    Pillow's text box includes side bearings, which left "10" two pixels right of centre, so the glyphs are rendered
    to a mask first and centred on what was actually drawn.
    """
    left, top, right, bottom = box
    for size in range(MAX_FONT_SIZE, 9, -1):
        glyphs = _glyph_mask(text, _font(size))
        if glyphs.width <= right - left and glyphs.height <= bottom - top:
            break
    x = round(left + (right - left - glyphs.width) / 2)
    y = round(top + (bottom - top - glyphs.height) / 2)
    image.paste(WHITE, (x, y, x + glyphs.width, y + glyphs.height), glyphs)


def _glyph_mask(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> Image.Image:
    canvas = Image.new("L", (SIZE * 2, SIZE * 2), 0)
    ImageDraw.Draw(canvas).text((SIZE // 2, SIZE // 2), text, font=font, fill=255)
    return canvas.crop(canvas.getbbox())


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeuib.ttf", size)  # Segoe UI Bold, shipped with Windows
    except OSError:
        return ImageFont.load_default(size)
