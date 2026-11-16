#!/usr/bin/env python3
"""The Conductor of the Deep -- ai-excited-01 entry.

A program that draws, from scratch with only the Python standard library,
one deterministic 1024x1024 PNG: a giant purple octopus conducting a
glowing jellyfish orchestra in the deep sea, the music itself spiralling
up out of the water as light.

Everything here is original code written for this entry: a small software
rasterizer (spans, circles, ellipses, bezier strokes, polygons, a 5x7
bitmap font) and a PNG encoder built on zlib.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = "/output/entry.png"


def lerp(a, b, t):
    return int(a + (b - a) * t)


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def span(self, y, x0, x1, col, a=255):
        """Fill a horizontal run of pixels on row y, blended by alpha a."""
        if y < 0 or y >= self.h:
            return
        if x0 > x1:
            x0, x1 = x1, x0
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x0 > x1:
            return
        r, g, b = col
        base = (y * self.w + x0) * 3
        if a >= 255:
            pat = bytes((r, g, b))
            n = x1 - x0 + 1
            self.buf[base:base + n * 3] = pat * n
        elif a > 0:
            ia = 255 - a
            buf = self.buf
            for x in range(x0, x1 + 1):
                i = (y * self.w + x) * 3
                buf[i] = (buf[i] * ia + r * a) // 255
                buf[i + 1] = (buf[i + 1] * ia + g * a) // 255
                buf[i + 2] = (buf[i + 2] * ia + b * a) // 255

    def dot(self, x, y, col, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            r, g, b = col
            if a >= 255:
                self.buf[i] = r
                self.buf[i + 1] = g
                self.buf[i + 2] = b
            elif a > 0:
                ia = 255 - a
                self.buf[i] = (self.buf[i] * ia + r * a) // 255
                self.buf[i + 1] = (self.buf[i + 1] * ia + g * a) // 255
                self.buf[i + 2] = (self.buf[i + 2] * ia + b * a) // 255

    def circle(self, cx, cy, rad, col, a=255):
        rad = int(rad)
        if rad <= 0:
            return
        for dy in range(-rad, rad + 1):
            dx = int(math.sqrt(rad * rad - dy * dy))
            self.span(cy + dy, cx - dx, cx + dx, col, a)

    def ellipse(self, cx, cy, rx, ry, col, a=255):
        rx = int(rx)
        ry = int(ry)
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-ry, ry + 1):
            t = dy / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
            self.span(cy + dy, cx - dx, cx + dx, col, a)

    def disc_glow(self, cx, cy, rad, col, peak=90):
        """Soft glow: layered discs fading outwards."""
        steps = 5
        for k in range(steps, 0, -1):
            r = rad * k // steps
            self.circle(cx, cy, r, col, peak * (steps - k + 1) // (steps * 2))

    def poly(self, pts, col, a=255):
        """Scanline fill of a simple polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, int(min(ys))), min(self.h - 1, int(max(ys)))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.span(y, int(xs[k]), int(xs[k + 1]), col, a)

    def bezier(self, p0, p1, p2, width, col, a=255, steps=40):
        """Thick quadratic bezier stroke, drawn as overlapping discs."""
        for s in range(steps + 1):
            t = s / steps
            mt = 1.0 - t
            x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
            y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
            w = width[0] + (width[1] - width[0]) * t
            self.circle(int(x), int(y), max(1, int(w / 2)), col, a)

    def bezier_point(self, p0, p1, p2, t):
        mt = 1.0 - t
        return (
            mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
            mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1],
        )

    def stroke(self, pts, width, col, a=255):
        """Thick polyline through pts."""
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            dist = math.hypot(x2 - x1, y2 - y1)
            n = max(1, int(dist / max(2.0, width / 3)))
            for s in range(n + 1):
                t = s / n
                self.circle(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t),
                            max(1, int(width / 2)), col, a)


# ---------------------------------------------------------------------------
# 5x7 bitmap font (glyphs drawn as rows of '#' / '.')
# ---------------------------------------------------------------------------
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
}

CHAR_W = 5
CHAR_H = 7


def text_width(s, scale, gap=None):
    if gap is None:
        gap = scale
    return len(s) * (CHAR_W * scale + gap) - gap


def draw_text(cv, s, x, y, scale, col, a=255, gap=None):
    if gap is None:
        gap = scale
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for row in range(CHAR_H):
            for c in range(CHAR_W):
                if glyph[row][c] == "#":
                    for dy in range(scale):
                        cv.span(y + row * scale + dy, cx + c * scale,
                                cx + c * scale + scale - 1, col, a)
        cx += CHAR_W * scale + gap


