from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


PAPER = (246, 241, 232, 255)
INK = (28, 25, 21, 255)
RED = (194, 59, 34, 255)
GREEN = (31, 107, 74, 255)
CREAM = (255, 250, 242, 255)


def _circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)


def make_icon(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((22, 26, 238, 246), radius=36, fill=(48, 32, 16, 48))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((18, 18, 238, 238), radius=36, fill=CREAM)
    draw.rounded_rectangle((18, 18, 238, 88), radius=36, fill=RED)
    draw.rectangle((18, 56, 238, 88), fill=RED)

    for cx in (86, 170):
        _circle(draw, cx, 40, 13, CREAM)
        _circle(draw, cx, 40, 7, RED)

    draw.rounded_rectangle((48, 112, 92, 148), radius=8, fill=PAPER)
    draw.rounded_rectangle((108, 112, 152, 148), radius=8, fill=PAPER)
    draw.rounded_rectangle((168, 112, 212, 148), radius=8, fill=PAPER)
    draw.rounded_rectangle((48, 164, 92, 200), radius=8, fill=PAPER)
    draw.rounded_rectangle((168, 164, 212, 200), radius=8, fill=PAPER)

    check = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(check)
    cdraw.line((104, 178, 126, 200, 168, 146), fill=GREEN, width=16)
    img = Image.alpha_composite(img, check)

    img.save(dest, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return dest


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "icon.ico"
    make_icon(target)
    print(target)
