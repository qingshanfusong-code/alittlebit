# Edit spec reference（render.py 的 JSON 格式）

A spec is one JSON file. Layers are drawn **in list order (first = bottom)**. Relative paths resolve against the
spec's folder (or `--base`). Run `render.py spec.json --plan` to see how macros expanded and when every layer starts.

## Contents
1. Top level
2. Time: seconds, beats, keyframes
3. Layers: sources, placement, keyframes
4. Motion presets (`anim`)
5. Transitions (`enter` / `exit`)
6. Masks
7. Effects (layer `effects` and global `post`)
8. Beat-synced global effects (`beat_fx`)
9. Macros (high-level building blocks)
10. CLI, speed, troubleshooting

---

## 1. Top level

```json
{
  "canvas": {"preset": "9:16", "fps": 30, "bg": "#000000"},
  "audio":  {"path": "music.mp3", "start": 42.0, "volume": 1.0, "fade_in": 0, "fade_out": 0.8},
  "beats":  "music.beats.json",
  "duration": "b32",
  "fonts":  {"serif_bold": "fonts/Bodoni-Bold.otf"},
  "layers": [ ... ],
  "post":   [ {"type": "grade", "preset": "film"}, {"type": "grain", "amount": 0.04} ],
  "beat_fx": [ {"type": "punch", "at": "downbeats", "amount": 0.05} ],
  "sfx":    [ {"path": "whoosh.wav", "at": "b16", "volume": 0.7} ]
}
```

- `canvas.preset`: `9:16` (1080×1920, default) `16:9` `4:3` `3:4` `1:1` `4:5` `21:9` `2.35:1`, or `width`/`height`.
- `audio`: one dict or a list. `start` = offset into the music file; `at` = where it starts on the timeline;
  `dur` optional. The **first** audio entry is "the music" the beat map belongs to.
- `beats`: path to the JSON written by `beats.py` (or inline dict). Analyse the **same file**; if you ran
  `beats.py --start 42` set `audio.start` to 42 too (the engine shifts automatically either way).
  No music? `"bpm": 120, "first_beat": 0.0` gives a synthetic grid. Without both, `1b` = 0.5 s.
- `duration`: optional; default = end of the last layer.
- `fonts`: override a font *role* (see §3 text) with a file path.
- `sfx`: one-shot sound effects (whoosh, camera shutter, film click…) placed at time refs.
- Keep the original sound of a clip: put `"audio": true, "volume": 0.8` on that video layer.

## 2. Time

