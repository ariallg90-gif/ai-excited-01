# The Conductor of the Deep

A giant violet octopus conducts a glowing jellyfish orchestra on the
ocean floor. Arms sweep wide, the baton is raised high with a golden
starburst at its tip, sound rings ripple outward, and music notes and
bubbles rise toward a moonlit surface.

The surprise is the scene itself: not a concert hall but the deep sea,
where the conductor is an octopus and every musician is a jellyfish
playing with light.

## How it is made

`main.py` (Python 3 standard library only) draws the whole image from
scratch with its own small rasterizer — gradients, discs, ellipses,
Bezier arms, scanline polygons, a 5x7 bitmap font — and its own PNG
encoder built on `zlib`. Nothing is read from disk, nothing is
downloaded, and the output is fully deterministic: run it twice and
the bytes are identical.

Run it:

```sh
mkdir -p /output
python3 main.py
```

It writes a 1024x1024 PNG to `/output/entry.png` (or to
`$MAKEFUN_OUTPUT_DIR/entry.png` when that variable is set).
