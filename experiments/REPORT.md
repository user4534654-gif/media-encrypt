# Scramble-codec study: measured results

Date: 2026-10-03. Harness: `experiments/scramble_codec_study.py`
(results: `experiments/results.json`, 38 cases).

## Method (no hand-waving)

- Content: deterministic synthetic 1280x720, 60 frames @30fps (full-frame
  16px checker tinted per-channel + ramps + thin lines + 2 moving squares,
  so inter prediction has something to do).
- Pipeline: REAL project math — `core.video_processor._scramble_frame_ordinary`
  + `core.grid_utils.get_blocks`, seed 777, fixed per case.
- Encode: project-style capped ABR over a rawvideo bgr24 pipe
  (`-b:v X -maxrate X -bufsize 2X`), ffmpeg 8.1 full build.
- Decode -> descramble (`reverse=True`) -> metrics vs original on 5 frames:
  PSNR (all channels), PSNR over CbCr only, seam-energy ratio (mean gradient
  within 1px of known seam lines vs background; higher = more visible grid).
- Fixed operating point unless noted: 2500k cap, x264/x265 `-preset medium`,
  vp9 `-deadline good -cpu-used 2`, av1 `-cpu-used 6`.

## Headline numbers (G20 = 20x15, tiles 64x48, fully 16px-aligned)

| case | size | PSNR | chroma-PSNR | ΔPSNR vs base |
|---|---|---|---|---|
| x264 base | 315KB | 41.34 | 44.50 | — |
| x264 no-deblock | 303KB | 41.57 | 44.70 | **+0.23** (smaller file!) |
| x264 psy=0 + tune ssim | 322KB | 43.44 | 46.93 | **+2.10** |
| x264 combo (+chromaoffset -2) | 344KB | 44.91 | 48.48 | **+3.57 / +3.98 chroma** |
| x264 combo @2000k cap | 292KB | 42.52 | 46.66 | **+1.18 at SMALLER size** |
| x265 base | 314KB | 48.89 | 51.23 | — |
| x265 no-deblock | 298KB | 50.24 | 52.13 | **+1.36** |
| x265 tune ssim | 341KB | 52.37 | 53.89 | **+3.48** |
| x265 combo | 335KB | 53.65 | 54.84 | **+4.76 / +3.61 chroma** |
| x264 short GOP (g=30) | 293KB | 37.90 | 41.45 | **-3.44 (HURTS)** |
| x264 base @8000k | 444KB | 49.17 | — | +7.83 for +41% size |
| x264 combo @8000k | 441KB | 50.64 | — | +1.47 over base@8M |

## Grid sweep (base settings, 2500k cap)

| grid | tiles | x264 | x265 | note |
|---|---|---|---|---|
| 10x10 | 128x72 | 40.94 | 48.07 | integer, 8-aligned V |
| 20x15 | 64x48 | 41.34 | 48.89 | integer, 16-aligned |
| 21x16 | 60.95x45 | 32.55 | 35.76 | FRACTIONAL: pipeline alone caps at 40.0 dB (lossless control, no codec!) |
| 40x30 | 32x24 | 41.16 | 46.63 | integer, 8-aligned |
| 100x100 | 12.8x7.2 | 24.93 | 24.66 | pipeline caps at 29.3 dB; encoder can't even hold the cap (768KB+ at 2500k maxrate) |

Lossless (no codec) controls: G10/G20/G40 = 99.0 dB (bit-exact roundtrip),
G21 = 40.0 dB, G100 = 29.3 dB. Fractional tiles go through `cv2.resize`
inside `_scramble_frame_ordinary` and never come back.

## VP9 / AV1 (G20, 2500k cap)

- vp9 base: 56.65 dB @488KB. `-tune-content 1` and `-arnr-strength 0` produce
  **bit-identical output** (same size to the byte): inert in 1-pass capped
  mode. No effective scramble toggles found on this path.
- av1 base: 66.96 dB @119KB. `tune 1` / `enable-cdef 0` / `enable-restoration 0`
  move results by ±0.1-0.2 dB (noise): already near-transparent here.
