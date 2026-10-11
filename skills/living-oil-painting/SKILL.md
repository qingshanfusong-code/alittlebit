---
name: living-oil-painting
description: >-
  Turn any oil painting into a '细腻 + 会动' living painting like the popular Douyin 名画画框穿越 edits
  (墨尔温 Van Gogh《星月夜》《向日葵》style): AI-repaint look (super-resolution, smooth creamy impasto
  strokes, soft 3D paint highlights, luminous palette) plus seamless-loop motion that follows the
  artist's own brushstrokes — skies and swirls flow, moons and stars spin, trees and flowers sway,
  water ripples, lights twinkle. Also includes the full 画框穿越 template (painting-in-painting, pull back
  to a framed painting on a coloured wall, whip-pan to the next frame with out-of-frame pop, cut-out
  collage + title, 96 BPM beat grid and an original score). Use whenever the user sends a painting and
  wants it 变细腻/高清/动起来/活起来/做成动态油画/让画动, wants a living-painting loop, or wants a
  名画/油画/画框穿越/画中画 short video in this style.
---

# 油画活化（细腻化 + 动起来）

Two deliverables, often both:
1. **活化画面** – a seamless loop (mp4) of one painting, enhanced and moving.
2. **画框穿越成片** – the 15 s template edit (`templates/frame_dive/`), whose paintings can be the loops from (1).

First run: `python3 scripts/setup.py` (deps + EDSR models into `scripts/models/`; `--fonts` for the template).
Needs python3, numpy, pillow, scipy, opencv-contrib-python-headless, ffmpeg.

## The style (learned from the references — read `references/style.md` for the measurements)
- **细腻**: strokes are clean, smooth, creamy ribbons of thick paint; no JPEG noise or canvas grain; every
  stroke has a soft highlight (impasto); high-key palette, creamy whites, cool shadows that keep deep colour.
- **Motion lives in the paint, not the picture**: after removing camera motion, the sky keeps flowing along
  the swirls (~15–20 px per 0.25 s at 1080p), the moon spins, flowers sway. Buildings, faces, bodies stay still.
- **Loops**: everything periodic so the clip (and the edit) can loop.

## Workflow

### 1. Look at the painting
Read the image. Note: what can plausibly move (sky, clouds, water, smoke, foliage, grass, hair, fabric,
light sources) and what must stay rigid (architecture, faces, hands, still life objects). Note the dominant
stroke directions and any swirls/centres. Make a gridded view to read coordinates:
```bash
python3 -c "from PIL import Image,ImageDraw;im=Image.open('in.jpg').convert('RGB');w,h=im.size;d=ImageDraw.Draw(im)
[d.line([(w*i//10,0),(w*i//10,h)],fill=(255,0,0)) or d.line([(0,h*i//10),(w,h*i//10)],fill=(255,0,0)) for i in range(1,10)];im.save('grid.jpg')"
```
Ask the user only if the intent is unclear (which parts should move); otherwise decide and state it.

### 2. Enhance (细腻化)
```bash
python3 scripts/livepaint.py enhance in.jpg work/enh.png --long 2560 --preset luminous   # or natural
```
- `--preset luminous` = the reference look (high-key, creamy, cool shadows). `natural` keeps the original palette.
- `--lic` (stroke smoothing, default 1.0; 1.3–1.6 for very noisy/low-res sources; 0.5 for fine detailed work),
  `--relief` (impasto, default 1.0; 0.5 for smooth classical paintings, 1.3 for Van Gogh-like impasto),
  `--denoise` (JPEG cleanup, default 4; 6–8 for heavily compressed images).
- Super-resolution result is cached as `work/enh_sr.png`, so re-tuning the look takes seconds.
- Compare a crop before/after (read both) — fix pits/plastic highlights by lowering `--relief`, mush by lowering `--lic`.

### 3. Write the motion spec
JSON, coordinates normalised 0–1 (x right, y down). Start from `examples/starry_night.json`.
Full parameter reference and recipes per subject: `references/motion-spec.md`. Layer types:
| type | use | key params |
|---|---|---|
| `flow` | sky, clouds, water currents, smoke, swirls, hair — texture slides along its own strokes | `speed` px/s @1920w (sky 25–40, water 15–25, smoke 10–20), `period` 1–1.5 s, `guides` (dir / vortex) choose the direction |
| `sway` | trees, flowers, grass, cypress, sails | `amp` px, `period` 2–4 s, `anchor_y` (base), `height` |
| `ripple` | lake/sea surface shimmer | `amp`, `wavelength`, `period` |
| `breathe` | very subtle scale pulse of a region | `amp` 0.003–0.008 |
| `twinkle` | stars, lamps, candles, glints | `threshold` (luma), `amp`, `glow`, `color` (BGR) |
Regions: `{"polys": [[[x,y],...]]}`, `{"circle": [cx, cy, r]}`, `{"all": true}`, optional `not_polys` to
exclude rigid things (e.g. a tree inside the sky polygon), `feather`.
Check the direction field before rendering:
```bash
python3 scripts/livepaint.py field work/enh.png spec.json work/field.jpg --layer 0
```

### 4. Render the loop
```bash
python3 scripts/livepaint.py animate work/enh.png spec.json out/alive.mp4 --width 1920 --seconds 6
```
~0.15 s per 1080p frame. `loop` in the spec (default 4–6 s) must be a multiple of every layer period
(the code rounds periods to divide it). Verify:
- `python3 scripts/localmotion.py f1.png f2.png lm.jpg` on two frames 0.25 s apart → motion should sit only
  in the intended regions; mean residual ~2–5 px at 960 px width is the reference range.
- Strip of frames: smearing/“liquid marble” means `speed*period` too large → lower speed or period.
- Loop seam: last-vs-first frame difference ≈ consecutive-frame difference.

### 5. (Optional) the 画框穿越 edit
`templates/frame_dive/` (see its README section in `references/frame-dive.md`): `render.py` = choreography
(T_* constants are the cut points on a 96 BPM grid: pull-back 4.05 s, pan 6.42 s, fly-off 8.98 s, title 10.42 s,
loop 14.43 s), `assets.py` = procedural carved frames + cut-out, `music.py` = original score on the reference
beat grid (hit 1.75 s, full stop 1.9–3.0 s, drop 4.25 s). Swap in the user's paintings and title; to use living
paintings, render the loop first and feed frame `t % loop` as the painting texture each frame.

## Delivering
Give the mp4, a before/after crop, and in Chinese: 细腻化做了什么, 哪些区域在动/怎么动, 可调的参数.
Video files over ~30 MB: also give a compressed preview (`-crf 23`).

## Honest limits
This is algorithmic, not a diffusion/video model: it cannot invent new detail or move bodies/faces
convincingly. Keep people and architecture static; let paint, sky, water, plants and light carry the motion.
Very small sources (< 600 px) stay soft even after EDSR.

## Copyright
Painters dead > 50 years are public domain in mainland China (life + 50); EU/US are life + 70 / publication
based — mention it when the user may post abroad.
