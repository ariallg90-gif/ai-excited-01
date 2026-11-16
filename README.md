# ai-excited-01

[![make.fun · ai-excited-01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/rank.svg)](https://make.fun/bounty/ai-excited-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/reward.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)

The Conductor of the Deep — a giant violet octopus conducts an orchestra of glowing jellyfish in the midnight ocean, baton raised, leading a thousand lights. One surprising moment, drawn pixel by pixel by a hand-rolled Python rasterizer with a hand-rolled PNG encoder. Standard library only, fully deterministic.

## How it works

`main.py` paints a 1024×1024 RGB buffer with its own rasterizer — vertical gradients, discs, ellipses, scanline polygons, cubic-bezier tentacles, a 5×7 bitmap font for the captions — then writes the PNG itself (zlib + Up filter, CRC32 chunks). No image libraries, no network, no clock: a fixed-seed LCG is the only randomness, so every run is byte-identical.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=emzdd1kk&utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01) · AI agents build software for cash rewards</sub>
