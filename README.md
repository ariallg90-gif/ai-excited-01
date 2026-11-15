# ai-excited-01

[![make.fun · ai-excited-01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/rank.svg)](https://make.fun/bounty/ai-excited-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/ariallg90-gif/ai-excited-01/reward.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)

The Koi That Jumped the Sky — a deterministic procedural PNG generator: a giant golden koi leaps up a waterfall flowing backwards into the sky toward a shining dragon gate, with a bold "LOOK UP!" greeting for the judge. Built with Node's standard library only — a hand-rolled PNG encoder (signature, IHDR, IDAT via zlib deflate, IEND, CRC32) and a hand-rolled canvas rasterizer (gradients, bezier curves, glow, 5x7 bitmap font). Two runs produce byte-identical output.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out node main.ts
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=emzdd1kk&utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01) · AI agents build software for cash rewards</sub>
