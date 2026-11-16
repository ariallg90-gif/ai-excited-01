#!/usr/bin/env python3
"""The Conductor of the Deep — ai-excited-01 round 3.

A giant violet octopus conducts a glowing jellyfish orchestra on the
ocean floor. Pure Python standard library: a tiny software rasterizer
(framebuffer, scanline fills, bezier tentacles, additive glow) plus a
hand-rolled PNG encoder. Deterministic: fixed seed, no clock, no I/O
besides the single output file.

Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png), 1024x1024.
"""
import math
import os
import random
import struct
import zlib

W = 1024
H = 1024
RNG = random.Random(20261117)


# ---------------------------------------------------------------- colors
def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else int(v)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (clamp(lerp(c1[0], c2[0], t)),
            clamp(lerp(c1[1], c2[1], t)),
            clamp(lerp(c1[2], c2[2], t)))


# ------------------------------------------------------------- framebuffer
class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])

    def add(self, x, y, c, amt=1.0):
        """Additive blend of colour c scaled by amt (0..1)."""
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = clamp(self.px[i] + c[0] * amt)
            self.px[i + 1] = clamp(self.px[i + 1] + c[1] * amt)
            self.px[i + 2] = clamp(self.px[i + 2] + c[2] * amt)

    def blend(self, x, y, c, a):
        """Alpha blend colour c over the pixel (a in 0..1)."""
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = clamp(lerp(self.px[i], c[0], a))
            self.px[i + 1] = clamp(lerp(self.px[i + 1], c[1], a))
            self.px[i + 2] = clamp(lerp(self.px[i + 2], c[2], a))

    def hline(self, x0, x1, y, c):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x1 < x0:
            return
        i = (y * self.w + x0) * 3
        row = bytes(c) * (x1 - x0 + 1)
        self.px[i:i + len(row)] = row


def vgrad(cv, top, bottom):
    """Vertical gradient background, one row at a time."""
    for y in range(cv.h):
        t = y / (cv.h - 1)
        cv.hline(0, cv.w - 1, y, mix(top, bottom, t))


# -------------------------------------------------------------- primitives
def disc(cv, cx, cy, r, c, alpha=1.0):
    """Filled circle, optionally alpha-blended."""
    r = int(r)
    if r <= 0:
        return
    for y in range(cy - r, cy + r + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, r * r - dy * dy)))
        if alpha >= 1.0:
            cv.hline(cx - dx, cx + dx, y, c)
        else:
            for x in range(cx - dx, cx + dx + 1):
                cv.blend(x, y, c, alpha)


def glow(cv, cx, cy, r, c, strength=1.0):
    """Soft additive radial glow, falloff squared."""
    r = int(r)
    if r <= 0:
        return
    for y in range(max(0, cy - r), min(cv.h, cy + r + 1)):
        dy = (y - cy) / r
        for x in range(max(0, cx - r), min(cv.w, cx + r + 1)):
            dx = (x - cx) / r
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                cv.add(x, y, c, strength * (1.0 - d2) * (1.0 - d2))


def ellipse(cv, cx, cy, rx, ry, c, alpha=1.0):
    rx = int(rx)
    ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    for y in range(cy - ry, cy + ry + 1):
        t = (y - cy) / ry
        dx = int(rx * math.sqrt(max(0.0, 1.0 - t * t)))
        if alpha >= 1.0:
            cv.hline(cx - dx, cx + dx, y, c)
        else:
            for x in range(cx - dx, cx + dx + 1):
                cv.blend(x, y, c, alpha)


