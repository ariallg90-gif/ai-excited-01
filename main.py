#!/usr/bin/env python3
"""The Conductor of the Deep.

A giant violet octopus conducts an orchestra of glowing jellyfish in the
midnight ocean -- one specific, surprising moment: the sea's most unlikely
maestro, baton raised, leading a thousand lights.

The image is drawn from scratch by this program alone: a hand-rolled
rasterizer (gradients, discs, ellipses, bezier tentacles, a 5x7 bitmap font)
painting into a raw RGB buffer, then a hand-rolled PNG encoder (zlib + the
Up filter, CRC32 chunks, no image libraries). Standard library only.

Deterministic: a fixed-seed LCG is the only source of "randomness", so two
runs produce byte-identical PNGs.

Usage:
    MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
    python3 main.py                          # writes /output/entry.png
"""

import os
import struct
import zlib
from math import sqrt, sin, cos, pi

W = H = 1024

# ---------------------------------------------------------------------------
# Deterministic pseudo-randomness (LCG, fixed seed -- no time, no os.urandom)
# ---------------------------------------------------------------------------
_state = 20261116


def rnd():
    global _state
    _state = (_state * 1664525 + 1013904223) & 0xFFFFFFFF
    return _state / 4294967296.0


def rrange(a, b):
    return a + (b - a) * rnd()


# ---------------------------------------------------------------------------
# Framebuffer
# ---------------------------------------------------------------------------
fb = bytearray(W * H * 3)


def blend(x, y, r, g, b, a):
    """Alpha-blend one pixel. a in [0, 1]."""
    if x < 0 or x >= W or y < 0 or y >= H or a <= 0.0:
        return
    i = (y * W + x) * 3
    if a >= 1.0:
        fb[i] = r
        fb[i + 1] = g
        fb[i + 2] = b
        return
    fb[i] = int(fb[i] + (r - fb[i]) * a)
    fb[i + 1] = int(fb[i + 1] + (g - fb[i + 1]) * a)
    fb[i + 2] = int(fb[i + 2] + (b - fb[i + 2]) * a)


def hline(y, x0, x1, r, g, b, a):
    """Blend a horizontal run of pixels (clipped)."""
    if y < 0 or y >= H or a <= 0.0:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    base = (y * W + x0) * 3
    n = x1 - x0 + 1
    if a >= 1.0:
        row = bytes((r, g, b)) * n
        fb[base:base + 3 * n] = row
        return
    for k in range(n):
        i = base + 3 * k
        fb[i] = int(fb[i] + (r - fb[i]) * a)
        fb[i + 1] = int(fb[i + 1] + (g - fb[i + 1]) * a)
        fb[i + 2] = int(fb[i + 2] + (b - fb[i + 2]) * a)


