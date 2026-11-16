#!/usr/bin/env python3
"""The Conductor of the Deep -- a deterministic 1024x1024 PNG, stdlib only.

A giant purple octopus conducts a glowing jellyfish orchestra on the
ocean floor: arms sweeping, baton raised, music notes and bubbles
bursting upward. Everything is drawn by the small rasterizer below;
no image files, no fonts from disk, no network, no randomness that
is not seeded by a fixed integer.
"""
import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
PATH = os.path.join(OUT, "entry.png")

# Deterministic pseudo-random stream (LCG) -- same output every run.
_seed = [987654321]


def rnd():
    _seed[0] = (_seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed[0] / 2147483648.0


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else int(v)


# The canvas: one flat RGB bytearray, row-major.
px = bytearray(W * H * 3)


def put(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i] = r
        px[i + 1] = g
        px[i + 2] = b


def blend(x, y, r, g, b, a):
    """Blend colour (r,g,b) over the pixel at (x,y) with alpha a in [0,1]."""
    if a <= 0.0:
        return
    if not (0 <= x < W and 0 <= y < H):
        return
    if a >= 1.0:
        put(x, y, r, g, b)
        return
    i = (y * W + x) * 3
    px[i] = clamp(px[i] + (r - px[i]) * a)
    px[i + 1] = clamp(px[i + 1] + (g - px[i + 1]) * a)
    px[i + 2] = clamp(px[i + 2] + (b - px[i + 2]) * a)


def disc(cx, cy, rad, col, a=1.0):
    """Filled circle, optionally translucent."""
    r, g, b = col
    rad = int(rad)
    if rad <= 0:
        return
    for yy in range(cy - rad, cy + rad + 1):
        dy = yy - cy
        half = int(math.sqrt(max(0, rad * rad - dy * dy)))
        for xx in range(cx - half, cx + half + 1):
            blend(xx, yy, r, g, b, a)


def glow(cx, cy, rad, col, peak=0.55):
    """Soft radial glow: several concentric translucent discs."""
    steps = 7
    for k in range(steps, 0, -1):
        t = k / steps
        blend_rad = rad * t
        blend_a = peak * (1.0 - t) * (1.0 - t) * 0.55 + 0.03
        disc(int(cx), int(cy), int(blend_rad), col, blend_a)


def ellipse(cx, cy, rx, ry, col, a=1.0):
    r, g, b = col
    for yy in range(int(cy - ry), int(cy + ry) + 1):
        dy = (yy - cy) / max(1.0, ry)
        if abs(dy) > 1.0:
            continue
        half = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        for xx in range(int(cx - half), int(cx + half) + 1):
            blend(xx, yy, r, g, b, a)


def line(x0, y0, x1, y1, col, thick=1, a=1.0):
    """Thick anti-aliased-ish line: stamps discs along the segment."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    steps = max(1, int(dist))
    rad = max(1, thick // 2)
    for k in range(steps + 1):
        t = k / steps
        disc(int(x0 + dx * t), int(y0 + dy * t), rad, col, a)


def bezier(p0, p1, p2, p3, col, w0, w1, a=1.0):
    """Cubic Bezier stamped as tapering discs (thick at start, thin at end)."""
    steps = 48
    for k in range(steps + 1):
        t = k / steps
        mt = 1.0 - t
        x = (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0]
             + 3 * mt * t * t * p2[0] + t ** 3 * p3[0])
        y = (mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1]
             + 3 * mt * t * t * p2[1] + t ** 3 * p3[1])
        w = w0 + (w1 - w0) * t
        disc(int(x), int(y), max(1, int(w)), col, a)


def poly(points, col, a=1.0):
    """Scanline fill of a simple polygon."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    for yy in range(int(min(ys)), int(max(ys)) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                t = (yy - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for xx in range(int(xs[k]), int(xs[k + 1]) + 1):
                blend(xx, yy, col[0], col[1], col[2], a)


def ring(cx, cy, rad, col, thick=3, a=1.0):
    """Thin circle outline."""
    steps = max(48, int(rad * 6))
    for k in range(steps):
        ang = 2 * math.pi * k / steps
        disc(int(cx + rad * math.cos(ang)), int(cy + rad * math.sin(ang)),
             thick, col, a)


# ---------------------------------------------------------------- PNG out
def chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    data += chunk(b"IEND", b"")
    os.makedirs(OUT, exist_ok=True)
    with open(PATH, "wb") as f:
        f.write(data)
    return len(data)


# ------------------------------------------------------------- bitmap font
# 5x7 glyphs, one string per row, '#' = ink. Only the letters we need.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00000", "00100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, cx, y, scale, col, glow_col=None):
    """Centred text at top y; optional soft glow behind the letters."""
    w = text_width(s, scale)
    x0 = cx - w // 2
    if glow_col is not None:
        for gy in range(y - 6, y + 7 * scale + 6, 3):
            for gx in range(x0 - 8, x0 + w + 8, 3):
                blend(gx, gy, glow_col[0], glow_col[1], glow_col[2], 0.05)
    for ci, ch in enumerate(s):
        glyph = FONT.get(ch, FONT[" "])
        bx = x0 + ci * 6 * scale
        for row in range(7):
            for c in range(5):
                if glyph[row][c] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            put(bx + c * scale + dx, y + row * scale + dy,
                                col[0], col[1], col[2])


# ------------------------------------------------------------- background
def paint_background():
    # Deep-sea vertical gradient: midnight indigo at top, teal at floor.
    top = (7, 10, 42)
    mid = (16, 32, 86)
    bot = (8, 58, 74)
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            u = t / 0.55
            c = tuple(int(top[i] + (mid[i] - top[i]) * u) for i in range(3))
        else:
            u = (t - 0.55) / 0.45
            c = tuple(int(mid[i] + (bot[i] - mid[i]) * u) for i in range(3))
        for x in range(W):
            put(x, y, c[0], c[1], c[2])
    # Moon-like glow high above the stage, off-centre right.
    glow(830, 150, 260, (120, 180, 255), 0.30)
    disc(830, 150, 62, (235, 244, 255))
    disc(830, 150, 46, (200, 225, 255))
    # Slanting god-rays from the surface.
    for bx, bw, al in ((120, 90, 0.05), (300, 60, 0.04), (620, 110, 0.05),
                       (880, 70, 0.04)):
        poly([(bx, 0), (bx + bw, 0), (bx + bw + 260, H), (bx + 260, H)],
             (140, 220, 255), al)
    # Distant rock silhouettes.
    poly([(0, 1024), (0, 880), (150, 830), (300, 890), (430, 850),
          (560, 905), (700, 860), (860, 900), (1024, 845), (1024, 1024)],
         (10, 22, 52), 0.9)
    # Sandy glowing stage floor.
    ellipse(512, 1010, 560, 110, (24, 78, 92))
    ellipse(512, 990, 470, 80, (36, 108, 118))
    ellipse(512, 975, 360, 55, (52, 140, 148))


# ------------------------------------------------------------- jellyfish
def jellyfish(cx, cy, size, bell, rim, tent, tilt=0.0):
    """One glowing jellyfish musician, bell + wavy tentacles."""
    glow(cx, cy, int(size * 1.5), bell, 0.35)
    # Bell: a dome made of stacked ellipses, brightest at the crown.
    for k in range(10):
        t = k / 9.0
        yy = cy - int(size * 0.45) + int(size * 0.55 * t)
        rx = int(size * math.sin(math.pi * (0.15 + 0.85 * t)) * 0.62)
        ry = max(2, int(size * 0.16))
        a = 0.55 + 0.45 * (1.0 - t)
        ellipse(cx + int(tilt * t * size * 0.3), yy, rx, ry, bell, a)
    # Rim fringe.
    for k in range(9):
        fx = cx - int(size * 0.55) + k * int(size * 0.137)
        disc(fx, cy + int(size * 0.12), max(2, int(size * 0.07)), rim, 0.9)
    # Inner glow spot.
    disc(cx, cy - int(size * 0.12), int(size * 0.22), (255, 255, 255), 0.5)
    # Tentacles: sine-wavy vertical strands, some holding instruments.
    for j in range(7):
        tx = cx - int(size * 0.5) + j * int(size * 0.167)
        pts = []
        for s in range(9):
            yy = cy + int(size * 0.15) + s * int(size * 0.16)
            xx = tx + int(math.sin(s * 0.9 + j * 1.3) * size * 0.09)
            pts.append((xx, yy))
        for a_, b_ in zip(pts, pts[1:]):
            line(a_[0], a_[1], b_[0], b_[1], tent, thick=max(2, int(size * 0.05)), a=0.85)
    # Two dark eyes on the bell, looking toward the conductor.
    disc(cx - int(size * 0.18), cy - int(size * 0.08), max(2, int(size * 0.05)),
         (20, 10, 40))
    disc(cx + int(size * 0.18), cy - int(size * 0.08), max(2, int(size * 0.05)),
         (20, 10, 40))


def music_note(cx, cy, size, col, tilt=0.0):
    """A quaver: filled head + stem + flag."""
    ellipse(cx, cy, int(size * 0.55), int(size * 0.38), col)
    line(cx + int(size * 0.5), cy, cx + int(size * 0.5),
         cy - int(size * 1.9), col, thick=max(2, int(size * 0.16)))
    bezier((cx + int(size * 0.5), cy - int(size * 1.9)),
           (cx + int(size * 1.1), cy - int(size * 1.7)),
           (cx + int(size * 1.3), cy - int(size * 1.1)),
           (cx + int(size * 0.9), cy - int(size * 0.7)),
           col, max(2, int(size * 0.14)), 2)
    disc(cx, cy, int(size * 0.2), (255, 255, 255), 0.6)


def bubbles_and_sparkles():
    # Rising bubbles, deterministic positions.
    for _ in range(46):
        bx = int(rnd() * W)
        by = int(120 + rnd() * 820)
        br = 2 + int(rnd() * 9)
        ring(bx, by, br, (180, 235, 255), thick=2, a=0.45)
        disc(bx - br // 3, by - br // 3, max(1, br // 4), (255, 255, 255), 0.7)
    # Four-point star sparkles.
    for _ in range(60):
        sx = int(rnd() * W)
        sy = int(rnd() * H)
        sr = 3 + int(rnd() * 7)
        col = [(255, 240, 160), (160, 240, 255), (255, 180, 230)][int(rnd() * 3)]
        line(sx - sr, sy, sx + sr, sy, col, thick=2, a=0.8)
        line(sx, sy - sr, sx, sy + sr, col, thick=2, a=0.8)
        disc(sx, sy, 2, (255, 255, 255), 0.9)


# ------------------------------------------------------------- the octopus
def octopus():
    cx, cy = 512, 560
    body = (168, 74, 220)       # vivid violet
    dark = (110, 40, 170)
    light = (216, 140, 255)
    pink = (255, 120, 200)
    # Halo behind the star of the show.
    glow(cx, cy - 40, 330, (150, 90, 255), 0.42)
    glow(cx, cy - 40, 190, (255, 140, 220), 0.22)
    # Back arms first (darker, sweeping out low and wide).
    back_arms = [
        ((cx - 90, cy + 60), (cx - 300, cy + 150), (cx - 430, cy + 60),
         (cx - 470, cy - 90)),
        ((cx + 90, cy + 60), (cx + 300, cy + 150), (cx + 430, cy + 60),
         (cx + 470, cy - 90)),
        ((cx - 60, cy + 90), (cx - 210, cy + 260), (cx - 330, cy + 330),
         (cx - 380, cy + 300)),
        ((cx + 60, cy + 90), (cx + 210, cy + 260), (cx + 330, cy + 330),
         (cx + 380, cy + 300)),
    ]
    for p0, p1, p2, p3 in back_arms:
        bezier(p0, p1, p2, p3, dark, 34, 7)
        bezier(p0, p1, p2, p3, body, 26, 5)
    # Front arms: two raised high conducting, two low and curling.
    front_arms = [
        # Left conducting arm, baton hand at the top, swept out to the
        # left so the baton star stays clear of the title text.
        ((cx - 70, cy + 40), (cx - 190, cy - 90), (cx - 330, cy - 240),
         (cx - 285, cy - 375)),
        # Right conducting arm, sweeping across.
        ((cx + 70, cy + 40), (cx + 200, cy - 80), (cx + 330, cy - 190),
         (cx + 350, cy - 330)),
        # Low left curl.
        ((cx - 50, cy + 100), (cx - 170, cy + 210), (cx - 150, cy + 330),
         (cx - 60, cy + 340)),
        # Low right curl.
        ((cx + 50, cy + 100), (cx + 170, cy + 210), (cx + 150, cy + 330),
         (cx + 60, cy + 340)),
    ]
    for p0, p1, p2, p3 in front_arms:
        bezier(p0, p1, p2, p3, body, 36, 8)
        bezier(p0, p1, p2, p3, light, 22, 4, a=0.55)
    # Suckers: pale dots along the two low curls.
    for t in [0.25, 0.45, 0.65, 0.85]:
        for sgn in (-1, 1):
            x = cx + sgn * (50 + 130 * t)
            y = cy + 100 + 240 * t * t
            disc(int(x), int(y), 7, (255, 210, 240), 0.85)
    # Mantle: big rounded dome.
    ellipse(cx, cy - 30, 185, 165, body)
    ellipse(cx, cy - 70, 150, 130, light, a=0.45)
    ellipse(cx - 40, cy - 110, 90, 70, (235, 170, 255), a=0.5)
    # Crown spots.
    for sx, sy, sr in ((-95, -150, 16), (-30, -185, 20), (45, -175, 14),
                       (105, -135, 18), (0, -120, 12)):
        disc(cx + sx, cy + sy, sr, pink, 0.75)
    # Eyes: huge, thrilled, looking up at the baton.
    for sgn in (-1, 1):
        ex = cx + sgn * 78
        ey = cy - 55
        disc(ex, ey, 42, (255, 255, 255))
        disc(ex, ey, 30, (30, 180, 220))
        disc(ex + sgn * 4, ey - 6, 16, (10, 10, 30))
        disc(ex - 10, ey - 14, 9, (255, 255, 255))
        # Raised brow arc.
        for k in range(9):
            ang = math.pi * (1.05 + 0.9 * k / 8)
            disc(int(ex + 46 * math.cos(ang)), int(ey - 52 + 26 * math.sin(ang)),
                 5, dark)
    # Open joyful mouth.
    ellipse(cx, cy + 55, 42, 26, (60, 10, 60))
    ellipse(cx, cy + 48, 26, 14, (255, 90, 160))
    # Blush.
    disc(cx - 128, cy + 18, 20, pink, 0.6)
    disc(cx + 128, cy + 18, 20, pink, 0.6)
    # Baton in the left raised hand: white stick + golden starburst tip.
    line(cx - 285, cy - 375, cx - 350, cy - 500, (255, 255, 255), thick=7)
    glow(cx - 350, cy - 500, 70, (255, 220, 120), 0.6)
    for k in range(8):
        ang = math.pi * k / 4
        line(cx - 350, cy - 500,
             int(cx - 350 + 34 * math.cos(ang)),
             int(cy - 500 + 34 * math.sin(ang)), (255, 215, 90), thick=4)
    disc(cx - 350, cy - 500, 12, (255, 240, 170))
    # Sound-wave rings bursting from the baton tip.
    ring(cx - 350, cy - 500, 58, (255, 230, 150), thick=4, a=0.7)
    ring(cx - 350, cy - 500, 88, (255, 180, 220), thick=3, a=0.45)


def orchestra():
    # Jellyfish band, left and right, small to large for depth.
    jellyfish(150, 430, 92, (255, 120, 190), (255, 170, 220), (255, 150, 210))
    jellyfish(880, 420, 98, (90, 220, 255), (150, 235, 255), (120, 210, 255))
    jellyfish(105, 680, 70, (255, 200, 90), (255, 225, 150), (255, 190, 110))
    jellyfish(925, 690, 74, (160, 255, 170), (200, 255, 210), (170, 245, 190))
    jellyfish(255, 800, 56, (200, 140, 255), (225, 180, 255), (205, 160, 255))
    jellyfish(775, 805, 58, (255, 150, 130), (255, 190, 170), (255, 165, 150))
    # Floating music notes between conductor and band.
    music_note(300, 330, 26, (255, 230, 120))
    music_note(700, 300, 30, (150, 240, 255))
    music_note(240, 560, 20, (255, 170, 220))
    music_note(790, 540, 22, (255, 220, 120))
    music_note(620, 180, 18, (200, 255, 200))
    music_note(380, 210, 18, (255, 190, 200))


# ------------------------------------------------------------- main
def main():
    paint_background()
    orchestra()
    octopus()
    bubbles_and_sparkles()
    # Title in clear sky space at the top; the octopus head stays below y=330.
    draw_text("THE CONDUCTOR", 512, 42, 7, (255, 244, 180), (255, 180, 90))
    draw_text("OF THE DEEP", 512, 118, 5, (190, 235, 255), (90, 160, 255))
    # Thin gold rule under the title.
    line(392, 168, 632, 168, (255, 215, 120), thick=3, a=0.9)
    disc(512, 168, 6, (255, 240, 170))
    n = write_png()
    print(f"wrote {PATH} ({n} bytes)")


if __name__ == "__main__":
    main()
