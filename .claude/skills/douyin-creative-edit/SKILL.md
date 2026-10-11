---
name: douyin-creative-edit
description: >-
  Plan and actually render creative short-video edits in the style of popular Douyin/TikTok/小红书/视频号 edits —
  卡点混剪, 歌词排版/海报风 MV, 艺术海报/抽象画风, 韦斯安德森式窗框画中画, 慢门快闪, 剪影概念片, 胶片回忆, 国风水墨,
  运动燃剪 — in 9:16 竖屏 or 16:9 横屏. Chooses techniques from the video's topic, mood, music and footage instead of
  one fixed template, then builds the edit with a bundled ffmpeg/Python engine (beat detection, kinetic typography,
  masks, transitions, colour grades) or writes a 分镜脚本 + 剪映/CapCut steps. Use this skill whenever the user wants to
  剪辑/剪/做/混剪 a video, make a 卡点/踩点 edit, turn clips/photos + music into a short video, copy or learn an editing
  style from a reference video, plan a 分镜/剪辑方案 for a 选题, or asks for 抖音/TikTok/Reels/Shorts editing help —
  even if they only say "帮我把这些素材剪一下" or "这个选题怎么剪".
---

# 抖音创意剪辑 (douyin-creative-edit)

Turn a topic + footage + music into an edit that *means something*: the techniques are chosen because they say the
same thing as the content. The vocabulary comes from five reference edits the user loved (analysed frame by frame,
see `references/style-recipes.md`) plus derived recipes; the bundled engine renders them.

Two deliverables, often both:
1. **成片** — an mp4 rendered with `scripts/render.py` from a JSON edit spec.
2. **剪辑方案** — 剪辑思路 + 分镜表 (+ 剪映/CapCut steps or a shot list to film) when there is no footage yet, the
   user edits by hand, or rendering isn't possible.

Requirements for rendering: `python3` with `numpy` + `Pillow`, and `ffmpeg`/`ffprobe` on PATH. Check once
(`ffmpeg -version`, `python3 -c "import numpy, PIL"`); if missing, tell the user how to install
(`brew install ffmpeg` / `winget install ffmpeg` / `apt install ffmpeg`; `pip install numpy pillow`) or fall back to
the 剪辑方案 deliverable. Chinese text needs a CJK font on the machine (macOS/Windows have one).

## Workflow

