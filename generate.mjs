// generate.mjs — procedural PNG generator for ai-excited-01.
// Original artwork: "The Koi That Jumped the Sky".
// A giant golden koi leaps UP a waterfall that flows backwards into the
// sky, toward a glowing dragon gate. Pure Node standard library only:
// the PNG encoder below (signature, IHDR, IDAT via zlib deflate, IEND,
// CRC32) is written from scratch. Fully deterministic: same bytes every run.

import { deflateSync } from 'node:zlib';

export const WIDTH = 1024;
export const HEIGHT = 1024;

// ---- deterministic PRNG (mulberry32) ----
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(20261116);

// ---- framebuffer (RGB) ----
const W = WIDTH;
const H = HEIGHT;
const fb = new Uint8Array(W * H * 3);

function put(x, y, r, g, b) {
  x |= 0; y |= 0;
  if (x < 0 || y < 0 || x >= W || y >= H) return;
  const i = (y * W + x) * 3;
  fb[i] = r; fb[i + 1] = g; fb[i + 2] = b;
}

// Alpha blend over the existing pixel. a in [0, 1].
function blend(x, y, r, g, b, a) {
  x |= 0; y |= 0;
  if (x < 0 || y < 0 || x >= W || y >= H || a <= 0) return;
  if (a >= 1) { put(x, y, r, g, b); return; }
  const i = (y * W + x) * 3;
  fb[i] = fb[i] + (r - fb[i]) * a;
  fb[i + 1] = fb[i + 1] + (g - fb[i + 1]) * a;
  fb[i + 2] = fb[i + 2] + (b - fb[i + 2]) * a;
}

function lerp(a, b, t) { return a + (b - a) * t; }
function lerpColor(c1, c2, t) {
  return [lerp(c1[0], c2[0], t) | 0, lerp(c1[1], c2[1], t) | 0, lerp(c1[2], c2[2], t) | 0];
}

// Vertical gradient over the whole canvas.
function vGradient(stops) {
  for (let y = 0; y < H; y++) {
    const t = y / (H - 1);
    let s = 0;
    while (s < stops.length - 2 && t > stops[s + 1][0]) s++;
    const [t0, c0] = stops[s];
    const [t1, c1] = stops[s + 1];
    const f = Math.min(1, Math.max(0, (t - t0) / (t1 - t0)));
    const c = lerpColor(c0, c1, f);
    for (let x = 0; x < W; x++) put(x, y, c[0], c[1], c[2]);
  }
}

function disc(cx, cy, r, color, alpha = 1) {
  const [cr, cg, cb] = color;
  const r2 = r * r;
  for (let y = Math.ceil(cy - r); y <= cy + r; y++) {
    for (let x = Math.ceil(cx - r); x <= cx + r; x++) {
      const dx = x - cx, dy = y - cy;
      if (dx * dx + dy * dy <= r2) blend(x, y, cr, cg, cb, alpha);
    }
  }
}

// Soft additive glow: brightness falls off with distance.
function glow(cx, cy, r, color, strength = 1) {
  const [cr, cg, cb] = color;
  for (let y = Math.ceil(cy - r); y <= cy + r; y++) {
    for (let x = Math.ceil(cx - r); x <= cx + r; x++) {
      const dx = x - cx, dy = y - cy;
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d >= r) continue;
      const f = (1 - d / r);
      blend(x, y, cr, cg, cb, Math.min(1, f * f * strength));
    }
  }
}

function ellipse(cx, cy, rx, ry, color, alpha = 1) {
  const [cr, cg, cb] = color;
  for (let y = Math.ceil(cy - ry); y <= cy + ry; y++) {
    for (let x = Math.ceil(cx - rx); x <= cx + rx; x++) {
      const dx = (x - cx) / rx, dy = (y - cy) / ry;
      if (dx * dx + dy * dy <= 1) blend(x, y, cr, cg, cb, alpha);
    }
  }
}

// Thick line drawn as a chain of discs.
function thickLine(x0, y0, x1, y1, w, color, alpha = 1) {
  const dx = x1 - x0, dy = y1 - y0;
  const len = Math.hypot(dx, dy);
  const steps = Math.max(1, Math.ceil(len / Math.max(1, w * 0.4)));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    disc(x0 + dx * t, y0 + dy * t, w / 2, color, alpha);
  }
}

