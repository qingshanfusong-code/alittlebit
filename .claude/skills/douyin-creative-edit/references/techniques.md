# 手法库（technique catalog）

Each entry: what it is · what it does to the viewer · when (not) to use · engine · 剪映/CapCut by hand.
Refs: (1) Take Me to The Moon · (2) 天使雕塑海报 · (3) Wes Anderson · (4) Slow Shutter · (5) 正在过去的.

## Contents
1. 节奏 Rhythm  2. 合成 Compositing  3. 文字 Typography  4. 转场 Transitions  5. 质感·调色 Look  6. 结构 Structure

---

## 1. 节奏 Rhythm

**1.1 卡点切 (cut on beat)** — every cut on a beat; the viewer *feels* the music. Default 1 beat at 70–120 BPM,
2 beats above 130 BPM. Engine: `sequence/montage cut "1b"` with `beats`. 剪映: 音频→踩点→自动踩点, then 分割 at marks.

**1.2 加速堆叠 (accelerating cuts)** — 2,2,1,1,½,½,½,½,¼… into the drop; builds tension. Engine: `pattern`.
剪映: manual markers, halve clip lengths each bar.

**1.3 高频闪剪 (flash burst, 8–12 cuts/s)** (1)(4) — a torrent of images = "everything at once". Needs an anchor
(fixed word/subject) or a colour order; keep ≤3–4 s. Engine: `montage cut "0.25b"` (or `"3f"`), `order: hue`.
剪映: 每 2–3 帧分割, 或"闪切"模板.

**1.4 定格 (freeze frame)** — stops time on the climax/punchline; pairs with a big word or label. Engine:
`"freeze": true, "in": 3.2`. 剪映: 定格 button.

**1.5 曲线变速 (speed ramp)** — fast→slow-mo→fast around the action peak; the signature of sports/hype edits.
Engine: `"speed": [[0, 2.5], [0.4, 0.3, "out"], [1.2, 0.3], [1.6, 2.0, "in"]]`. 剪映: 变速→曲线变速→蒙太奇/英雄时刻.

**1.6 节拍特效 (beat FX)** — zoom punch / shake / flash / invert / RGB pulse on chosen beats; adds impact without
new footage. Use on downbeats or the drop only. Engine: `beat_fx`. 剪映: 特效 "震动/闪白/放大" placed on 踩点.

**1.7 留白 (holds & silence)** — a 1–2 beat hold or black after a burst; contrast makes the burst hit. Engine:
a `color` layer or long shot. 剪映: 黑场 + 文字.

## 2. 合成 Compositing

**2.1 固定主体·换世界 (bg_swap)** (1) — same cut-out person/object, background changes on each beat. Says "same me,
many places/moods". Needs a clean cut-out (`make_cutout.py`, 剪映 智能抠像). Engine: `bg_swap`.
剪映: 抠像后的人放画中画顶层不动, 主轨背景每拍切换.

**2.2 字压人后 (text behind subject)** (1) — giant word between background and cut-out; instant depth, magazine
cover look. Engine: `bg_swap between`, or layers bg → text → cut-out. 剪映: 复制主体轨道并抠像, 文字放两轨之间.

**2.3 幽灵大字 (ghost word)** (1) — the same word huge, white, 30–40 % opacity behind the readable one; texture +
emphasis. Engine: `lyrics poster_stack/font_cycle` (`ghost: true`). 剪映: 文字放大, 不透明度 35%.

**2.4 窗框画中画 (frame in frame)** (3) — the picture shrinks into a coloured window and shots swap inside; authored,
dollhouse feeling; also makes landscape clips work on 9:16. Engine: `window` (`intro: zoom_out`).
剪映: 画中画 + 矩形蒙版 + 关键帧缩放, 底色用纯色背景.

**2.5 圆窗/舷窗 (porthole)** (3) — circular window on an ornamental/coloured plate. Engine: `window shape: circle`,
`border`. 剪映: 圆形蒙版 + 描边贴纸.

**2.6 分屏 (split screen)** (3)(4) — 2/3/4 panels arriving on beats; compare, show variety, or build a triptych title.
Engine: `split` (`cols` landscape, `rows` portrait, `grid`). 剪映: 画中画多轨 + 位置, 或分屏模板.

**2.7 拼贴弹出 (collage pop)** (1)(3) — cards/polaroids pop in on beats; memories, collections, tickets. Engine:
`collage` (`layout`, `border`, `rotate`). 剪映: 画中画 + 入场动画 "弹入", 白边用 "描边".

**2.8 镂空字 (footage inside text)** — the clip plays inside giant letters; title cards with energy. Engine: layer
`mask: {"type": "text", "text": "TOKYO", "font": "condensed", "size": 0.5}`. 剪映: 文字 + 蒙版/混合模式"正片叠底".

**2.9 剪影 (silhouette)** (5) — subject turned into a flat white/colour shape; universal "anyone", concept pieces.
Engine: effect `silhouette` (alpha or luma), + `rgb_split`. 剪映: 抠像 + 亮度/饱和度拉到底(或拉满).

**2.10 虚拟运镜 (camera move over a composition)** (2) — move/zoom a whole poster as one; motion without cuts.
Engine: `group` with `scale`/`x`/`y` keyframes. 剪映: 复合片段 + 关键帧.

**2.11 色块滑入 (Bauhaus blocks)** (2) — flat colour rectangles slide in on beats behind type/objects; designed,
"高级". Engine: `blocks`. 剪映: 形状贴纸/纯色图片 + 关键帧位置.

