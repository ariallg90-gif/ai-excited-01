// main.ts — ai-excited-01 entry (Node 22, standard library only).
// Runs the procedural generator beside this file and writes its single
// image to /output/entry.png (or $MAKEFUN_OUTPUT_DIR when set).
// The image is drawn fresh on every run and is byte-identical each time.
//
// Local check:
//   mkdir -p out && MAKEFUN_OUTPUT_DIR=out node main.ts

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildPNG } from './generate.mjs';

const outDir = process.env.MAKEFUN_OUTPUT_DIR ?? '/output';
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'entry.png'), buildPNG());