### 0. Gather the brief (ask only what's missing, one short message)
选题/想表达什么 · 素材在哪 · 横屏还是竖屏 (default 9:16 for Douyin) · 时长 (default: fit the music section,
10–30 s) · 音乐 (file, or let them pick; you can't download copyrighted songs) · 参考视频 (optional) · 文字/歌词.
If the user already gave enough, don't ask — state your assumptions and proceed.

### 1. Look at everything before deciding
```bash
SK=<this skill's folder>/scripts
python3 $SK/probe_media.py <footage dirs/files> -o work/media.json --sheet work/media_sheet.png [--shots]
python3 $SK/beats.py music.mp3 -o work/music.beats.json [--start 30 --duration 20]
python3 $SK/analyze_reference.py ref.mp4 --out work/ref     # only if they sent a reference edit
```
Open the contact sheets (Read the PNGs) — you must actually see the footage to pick shots, focus points and
colours. Note BPM, beat length, energy segments and `drop` from `beats.py`. `--shots` splits long videos into usable
shots with their most active moments.

### 2. Decide the style（剪辑思路）
Read `references/topic-matching.md` and answer its five questions in a short block you show the user:
- 母题: the one idea + a visual motif that repeats and transforms
- 情绪 → 节奏档位 (shot lengths in beats per section), transitions, movement, grade
- backbone recipe from `references/style-recipes.md` + at most 2–3 borrowed signature moves (say *why* each one fits)
- orientation adaptations (safe area, layout)
- text: which words, which 1–2 typefaces
Different topics should produce visibly different edits. Avoid defaulting to the same recipe every time.
`references/techniques.md` has every technique with purpose, engine syntax and 剪映 steps.

### 3. 分镜表 (shot plan) mapped to the music
Write sections in beats: e.g. `b0–b4 hook | b4–b16 setup | b16–b24 build | b24–b32 drop burst | b32–b36 release/loop`.
For each: shots (which files, in-points), technique, text, transition into the next. The hook (first 1–2 s) gets the
strongest image and the key word.

### 4. Build the spec and look before you render
Write `work/edit.json` (format: `references/spec.md`; complete working examples in `examples/` — copy the closest
one and adapt rather than starting blank):

| example | style | canvas |
|---|---|---|
| `poster_typography.json` | A 海报歌词排版 (bg_swap, ghost words, font-flicker burst, loop) | 16:9 |
| `art_poster.json` | B 艺术海报 (group camera, staircase type, blocks, defocus) | 16:9 |
| `auteur_window_vertical.json` | C 导演美学 (window, porthole + strip, split, collage, chapter cards) | 9:16 |
| `slow_shutter.json` | D 慢门快闪 (triptych title, shutter + trails montage, print border) | 16:9 |
| `concept_silhouette_vertical.json` | E 概念剪影 (silhouettes, zoom_into, flip clock, inversions) | 9:16 |
| `film_memory_3x4.json` | F 胶片回忆 (dissolves, light leak, polaroid stack, typewriter dates) | 3:4 |
| `abstract_art_vertical.json` | G 抽象艺术 (footage in letters, mondrian, duotone/halftone/threshold) | 9:16 |
| `hype_speedramp_vertical.json` | H 运动燃剪 (whips, accelerating cuts, speed ramp → freeze + word, shake) | 9:16 |

They run on synthetic media: `python3 $SK/make_demo_media.py work/demo` then
`python3 $SK/render.py <example> --base work/demo --sheet work/ex.png --preview 0.5`. Then iterate on yours:
```bash
python3 $SK/render.py work/edit.json --plan                                  # timing sanity
python3 $SK/render.py work/edit.json --sheet work/check.png --preview 0.5 --at b0,b2,b8,b16,drop
```
Read `check.png`, fix what's wrong (text size/position, safe area, empty frames, colours, wrong shot), repeat.
Then a fast draft, then the final:
```bash
python3 $SK/render.py work/edit.json -o work/draft.mp4 --preview 0.5 --speed veryfast
python3 $SK/render.py work/edit.json -o out/final.mp4
```
Rendering is CPU-bound (~5 fps at 1080p; a 30 s edit ≈ 3 min) — use `--from/--to` to re-render one section while
iterating, and run long renders in the background if your environment allows.

### 5. Self-check before delivering
- Hook in the first 1.5 s; no slow fade from black at the start.
- Cuts land on beats (sheet labels show `b` positions); shot lengths change between sections; bursts ≤ 4 s.
- Text readable (contrast/shadow), never over faces, inside the 9:16 safe area (x 0.06–0.86, y 0.10–0.76).
- No black/empty frames except intentional ones; nothing pops out a frame early (check `--plan` ends).
- Music fades out; the ending holds, loops, or lands on a final card.
- Both orientations requested? Make two specs; re-layout, don't just crop.

### 6. Deliver
Give the mp4 path(s), then in Chinese: 剪辑思路 (3–5 lines: motif, why these techniques), 分镜表 (time/beat →
content → technique), what to tweak next. Offer the 剪映 manual steps for the 2–3 signature moves (from
`techniques.md`) if the user may want to edit by hand, and optionally a title + 3–5 hashtags.

## The five reference styles at a glance

| | style | signature moves | rhythm (measured) | fits topics |
|---|---|---|---|---|
| A | 海报歌词排版 MV | fixed subject/type, worlds swap behind; ghost giant word; word-by-word lyrics; font-flicker burst; 失LOST了 pun; eye-close loop | 1 beat → 8 cuts/s burst (3.5 s) → black → loop | travel, love, music, 一个人 |
| B | 艺术海报动态 | statue cut-out on flat colour; staircase thin gold type + red thread; Bauhaus blocks; camera push; defocus transition; drifting ornaments | no hard cuts; type on beats | art, brand, perfume, poetry, 抽象/艺术感 |
| C | 导演美学混剪 | shrink into window frame; circular porthole; slit & brush transitions; tile assembly; quad colour variants; chapter cards; symmetry | ~1 shot per beat at 152 BPM | film tribute, city/café/hotel, lifestyle |
| D | 慢门快闪 | long-exposure smears & light trails; colour-ordered flow; triptych title; letters landing; print borders; © card | 8–12 cuts/s bursts + holds | photography, night city, sport, dance |
| E | 概念剪影 | white silhouettes; dive into an eye; RGB split; inversions on beats; flip-clock counter; colour flips; silhouette → real | beat cuts + 2-frame flashes | time, growth, 打工人, concepts, little footage |

Derived recipes (F–L): 胶片回忆, 抽象几何艺术, 运动燃剪, 国风水墨, 美食探店 Vlog, 故障赛博, 极简治愈.

## Engine cheat sheet
- Layers draw in order (first = bottom). Times: seconds, or beat refs `b8`, `d2` (bar), `drop`; lengths `"2b"`.
- Sources: `video` (`in`, `speed` incl. ramps, `freeze`, `shutter`), `image`, `text`, `shape`, `group`, `color`,
  `gradient`. Placement: `box` [x,y,w,h] + `fit` (`cover|contain|blur_fill`), `x y scale rotation opacity`.
- `anim` presets (pop_in, punch_in, ken_burns, drift, slide_in, typewriter…), `enter`/`exit` transitions,
  `mask` (rect/circle/text/strip/brush…), `effects` (grade, silhouette, rgb_split, trails…), `blend`.
- Macros: `sequence`, `montage`, `bg_swap`, `lyrics` (poster_stack, font_cycle, staircase, word_pop, swap,
  typewriter, subtitle, letters, vertical, stack), `collage`, `split`, `window`, `chapter`, `blocks`.
- Global: `post` (grade, grain, vignette, letterbox, film_frame), `beat_fx` (punch/shake/flash/invert on beats), `sfx`.
- Font roles (`serif_bold`, `condensed`, `script`, `light`, `cjk_brush`…) adapt to the machine; check with
  `python3 scripts/engine/fonts.py`. If the user has nice fonts (思源宋体, Bebas Neue, Playfair…), set `"fonts"`.
Full reference: `references/spec.md`.

## Scripts
| script | use |
|---|---|
| `scripts/probe_media.py` | footage/music inventory + contact sheets (`--shots` for long videos) |
| `scripts/beats.py` | BPM, beats, bars, onsets, energy, drop → beats.json |
| `scripts/analyze_reference.py` | learn a new reference edit: shots, cut rate, beat alignment, palette, sheet |
| `scripts/render.py` | spec → `--plan` / `--sheet` / `--still` / mp4 (`--preview`, `--from/--to`, `--base`) |
| `scripts/make_cutout.py` | subject cut-out PNG/alpha MOV (rembg if installed; `--luma`/`--key` fallbacks) |
| `scripts/make_demo_media.py` | synthetic demo footage/music to smoke-test the engine and examples |

## Learning a new style from a reference
When the user sends a new reference: run `analyze_reference.py`, view its sheet, then extract more frames around
interesting moments (`ffmpeg -ss T -t 2 -i ref.mp4 -vf fps=8,scale=480:-1,tile=4x4 strip.jpg`) to understand
transitions. Describe it in the recipe format (measured rhythm, moves, why it works, fits topics, engine mapping) —
offer to append it to `references/style-recipes.md` so the skill keeps growing. If a move has no engine equivalent,
approximate it with masks/groups/effects, or give the 剪映 steps.

## Notes
- Respect copyright: use the user's own footage/music or material they have rights to; don't fetch copyrighted songs.
- Screen recordings of other people's videos are fine as *references*; don't reuse their footage in deliverables
  unless the user says it's theirs.
- Keep work files in a `work/` folder next to the user's footage; never overwrite their originals.
- iPhone HEIC photos: convert to JPG first (macOS `sips -s format jpeg in.heic --out out.jpg`).
- Beat grid looks off by half a beat or 2×? Re-run `beats.py --bpm <value>`; check by rendering a sheet `--at b0,b1,b2,b3`.
