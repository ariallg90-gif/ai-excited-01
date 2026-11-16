#!/usr/bin/env python3
"""The Conductor of the Deep -- ai-excited-01 entry.

A deep-sea concert: a giant purple octopus conducts a glowing jellyfish
orchestra while music notes and bubbles rise through shafts of light.
Everything is drawn by a small rasterizer written here from scratch
(framebuffer, shapes, glow) and encoded to PNG with the stdlib zlib.
Deterministic: same bytes on every run.
"""

import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- framebuffer

fb = bytearray(W * H * 3)


def _idx(x, y):
    return (y * W + x) * 3


def put(x, y, r, g, b):
    """Set one pixel, clipped."""
    if 0 <= x < W and 0 <= y < H:
        i = _idx(x, y)
        fb[i] = r
        fb[i + 1] = g
        fb[i + 2] = b


def blend(x, y, r, g, b, a):
    """Alpha-blend a colour over the pixel (a in 0..1), clipped."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        if a >= 1.0:
            put(x, y, r, g, b)
            return
        i = _idx(x, y)
        ia = 1.0 - a
        fb[i] = int(fb[i] * ia + r * a)
        fb[i + 1] = int(fb[i + 1] * ia + g * a)
        fb[i + 2] = int(fb[i + 2] * ia + b * a)


def add(x, y, r, g, b, a):
    """Additive glow: add a fraction of a colour, clamped, clipped."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = _idx(x, y)
        v = fb[i] + int(r * a)
        fb[i] = 255 if v > 255 else v
        v = fb[i + 1] + int(g * a)
        fb[i + 1] = 255 if v > 255 else v
        v = fb[i + 2] + int(b * a)
        fb[i + 2] = 255 if v > 255 else v


def hspan(y, x0, x1, r, g, b):
    """Solid horizontal span, clipped."""
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    i = _idx(x0, y)
    n = x1 - x0 + 1
    fb[i:i + n * 3] = bytes((r, g, b)) * n


def hspan_blend(y, x0, x1, r, g, b, a):
    """Alpha-blended horizontal span, clipped."""
    if y < 0 or y >= H or a <= 0.0:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    if a >= 1.0:
        hspan(y, x0, x1, r, g, b)
        return
    ia = 1.0 - a
    for x in range(x0, x1 + 1):
        i = _idx(x, y)
        fb[i] = int(fb[i] * ia + r * a)
        fb[i + 1] = int(fb[i + 1] * ia + g * a)
        fb[i + 2] = int(fb[i + 2] * ia + b * a)


# ------------------------------------------------------------- deterministic rng

_seed = 123456789


def rnd():
    """Tiny LCG, fixed seed: same sequence every run."""
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 2147483648.0


def rr(a, b):
    return a + (b - a) * rnd()


# ---------------------------------------------------------------- PNG encoder

def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(path):
    """Encode the framebuffer as a PNG (filter 0 rows, zlib level 9)."""
    raw = bytearray()
    row = W * 3
    for y in range(H):
        raw.append(0)
        raw += fb[y * row:(y + 1) * row]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------- shape primitives

def disc(cx, cy, r, col, a=1.0):
    """Filled circle, optionally alpha-blended."""
    r = int(r)
    if r <= 0:
        return
    r2 = r * r
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        dx = int((r2 - dy * dy) ** 0.5)
        if a >= 1.0:
            hspan(y, cx - dx, cx + dx, col[0], col[1], col[2])
        else:
            hspan_blend(y, cx - dx, cx + dx, col[0], col[1], col[2], a)


def soft_disc(cx, cy, r, col, peak=0.55):
    """Glow disc: brightness falls off quadratically to the rim."""
    r = int(r)
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        for dx in range(-r, r + 1):
            d2 = dx * dx + dy * dy
            if d2 > r * r:
                continue
            t = 1.0 - d2 / (r * r)
            add(cx + dx, y, col[0], col[1], col[2], peak * t * t)


