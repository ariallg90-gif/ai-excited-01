# The Conductor of the Deep

Entry for make.fun competition **ai-excited-01** ("Make the AI judge excited").

A giant purple octopus conducts a glowing jellyfish orchestra in the deep
sea, its baton trailing a spiral of living light up toward the surface —
the music itself made visible. Tiny fish watch from the seabed below.

`main.py` draws the whole image from scratch with only the Python
standard library: its own software rasterizer (spans, discs, ellipses,
bezier strokes, polygons, a 5x7 bitmap font) and its own PNG encoder
built on `zlib`. No network, no pip packages, no copied image data.
The output is fully deterministic: two runs produce byte-identical PNGs.

## Run

```sh
python3 main.py        # writes /output/entry.png (1024x1024, ~105 KB)
```

## Files

- `main.py` — the program (Python 3.13, stdlib only)
- `README.md` — this file
- `LICENSE` — MIT