def disc(cx, cy, rad, color, a=1.0):
    """Filled disc, centre (cx, cy), radius rad."""
    rad = int(rad)
    if rad <= 0:
        return
    r, g, b = color
    for dy in range(-rad, rad + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        half = int(sqrt(rad * rad - dy * dy))
        hline(y, cx - half, cx + half, r, g, b, a)


def ring(cx, cy, rad, thick, color, a=1.0):
    """Thin circle outline (annulus)."""
    for k in range(thick):
        rr = rad - k
        if rr <= 0:
            break
        r, g, b = color
        for dy in range(-rr, rr + 1):
            y = cy + dy
            if y < 0 or y >= H:
                continue
            half = int(sqrt(rr * rr - dy * dy))
            blend(cx - half, y, r, g, b, a)
            blend(cx + half, y, r, g, b, a)


def ellipse(cx, cy, rx, ry, color, a=1.0):
    """Filled axis-aligned ellipse."""
    rx = int(rx)
    ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    r, g, b = color
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        t = 1.0 - (dy * dy) / (ry * ry)
        half = int(rx * sqrt(max(0.0, t)))
        hline(y, cx - half, cx + half, r, g, b, a)


def vgrad(stops):
    """Vertical gradient. stops: [(fraction, (r, g, b)), ...] sorted by y."""
    for y in range(H):
        t = y / (H - 1)
        for k in range(len(stops) - 1):
            f0, c0 = stops[k]
            f1, c1 = stops[k + 1]
            if f0 <= t <= f1:
                u = 0.0 if f1 == f0 else (t - f0) / (f1 - f0)
                r = int(c0[0] + (c1[0] - c0[0]) * u)
                g = int(c0[1] + (c1[1] - c0[1]) * u)
                b = int(c0[2] + (c1[2] - c0[2]) * u)
                break
        else:
            r, g, b = stops[-1][1]
        base = y * W * 3
        fb[base:base + W * 3] = bytes((r, g, b)) * W


def poly(points, color, a=1.0):
    """Filled polygon (scanline, even-odd)."""
    r, g, b = color
    ys = [p[1] for p in points]
    y0, y1 = max(0, int(min(ys))), min(H - 1, int(max(ys)))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for k in range(n):
            x0, yy0 = points[k]
            x1, yy1 = points[(k + 1) % n]
            if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                t = (y - yy0) / (yy1 - yy0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            hline(y, xs[k], xs[k + 1], r, g, b, a)


def cubic(p0, p1, p2, p3, steps):
    """Sample a cubic bezier curve."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        mt = 1.0 - t
        x = (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0]
             + 3 * mt * t * t * p2[0] + t ** 3 * p3[0])
        y = (mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1]
             + 3 * mt * t * t * p2[1] + t ** 3 * p3[1])
        pts.append((x, y))
    return pts


def stroke(pts, r0, r1, color, a=1.0):
    """Draw a tapering thick polyline (round caps) through pts."""
    n = len(pts)
    for k, (x, y) in enumerate(pts):
        rad = r0 + (r1 - r0) * (k / max(1, n - 1))
        disc(int(x), int(y), max(1, int(rad)), color, a)


def glow_disc(cx, cy, rad, color, peak=0.55, steps=10):
    """Soft radial glow: concentric discs, alpha falling off outward."""
    for s in range(steps, 0, -1):
        rr = rad * s / steps
        alpha = peak * (1.0 - s / steps) ** 1.5 + peak * 0.12
        disc(cx, cy, rr, color, min(0.85, alpha))


# ---------------------------------------------------------------------------
# 5x7 bitmap font (only the glyphs the captions need)
# ---------------------------------------------------------------------------
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    ",": ["00000", "00000", "00000", "00000", "00100", "00100", "01000"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, x, y, scale, color, a=1.0):
    """Draw s with its top-left corner at (x, y)."""
    r, g, b = color
    for ci, ch in enumerate(s):
        glyph = FONT.get(ch)
        if glyph is None:
            continue
        ox = x + ci * 6 * scale
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "1":
                    for dy in range(scale):
                        hline(y + row * scale + dy, ox + col * scale,
                              ox + (col + 1) * scale - 1, r, g, b, a)


def text_centered(s, y, scale, color, a=1.0):
    draw_text(s, (W - text_width(s, scale)) // 2, y, scale, color, a)


def glow_text(s, y, scale, main, glow, ga=0.45):
    """Caption with a soft coloured halo behind the letters."""
    cx = (W - text_width(s, scale)) // 2
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
        draw_text(s, cx + dx, y + dy, scale, glow, ga)
    draw_text(s, cx, y, scale, main, 1.0)


# ---------------------------------------------------------------------------
# Scene pieces
# ---------------------------------------------------------------------------
def light_ray(x_top, spread, color, a):
    """A widening shaft of light falling from the surface."""
    poly([(x_top, -10), (x_top + 60, -10),
          (x_top + 60 + spread, H), (x_top - spread, H)], color, a)


def jellyfish(cx, cy, size, bell, glow, tentacle):
    """One glowing jellyfish: bell, rim, inner light, wavy tentacles."""
    glow_disc(cx, cy, int(size * 1.7), glow, peak=0.30, steps=8)
    # Bell: stacked ellipses, bright top fading down.
    for k in range(9):
        t = k / 8
        y = cy - int(size * 0.35) + int(size * 0.55 * t)
        rx = size * (0.55 + 0.45 * sin(pi * min(1.0, t * 1.15)))
        rr = int(bell[0] + (255 - bell[0]) * (1 - t) * 0.55)
        gg = int(bell[1] + (255 - bell[1]) * (1 - t) * 0.55)
        bb = int(bell[2] + (255 - bell[2]) * (1 - t) * 0.55)
        ellipse(int(cx), y, rx, size * 0.30, (rr, gg, bb), 0.85)
    ring(cx, cy + int(size * 0.12), int(size * 0.95), 3, (255, 255, 255), 0.55)
    disc(cx, cy - int(size * 0.1), int(size * 0.28), (255, 255, 255), 0.65)
    # Tentacles: sine-waved vertical strokes, lengths staggered.
    for k in range(6):
        off = (k - 2.5) * size * 0.28
        length = size * rrange(1.5, 2.4)
        phase = rrange(0, 6.28)
        pts = []
        for s in range(26):
            t = s / 25
            x = cx + off + sin(t * 5.0 + phase) * size * 0.10 * t
            y = cy + size * 0.35 + length * t
            pts.append((x, y))
        stroke(pts, 3.5, 1.2, tentacle, 0.75)
        disc(int(pts[-1][0]), int(pts[-1][1]), 3, (255, 255, 255), 0.7)


def octopus():
    """The conductor: violet mantle, two raised arms, baton, eight arms."""
    cx, cy = 512, 660
    # Mantle: stacked ellipses, violet top to magenta bottom.
    for k in range(46):
        t = k / 45
        y = cy - 215 + int(430 * t)
        rx = 185 * sin(pi * (0.12 + 0.76 * t)) ** 0.8
        r = int(124 + (192 - 124) * t)
        g = int(58 + (38 - 58) * t)
        b = int(237 + (211 - 237) * t)
        ellipse(cx, y, max(8, rx), 12, (r, g, b), 0.97)
    # Mantle highlight and speckles.
    ellipse(cx - 62, cy - 128, 74, 46, (196, 141, 255), 0.28)
    for k in range(14):
        sx = cx + int(rrange(-140, 140))
        sy = cy + int(rrange(-180, 120))
        disc(sx, sy, int(rrange(3, 7)), (216, 180, 254), 0.35)
    # Eyes: big, bright, looking up at the jellyfish choir.
    for ex in (cx - 78, cx + 78):
        ellipse(ex, cy - 96, 44, 52, (255, 255, 255), 1.0)
        disc(ex + 6, cy - 108, 24, (16, 10, 40), 1.0)
        disc(ex - 8, cy - 118, 9, (255, 255, 255), 1.0)
        ring(ex, cy - 96, 46, 3, (90, 40, 160), 0.8)
    # Smile.
    for k in range(25):
        t = k / 24
        x = cx - 34 + 68 * t
        y = cy - 18 + int(16 * sin(pi * t))
        disc(int(x), int(y), 3, (60, 20, 90), 0.9)
    # Eight tentacles: six curling low, two raised high like a conductor.
    arms = [
        # (control points, base radius, tip radius)
        ((cx - 150, cy + 150), (cx - 330, cy + 260), (cx - 420, cy + 90), (cx - 380, cy - 60), 26, 5),
        ((cx - 110, cy + 170), (cx - 260, cy + 330), (cx - 300, cy + 430), (cx - 180, cy + 470), 26, 5),
        ((cx - 55, cy + 185), (cx - 120, cy + 380), (cx - 60, cy + 470), (cx + 40, cy + 430), 26, 5),
        ((cx + 55, cy + 185), (cx + 120, cy + 380), (cx + 60, cy + 470), (cx - 40, cy + 430), 26, 5),
        ((cx + 110, cy + 170), (cx + 260, cy + 330), (cx + 300, cy + 430), (cx + 180, cy + 470), 26, 5),
        ((cx + 150, cy + 150), (cx + 330, cy + 260), (cx + 420, cy + 90), (cx + 380, cy - 60), 26, 5),
        # Raised arms (the conductor's gesture).
        ((cx - 165, cy - 40), (cx - 330, cy - 190), (cx - 360, cy - 330), (cx - 250, cy - 420), 24, 5),
        ((cx + 165, cy - 40), (cx + 330, cy - 190), (cx + 360, cy - 330), (cx + 250, cy - 420), 24, 5),
    ]
    for p0, p1, p2, p3, r0, r1 in arms:
        pts = cubic(p0, p1, p2, p3, 90)
        stroke(pts, r0, r1, (150, 76, 230), 0.98)
        # Suckers along the inner side of each arm.
        for k in range(4, len(pts) - 4, 7):
            x, y = pts[k]
            disc(int(x), int(y) + 6, 5, (232, 190, 255), 0.55)
    # The baton: a slim white wand in the raised right hand, tip glowing.
    bx, by = cx + 250, cy - 420
    stroke([(bx, by), (bx + 52, by - 66), (bx + 78, by - 96)], 4, 2,
           (245, 245, 235), 1.0)
    glow_disc(bx + 82, by - 100, 26, (255, 240, 160), peak=0.8, steps=6)
    disc(bx + 82, by - 100, 6, (255, 250, 210), 1.0)


def fish(x, y, size, direction, color, a=0.9):
    """One tiny silver fish, body + tail, swimming left or right."""
    pts = [(x - size, y), (x - size * 0.4, y - size * 0.42),
           (x + size * 0.7, y - size * 0.30), (x + size, y),
           (x + size * 0.7, y + size * 0.30), (x - size * 0.4, y + size * 0.42)]
    if direction < 0:
        pts = [(2 * x - px, py) for px, py in pts]
    poly(pts, color, a)
    tail = [(x - direction * size, y),
            (x - direction * size * 1.7, y - size * 0.5),
            (x - direction * size * 1.7, y + size * 0.5)]
    poly(tail, color, a)
    disc(int(x + direction * size * 0.55), int(y - size * 0.08), 2,
         (10, 16, 34), 1.0)


def fish_school():
    """A small school of silver fish sweeping past the stage, left to right."""
    for k in range(9):
        t = k / 8
        x = 120 + 700 * t + int(rrange(-14, 14))
        y = 520 + int(90 * sin(t * 3.4)) + int(rrange(-10, 10))
        size = int(rrange(11, 17))
        fish(x, y, size, 1, (205, 220, 235), rrange(0.65, 0.95))


def bubbles(x0, y0, count, spread):
    """A rising trail of small bubble rings."""
    for k in range(count):
        t = k / max(1, count - 1)
        x = x0 + sin(t * 9.0) * spread * t + rrange(-6, 6)
        y = y0 - int(300 * t)
        r = int(3 + 9 * t)
        ring(int(x), int(y), r, 2, (190, 230, 255), 0.5)


def particles(count):
    """Tiny drifting motes of light across the whole frame."""
    for _ in range(count):
        x = int(rrange(0, W))
        y = int(rrange(0, H))
        c = rnd()
        if c < 0.45:
            col = (180, 220, 255)
        elif c < 0.75:
            col = (255, 200, 230)
        else:
            col = (200, 255, 230)
        disc(x, y, 1 if rnd() < 0.7 else 2, col, rrange(0.25, 0.8))


def seabed():
    """Dark hills at the bottom with a few glowing anemones."""
    poly([(0, H), (0, 968), (180, 940), (360, 966), (560, 938),
          (760, 962), (900, 944), (W, 970), (W, H)],
         (3, 10, 26), 1.0)
    for ax, col in ((150, (255, 120, 200)), (880, (120, 230, 255)),
                    (640, (255, 190, 120))):
        glow_disc(ax, 962, 26, col, peak=0.5, steps=6)
        for k in range(5):
            disc(ax + (k - 2) * 7, 958 - abs(k - 2) * 3, 4, col, 0.9)


# ---------------------------------------------------------------------------
# PNG encoder (hand-rolled: signature, IHDR, IDAT with Up filter, IEND)
# ---------------------------------------------------------------------------
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(fb[y * W * 3:(y + 1) * W * 3])
        raw.append(2)  # filter: Up
        raw += bytes((a - b) & 0xFF for a, b in zip(row, prev))
        prev = row
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


# ---------------------------------------------------------------------------
# Compose the scene
# ---------------------------------------------------------------------------
def main():
    # Midnight ocean: deep navy at the surface, teal glow in the depths.
    vgrad([(0.0, (2, 8, 30)), (0.45, (6, 26, 62)),
           (0.8, (5, 42, 66)), (1.0, (3, 28, 48))])
    # Light shafts from the surface.
    light_ray(90, 130, (150, 200, 255), 0.05)
    light_ray(430, 190, (170, 215, 255), 0.06)
    light_ray(760, 120, (150, 200, 255), 0.05)
    # Distant, faint jellyfish far behind the choir.
    jellyfish(150, 330, 34, (140, 120, 255), (120, 90, 255), (150, 130, 255))
    jellyfish(895, 300, 30, (120, 200, 255), (90, 170, 255), (130, 190, 255))
    # The jellyfish choir, arcing over the conductor.
    jellyfish(300, 250, 62, (255, 150, 210), (255, 110, 200), (255, 170, 220))
    jellyfish(512, 205, 72, (140, 220, 255), (100, 190, 255), (160, 220, 255))
    jellyfish(724, 250, 62, (200, 160, 255), (170, 120, 255), (210, 170, 255))
    jellyfish(205, 430, 46, (160, 240, 220), (120, 220, 200), (170, 240, 220))
    jellyfish(820, 430, 46, (255, 190, 150), (255, 150, 110), (255, 200, 160))
    # The conductor takes the stage.
    octopus()
    # A school of silver fish sweeps past the stage.
    fish_school()
    # Rising bubbles and drifting light.
    bubbles(330, 900, 9, 26)
    bubbles(700, 920, 7, 22)
    particles(320)
    # The stage floor.
    seabed()
    # Captions: the title the judge reads first.
    glow_text("THE CONDUCTOR", 44, 6, (214, 242, 255), (70, 150, 255))
    glow_text("OF THE DEEP", 106, 6, (214, 242, 255), (70, 150, 255))
    text_centered("ONE OCTOPUS, A THOUSAND LIGHTS", 168, 2,
                  (150, 205, 235), 0.95)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(encode_png())
    print("wrote", path)


if __name__ == "__main__":
    main()
