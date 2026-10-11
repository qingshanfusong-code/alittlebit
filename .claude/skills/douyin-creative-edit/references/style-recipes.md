# Style recipes（风格配方）

Recipes are *starting vocabularies*, not templates. Pick one as the backbone, borrow 1–3 signature moves from
another when the topic asks for it, and change what the topic doesn't need. Numbers marked "measured" come from
frame-by-frame + beat analysis of the user's reference videos.

## Contents
- A. 海报歌词排版 / poster typography MV（ref 1 "Take Me to The Moon"）
- B. 艺术海报动态 / art-poster motion design（ref 2 "你真的存在吗"）
- C. 导演美学混剪 / auteur-aesthetic montage（ref 3 Wes Anderson）
- D. 慢门快闪 / slow-shutter flash montage（ref 4 "Slow Shutter"）
- E. 概念隐喻·剪影 / concept metaphor & silhouettes（ref 5 "正在过去的……"）
- F–L. Derived recipes: 胶片回忆, 抽象几何艺术, 运动燃剪, 国风水墨, 美食探店/Vlog, 故障赛博, 极简治愈
- Mixing rules

---

## A. 海报歌词排版 MV（ref 1）

**Measured:** 16:9, 12.6 s, music ≈70 BPM (beat 0.86 s). Calm 1-beat cuts for 4 bars, then a 3.5 s burst of
≈8 cuts/s (0.125 s per shot, 28 shots), then black, then a loop back to the first frame.

**Structure as edited:**
1. Hook (0–1.5 s): extreme close-up eye + giant word "Take" (cyan) + two reaching hands (Creation of Adam —
   one real, one white flat sticker). Type and hands stay fixed while the background behind swaps 3× in 0.6 s
   (eye → moon → nebula → earth).
2. Collage beat (1.6–2.6 s): screenshot cards pop in over night footage of runners; a dense paragraph of lyrics is
   used as *texture*; small red "MOON" tag in a corner.
3. Same subject, new world (2.6–6.8 s): a cut-out person sitting on a rock never moves; every beat the world behind
   changes (moon, plane window, sea, harbour, sunset). Lyrics land word by word: small white serif side words
   ("where … both") around one red condensed word, with the same word huge, white and translucent *behind*.
4. Burst (6.8–10.3 s): "LOVE" stays centred while 28 travel shots flash at 1/8 s and the word's typeface changes
   on every cut (condensed, script, italic, stretched…).
5. Bilingual pun on black ("失LOST了": grey LOST overlapping 失…了) → closed eye → eye opens → first frame (loop).

**Why it works:** the fixed layer (subject/type) gives the eye an anchor so even 8 cuts/s read as one idea
("everywhere = love"); the burst is short; the loop makes people rewatch.

**Use for:** travel, "one person many places", couple/love, music covers, city collections, self-introduction.
**Engine:** `bg_swap` + `lyrics:poster_stack` → `montage cut 0.25b` + `lyrics:font_cycle` → `chapter:bilingual` →
reprise of the opening. Grade `vivid`/`teal_orange`, light grain. See `examples/poster_typography.json`.
**剪映:** 抠像 the subject once (智能抠像) and keep it on the top track; backgrounds on main track cut with 自动踩点;
big ghost word = 文字 + 不透明度 30–40% + 字间距收紧; font flicker = duplicate the text clip per beat and change 字体.

## B. 艺术海报动态（ref 2）

**Measured:** 16:9, 8.4 s, ≈100 BPM, **zero hard cuts**. One continuous virtual camera move (pan down, slow push),
a defocus-to-dark in the middle, slow drifting ornaments at the end.