**2.12 线条生长 (line drawing)** (2)(5) — a line draws itself through words or a spiral; guides the eye.
Engine: `shape: path` with `"draw": {"from": 0, "to": 1}`. 剪映: "画笔/描边" 动画贴纸.

**2.13 混合叠加 (blend overlays)** — light leaks, dust, fire, smoke over footage with `blend: screen`; textures with
`multiply`. Engine: `blend`. 剪映: 混合模式 滤色/正片叠底.

## 3. 文字 Typography

**3.1 逐词歌词 (word-by-word lyrics)** (1)(2) — one word per beat; makes the music visible. Engine: `lyrics` styles.
**3.2 字体闪切 (font flicker)** (1) — same word, different typeface each cut; energy with stability. Engine:
`font_cycle` or `text` + `fonts` + `cycle`. 剪映: 复制文字片段, 逐个换字体.
**3.3 阶梯排版 (staircase layout)** (2) — words descending diagonally, thin face, thread line; poetic, gallery-like.
Engine: `lyrics staircase`.
**3.4 字母落位 (letters landing)** (4) — title letters appear one by one in random order. Engine: `lyrics letters`.
**3.5 打字机 / 竖排 (typewriter / vertical)** — dates, notes, poems; vertical for Chinese poetic text. Engine:
`typewriter`, `vertical`.
**3.6 翻牌计数 (counter / flip clock)** (5) — numbers replacing on beats; time, countdowns, years. Engine:
`lyrics swap` + `box` + `glow`.
**3.7 双语谐音 (bilingual pun)** (1) — Chinese + English overlapped (失LOST了); wit, rewatch value. Engine:
`chapter bilingual`.
**3.8 章节卡 (chapter cards)** (3) — small tracked caps + subtitle; structures long videos, cinematic. Engine:
`chapter wes/minimal`.
**3.9 文字墙 (text wall)** (1) — dense paragraph as texture behind images. Engine: `lyrics stack` small size, low opacity.

Rules: max 2 typefaces except deliberate flicker; huge-vs-tiny size contrast; keep 9:16 text inside the safe area;
light text needs a darker background or `shadow`.

## 4. 转场 Transitions

Prefer *motivated* transitions (the picture causes them) over decorative ones.

| transition | feeling | engine | 剪映 |
|---|---|---|---|
| hard cut on beat | clean, confident | `cut` | 分割 |
| match cut (shape/motion/colour continues) (3)(5) | clever, seamless | plan shots: same position/motion across the cut; `cut` | 手动对齐 |
| object wipe (something passes the lens) (3) | natural | cut where the object fills the frame | 遮挡转场 |
| zoom into a point (eye, window, lamp) (5) | going inside, dream | `zoom_into` + `point` | 关键帧放大 + 叠化 |
| strip / slit opening (3) | theatrical reveal | `strip` | 转场 "开幕/竖线" |
| brush / ink (3) | handmade, Chinese, artsy | `brush`, `brush_blob` | 转场 "水墨/笔刷" |
| iris | storybook, focus | `iris` | 转场 "圆形遮罩" |
| defocus blur (2) | memory, dreamy, luxury | `blur` | 模糊 关键帧 |
| flash / dip white | memory flash, beat accent | `flash`, `dip_white` | 闪白 |
| whip / push | energy, travel | `whip_*`, `push_*` | 转场 "拉镜/推近" |
| glitch / invert (5) | tension, tech, concept | `glitch`, `invert` | 故障/负片 |
| grid / tiles (3) | assembling, collection | `grid`, `collage layout grid` | 拼图转场 |

## 5. 质感·调色 Look

- **调色 presets**: `wes_pastel` (pastel, warm), `teal_orange` (cinematic), `film` (soft filmic), `night_neon`
  (city night), `bw_contrast` (graphic B&W), `moody_blue` (introspective), `warm_gold` (golden hour), `vivid`
  (travel pop), `faded` (matte/vintage), `sunset`, `cold_clean`. One grade for the whole video (in `post`) unless a
  section is deliberately different (e.g. B&W ending).
- **慢门/拖影 (shutter & trails)** (4) — `shutter: 0.15–0.5` on video, `trails decay 0.8–0.92`; light streaks and
  ghosted motion. 剪映: 特效 "拖影/残影", 动感模糊.
- **颗粒/暗角/胶片框** — `grain 0.02–0.06`, `vignette 0.2–0.35`, `film_frame`, `letterbox 2.35`.
- **平面化 (graphic)** — `duotone`, `threshold`, `posterize`, `halftone`, `edges`; turns footage into poster material.
- **对称 (symmetry)** — `mirror`, or simply choose centred shots (3).
- **发光 (glow)** — `glow` for neon, counters, highlights.

## 6. 结构 Structure

- **钩子 (hook 0–2 s)**: the best image + the key word at second 0. Never start with a logo or slow fade-in.
- **首尾呼应 / 循环 (loop)** (1)(5): end on the opening image (closed eye → open eye → first frame); Douyin rewatches
  count. Engine: repeat the first layers at the end.
- **主题词反复变形**: the motif word reappears in new fonts/places (MOON → LOVE → LOST).
- **章节化**: 3–4 chapters with cards for >30 s videos.
- **署名尾卡**: tiny "© 2026 NAME" or handwritten signature on black, 1–2 s (4)(5).
- **情绪曲线**: calm → build → peak → release; vary shot length, colour and text density between sections.
