from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def make_icon(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((12, 12, 243, 243), radius=42, fill=(255, 250, 242, 255))
    draw.rounded_rectangle((12, 12, 243, 72), radius=42, fill=(194, 59, 34, 255))
    draw.rectangle((12, 42, 243, 72), fill=(194, 59, 34, 255))
    font = _font(118)
    text = "16"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, 78 + (150 - th) / 2), text, font=font, fill=(194, 59, 34, 255))
    img.save(dest, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return dest


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "icon.ico"
    make_icon(target)
    print(target)