**Look:** cut-out marble angel on flat deep navy (#1d3f6e); thin gold (#d8b46a) lyric words placed on a diagonal
staircase (C'est / ta / love / story), each fading/blurring in on its beat; a thin red line threads between words;
tiny wide-spaced Chinese subtitle (你 真 的 存 在 吗) + Latin small caps; gold/red/navy Bauhaus blocks slide in
behind the statue; rack-focus blur to near-black; the wing returns sharp on the left; gold moon & sun reliefs drift
diagonally across.

**Why it works:** gallery stillness — motion comes from the camera and from type arriving on the beat, so 8 s feel
luxurious. Three flat colours + one texture (marble) = instant "poster".

**Use for:** art/museum/exhibition, perfume/jewellery/brand mood, poetry, music with French/English lyrics,
"抽象画/艺术感" requests, anything with one strong cut-out object.
**Engine:** `group` (statue + `blocks` + `lyrics:staircase`) with `scale`/`y` keyframes as the camera, `exit: blur`,
then new layers with `enter: blur` and `drift`/`spin`. See `examples/art_poster.json`.
**剪映:** whole composition on 复合片段, keyframe 缩放/位置 for the camera; 模糊 effect keyframed for the rack focus.

## C. 导演美学混剪（ref 3 Wes Anderson）

**Measured:** 4:3 content, 29.6 s, 152 BPM, 72 shots, median shot 0.37 s ≈ **1 beat**; cut rate ~1.5–3.5/s rising to
7.5/s in the last 2 s.

**Moves:** handwritten Latin title + brush Chinese title (韦斯·安德森 电影美学) → the picture **shrinks into a mint
window frame** and shots swap inside on the beat → red Chinese ornament plate with a **round porthole**, a **thin vertical
slit** opens the next shot, a **red brush stroke** circles and wipes → top-down **tiles assemble** one by one →
**2×2 quad** of the same hotel in different colours/seasons → oval vignette portraits pop on top → match cuts on motion
(a door push, a METRO sign passing = natural wipe) → **chapter cards** (LOCAL COLOR / ARTS AND ARTISTS / TASTES & SMELLS)
between symmetric centred shots.

**Why it works:** every transition is itself a *composition* (frames, circles, grids) — it imitates the director's
symmetry and dollhouse framing, so the edit feels authored, not just cut.

**Use for:** film/director tributes, city or hotel tours, café/food shops, interior design, "pastel" lifestyle,
any footage with symmetric/centred shots.
**Engine:** `chapter:script` → `window` (rect) → `window` (circle, `transition: strip`) → `split` grid →
`collage` → `chapter:wes`; post `grade: wes_pastel`. See `examples/auteur_window_vertical.json`.
**剪映:** 画中画 + 蒙版(矩形/圆形), 关键帧缩放做"缩进窗框"; 转场 "竖线开幕/线性擦除"; 笔刷转场 "水墨/笔刷"。

## D. 慢门快闪（ref 4）

**Measured:** 16:9, 18.7 s, ≈83 BPM; long stretches of 2–3-frame shots (0.08–0.12 s ⇒ 8–12 cuts/s) broken by
0.5–1 s holds; colour-grouped flow (orange instruments → white birds → blue crowds → B&W).

**Moves:** opening triptych (blurred face / high-contrast white horse / neon walker) with "SLOW SHUTTER" landing letter
by letter; every image is a long-exposure smear (light trails, ghosted motion); colour families flow into each other;
B&W high-contrast section in white print borders; pocket watch (time) as the last image; tiny "© 2026 NAME" on black.

**Why it works:** each frame is a still photograph of motion, so ultra-fast cutting reads as *one continuous blur
of a city* rather than chaos; colour grouping supplies the hidden order.

**Use for:** photography portfolios, night city, street, sport, dance, trains, "time"; anyone with lots of short
clips or photos. Keep 8–12 cuts/s bursts ≤3–4 s, separated by holds.
**Engine:** `split` triptych + `lyrics:letters` → `montage` with `shutter: 0.2`, `trails`, `order: hue`,
`pattern: [0.5,0.5,0.25,0.25,0.5,1]` → B&W montage in `box` + `film_frame: print` → credit text.
See `examples/slow_shutter.json`.
**剪映:** 素材本身用慢门/动态模糊拍；后期可用 "残影"/"拖影" 特效 + "动感模糊"; 快闪用 "分割" 每 2–3 帧。

## E. 概念隐喻·剪影（ref 5）

**Measured:** 16:9, 10 s, ≈144 BPM; hard cuts and colour flips on beats, many 2–3-frame flashes.

**Moves:** white silhouette walking on black → dive into an eye (pupil) → silhouettes (climber on a grid, bird,
butterfly) with RGB-split glitch, morphing into each other → golden spiral drawn by a line → Newton's cradle and
metronome with **colour inversion/palette swaps on the beat** → office-building windows lighting up → **flip clock**
23:59 → 00:00 → 01:01 → … with evolution figures (ape → human → astronaut), background colour changing every beat →
a real man walks in (the silhouette becomes real). Signature watermark bottom centre.

**Why it works:** one abstract idea (time passing) told only with symbols; silhouettes remove the specific person
so the viewer projects themselves; the counter gives a ticking spine.

**Use for:** concept pieces (time, growth, anxiety, dreams, 打工人, 年终总结), education/explainers, brand
manifestos, "抽象" edits with little footage.
**Engine:** images with `effects: silhouette` (+ `rgb_split`, `shake`), `sequence transition: zoom_into` with `point`,
`sequence` of colour shots `repeat`, `lyrics:swap` with `box`+`glow` for counters, `beat_fx: invert`.
See `examples/concept_silhouette.json`.
**剪映:** 抠像后 "调节→亮度拉满/色度0" 做白色剪影; "RGB分离"/"故障" 特效; 反相 = 特效 "负片"; 数字用文字模板逐拍替换.

---

## F. 胶片回忆 (film memory)
For: 毕业, 家人, 旧照片, 恋爱纪念日, 年度回顾. Rhythm: 2–4 beats per shot, fades/dissolves, one faster montage at
the chorus. Look: `grade: film`/`warm_gold`, grain 0.05, `film_frame` 35mm or print, `collage layout: stack` polaroids
(`border_bottom` bigger), typewriter dates (`lyrics:typewriter`, font mono), light leaks as `blend: screen` videos.
End on a freeze frame (`freeze: true`) with a date.

## G. 抽象几何·艺术感 (abstract art / "抽象画")
For: 设计/展览/音乐/品牌, or when the user says 抽象, 艺术感, 高级感. Footage becomes material:
`duotone`, `posterize`, `halftone`, `threshold`, `edges`; forced symmetry `mirror`; footage inside giant letters
(`mask: text`); `blocks` (bauhaus/mondrian/stripes); `shape: path` lines drawing on beats; flat 3–4 colour palette;
`blend: multiply/screen` overlays. Rhythm: shapes arrive on beats, footage cuts every 2 beats; camera drifts on
`group`. Avoid realistic grading — commit to the palette.

## H. 运动燃剪 (hype / sport)
For: 篮球, 健身, 滑板, 赛车, 舞蹈, 游戏高光. Speed ramps (`speed` keyframes fast→0.3→fast around the action peak),
`punch_in` on every downbeat, `beat_fx: punch/shake/flash` at the drop, `whip_*` and `zoom` transitions, freeze frame +
huge condensed word on the climax, `rgb_split`/`glitch` for 1–2 beats, contrasty `teal_orange`/`bw_contrast`.
Build: `pattern` 2,2,1,1,0.5×4,0.25×8 into the drop.

## I. 国风·水墨 (Chinese ink)
For: 古风, 汉服, 节气, 江南/古镇旅行, 书法, 茶. Slow (2–4 beats), `brush`/`brush_blob` transitions, `edges` or
`duotone` (ink #1a1a1a on paper #f2ece0) on some shots, vertical brush titles (`chapter style: brush, vertical: true`,
`lyrics:vertical`), a red seal (red square shape + white cjk text), mist via `blur_in`, `grade: faded`.

## J. 美食·探店·手作 Vlog
For: 美食, 探店, 开箱, 手作, 装修. Clear chapters (`chapter style: wes` or `bold`), 1-beat process cuts, `split`
before/after, top-down `collage layout: grid` of ingredients, `freeze` + label box (`text` with `box`), sizzling
moments with `audio: true`. Warm `grade` (`warm_gold`/`wes_pastel`), symmetric framing when possible.

## K. 故障·赛博 (glitch / cyber)
For: 科技, 数码, 夜景, 电子乐, 游戏. `night_neon`, `rgb_split`, `pixelate` flashes, `invert` on snares,
`glitch` transitions, `trails` on lights, mono font text with `flicker`, `shake` beats. Use sparingly over a calm base
or it becomes noise.

## L. 极简·治愈 (minimal / healing)
For: 日常, 独处, 读书, 自然, 早晨, 疗愈. Shots 4–8 beats, `fade`/`blur` only, very wide tracked thin type
(`chapter style: minimal`), lots of negative space (`box` the footage small on a cream canvas), `grade: faded` or
`cold_clean`, no beat_fx. The restraint *is* the technique.

---

## Mixing rules
- One backbone recipe + at most 2–3 borrowed signature moves. More than that and the edit loses identity.
- Borrow by *function*: need an anchor for fast cuts → fixed subject/type (A); need breathing room → camera drift
  (B); need structure for a long piece → chapter cards (C); need energy without new footage → shutter/trails (D);
  need meaning without footage → silhouettes/symbols/counter (E).
- Change density across sections (calm → build → burst → release). Never keep one cut length for the whole video.
- Repeat a motif and transform it (same word in new fonts, same subject in new worlds, same frame at start and end).
