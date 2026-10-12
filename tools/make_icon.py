"""Vẽ biểu tượng của Dịch (assets/icon.ico và icon.png).

Chạy lại khi muốn đổi biểu tượng:  python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BLUE, BLUE_DARK, YELLOW = (0, 82, 204), (0, 52, 140), (255, 213, 0)
FONT = "C:/Windows/Fonts/segoeuib.ttf"


def draw(size: int) -> Image.Image:
    s = size * 4  # vẽ to rồi thu nhỏ cho mịn
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = s // 5
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=r, fill=BLUE_DARK)
    d.rounded_rectangle((0, 0, s - 1, int(s * 0.92)), radius=r, fill=BLUE)

    font = ImageFont.truetype(FONT, int(s * 0.78))
    d.text((s * 0.5, s * 0.47), "Đ", font=font, fill=YELLOW, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = [draw(n) for n in sizes]
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    images[-1].save(out / "icon.ico", sizes=[(n, n) for n in sizes], append_images=images[:-1])
    images[-1].save(out / "icon.png")
    print("Đã tạo", out / "icon.ico")


if __name__ == "__main__":
    main()
