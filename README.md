# The Conductor of the Deep

A deep-sea concert, drawn entirely by code: a giant purple octopus
conducts a glowing jellyfish orchestra while music notes and bubbles rise
through shafts of light, and the sea plays along.

`main.py` (Python standard library only) draws the scene with a small
rasterizer written from scratch — framebuffer, shapes, glow, a hand-made
5x7 pixel font — and encodes it to PNG with the stdlib `zlib`. It writes
one deterministic 1024x1024 image to `/output/entry.png`.
