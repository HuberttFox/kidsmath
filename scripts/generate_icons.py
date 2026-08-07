"""生成 PWA/安卓所需 PNG 图标（192/512 + maskable），输出到 src/mathgen/static/icons/。

依赖 Pillow（dev 组）。用法：uv run python scripts/generate_icons.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "src" / "mathgen" / "static" / "icons"

BG = (168, 230, 207)       # --mint
FG = (255, 253, 247)       # 暖白
DOT = (255, 183, 197)      # --pink


def draw(size: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 0 if maskable else int(size * 0.06)
    r = int(size * 0.22)
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=r, fill=BG)
    # 圆角方块内：三条横线 + 加号 + 圆点（近似 math-icon.svg）
    w = size * 0.55
    x0 = size * 0.24
    y = size * 0.28
    bar_h = size * 0.11
    for i in range(3):
        d.rounded_rectangle([x0, y + i * (bar_h + size * 0.09),
                             x0 + w, y + i * (bar_h + size * 0.09) + bar_h],
                            radius=bar_h // 2, fill=FG)
    px = x0 + w + size * 0.12
    th = size * 0.12
    d.rounded_rectangle([px, y + bar_h * 1.35, px + th, y + bar_h * 1.35 + size * 0.33],
                        radius=th // 2, fill=FG)
    d.ellipse([size * 0.74, size * 0.62, size * 0.88, size * 0.76], fill=DOT)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw(size).save(OUT / f"icon-{size}.png")
        draw(size, maskable=True).save(OUT / f"icon-maskable-{size}.png")
    print(f"已生成图标：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
