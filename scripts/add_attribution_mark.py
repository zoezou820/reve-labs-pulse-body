#!/usr/bin/env python3
"""Add the REVE LABS SOUND pulse attribution mark to a data-body image."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font_for(size: int):
    for path in [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    parser = argparse.ArgumentParser(description="Add a REVE LABS SOUND pulse attribution mark.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    image = Image.open(args.input).convert("RGBA")
    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    font = font_for(max(18, round(width * 0.021)))

    x = round(width * 0.685)
    y = round(height * 0.855)
    ink = (30, 30, 28, 168)
    draw.text((x, y), "REVE LABS SOUND", font=font, fill=ink)

    line_y = y + round(width * 0.046)
    line_width = round(width * 0.245)
    pulse = [
        (0.00, 0), (0.10, 0), (0.16, -1), (0.22, 1),
        (0.28, 0), (0.34, 0), (0.37, 6), (0.39, -15),
        (0.41, 12), (0.44, -5), (0.48, 1), (0.55, 0),
        (0.64, 0), (0.70, -1), (0.76, 1), (0.83, 0), (1.00, 0),
    ]
    points = [(x + round(px * line_width), line_y + round(py * width / 941)) for px, py in pulse]
    draw.line(points, fill=ink, width=max(1, round(width / 700)))
    endpoint_x = x + line_width + round(width * 0.025)
    radius = max(5, round(width * 0.008))
    draw.ellipse((endpoint_x - radius, line_y - radius, endpoint_x + radius, line_y + radius), outline=ink, width=max(1, round(width / 700)))
    draw.ellipse((endpoint_x - 2, line_y - 2, endpoint_x + 2, line_y + 2), fill=ink)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(args.output, quality=96)
    print(args.output)


if __name__ == "__main__":
    main()