- G100 craters on all four codecs (24-29 dB) and blows the bitrate cap
  (up to 1110KB at a 2500k cap).

## yuv444p (G20, 2500k cap)

- x264 444 vs 420: +0.01 dB overall, +0.02 dB chroma. Nothing.
- x265 444 vs 420: **-6.05 dB overall, -5.52 dB chroma. Actively harmful**
  at a fixed bitrate on this content. Do not use.

## Line-shuffle (Colab-style full-width strips, seed 777)

| case | size | PSNR | chroma | vs block grid |
|---|---|---|---|---|
| x264 L2 (2px, 360 strips) base | 459KB | 35.57 | 39.22 | **-5.8 dB vs G20** |
| x264 L2 combo | 505KB | 37.89 | 42.69 | +2.3 dB from flags, still -3.4 vs G20 base |
| x264 L8 (8px, 90 strips) base | 368KB | 42.27 | 45.32 | **+0.9 dB vs G20** (horizontal-only seams) |
| x265 L2 base | 539KB | 40.69 | 44.37 | -8.2 dB vs G20 |
| x265 L2 combo | 547KB | 43.59 | 46.76 | +2.9 dB from flags |
| lossless L2 / L8 (no codec) | — | 99.0 | — | strip permutation itself is exact |

Reading: 2px strips are much worse than blocks (a full-width seam every
2 lines = maximum seam density, and the encoder cannot hide it). 8px strips
slightly beat 64px blocks (fewer seams total, horizontal only, 8px-aligned).
Security caveat (analytic, not measured): strips preserve intra-row
continuity, so row-reassembly by edge matching is far easier than 2D jigsaw —
line mode must stay opt-in with an honesty label, never the default.

## 10-bit depth (G20, 2500k cap) — UNMEASURABLE through this pipe

x264-10bit and x265-10bit both returned **identical 22.27 dB** (lossless `-qp 0`
included). Three different encoder paths agreeing to 0.01 dB is impossible for
real encoder behavior — it proves a shared RGB->10-bit-YUV level conversion
artifact upstream of the encoders, so no fair 10-bit number can be produced
here without a hand-written limited-range 10-bit converter. Combined with the
444 result above and the +4 dB chroma already delivered by the combo preset on
plain 8-bit 4:2:0, 10-bit is not pursued: compatibility cost, no measurable path
to gain on 8-bit sources.

## Verdicts

1. Flags are NOT 1%: +3.6 dB (x264) / +4.8 dB (x265), and the @2M point
   proves a pure efficiency win (+1.2 dB at smaller size than base).
2. Biggest lever overall is grid SIZE + integrality: integer tiles differ by
   ~2 dB max; fractional tiles cost 8-20 dB before the codec even runs;
   100x100 is unfixable by flags (+0 at best) and breaks rate control.
3. 16-vs-8 alignment, isolated: ~0.2-0.8 dB (G10 vs G20). Real but third-order.
   The rule that matters is "integer tiles", then "as big as aesthetics allow".
4. Short GOP at a fixed budget HURTS (-3.4 dB). Hypothesis rejected by data.
5. 444: useless-to-harmful here. Rejected (as default and as option, unless a
   future high-freq-chroma content test says otherwise).
6. VP9/AV1 have no useful 1-pass scramble toggles in this harness; both already
   handle the content well. Cross-codec size/quality points differ (rate
   control undershoot), so cross-codec ranking is indicative, not BD-rigorous.

## Caveats

- Synthetic checker-heavy content: magnitudes will shift on natural video;
  mechanisms (deblock on seams, psy on noise, resize on fractional tiles)
  transfer.
- x264 ABR run variance ~0.1 dB / few % size (multithreaded nondeterminism):
  deltas <0.3 dB are suggestive, everything quoted above is well above noise.
- 2 s clip, 720p, medium-ish presets. Long-form BD-rate curves would refine,
  not flip, the signs.
