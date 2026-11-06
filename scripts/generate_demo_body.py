#!/usr/bin/env python3
"""Create the repository's deterministic, original demo data-body asset."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


W, H = 720, 1280
OUT = Path(__file__).resolve().parents[1] / "assets" / "demo_data_body.png"


def ellipse_point(rng, cx, cy, rx, ry):
    angle = rng.uniform(0, np.pi * 2)
    radius = np.sqrt(rng.random())
    return cx + np.cos(angle) * rx * radius, cy + np.sin(angle) * ry * radius


def main():
    rng = np.random.default_rng(2601)
    image = Image.new("RGB", (W, H), (242, 240, 234))
    draw = ImageDraw.Draw(image, "RGBA")
    core_x, core_y = 365, 817

    draw.line((core_x, 40, core_x, H - 42), fill=(35, 35, 32, 38), width=1)
    draw.line((112, 366, 610, 366), fill=(35, 35, 32, 24), width=1)

    points = []
    for _ in range(3700):
        x, y = ellipse_point(rng, 365, 313, 148, 225)
        if y > 455 and abs(x - 365) > 72:
            continue
        points.append((x, y, rng.uniform(0.3, 1)))
    for _ in range(2500):
        x, y = ellipse_point(rng, 365, 815, 320, 340)
        neck = 80 + max(0, (y - 500) * 0.30)
        if y < 640 and abs(x - 365) > neck:
            continue
        points.append((x, y, rng.uniform(0.2, 1)))

    nodes = [(x, y) for x, y, _ in points[::37]]
    for i, (x, y) in enumerate(nodes):
        distances = sorted(nodes, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
        for tx, ty in distances[1:3]:
            if (tx - x) ** 2 + (ty - y) ** 2 < 145 ** 2:
                draw.line((x, y, tx, ty), fill=(30, 30, 28, 25), width=1)
        if i % 6 == 0:
            r = rng.choice([2, 3, 5])
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(24, 24, 22, 120))

    for x, y, density in points:
        distance = np.hypot(x - core_x, y - core_y)
        core_density = np.exp(-((distance - 135) ** 2) / (2 * 88 ** 2))
        alpha = int(28 + 100 * density + 68 * core_density)
        radius = 0.55 + 1.25 * density
        value = int(38 + 98 * (1 - density))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(value, value, value, alpha))

    for radius in range(18, 188, 9):
        alpha = max(12, 74 - radius // 3)
        draw.ellipse((core_x - radius, core_y - radius, core_x + radius, core_y + radius), outline=(35, 35, 32, alpha), width=1)

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow, "RGBA")
    for radius in range(34, 2, -2):
        alpha = int(5 + (34 - radius) * 3.4)
        gd.ellipse((core_x - radius, core_y - radius, core_x + radius, core_y + radius), fill=(255, 253, 244, alpha))
    image = Image.alpha_composite(image.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(7))).convert("RGB")
    image.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