def ring(cx, cy, r, thick, col, a=1.0):
    """Circle outline of given thickness."""
    r = int(r)
    if r <= 0:
        return
    for dy in range(-r - thick, r + thick + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        for dx in range(-r - thick, r + thick + 1):
            d = (dx * dx + dy * dy) ** 0.5
            if abs(d - r) <= thick * 0.5:
                blend(cx + dx, y, col[0], col[1], col[2], a)


def thick_line(x0, y0, x1, y1, w, col, a=1.0):
    """Line drawn as a chain of discs."""
    steps = int(max(abs(x1 - x0), abs(y1 - y0)) / max(1.0, w * 0.45)) + 2
    for i in range(steps + 1):
        t = i / steps
        disc(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
             max(1, w // 2), col, a)


def bezier(p0, p1, p2, p3, n=48):
    """Cubic Bezier sample points."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
             + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
        y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
             + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
        pts.append((x, y))
    return pts


def taper_stroke(pts, r0, r1, col, shade=None):
    """Stroke a polyline with radius tapering r0 -> r1."""
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / (n - 1) if n > 1 else 0.0
        r = r0 + (r1 - r0) * t
        c = col
        if shade is not None:
            f = 1.0 - shade * t
            c = (int(col[0] * f), int(col[1] * f), int(col[2] * f))
        disc(int(x), int(y), max(1, int(r)), c)


def ellipse(cx, cy, rx, ry, col, a=1.0):
    """Filled ellipse."""
    rx = int(rx)
    ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        f = 1.0 - (dy * dy) / (ry * ry)
        if f < 0:
            continue
        dx = int(rx * (f ** 0.5))
        if a >= 1.0:
            hspan(y, cx - dx, cx + dx, col[0], col[1], col[2])
        else:
            hspan_blend(y, cx - dx, cx + dx, col[0], col[1], col[2], a)


def half_dome(cx, cy, rx, ry, col):
    """Upper half of an ellipse (jellyfish bell)."""
    rx = int(rx)
    ry = int(ry)
    for dy in range(-ry, 1):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        f = 1.0 - (dy * dy) / (ry * ry)
        if f < 0:
            continue
        dx = int(rx * (f ** 0.5))
        hspan(y, cx - dx, cx + dx, col[0], col[1], col[2])


def radial_glow(cx, cy, r, col, peak=0.5):
    """Big soft additive glow, quadratic falloff."""
    r = int(r)
    if r <= 0:
        return
    step = 2
    for dy in range(-r, r + 1, step):
        y = cy + dy
        if y < 0 or y >= H:
            continue
        for dx in range(-r, r + 1, step):
            d2 = dx * dx + dy * dy
            if d2 > r * r:
                continue
            t = 1.0 - d2 / (r * r)
            add(cx + dx, y, col[0], col[1], col[2], peak * t * t)


# ------------------------------------------------------------------- tiny font
# 5x7 pixel glyphs, written out by hand ('#' = on). Only the letters the
# title needs plus a few extras, so the text stays crisp and legible.

GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, cx, y, scale, col, glow=None):
    """Draw centred text; glow (colour) first as a soft halo if given."""
    w = text_width(s, scale)
    x0 = cx - w // 2
    for ci, ch in enumerate(s):
        g = GLYPHS.get(ch.upper(), GLYPHS[" "])
        gx = x0 + ci * 6 * scale
        for row in range(7):
            bits = g[row]
            for b in range(5):
                if bits[b] == "1":
                    bx = gx + b * scale
                    by = y + row * scale
                    if glow is not None:
                        for ox in range(-1, 2):
                            for oy in range(-1, 2):
                                disc(bx + scale // 2 + ox * scale,
                                     by + scale // 2 + oy * scale,
                                     scale, glow, 0.10)
                    for dx in range(scale):
                        for dy in range(scale):
                            put(bx + dx, by + dy, col[0], col[1], col[2])


# ---------------------------------------------------------------------- scene

def background():
    """Deep-sea gradient: teal-lit water above, abyss below, vignette."""
    for y in range(H):
        t = y / (H - 1)
        r = int(6 + 4 * t)
        g = int(34 + 26 * t - 14 * t * t)
        b = int(78 + 34 * t - 40 * t * t)
        fb[y * W * 3:(y + 1) * W * 3] = bytes((r, g, b)) * W
    # warm glow from the stage floor, cool glow from the surface
    radial_glow(512, 880, 420, (16, 90, 110), 0.55)
    radial_glow(512, 60, 380, (30, 110, 150), 0.35)
    # vignette: darken the corners
    for yy in range(0, H, 3):
        for xx in range(0, W, 3):
            dx = (xx - W / 2) / (W / 2)
            dy = (yy - H / 2) / (H / 2)
            d = dx * dx + dy * dy
            if d > 1.0:
                a = min(0.5, (d - 1.0) * 0.55)
                blend(xx, yy, 0, 2, 10, a)


def light_rays():
    """Slanted shafts of surface light, brightest upper-left."""
    for bx, top_w, alpha in ((180, 90, 0.10), (330, 60, 0.08),
                             (620, 110, 0.09), (820, 70, 0.07)):
        for s in range(0, 900, 4):
            y = 40 + s
            x = bx + int(s * 0.22)
            w = top_w + int(s * 0.12)
            for xx in range(x - w // 2, x + w // 2 + 1, 2):
                fade = 1.0 - s / 950.0
                blend(xx, y, 120, 210, 235, alpha * fade * 0.5)


def bubble(x, y, r):
    ring(x, y, r, 2, (170, 225, 245), 0.75)
    disc(x - r // 3, y - r // 3, max(1, r // 4), (220, 245, 255), 0.9)


def music_note(x, y, s, col, tilt=0.0):
    """A quaver: filled head, stem, flag."""
    ellipse(x, y, int(7 * s), int(5 * s), col)
    thick_line(x + int(6 * s), y, x + int(6 * s), y - int(22 * s),
               max(2, int(2.5 * s)), col)
    pts = bezier((x + int(6 * s), y - int(22 * s)),
                 (x + int(16 * s), y - int(20 * s)),
                 (x + int(18 * s), y - int(10 * s)),
                 (x + int(12 * s), y - int(4 * s)), 12)
    taper_stroke(pts, 3 * s, 1.5 * s, col)


def jellyfish(cx, cy, size, bell, glow_col, tent_col, phase):
    """One glowing jellyfish: dome bell, scalloped rim, wavy tentacles."""
    soft_disc(cx, cy, int(size * 1.7), glow_col, 0.30)
    # bell: dome + inner dome for depth
    half_dome(cx, cy, int(size), int(size * 0.82), bell)
    half_dome(cx, cy - int(size * 0.12), int(size * 0.62),
              int(size * 0.5), (255, 255, 255))
    # scalloped rim
    for k in range(5):
        t = -0.8 + k * 0.4
        sx = cx + int(t * size * 0.9)
        disc(sx, cy + int(size * 0.06), int(size * 0.16), bell)
    # oral arms + tentacles: sine waves falling away
    import math
    for k in range(5):
        tx = cx + int((k - 2) * size * 0.34)
        length = size * (1.5 + 0.35 * ((k * 7 + phase) % 3))
        pts = []
        steps = 26
        for i in range(steps + 1):
            t = i / steps
            sway = math.sin(t * 5.0 + phase + k * 1.3) * size * 0.16 * t
            pts.append((tx + sway, cy + t * length))
        taper_stroke(pts, max(2, size * 0.07), 1.5, tent_col)


def octopus():
    """The conductor: big purple dome, two bright eyes, eight sweeping
    arms, one raised arm holding a glowing baton."""
    import math
    cx, cy = 512, 545
    # halo behind the head
    radial_glow(cx, cy - 40, 330, (120, 60, 190), 0.42)
    # arms first (behind the head): four each side, sweeping down and out
    arm_defs = [
        # (control points, base radius)
        ((cx - 90, cy + 60), (cx - 260, cy + 210), (cx - 430, cy + 330),
         (cx - 470, cy + 560), 30),
        ((cx - 60, cy + 90), (cx - 170, cy + 260), (cx - 300, cy + 430),
         (cx - 330, cy + 640), 28),
        ((cx - 25, cy + 105), (cx - 60, cy + 300), (cx - 110, cy + 480),
         (cx - 120, cy + 690), 26),
        ((cx + 20, cy + 110), (cx + 30, cy + 300), (cx + 40, cy + 500),
         (cx + 30, cy + 700), 26),
        ((cx + 60, cy + 100), (cx + 130, cy + 280), (cx + 210, cy + 460),
         (cx + 250, cy + 660), 27),
        ((cx + 95, cy + 70), (cx + 230, cy + 220), (cx + 360, cy + 340),
         (cx + 430, cy + 520), 29),
    ]
    purple = (122, 62, 196)
    purple_dark = (74, 32, 128)
    for p0, p1, p2, p3, r0 in arm_defs:
        pts = bezier(p0, p1, p2, p3, 56)
        taper_stroke(pts, r0, 6, purple, shade=0.35)
        # suction cups along the inner side
        for i in range(6, len(pts), 7):
            x, y = pts[i]
            disc(int(x), int(y), 5, (196, 150, 235), 0.85)
    # head: big dome with a lighter crown
    half_dome(cx, cy + 40, 205, 195, purple)
    half_dome(cx, cy + 28, 165, 150, (146, 84, 214))
    ellipse(cx, cy + 30, 205, 60, purple)
    # crown highlight
    ellipse(cx - 55, cy - 95, 95, 42, (168, 110, 228), 0.55)
    # eyes: wide, bright, looking up-right toward the baton
    for ex in (cx - 78, cx + 78):
        ellipse(ex, cy - 30, 42, 50, (245, 250, 255))
        disc(ex + 10, cy - 26, 20, (16, 8, 34))
        disc(ex + 4, cy - 36, 8, (255, 255, 255))
    # blush + smile
    ellipse(cx - 128, cy + 28, 22, 12, (216, 110, 190), 0.6)
    ellipse(cx + 128, cy + 28, 22, 12, (216, 110, 190), 0.6)
    # raised conducting arm, curving up-right with the baton
    pts = bezier((cx + 130, cy - 60), (cx + 260, cy - 150),
                 (cx + 330, cy - 260), (cx + 350, cy - 380), 40)
    taper_stroke(pts, 26, 7, purple, shade=0.25)
    for i in range(5, len(pts), 8):
        x, y = pts[i]
        disc(int(x), int(y), 5, (196, 150, 235), 0.85)
    # baton: gold wand with a starburst tip, held at the raised arm's tip
    bx, by = cx + 350, cy - 380
    thick_line(bx, by, bx + 90, by - 110, 5, (255, 214, 110))
    soft_disc(bx + 90, by - 110, 46, (255, 220, 120), 0.8)
    disc(bx + 90, by - 110, 9, (255, 246, 200))
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        thick_line(bx + 90, by - 110,
                   bx + 90 + int(26 * math.cos(a)),
                   by - 110 + int(26 * math.sin(a)), 3, (255, 230, 150), 0.9)


def seafloor():
    """Dark rocks, glowing anemones and coral at the bottom."""
    import math
    for y in range(930, H):
        t = (y - 930) / 94.0
        r = int(10 - 8 * t)
        g = int(22 - 16 * t)
        b = int(40 - 26 * t)
        fb[y * W * 3:(y + 1) * W * 3] = bytes((r, g, b)) * W
    # rock humps
    for cx, rx, ry in ((140, 170, 46), (430, 210, 58), (760, 230, 52),
                       (960, 150, 40)):
        ellipse(cx, 968, rx, ry, (14, 26, 48))
        ellipse(cx - 30, 952, rx // 2, ry // 2, (22, 38, 66), 0.8)
    # glowing anemone tufts
    for cx, col in ((120, (255, 120, 170)), (330, (90, 230, 220)),
                    (700, (255, 190, 90)), (900, (170, 140, 255))):
        for k in range(7):
            ang = math.pi * (0.15 + 0.7 * k / 6.0)
            ex = cx + int(26 * math.cos(math.pi - ang))
            ey = 940 - int(34 * math.sin(ang))
            thick_line(cx, 945, ex, ey, 4, col, 0.9)
            disc(ex, ey, 4, (255, 255, 255), 0.9)
        soft_disc(cx, 930, 34, col, 0.35)


# ---------------------------------------------------------------------- compose

def main():
    background()
    light_rays()

    # title, high in clear water, glowing cyan-white
    draw_text("THE CONDUCTOR", 512, 52, 5, (235, 250, 255),
              glow=(60, 190, 230))
    draw_text("OF THE DEEP", 512, 104, 5, (170, 225, 250),
              glow=(60, 190, 230))

    # jellyfish orchestra: an arc of glowing players below the conductor
    players = [
        (150, 700, 52, (90, 220, 235), (0, 200, 220), (110, 235, 245), 0.0),
        (300, 790, 60, (255, 130, 190), (235, 60, 140), (255, 150, 200), 1.1),
        (512, 830, 66, (255, 205, 90), (230, 160, 40), (255, 220, 130), 2.2),
        (720, 790, 58, (150, 120, 255), (120, 80, 235), (180, 150, 255), 3.0),
        (880, 700, 50, (90, 235, 170), (20, 200, 140), (120, 245, 190), 4.1),
    ]
    for cx, cy, size, bell, glowc, tent, ph in players:
        jellyfish(cx, cy, size, bell, glowc, tent, ph)

    octopus()

    # rising music notes, gold and cyan, drifting up from the orchestra
    notes = [
        (250, 560, 1.0, (255, 214, 110)), (700, 520, 1.1, (140, 230, 245)),
        (820, 430, 0.9, (255, 214, 110)), (180, 430, 0.85, (140, 230, 245)),
        (610, 340, 1.0, (255, 214, 110)), (420, 300, 0.8, (140, 230, 245)),
        (880, 600, 0.9, (255, 190, 140)), (120, 600, 0.8, (255, 190, 140)),
    ]
    for x, y, s, col in notes:
        soft_disc(x, y - 8, int(26 * s), col, 0.35)
        music_note(x, y, s, col)

    # bubbles rising in loose streams
    for bx, by, n in ((200, 900, 6), (830, 880, 6), (512, 950, 5),
                      (60, 820, 4), (970, 800, 4)):
        for k in range(n):
            r = int(rr(4, 11))
            x = int(bx + rr(-26, 26) + k * 4)
            y = int(by - k * 62 - rr(0, 30))
            bubble(x, y, r)

    # drifting plankton motes for depth
    for _ in range(320):
        x = int(rr(0, W))
        y = int(rr(0, H))
        c = rr(0, 1)
        if c < 0.5:
            put(x, y, 150, 210, 235)
        else:
            put(x, y, 200, 180, 255)

    os.makedirs("/output", exist_ok=True)
    n = write_png("/output/entry.png")
    print("wrote /output/entry.png", n, "bytes")


if __name__ == "__main__":
    main()