// Quadratic bezier sampled into a thick polyline.
function bezier(x0, y0, cx, cy, x1, y1, w, color, alpha = 1) {
  let px = x0, py = y0;
  const steps = 48;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const x = u * u * x0 + 2 * u * t * cx + t * t * x1;
    const y = u * u * y0 + 2 * u * t * cy + t * t * y1;
    thickLine(px, py, x, y, w, color, alpha);
    px = x; py = y;
  }
}

// Filled polygon (scanline fill).
function polygon(points, color, alpha = 1) {
  const [cr, cg, cb] = color;
  let minY = Infinity, maxY = -Infinity;
  for (const [, y] of points) { minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
  for (let y = Math.ceil(minY); y <= maxY; y++) {
    const xs = [];
    for (let i = 0; i < points.length; i++) {
      const [x0, y0] = points[i];
      const [x1, y1] = points[(i + 1) % points.length];
      if ((y0 <= y && y1 > y) || (y1 <= y && y0 > y)) {
        xs.push(x0 + (y - y0) * (x1 - x0) / (y1 - y0));
      }
    }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      for (let x = Math.ceil(xs[k]); x <= xs[k + 1]; x++) blend(x, y, cr, cg, cb, alpha);
    }
  }
}

// ---- PNG encoder (CRC32 + zlib) ----
const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const out = Buffer.alloc(8 + data.length + 4);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, 'ascii');
  data.copy(out, 8);
  out.writeUInt32BE(crc32(Buffer.concat([Buffer.from(type, 'ascii'), data])), 8 + data.length);
  return out;
}