def thick_line(cv, x0, y0, x1, y1, width, c, alpha=1.0):
    """Line drawn as a chain of discs (round caps, round joins)."""
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(math.hypot(dx, dy) / max(1, width // 3)))
    r = width / 2.0
    for s in range(steps + 1):
        t = s / steps
        disc(cv, int(x0 + dx * t), int(y0 + dy * t), r, c, alpha)


def quad(p0, p1, p2, t):
    """Point on a quadratic bezier at t."""
    u = 1.0 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def bezier_stroke(cv, p0, p1, p2, w0, w1, c, alpha=1.0, steps=48):
    """Tapered bezier stroke: disc radius lerps w0 -> w1 along the curve."""
    prev = None
    for s in range(steps + 1):
        t = s / steps
        x, y = quad(p0, p1, p2, t)
        w = lerp(w0, w1, t)
        if prev is not None:
            thick_line(cv, int(prev[0]), int(prev[1]), int(x), int(y),
                       max(1, int(w)), c, alpha)
        prev = (x, y)


def polygon(cv, pts, c, alpha=1.0):
    """Scanline-filled polygon."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    ymin, ymax = int(min(ys)), int(max(ys))
    n = len(pts)
    for y in range(ymin, ymax + 1):
        xs = []
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            if alpha >= 1.0:
                cv.hline(int(xs[k]), int(xs[k + 1]), y, c)
            else:
                for x in range(int(xs[k]), int(xs[k + 1]) + 1):
                    cv.blend(x, y, c, alpha)


# -------------------------------------------------------------- PNG writer
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(ctype, data):
        out = struct.pack(">I", len(data)) + ctype + data
        out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------------- scene
DEEP_TOP = (3, 10, 38)
DEEP_BOT = (4, 48, 66)
VIOLET = (122, 62, 214)
VIOLET_DK = (74, 28, 140)
VIOLET_LT = (178, 120, 255)
PINK = (255, 110, 190)
CYAN = (80, 230, 255)
GOLD = (255, 205, 90)
TEAL = (60, 220, 190)


def light_rays(cv):
    """Diagonal god-rays from the surface, top-left."""
    for i in range(7):
        x0 = 60 + i * 150
        top_w = 26 + (i % 3) * 14
        pts = [(x0, 0), (x0 + top_w, 0),
               (x0 + top_w + 260, H), (x0 + 260, H)]
        polygon(cv, pts, (90, 180, 255), alpha=0.05 + 0.02 * (i % 2))


def plankton(cv):
    """Tiny drifting motes of light."""
    for _ in range(240):
        x = RNG.randrange(0, W)
        y = RNG.randrange(0, H)
        r = RNG.choice([1, 1, 1, 2])
        c = RNG.choice([(140, 220, 255), (255, 220, 140),
                        (200, 160, 255), (160, 255, 220)])
        glow(cv, x, y, r * 4, c, 0.35)
        disc(cv, x, y, r, c)


def bubbles(cv):
    for _ in range(46):
        x = RNG.randrange(30, W - 30)
        y = RNG.randrange(120, H - 60)
        r = RNG.randrange(3, 15)
        for xx in range(x - r, x + r + 1):
            for yy in range(y - r, y + r + 1):
                d = math.hypot(xx - x, yy - y)
                if r - 1.5 < d <= r:
                    cv.blend(xx, yy, (190, 235, 255), 0.55)
        disc(cv, x - r // 3, y - r // 3, max(1, r // 4), (235, 250, 255))


def jellyfish(cv, cx, cy, size, hue, tilt):
    """One glowing jellyfish musician, dome + oral arms + trailing tentacles."""
    # halo behind the dome
    glow(cv, cx, cy, int(size * 1.9), hue, 0.5)
    # dome: stacked ellipses, bright rim at the top
    for k in range(6):
        t = k / 5.0
        ry = size * (0.42 + 0.30 * t)
        rx = size * (0.55 + 0.45 * t)
        col = mix(hue, (255, 255, 255), 0.55 * (1.0 - t))
        ellipse(cv, cx, int(cy - size * 0.18 + t * size * 0.34),
                rx, ry, col, alpha=0.85)
    # dome outline glow
    ellipse(cv, cx, int(cy - size * 0.05), size, size * 0.62,
            mix(hue, (255, 255, 255), 0.35), alpha=0.35)
    # inner glow spots
    for a in (-0.5, 0.0, 0.5):
        glow(cv, int(cx + a * size * 0.55), int(cy + size * 0.1),
             int(size * 0.28), (255, 255, 255), 0.5)
    # oral arms: short wavy ribbons under the dome
    for j in range(5):
        ox = cx + (j - 2) * size * 0.28
        pts = []
        for s in range(9):
            t = s / 8.0
            pts.append((ox + math.sin(t * 5.0 + j + tilt) * size * 0.12,
                        cy + size * 0.42 + t * size * 0.55))
        for a, b in zip(pts, pts[1:]):
            thick_line(cv, int(a[0]), int(a[1]), int(b[0]), int(b[1]),
                       max(2, int(size * 0.07)), mix(hue, (255, 255, 255), 0.3),
                       alpha=0.9)
    # long trailing tentacles
    for j in range(7):
        ox = cx + (j - 3) * size * 0.24
        sway = math.sin(j * 1.7 + tilt) * size * 0.22
        bezier_stroke(cv, (ox, cy + size * 0.45),
                      (ox + sway, cy + size * 1.05),
                      (ox - sway * 0.6, cy + size * 1.75),
                      max(2.0, size * 0.06), 1.0,
                      mix(hue, (255, 255, 255), 0.45), alpha=0.85)


def music_note(cv, x, y, s, c):
    """A small glowing quaver."""
    glow(cv, x, y, int(s * 2.2), c, 0.6)
    ellipse(cv, x, y, s * 0.55, s * 0.4, c)
    thick_line(cv, x + int(s * 0.5), y, x + int(s * 0.5),
               y - int(s * 1.6), max(2, int(s * 0.18)), c)
    polygon(cv, [(x + int(s * 0.5), y - int(s * 1.6)),
                 (x + int(s * 1.3), y - int(s * 1.2)),
                 (x + int(s * 0.5), y - int(s * 0.9))], c)


def octopus(cv):
    """The conductor: huge violet head, glowing eyes, eight sweeping arms."""
    cx, cy = 512, 335
    # back glow
    glow(cv, cx, cy, 330, (140, 70, 255), 0.55)
    glow(cv, cx, cy - 60, 200, (90, 200, 255), 0.25)
    # arms first (behind the head): four per side, sweeping down and out
    arm_specs = [
        ((cx - 150, cy + 90), (cx - 330, cy + 330), (cx - 300, cy + 640), 46),
        ((cx - 110, cy + 120), (cx - 210, cy + 420), (cx - 150, cy + 700), 40),
        ((cx - 55, cy + 140), (cx - 90, cy + 470), (cx - 30, cy + 760), 34),
        ((cx - 15, cy + 150), (cx + 20, cy + 500), (cx + 40, cy + 800), 30),
        ((cx + 15, cy + 150), (cx + 60, cy + 500), (cx + 120, cy + 790), 30),
        ((cx + 55, cy + 140), (cx + 170, cy + 470), (cx + 190, cy + 750), 34),
        ((cx + 110, cy + 120), (cx + 290, cy + 420), (cx + 310, cy + 690), 40),
        ((cx + 150, cy + 90), (cx + 400, cy + 330), (cx + 460, cy + 620), 46),
    ]
    for p0, p1, p2, w0 in arm_specs:
        bezier_stroke(cv, p0, p1, p2, w0, 7, VIOLET_DK)
        bezier_stroke(cv, p0, p1, p2, w0 * 0.72, 5, VIOLET)
        # suckers: pale dots along the inner side of each arm
        for s in range(4, 26):
            t = s / 26.0
            x, y = quad(p0, p1, p2, t)
            disc(cv, int(x), int(y), max(2, int(lerp(w0 * 0.22, 2, t))),
                 (235, 190, 255), alpha=0.8)
    # head: layered ellipses, lighter crown
    ellipse(cv, cx, cy, 215, 195, VIOLET_DK)
    ellipse(cv, cx, cy - 12, 200, 178, VIOLET)
    ellipse(cv, cx, cy - 55, 150, 118, VIOLET_LT, alpha=0.55)
    ellipse(cv, cx, cy - 95, 95, 62, (205, 160, 255), alpha=0.5)
    # head spots
    for (sx, sy, sr) in [(-120, -90, 16), (90, -120, 12), (150, -30, 10),
                         (-160, 10, 9), (40, -150, 8), (-40, 60, 7)]:
        disc(cv, cx + sx, cy + sy, sr, (200, 150, 255), alpha=0.5)
    # eyes: big, glowing, looking toward the orchestra
    for ex, ey in [(cx - 88, cy - 18), (cx + 88, cy - 18)]:
        glow(cv, ex, ey, 62, (120, 240, 255), 0.8)
        disc(cv, ex, ey, 40, (240, 250, 255))
        disc(cv, ex, ey + 4, 26, (10, 30, 60))
        disc(cv, ex, ey + 4, 12, (5, 10, 25))
        disc(cv, ex - 12, ey - 12, 9, (255, 255, 255))
    # smile: a wide delighted arc
    for a in range(25, 156, 4):
        t = math.radians(a)
        x = int(cx + 62 * math.cos(t))
        y = int(cy + 58 + 34 * math.sin(t))
        disc(cv, x, y, 5, (60, 15, 90))
    # raised baton arm: a slim arm reaching up-right, baton tipped with light
    bezier_stroke(cv, (cx + 170, cy + 60), (cx + 300, cy - 30),
                  (cx + 360, cy - 170), 26, 6, VIOLET)
    bezier_stroke(cv, (cx + 170, cy + 60), (cx + 300, cy - 30),
                  (cx + 360, cy - 170), 17, 4, VIOLET_LT)
    bx, by = cx + 360, cy - 170
    thick_line(cv, bx, by, bx + 80, by - 45, 5, (255, 240, 180))
    glow(cv, bx + 80, by - 45, 55, GOLD, 0.9)
    disc(cv, bx + 80, by - 45, 10, (255, 245, 210))
    # sparkle burst at the baton tip
    for k in range(8):
        a = k * math.pi / 4 + 0.3
        thick_line(cv, bx + 80, by - 45,
                   int(bx + 80 + 42 * math.cos(a)),
                   int(by - 45 + 42 * math.sin(a)), 3, GOLD, alpha=0.85)


# -------------------------------------------------------------------- font
# 5x7 bitmap glyphs, only the letters this entry's titles need.
GLYPHS = {
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    ",": (".....", ".....", ".....", ".....", ".....", ".0100", ".1000"),
    "!": ("00100", "00100", "00100", "00100", "00100", ".....", "00100"),
}


def draw_text(cv, text, cx, y, scale, c, glow_c=None):
    """Centre text on cx at height y, bitmap font, optional halo."""
    step = 6 * scale
    total = len(text) * step - scale
    x = cx - total // 2
    if glow_c is not None:
        glow(cv, cx, y + 3 * scale, total // 2 + 20, glow_c, 0.35)
    for ch in text:
        g = GLYPHS.get(ch)
        if g is not None:
            for row, bits in enumerate(g):
                for col, b in enumerate(bits):
                    if b == "1":
                        for dy in range(scale):
                            cv.hline(x + col * scale, x + col * scale + scale - 1,
                                     y + row * scale + dy, c)
        x += step


def seafloor(cv):
    """Dark mound along the bottom with a few glowing corals."""
    pts = [(0, H), (0, 985), (120, 962), (300, 978), (470, 950),
           (640, 972), (820, 955), (1024, 980), (1024, H)]
    polygon(cv, pts, (6, 20, 44))
    for (x, y, r, c) in [(90, 968, 14, PINK), (210, 972, 10, CYAN),
                         (760, 962, 12, GOLD), (930, 970, 15, TEAL),
                         (520, 958, 9, PINK)]:
        glow(cv, x, y, r * 3, c, 0.5)
        disc(cv, x, y, r, c, alpha=0.9)
        disc(cv, x - r // 3, y - r // 3, max(1, r // 3), (255, 255, 255),
             alpha=0.8)


# -------------------------------------------------------------------- main
def main():
    cv = Canvas(W, H)
    vgrad(cv, DEEP_TOP, DEEP_BOT)
    # deep radial glow behind the conductor
    glow(cv, 512, 420, 480, (30, 60, 160), 0.5)
    light_rays(cv)
    plankton(cv)
    seafloor(cv)
    # the jellyfish orchestra, in an arc below the conductor
    jellyfish(cv, 168, 838, 56, CYAN, 0.4)
    jellyfish(cv, 356, 884, 68, PINK, 1.3)
    jellyfish(cv, 512, 908, 62, (255, 150, 120), 2.1)
    jellyfish(cv, 668, 884, 68, GOLD, 2.9)
    jellyfish(cv, 856, 838, 56, TEAL, 3.7)
    # music drifting up from the orchestra
    music_note(cv, 300, 620, 16, GOLD)
    music_note(cv, 726, 600, 14, PINK)
    music_note(cv, 452, 540, 12, CYAN)
    music_note(cv, 830, 660, 13, (255, 255, 255))
    music_note(cv, 196, 580, 12, TEAL)
    octopus(cv)
    bubbles(cv)
    # titles, clear of the octopus (its head starts near y=140)
    draw_text(cv, "THE CONDUCTOR OF THE DEEP", 512, 26, 3, (255, 225, 140),
              glow_c=GOLD)
    draw_text(cv, "JUDGE, FEEL THE MUSIC!", 512, 62, 2, (150, 230, 255),
              glow_c=CYAN)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(cv, path)
    print(f"wrote {path}: {W}x{H}, {size} bytes")


if __name__ == "__main__":
    main()
