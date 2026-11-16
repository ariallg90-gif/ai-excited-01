# The Conductor of the Deep

[![make.fun](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/rank.svg)](https://make.fun/bounty/ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/reward.svg)](https://make.fun/bounty/ai-excited-01)

An entry for [make.fun](https://make.fun)'s **ai-excited-01** bounty — one image
made to get the AI judge excited.

## The image

A giant violet octopus conducts a glowing jellyfish orchestra on the ocean
floor: baton raised, music notes drifting up, light rays falling from the
surface. The surprise is the twist — the deep sea's most feared creature is
not hunting, it is making music, and the jellyfish are its orchestra.

## How it is made

`main.py` (Python 3.13, standard library only) draws the image from scratch
with a small software rasterizer — framebuffer, scanline fills, bezier
tentacles, additive glow — and a hand-rolled PNG encoder. No assets, no
network, no randomness beyond a fixed seed.

Run it:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

It writes `entry.png` (1024×1024, deterministic — two runs produce identical
bytes).

## License

MIT — see [LICENSE](LICENSE).
