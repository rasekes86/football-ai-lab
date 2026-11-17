#!/usr/bin/env python3
"""Generate 192/512 PWA PNGs without Pillow, ImageMagick or paid dependencies.

Icon follows site/pwa-icon.svg's navy/coral football identity. Source and
generator remain versioned; output PNGs are built in the GitHub Pages workflow.
"""
from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path

CENTER = (256.0, 250.0)
POLY = [
    (256.0, 186.0), (317.0, 230.0), (294.0, 302.0),
    (218.0, 302.0), (195.0, 230.0),
]
SPOKES = [
    ((256, 186), (256, 129)), ((317, 230), (370, 209)),
    ((294, 302), (322, 361)), ((218, 302), (190, 361)),
    ((195, 230), (142, 209)),
]
EDGES = tuple(zip(POLY, POLY[1:] + POLY[:1]))


def segment_distance(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) /
                         (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def inside_polygon(x, y, vertices=POLY):
    result = False
    previous = vertices[-1]
    for vertex in vertices:
        xi, yi = vertex
        xj, yj = previous
        if (yi > y) != (yj > y):
            intercept = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < intercept:
                result = not result
        previous = vertex
    return result


def sample(x, y):
    # Smooth navy gradient with a subtle halo.
    shade = min(1.0, math.hypot(x - 95, y - 70) / 660)
    bg = (int(17 - 11 * shade), int(48 - 27 * shade), int(65 - 31 * shade))
    d = math.hypot(x - CENTER[0], y - CENTER[1])
    if 145 < d < 158:
        strength = max(0.0, (158 - d) / 58)
        bg = tuple(int(v * (1 - strength) + red * strength)
                   for v, red in zip(bg, (250, 49, 88)))
    if d <= 145:
        shade_red = min(1.0, math.hypot(x - 200, y - 185) / 270)
        bg = (int(255 - 18 * shade_red),
              int(86 - 55 * shade_red), int(119 - 43 * shade_red))
        if 124 <= d <= 134:
            bg = (250, 251, 253)
        if inside_polygon(x, y):
            bg = (11, 35, 53)
        if any(segment_distance(x, y, a, b) <= 5.5 for a, b in EDGES):
            bg = (253, 253, 254)
        if any(segment_distance(x, y, a, b) <= 5.0 for a, b in SPOKES):
            bg = (253, 253, 254)
        if math.hypot(x - 256, y - 250) < 4.5:
            bg = (248, 249, 251)
    return bg


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(
        ">I", zlib.crc32(body) & 0xFFFFFFFF)


def build_png(size):
    if size not in (192, 512):
        raise ValueError("PWA icon size must be 192 or 512")
    scale = 512 / size
    rows = []
    for py in range(size):
        row = bytearray((0,))
        for px in range(size):
            accum = [0, 0, 0]
            # 2x2 subpixel anti-aliasing for maskable Android icons.
            for oy in (0.25, 0.75):
                for ox in (0.25, 0.75):
                    values = sample((px + ox) * scale, (py + oy) * scale)
                    for i, val in enumerate(values):
                        accum[i] += val
            row.extend((accum[0] // 4, accum[1] // 4, accum[2] // 4, 255))
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) +
            chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        path = out / f"icon-{size}.png"
        path.write_bytes(build_png(size))
        print(f"Creado {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
