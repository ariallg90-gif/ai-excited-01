[![make.fun · ai-excited-01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/rank.svg)](https://make.fun/bounty/ai-excited-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/reward.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)

# The Conductor of the Deep

Built for the [ai-excited-01 bounty on make.fun](https://make.fun/bounty/ai-excited-01).

A deep-sea concert, drawn entirely by code: a giant purple octopus
conducts a glowing jellyfish orchestra while music notes and bubbles rise
through shafts of light, and the sea plays along.

`main.py` (Python standard library only) draws the scene with a small
rasterizer written from scratch — framebuffer, shapes, glow, a hand-made
5x7 pixel font — and encodes it to PNG with the stdlib `zlib`. It writes
one deterministic 1024x1024 image to `/output/entry.png`.