# ---------------------------------------------------------------------------
# PNG encoder (zlib is stdlib)
# ---------------------------------------------------------------------------
def write_png(path, cv):
    raw = bytearray()
    rowlen = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * rowlen:(y + 1) * rowlen]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
DEEP_TOP = (10, 18, 58)
DEEP_MID = (10, 34, 78)
DEEP_BOT = (3, 20, 34)
PURPLE_DARK = (74, 32, 122)
PURPLE = (126, 62, 188)
PURPLE_LIGHT = (172, 112, 232)
LAVENDER = (208, 168, 252)
GOLD = (255, 208, 92)
GOLD_LIGHT = (255, 238, 170)
CYAN = (90, 222, 255)


def draw_background(cv):
    for y in range(H):
        t = y / (H - 1)
        if t < 0.55:
            col = mix(DEEP_TOP, DEEP_MID, t / 0.55)
        else:
            col = mix(DEEP_MID, DEEP_BOT, (t - 0.55) / 0.45)
        cv.span(y, 0, W - 1, col)
    # soft violet glow behind the stage, centre of the canvas
    cv.disc_glow(512, 560, 430, (96, 64, 168), peak=46)
    cv.disc_glow(512, 560, 260, (140, 96, 210), peak=40)


def draw_rays(cv):
    # pale light shafts falling from the surface
    top = (512, -60)
    for k, (dx, spread, a) in enumerate(
            [(-430, 90, 13), (-240, 70, 16), (-60, 60, 18),
             (130, 70, 16), (330, 90, 13)]):
        x = top[0] + dx
        cv.poly([(x - spread, 0), (x + spread, 0),
                 (x + spread + dx // 3, H), (x - spread + dx // 3, H)],
                (150, 200, 255), a)


def draw_seabed(cv):
    cv.ellipse(180, 1060, 330, 120, (6, 26, 40))
    cv.ellipse(860, 1075, 360, 130, (5, 22, 36))
    cv.ellipse(512, 1100, 420, 110, (4, 18, 30))
    # a few glowing pebbles / coral dots on the floor
    for (x, y, r, col) in [(140, 972, 7, CYAN), (205, 990, 5, GOLD),
                           (880, 968, 7, (255, 130, 200)),
                           (930, 992, 5, CYAN), (512, 995, 6, GOLD)]:
        cv.disc_glow(x, y, r * 3, col, peak=70)
        cv.circle(x, y, r, col)


def draw_arms(cv):
    """Eight flowing arms; the right one rises to conduct with a baton."""
    arms = [
        # (start, control, end, width start->end, colour)
        ((620, 690), (770, 600), (838, 428), (48, 18), PURPLE),
        ((648, 728), (810, 758), (905, 700), (44, 16), PURPLE_LIGHT),
        ((604, 756), (730, 862), (862, 902), (42, 14), PURPLE),
        ((404, 690), (292, 596), (206, 468), (48, 18), PURPLE_LIGHT),
        ((376, 728), (238, 756), (118, 700), (44, 16), PURPLE),
        ((420, 756), (306, 862), (162, 902), (42, 14), PURPLE_LIGHT),
        ((478, 748), (448, 852), (418, 952), (40, 14), PURPLE),
        ((548, 748), (580, 852), (612, 952), (40, 14), PURPLE_LIGHT),
    ]
    for p0, p1, p2, wdt, col in arms:
        cv.bezier(p0, p1, p2, wdt, col, steps=48)
        # lighter ridge along the top of each arm
        cv.bezier(p0, p1, p2, (wdt[0] * 0.45, wdt[1] * 0.45), LAVENDER,
                  a=70, steps=48)
    # suckers: pale dots trailing along the two front arms
    for p0, p1, p2 in (arms[6][:3], arms[7][:3]):
        for k in range(1, 8):
            t = k / 8.0
            x, y = cv.bezier_point(p0, p1, p2, t)
            cv.circle(int(x), int(y), 7, LAVENDER, a=150)
    # the conducting baton: gold, held at the tip of the raised arm
    cv.stroke([(838, 428), (908, 332)], 9, GOLD)
    cv.disc_glow(908, 332, 60, GOLD, peak=90)
    cv.circle(908, 332, 12, GOLD_LIGHT)
    # four-point sparkle star at the baton tip
    cv.poly([(908, 300), (916, 324), (940, 332), (916, 340),
             (908, 364), (900, 340), (876, 332), (900, 324)],
            GOLD_LIGHT)


def draw_jelly(cv, cx, cy, r, dome, glow, tent):
    """One glowing jellyfish: dome, scalloped rim, wavy tentacles."""
    cv.disc_glow(cx, cy, int(r * 1.7), glow, peak=55)
    # dome
    cv.ellipse(cx, cy, r, int(r * 0.78), dome)
    cv.ellipse(cx - r // 5, cy - r // 4, int(r * 0.62), int(r * 0.42),
               (255, 255, 255), a=70)
    cv.ellipse(cx - r // 3, cy - r // 3, int(r * 0.3), int(r * 0.18),
               (255, 255, 255), a=110)
    # scalloped lower rim
    for k in range(-2, 3):
        sx = cx + k * r // 2
        sy = cy + int(r * 0.62)
        cv.circle(sx, sy, r // 5, dome)
    # bright rim along the dome top
    for s in range(13):
        t = math.pi * s / 12
        x = cx + int(r * 0.96 * math.cos(math.pi + t))
        y = cy - int(r * 0.74 * math.sin(t))
        cv.circle(x, y, 4, (255, 255, 255), a=150)
    # two glowing spots inside the dome
    cv.circle(cx - r // 3, cy + r // 8, r // 8, (255, 255, 255), a=120)
    cv.circle(cx + r // 4, cy + r // 5, r // 10, (255, 255, 255), a=120)
    # tentacles: sine-wave strokes hanging from the rim
    for k in range(-2, 3):
        x0 = cx + k * r // 2
        y0 = cy + int(r * 0.68)
        length = int(r * (1.5 + 0.18 * abs(k)))
        pts = []
        for s in range(17):
            t = s / 16
            pts.append((x0 + int(9 * math.sin(t * 5.2 + k * 1.7)),
                        y0 + int(length * t)))
        cv.stroke(pts, 5, tent, a=210)


def draw_jellies(cv):
    # the orchestra, arched above the conductor
    draw_jelly(cv, 252, 330, 76, (255, 120, 200), (255, 90, 180), (255, 170, 220))
    draw_jelly(cv, 392, 238, 64, (90, 220, 255), (60, 190, 255), (150, 235, 255))
    draw_jelly(cv, 545, 205, 70, (255, 200, 90), (255, 180, 60), (255, 225, 150))
    draw_jelly(cv, 688, 242, 64, (180, 120, 255), (150, 90, 255), (205, 165, 255))
    draw_jelly(cv, 822, 332, 76, (120, 255, 200), (80, 240, 170), (170, 255, 215))
    # two small ones flanking the stage
    draw_jelly(cv, 138, 500, 52, (255, 150, 120), (255, 120, 90), (255, 190, 160))
    draw_jelly(cv, 890, 498, 52, (120, 200, 255), (90, 170, 255), (160, 215, 255))


def draw_note(cv, x, y, s, col, tilt=0):
    """A quaver: filled head, stem, flag."""
    cv.ellipse(x, y, int(8 * s), int(6 * s), col)
    # stem: a short vertical bar rising from the head
    sx = x + int(7 * s)
    for yy in range(y - int(28 * s), y + 1):
        cv.span(yy, sx, sx + max(1, int(2.5 * s)), col)
    cv.poly([(sx, y - int(28 * s)),
             (sx + int(14 * s), y - int(20 * s)),
             (sx, y - int(12 * s))], col)
    cv.circle(x, y, int(3 * s), (255, 255, 255), a=160)


def draw_music(cv):
    # the music itself, spiralling up from the baton toward the surface:
    # a trail of glowing dots that tightens as it rises
    for k in range(46):
        t = k / 45.0
        ang = 1.1 + t * 5.4
        rad = 30 + 250 * (1 - t) * 0.9
        x = int(880 - rad * math.cos(ang) * 0.55 - t * 60)
        y = int(360 - t * 250 + 40 * math.sin(ang))
        r = max(2, int(9 - 6 * t))
        col = GOLD if k % 3 else CYAN
        cv.disc_glow(x, y, r * 4, col, peak=70)
        cv.circle(x, y, r, col)
    # floating quavers along the spiral and around the jellies
    for (x, y, s, col) in [(700, 470, 1.5, GOLD), (770, 400, 1.2, CYAN),
                           (836, 330, 1.4, GOLD_LIGHT), (300, 470, 1.3, CYAN),
                           (180, 620, 1.1, GOLD), (850, 600, 1.2, GOLD),
                           (620, 330, 1.0, CYAN), (430, 330, 1.0, GOLD)]:
        draw_note(cv, x, y, s, col)


def draw_bubbles(cv):
    for i in range(30):
        x = int(50 + (i * 137.5) % 924)
        y = int(920 - (i * 61.7) % 760)
        r = 4 + (i * 7) % 13
        cv.circle(x, y, r, (170, 220, 255), a=55)
        cv.circle(x - r // 3, y - r // 3, max(1, r // 4), (255, 255, 255), a=170)


def draw_fish(cv, x, y, s, col):
    """A tiny silhouetted fish, part of the audience below."""
    cv.ellipse(x, y, int(22 * s), int(10 * s), col)
    cv.poly([(x - int(20 * s), y), (x - int(34 * s), y - int(11 * s)),
             (x - int(34 * s), y + int(11 * s))], col)
    cv.circle(x + int(10 * s), y - 2, max(1, int(2.5 * s)), (200, 230, 255))


def draw_title(cv):
    title = "THE CONDUCTOR OF THE DEEP"
    sub = "THE ABYSS PLAYS TONIGHT"
    scale = 4
    tw = text_width(title, scale)
    tx = (W - tw) // 2
    # dark halo so the gold reads over the rays
    draw_text(cv, title, tx + 3, 51, scale, (8, 10, 40))
    draw_text(cv, title, tx, 48, scale, GOLD)
    draw_text(cv, title, tx, 48, scale, GOLD_LIGHT, a=60)
    sw = text_width(sub, 2)
    draw_text(cv, sub, (W - sw) // 2, 102, 2, CYAN)


def draw_octopus_head(cv):
    cx, cy = 512, 585
    # head dome, layered for a soft shaded look
    cv.ellipse(cx, cy, 208, 178, PURPLE_DARK)
    cv.ellipse(cx - 8, cy - 12, 192, 162, PURPLE)
    cv.ellipse(cx - 26, cy - 38, 150, 118, PURPLE_LIGHT, a=150)
    cv.ellipse(cx - 70, cy - 78, 62, 40, LAVENDER, a=110)
    # belly patch where the arms meet the head
    cv.ellipse(cx, cy + 118, 128, 62, LAVENDER, a=120)
    # blush
    cv.circle(392, 648, 26, (255, 130, 190), a=80)
    cv.circle(632, 648, 26, (255, 130, 190), a=80)
    # eyes: big, looking up toward the baton
    for ex in (438, 586):
        cv.ellipse(ex, 556, 50, 60, (242, 248, 255))
        cv.ellipse(ex + 12, 544, 21, 29, (18, 10, 42))
        cv.circle(ex + 4, 532, 9, (255, 255, 255))
        cv.circle(ex + 18, 560, 4, (255, 255, 255), a=200)
    # happy raised brows
    cv.bezier((398, 478), (430, 452), (468, 472), (10, 10), PURPLE_DARK)
    cv.bezier((556, 472), (594, 452), (626, 478), (10, 10), PURPLE_DARK)
    # wide joyful smile
    pts = []
    for s in range(21):
        t = s / 20
        x = 448 + 128 * t
        y = 640 + 34 * math.sin(math.pi * t) * 0.9
        pts.append((x, y))
    cv.stroke(pts, 11, (52, 18, 88))
    cv.circle(448, 640, 7, (52, 18, 88))
    cv.circle(576, 640, 7, (52, 18, 88))


def draw_scene(cv):
    draw_background(cv)
    draw_rays(cv)
    draw_seabed(cv)
    draw_arms(cv)
    draw_octopus_head(cv)
    draw_jellies(cv)
    draw_music(cv)
    draw_bubbles(cv)
    for (fx, fy, fs, fc) in [(120, 935, 1.0, (30, 66, 104)),
                             (205, 962, 0.8, (26, 58, 94)),
                             (905, 940, 1.1, (30, 66, 104)),
                             (820, 965, 0.7, (26, 58, 94))]:
        draw_fish(cv, fx, fy, fs, fc)
    draw_title(cv)


def main():
    cv = Canvas(W, H)
    draw_scene(cv)
    write_png(OUT, cv)


if __name__ == "__main__":
    main()