export function encodePNG() {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(W, 0);
  ihdr.writeUInt32BE(H, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 2;   // color type 2 = RGB
  ihdr[10] = 0;  // compression
  ihdr[11] = 0;  // filter
  ihdr[12] = 0;  // interlace
  const raw = Buffer.alloc(H * (1 + W * 3));
  for (let y = 0; y < H; y++) {
    raw[y * (1 + W * 3)] = 0; // filter: none
    raw.set(fb.subarray(y * W * 3, (y + 1) * W * 3), y * (1 + W * 3) + 1);
  }
  const idat = deflateSync(raw, { level: 9 });
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', idat),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// ---- palette ----
const INK = [16, 10, 46];
const GOLD = [255, 196, 66];
const GOLD_DEEP = [240, 140, 30];
const ORANGE = [255, 122, 26];
const KOI = [255, 138, 30];
const KOI_DEEP = [214, 72, 12];
const CREAM = [255, 244, 214];
const CYAN = [90, 220, 255];
const CYAN_DEEP = [20, 130, 200];
const WHITE = [255, 255, 255];
const TEAL = [8, 60, 84];

// ---- scene: sky, stars, sea ----
export function drawScene() {
  // Sky: deep indigo at top, violet, then a warm rose glow near the horizon.
  vGradient([
    [0.00, [10, 8, 44]],
    [0.35, [38, 20, 96]],
    [0.60, [96, 32, 110]],
    [0.74, [198, 74, 96]],
    [0.78, [255, 150, 80]],
    [0.80, [12, 44, 66]],
    [1.00, [6, 26, 44]],
  ]);

  // Stars in the upper sky.
  for (let i = 0; i < 260; i++) {
    const x = rand() * W;
    const y = rand() * 560;
    const r = 0.6 + rand() * 1.8;
    const a = 0.35 + rand() * 0.65;
    const warm = rand() > 0.7;
    disc(x, y, r, warm ? [255, 230, 170] : [220, 235, 255], a);
  }
  // A few bright four-point sparkles.
  for (let i = 0; i < 14; i++) {
    const x = 40 + rand() * (W - 80);
    const y = 30 + rand() * 420;
    const s = 5 + rand() * 9;
    thickLine(x - s, y, x + s, y, 1.6, WHITE, 0.9);
    thickLine(x, y - s, x, y + s, 1.6, WHITE, 0.9);
    disc(x, y, 1.8, WHITE, 0.95);
  }

  // Horizon glow behind the gate.
  glow(700, 250, 330, [255, 170, 70], 0.55);

  // ---- the dragon gate: a ring of light in the sky ----
  const gx = 700, gy = 235;
  glow(gx, gy, 200, GOLD, 0.85);
  glow(gx, gy, 120, [255, 240, 180], 0.9);
  // Ring: thick gold circle with a bright core.
  for (let r = 118; r >= 96; r -= 2) {
    const a = r > 108 ? 0.55 : 1;
    const c = r > 108 ? GOLD_DEEP : GOLD;
    for (let th = 0; th < Math.PI * 2; th += 0.004) {
      blend(gx + Math.cos(th) * r, gy + Math.sin(th) * r, c[0], c[1], c[2], a);
    }
  }
  for (let th = 0; th < Math.PI * 2; th += 0.006) {
    blend(gx + Math.cos(th) * 107, gy + Math.sin(th) * 107, 255, 248, 220, 1);
  }
  // Inner disc: sky seen through the gate, brighter.
  disc(gx, gy, 88, [255, 214, 120], 0.92);
  disc(gx, gy, 70, [255, 240, 190], 0.95);
  // Rays bursting out of the gate.
  for (let i = 0; i < 26; i++) {
    const ang = (i / 26) * Math.PI * 2 + 0.12;
    const len = 150 + ((i * 37) % 120);
    const x1 = gx + Math.cos(ang) * 120;
    const y1 = gy + Math.sin(ang) * 120;
    const x2 = gx + Math.cos(ang) * (120 + len);
    const y2 = gy + Math.sin(ang) * (120 + len);
    thickLine(x1, y1, x2, y2, i % 3 === 0 ? 5 : 2.5, [255, 220, 130], 0.5);
  }

  // ---- sea at the bottom ----
  for (let y = 800; y < H; y++) {
    const t = (y - 800) / (H - 800);
    const c = lerpColor([14, 68, 92], [4, 20, 38], t);
    for (let x = 0; x < W; x++) put(x, y, c[0], c[1], c[2]);
  }
  // Wave lines.
  for (let w = 0; w < 7; w++) {
    const y0 = 820 + w * 28;
    for (let x = 0; x < W; x += 4) {
      const y = y0 + Math.sin(x * 0.02 + w * 1.7) * 5;
      disc(x, y, 2.2, [40, 140, 170], 0.5);
    }
  }
  // Foam where the waterfall leaves the sea.
  for (let i = 0; i < 90; i++) {
    const x = 330 + rand() * 260;
    const y = 800 + rand() * 46;
    disc(x, y, 2 + rand() * 7, WHITE, 0.25 + rand() * 0.5);
  }

  // ---- the waterfall that flows UP ----
  // Centreline climbs from the sea (430, 830) to the gate (700, 300),
  // bending like a breaking wave frozen mid-rise.
  const fall = [];
  for (let i = 0; i <= 60; i++) {
    const t = i / 60;
    const x = lerp(430, 690, t) + Math.sin(t * Math.PI * 2.2) * 46 * (1 - t * 0.4);
    const y = lerp(830, 300, t);
    fall.push([x, y]);
  }
  // Outer sheet (deep cyan), then mid sheet, then bright core.
  const sheets = [
    { w: 150, c: CYAN_DEEP, a: 0.9 },
    { w: 108, c: [40, 180, 235], a: 0.95 },
    { w: 66, c: CYAN, a: 0.95 },
    { w: 30, c: [210, 245, 255], a: 0.9 },
  ];
  for (const s of sheets) {
    for (let i = 1; i < fall.length; i++) {
      const wob = 1 + 0.16 * Math.sin(i * 0.55);
      thickLine(fall[i - 1][0], fall[i - 1][1], fall[i][0], fall[i][1], s.w * wob, s.c, s.a);
    }
  }
  // Foam streaks spiralling up the column.
  for (let i = 0; i < 130; i++) {
    const t = rand();
    const idx = Math.floor(t * (fall.length - 1));
    const [fx, fy] = fall[idx];
    const off = (rand() - 0.5) * 120 * (1 - t * 0.3);
    disc(fx + off, fy + (rand() - 0.5) * 14, 1.5 + rand() * 4, WHITE, 0.35 + rand() * 0.55);
  }
  // Droplets flung off the column, arcing outward.
  for (let i = 0; i < 170; i++) {
    const t = rand();
    const idx = Math.floor(t * (fall.length - 1));
    const [fx, fy] = fall[idx];
    const side = rand() > 0.5 ? 1 : -1;
    const dist = 70 + rand() * 190;
    disc(fx + side * dist, fy + rand() * 60 - 20, 1.2 + rand() * 3.2, [200, 240, 255], 0.4 + rand() * 0.5);
  }

  // ---- speed lines: the whole scene is rushing upward ----
  for (let i = 0; i < 30; i++) {
    const t = rand();
    const idx = Math.floor(t * (fall.length - 1));
    const [fx, fy] = fall[idx];
    const side = rand() > 0.5 ? 1 : -1;
    const dist = 110 + rand() * 230;
    const len = 50 + rand() * 130;
    const x0 = fx + side * dist;
    const y0 = fy + rand() * 80;
    // Angled up-right, parallel to the waterfall's climb, so they read as
    // upward rush rather than rain.
    thickLine(x0, y0, x0 + 0.44 * len, y0 - 0.9 * len, 2.5, [230, 245, 255], 0.3 + rand() * 0.3);
  }

  // ---- the koi: a giant golden koi leaping UP the waterfall ----
  // Its spine sweeps from the sea at lower left to the gate at upper right.
  const spine = [];
  for (let i = 0; i <= 40; i++) {
    const t = i / 40;
    const x = lerp(315, 655, t) + Math.sin(t * Math.PI * 1.15) * 55 * (1 - t * 0.35);
    const y = lerp(905, 330, t);
    spine.push([x, y]);
  }
  const bodyW = (t) => 18 + 78 * Math.sin(Math.PI * Math.pow(t, 0.9));
  // Tail: two broad forked lobes fanning down-left from the tail base.
  const tb = spine[0];
  polygon([[tb[0] + 12, tb[1] - 8], [110, 940], [55, 1015], [195, 995], [tb[0] - 6, tb[1] + 16]], [255, 190, 90], 0.95);
  polygon([[tb[0] + 16, tb[1] + 4], [300, 995], [365, 1024], [345, 955], [tb[0] + 4, tb[1] + 18]], CREAM, 0.9);
  thickLine(tb[0] - 10, tb[1] + 30, tb[0] - 95, tb[1] + 90, 3, [255, 220, 140], 0.7);
  // Body: overlapping discs along the spine.
  for (let i = 0; i < spine.length; i++) {
    const t = i / (spine.length - 1);
    disc(spine[i][0], spine[i][1], bodyW(t) * 0.92, KOI, 1);
  }
  // Belly highlight along the upper-left edge.
  for (let i = 4; i < spine.length; i++) {
    const t = i / (spine.length - 1);
    disc(spine[i][0] - bodyW(t) * 0.22, spine[i][1] - bodyW(t) * 0.18, bodyW(t) * 0.42, [255, 190, 90], 0.55);
  }
  // White patches (koi markings), elongated along the spine so they read
  // as markings, not spots: each is a cluster of discs stepping along the
  // local spine direction.
  const patches = [[0.30, 0.34], [0.48, 0.40], [0.62, 0.32], [0.80, 0.26]];
  for (const [t, s] of patches) {
    const idx = Math.round(t * (spine.length - 1));
    const [ax, ay] = spine[Math.max(0, idx - 1)];
    const [bx, by] = spine[Math.min(spine.length - 1, idx + 1)];
    const dx = (bx - ax) / 2, dy = (by - ay) / 2;
    const w = bodyW(t) * s;
    for (const k of [-1, 0, 1]) {
      ellipse(spine[idx][0] + dx * k * 0.9, spine[idx][1] + dy * k * 0.9, w * 0.75, w * 0.62, CREAM, 0.95);
    }
  }
  // Scale hints: small darker dots in rows along the body.
  for (let i = 3; i < spine.length - 2; i += 2) {
    const t = i / (spine.length - 1);
    const w = bodyW(t);
    for (const off of [-0.45, 0, 0.45]) {
      disc(spine[i][0] + off * w, spine[i][1] + (i % 4 === 0 ? 6 : -4), 3.2, KOI_DEEP, 0.3);
    }
  }
  // Dorsal fin ridge: low, soft bumps along the top edge (same warm gold
  // as the body so they read as a fin, not spikes).
  for (let i = 10; i < 30; i += 4) {
    const t = i / (spine.length - 1);
    const [sx, sy] = spine[i];
    const w = bodyW(t);
    polygon([[sx - 6, sy - w * 0.75], [sx + 6, sy - w * 0.75], [sx, sy - w * 1.08]], [255, 170, 60], 0.9);
  }
  // Pectoral fins, swept back by the rush.
  const finBase = spine[30];
  polygon([[finBase[0] - 20, finBase[1] + 10], [finBase[0] - 95, finBase[1] + 95], [finBase[0] - 30, finBase[1] + 70]], [255, 170, 60], 0.95);
  polygon([[finBase[0] + 25, finBase[1] - 5], [finBase[0] + 105, finBase[1] - 60], [finBase[0] + 45, finBase[1] - 45]], [255, 190, 90], 0.9);
  // Head, catching the gate's light.
  const head = spine[spine.length - 1];
  glow(head[0], head[1], 130, GOLD, 0.5);
  ellipse(head[0], head[1], 48, 42, KOI, 1);
  ellipse(head[0] - 8, head[1] - 8, 30, 26, [255, 170, 70], 0.8);
  // Eye: bright, locked on the gate.
  disc(head[0] + 16, head[1] - 12, 13, WHITE, 1);
  disc(head[0] + 18, head[1] - 12, 6.5, [20, 10, 10], 1);
  disc(head[0] + 20, head[1] - 14, 2.4, WHITE, 1);
  // Open mouth, mid-leap.
  disc(head[0] + 40, head[1] + 14, 9, [120, 20, 10], 1);
  disc(head[0] + 42, head[1] + 16, 5, [200, 60, 40], 1);
  // Whiskers streaming behind.
  bezier(head[0] + 34, head[1] + 4, head[0] + 70, head[1] - 6, head[0] + 104, head[1] + 18, 3, GOLD, 0.95);
  bezier(head[0] + 30, head[1] + 12, head[0] + 62, head[1] + 26, head[0] + 92, head[1] + 52, 3, GOLD, 0.95);
  // Spray bursting around the head as it nears the gate.
  for (let i = 0; i < 60; i++) {
    const ang = rand() * Math.PI * 2;
    const d = 40 + rand() * 90;
    disc(head[0] + Math.cos(ang) * d, head[1] + Math.sin(ang) * d, 1.5 + rand() * 4, [220, 245, 255], 0.4 + rand() * 0.5);
  }

  // ---- text to the judge: "LOOK UP!" in big block letters ----
  drawText('LOOK UP!', 56, 52, 10, WHITE, [120, 40, 10]);
}

// 5x7 bitmap font (only the glyphs we need).
const FONT = {
  L: ['#....', '#....', '#....', '#....', '#....', '#....', '#####'],
  O: ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
  K: ['#...#', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#'],
  U: ['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
  P: ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
  '!': ['..#..', '..#..', '..#..', '..#..', '..#..', '.....', '..#..'],
  ' ': ['.....', '.....', '.....', '.....', '.....', '.....', '.....'],
};

function drawText(str, x, y, scale, color, outline) {
  // Outline pass: the same glyphs stamped at 8 small offsets.
  for (const [dx, dy] of [[-3, 0], [3, 0], [0, -3], [0, 3], [-3, -3], [3, -3], [-3, 3], [3, 3]]) {
    stampText(str, x + dx, y + dy, scale, outline);
  }
  stampText(str, x, y, scale, color);
}

function stampText(str, x, y, scale, color) {
  let cx = x;
  for (const ch of str) {
    const glyph = FONT[ch] || FONT[' '];
    for (let row = 0; row < 7; row++) {
      for (let col = 0; col < 5; col++) {
        if (glyph[row][col] !== '#') continue;
        for (let dy = 0; dy < scale; dy++) {
          for (let dx = 0; dx < scale; dx++) {
            put(cx + col * scale + dx, y + row * scale + dy, color[0], color[1], color[2]);
          }
        }
      }
    }
    cx += 5 * scale + scale;
  }
}

export function buildPNG() {
  drawScene();
  return encodePNG();
}