| form | meaning |
|---|---|
| `3.5` / `"3.5"` | seconds (inside a group: seconds from the group's start) |
| `"b8"`, `"b8.5"` | beat 8 (0 = first beat of the music as used), fractional = between beats |
| `"d3"` | 4th bar's downbeat |
| `"drop"` | detected drop (big energy rise) — check `beats.py` output first |
| `"o5"` | 6th detected onset |
| `"b8+0.5b"`, `"d2-0.1"` | offsets: durations after the first term |

Durations (`dur`, `cut`, `td`, anim `dur`): `0.4` / `"0.4s"` seconds, `"2b"` beats (measured on the real beat grid
from that point, so tempo drift is followed), `"1bar"`, `"12f"` (frames at 30 fps).

**Beat refs are always absolute music positions** (also inside groups); plain numbers are parent-local.

### Animating any value
Transform keys (`x y scale scale_x scale_y rotation opacity`) accept keyframe lists directly:
`"scale": [[0, 1.2], [0.4, 1.0, "out"], ["end", 1.05]]`. Keyframe time: seconds from layer start, `"50%"`,
`"end"`, `"end-0.3"`, or an absolute beat ref like `"b12"`.
Everything else (source, mask and effect params) uses an explicit form:
- `{"kf": [[0, 0.0], ["b4", 1.0, "inout"]]}`
- `{"from": 0, "to": 1, "dur": "2b", "delay": 0.2, "ease": "out"}` (dur defaults to the rest of the layer)

Easing: `linear in out inout sine expo_in expo_out expo_inout back_out elastic_out step`.

## 3. Layers

Every layer needs exactly one **source** key:

| source | extra keys |
|---|---|
| `"video": path` | `in` (in-point s), `speed` (number or keyframes = speed ramp), `freeze` (true = hold the in-point frame), `shutter` (s of real frame accumulation = slow-shutter smear, 0.1–0.5), `loop` (default true when the layer is longer than the clip), `reverse`, `audio`, `volume` |
| `"image": path` | — (PNG alpha respected) |
| `"text": "..."` | `font`, `size` (fraction of canvas short side), `color`, `stroke` (fraction of size), `stroke_color`, `outline` (true = hollow letters), `scale_x` (<1 condensed), `skew` (italic), `tracking` (letter spacing, fraction of size), `line_spacing`, `align`, `vertical` (竖排), `case` (`upper`), `shadow` {dx,dy,blur,color}, `glow` {radius,color,strength}, `box` {color,pad} (label plate), `fonts` + `cycle` (font changes every `cycle`, e.g. `"0.5b"`) |
| `"shape": kind` | `rect` (`rect`:[x,y,w,h] top-left, or `x y w h` centred; `radius`), `ellipse`/`circle` (`x y r` or `rx ry`), `line`/`path` (`points` [[x,y],…], `width`, `smooth`, `draw` 0→1 progress = line drawing), `polygon`; `color`, `outline_width` |
| `"group": [layers]` | child layers in group-local time; the group is then moved/scaled as one picture (camera moves, picture-in-picture, window intros) |
| `"color": "#hex"` | full box solid |
| `"gradient": {"colors": [...], "angle": 90, "radial": false}` | |

Font **roles** (resolved per OS, falls back gracefully): `sans sans_bold light thin serif serif_bold condensed
script mono cjk_sans cjk_bold cjk_serif cjk_brush cjk_hand`, or a file path / font-name fragment. Chinese text
automatically switches to the matching CJK role. Missing condensed/script faces are faked with squash/skew.
`python scripts/engine/fonts.py` prints what each role resolves to on this machine.

Common layer keys:

| key | meaning |
|---|---|
| `start` `end` / `dur` | timing (default: whole timeline; a video without end plays to its end) |
| `box` | `[x, y, w, h]` **top-left** fractions of the canvas the media is fitted into (default whole canvas) |
| `fit` | `cover` (crop to fill, default) `contain` `blur_fill` (contain over its own blurred copy — the standard way to put landscape footage in 9:16) `stretch` `width` `height` `none` |
| `focus` | `[fx, fy]` which part survives a cover crop (0.5,0.5 centre; `[0.3,0.5]` keeps left-of-centre — reframe 横转竖) |
| `crop` | `[x,y,w,h]` fractions of the source to use first (cut off watermarks, UI bars) |
| `x` `y` | **centre** position in canvas fractions (default: box centre) |
| `scale` `scale_x` `scale_y` `rotation` (deg, clockwise) `opacity` `anchor` [ax,ay] | transform |
| `anim` | motion presets (§4) |
| `enter` / `exit` | transitions (§5) |
| `mask` | dict or list of masks (§6), canvas coordinates |
| `effects` | per-layer effects (§7), applied before transform |
| `blend` | `normal screen multiply add overlay soft_light hard_light difference lighten darken` |
| `oversample` | decode bigger than the box (e.g. 1.3) when you zoom in a lot |

## 4. Motion presets (`anim`)

`"anim": ["pop_in", {"name": "drift", "dir": "left", "amount": 0.04}]` — params: `dur`, `delay`, `amount`, `dir`.

| preset | what it does |
|---|---|
| `pop_in` / `pop_out` | overshoot scale-in / shrink-out (stickers, collage cards, word pops) |
| `punch_in` | starts 18% bigger and snaps back (a cut that *hits*) |
| `scale_in` `stretch_in` | grow from 0 / grow vertically from a line |
| `ken_burns` | slow push-in (`amount` 0.12, `pan_x`, `pan_y`) — stills come alive |
| `zoom_out` | slow pull-back |
| `drift` | slow slide (`dir`, `amount` 0.03) — poster parallax |
| `slide_in` `slide_out` `whip_in` `whip_out` | from/to `dir`; whip adds motion blur |
| `fade_in` `fade_out` `blur_in` `blur_out` `rise` | soft entrances (rise = subtitles) |
| `shake` `wiggle` `float` `spin` | jitter (`amount`, `freq`), sway, bob (`period`), rotate (`amount` deg/s) |
| `pulse` | scale bump on every beat (`at`: beats/downbeats/…) |
| `flicker` | random dropouts (glitchy text) |
| `typewriter` | text reveals glyph by glyph over `dur` |
| `flash_in` | layer starts white-hot and cools down |

## 5. Transitions (`enter` / `exit`)

`"enter": {"type": "iris", "dur": "1b", "x": 0.5, "y": 0.4}`. An `enter` must overlap the previous picture to be
seen, so inside a `sequence` the macro handles overlaps for you.

`fade` `zoom` `zoom_out` `slide_left|right|up|down` `whip_*` `wipe_left|right|up|down` `iris` `strip`
(a slit opening from the centre — Wes edit) `strip_h` `blinds` (`n`, `dir`) `grid` (tiles, `cols`, `rows`)
`brush` (painted sweep) `brush_blob` (rough paint iris) `blur` (defocus, `amount`) `glitch` `spin` `pop`
`flash` `invert` and exit-only `zoom_into` (`x`,`y`, `amount`: dive into a point, e.g. a pupil or a window).

Sequence-only transition names: `cut` `flash` (white frame) `dip_black` `dip_white` `push_<dir>` (old and new slide
together) `whip_<dir>` `zoom_into` (uses the outgoing shot's `point`) `flash_in`.

## 6. Masks (canvas coordinates)

| type | params |
|---|---|
| `rect` | `x y w h` centred or `box` [x,y,w,h] top-left, `radius`, `feather` |
| `circle` / `ellipse` | `x y r` (r = fraction of short side) or `rx ry` |
| `iris` | `progress`, `x`, `y` |
| `polygon` | `points` |
| `strip` | `x`, `w` (or `y`, `w`, `horizontal`) |
| `wipe` | `progress`, `dir` (left/right/up/down or degrees), `feather` |
| `blinds` / `grid` | `progress`, `n` / `cols rows seed` |
| `brush` | `progress`, `style` sweep\|blob\|ring, `x y r width seed` |
| `text` | `text` + any text keys + `x y` → footage visible only inside the letters (镂空字) |
| `image` | `path` (alpha, or luminance if opaque) |

All accept `invert` and `feather`. Animate with `{"from":…, "to":…}` e.g. `"r": {"from": 0.05, "to": 0.6, "dur": "2b"}`.

## 7. Effects

Per layer: `"effects": [{"type": "grade", "preset": "film"}, "bw"]`. Global: `"post": [...]` (same list plus
`letterbox`, `film_frame`; size-changing ones are layer-only). Animate params with `{"kf": ...}` / `{"from","to"}`.

| effect | params / notes |
|---|---|
| `grade` | `preset`: `film teal_orange wes_pastel bw_contrast bw_soft night_neon moody_blue warm_gold vivid faded sunset cold_clean`, or raw `exposure contrast saturation temperature tint lift gamma shadows:[color,amt] highlights:[color,amt] mix` |
| `adjust` | `brightness contrast saturation` (multipliers) |
| `blur` `motion_blur` `zoom_blur` | `radius` / `length angle` / `amount x y` |
| `rgb_split` | `amount angle` — chromatic glitch |
| `invert` `bw` `posterize` `pixelate` `flip` `mirror` | `contrast` / `levels` / `size` / `dir` / `axis keep` (mirror = forced symmetry) |
| `threshold` | `level soft dark light` — two-tone poster |
| `duotone` `tint` | `dark light` / `color amount` |
| `silhouette` | `color`; uses alpha if the source has it, else luma key (`mode` dark\|light, `level`) |
| `glow` | `radius threshold strength` — bloom on highlights |
| `grain` `vignette` | `amount` / `amount softness` |
| `edges` `halftone` | sketch line-art (`ink paper strength`) / dot screen (`cell ink paper`) |
| `trails` `echo` | light trails (`decay` 0.8–0.95) / ghosting (`decay`) — stateful |
| `chroma_key` `luma_key` | `color tolerance softness` / `low high invert` — drop backgrounds |
| `stroke` `shadow` `border` | sticker outline / drop shadow / card or polaroid border (`width bottom color`) |
| `opacity` | `value` |
| `letterbox` (post) | `ratio` (2.35), `color` |
| `film_frame` (post) | `style` `35mm` (sprocket holes) \| `print` (white photo border), `label` |

## 8. Beat-synced global effects

```json
"beat_fx": [
  {"type": "punch",  "at": "downbeats", "amount": 0.06, "decay": 0.15},
  {"type": "flash",  "at": {"every": "2b", "from": "b16", "to": "b32"}, "amount": 0.5},
  {"type": "invert", "at": ["b31", "b31.5"], "hold": 0.07}
]
```
Types: `punch` (zoom bump) `shake` `flash` (`color`) `dark` `invert` (`hold`) `rgb` `blur`.
`at`: `beats` `downbeats` `onsets` `strong_onsets`, a list of refs, or `{every, from, to}`.

## 9. Macros

Write `{"macro": "<name>", ...}` anywhere a layer can go (also inside groups). Shared layer keys given on the macro
(`fit box focus effects anim mask blend crop speed shutter`…) apply to every generated layer.

### `sequence` — shots back to back
`shots` (each: any layer + `dur`, `transition`, `td`, `point`), `start`, `end`, `cut` (default length, `"1b"`),
`pattern` (lengths in beats, cycled, e.g. `[2,2,1,1,0.5,0.5,0.5,0.5]` = accelerate), `transition`, `td`,
`repeat` (cycle shots until `end`), `count`.

### `montage` — many clips, automatic in-points
`clips` (paths / globs / dicts), `start`, `end` or `count`, `cut` / `pattern`, `pick` `random|middle|start|sequential`,
`order` `given|shuffle|hue|brightness` (hue = rainbow colour flow), `seed`, + sequence keys.

### `bg_swap` — subject stays, world changes (ref 1)
`backgrounds` (clips/globs), `start`, `end`, `cut`, `foreground` (layer or list — PNG/alpha video cut-out, or text),
`between` (layers drawn between background and subject → **text behind the subject**), `bg_effects`.

### `lyrics` (alias `type`) — kinetic typography
`items`: strings or `{text, at, to, dur, left, right, ghost, x, y}`; `start`, `end`, `cut` (spacing when `at` missing),
`style`:
- `poster_stack` (ref 1): giant translucent ghost word + condensed accent word + small side words (`left`/`right`).
  Keys: `accent`, `font`, `size`, `scale_x`, `ghost`, `ghost_size`, `ghost_opacity`, `side_font`, `upper`, `anim`.
- `font_cycle` (ref 1 "LOVE"): the word changes typeface every `cycle` (`"0.5b"`, `"0.25b"`); `fonts` list optional.
- `staircase` (ref 2): words step diagonally (`x y step`), thin gold type, `subtitle` (spaced CJK line), a red thread
  `line` drawn through them (`line_color`), `hold`.
- `word_pop` (one big word at a time), `swap` (instant replace — counters/flip clocks), `typewriter` (`type_dur`),
  `subtitle` (bottom, safe area aware), `stack` (lines accumulate — dense lyric texture), `vertical` (竖排 columns),
  `letters` (ref 4 title: glyphs land one by one in random order, `reveal`).
  All take `font size color anim stroke shadow glow tracking box case x y`.

### `collage` — cards popping in on beats
`items`, `start`, `end`, `at` (interval like `"0.5b"` or list), `layout` `scatter|grid|row|column|stack`, `size`,
`cols rows rotate border border_color border_bottom shadow pop aspect seed bg effects`.

### `split` — split screen panels (ref 3, ref 4 triptych)
`panels`, `layout` `auto|cols|rows|grid`, `cols`, `start`, `end`, `stagger`, `gap`, `gap_color`,
`anim` `slide|stretch|pop|fade|cut`.

### `window` — frame in frame (ref 3)
`shots`, `start`, `end`, `cut`, `transition`, `td`, `frame_color` (or a layer dict, e.g. a patterned image),
`inset` or `window` [x,y,w,h], `shape` `rect|circle`, `radius`, `border` {width,color}, `intro` `zoom_out|none`
(full-screen shot shrinks into the window), `intro_dur`, `decor` (extra layers on the frame), `enter`/`exit`.

### `chapter` (alias `title`) — title / chapter cards
`title`, `sub`, `note`, `start`, `end`, `bg` (`#hex`, media path or layer), `style`:
`wes` (small tracked caps + sub + gold note), `bold` (huge condensed accent), `script` (hand-script),
`brush` (书法/毛笔 CJK, `vertical`), `minimal` (thin, very wide tracking), `bilingual` (`latin` word behind CJK —
ref 1 "失LOST了"). Also `color font size x y`.

### `blocks` — Bauhaus colour blocks sliding in (ref 2)
`start`, `end`, `palette`, `count`, `at`, `style` `bauhaus|stripes|mondrian`, `seed`, `opacity`, `slide_dur`.

## 10. CLI, speed, troubleshooting

```
python scripts/render.py edit.json --plan                       # timeline after macro expansion
python scripts/render.py edit.json --sheet sheet.png --preview 0.5 --at b0,b4,b8,drop
python scripts/render.py edit.json -o draft.mp4 --preview 0.5 --speed veryfast
python scripts/render.py edit.json -o final.mp4                  # 1080p ≈ 5 fps on a laptop CPU
python scripts/render.py edit.json -o part.mp4 --from b16 --to b32
```
- Always look at a `--sheet` before rendering video; it costs seconds and catches layout/legibility problems.
- `--preview 0.5` renders ~4× faster; all sizes are relative so the layout is identical.
- Text too small/large → `size` is relative to the canvas **short side** (0.1 on 1080-wide = 108 px).
- "unknown effect/transition/anim" errors list the valid names.
- A key frame list on a non-transform key silently becomes a list — use `{"kf": ...}` there.
- Layers drawn in list order: put the background first, text and cut-outs last.
