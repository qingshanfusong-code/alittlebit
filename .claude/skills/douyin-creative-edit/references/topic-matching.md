# 选题 → 剪辑手法：怎么选（topic matching）

The goal is an edit whose *form says the same thing as its content*. Work through the five questions below, write
the answers down in one short block (the "剪辑思路"), and only then open the recipes/spec.

## 1. What is the one idea? (一句话母题)
Reduce the topic to one sentence and one **visual motif** that can repeat and transform.

| topic | idea | motif that can repeat |
|---|---|---|
| 一个人的旅行 | "I take myself everywhere" | the same cut-out me, new world every beat (bg_swap) |
| 毕业季 | "a chapter closes" | chapter cards / polaroids stacking, ends on freeze frame |
| 时间/成长 | "time keeps passing" | counter, clock, silhouettes changing, eye opening/closing |
| 城市夜跑 | "speed and lights" | light trails, shutter smear, punch on every step |
| 香水/品牌 | "a mood, not a product" | one object on flat colour, slow camera, type arriving |
| 恋爱纪念 | "us across many days" | one word (LOVE/爱) staying while days flash by |
| 打工人日常 | "the loop of days" | repeated identical frame/sound that ends where it began |

If the user gave lyrics or a title, the motif is often a word from it (ref 1 used MOON / LOVE / LOST).

## 2. Emotion → rhythm & transitions

| emotion | shot length (beats) | transitions | movement | grade |
|---|---|---|---|---|
| 浪漫·温柔 | 2–4, one 0.5b burst at chorus | fade, blur, iris, dissolve | ken_burns, drift | film, warm_gold, wes_pastel |
| 治愈·极简 | 4–8 | fade only | almost none | faded, cold_clean |
| 燃·热血·运动 | 1 → 0.5 → 0.25 into drop | cut, whip, zoom, flash, glitch | punch, shake, speed ramps | teal_orange, bw_contrast |
| 文艺·复古·怀旧 | 2 | dissolve, film flash, dip_white | slow push | film, grain, film_frame |
| 高级·艺术·抽象 | 2–4 or no cuts (camera move) | blur/defocus, strip, mask reveals | group camera drift, blocks sliding | flat palette, duotone/threshold |
| 悬疑·哲思·概念 | 1, with sudden holds | hard cut, invert, zoom_into | still silhouettes, rgb flicker | moody_blue, bw |
| 搞笑·抽象梗 | irregular: hold, then 3 fast cuts | hard cut, zoom punch, freeze | shake, pop_in stickers | vivid |
| 都市·潮流 | 1 | cut, push, split screens | punch on downbeats | night_neon, teal_orange |

Rhythm curve: hook (0–2 s, the strongest image + text) → set-up (calmer, establishes motif) → build
(shortening shots) → peak/drop (densest; ≤3–4 s of 0.25b cuts) → release (a hold, black, or the motif
transformed) → ending that loops or lands on a punchline.

## 3. What material is there? (素材决定可行性)

| material | strong choices |
|---|---|
| many short clips, varied places | montage + an anchor (fixed type or subject), colour-ordered flow |
| a few long clips | sequence of 2–4 beat shots, `speed` ramps, freeze frames, split screen of the same clip at different moments |
| mostly photos | collage pop, ken_burns, shutter-smear look is impossible → use poster typography, frame-in-frame, `halftone`/`duotone` |
| one person in many places | cut-out + bg_swap (text between bg and subject) |
| art / product / object images | art-poster motion (group camera, blocks, staircase type) |
| film/TV clips (混剪) | window/porthole frames, chapter cards, match cuts on motion, symmetric shots |
| almost nothing | concept edit: silhouettes, shapes, counters, colour backgrounds, kinetic type |
| night/motion footage | shutter + trails, night_neon |
| interviews/voice | keep original audio (`audio: true`), subtitles style, cut on sentence ends not beats |

Run `probe_media.py` first: motion score, brightness and orientation tell you what is usable
(high motion → fast cuts/shutter; dark → neon/trails; static → collage/poster).

## 4. Orientation (横屏 / 竖屏)

**竖屏 9:16 (Douyin feed):** top ~8 % and bottom ~22 % and the right ~12 % are covered by UI — keep faces and text
inside x 0.06–0.86, y 0.10–0.76. Text larger relative to width; stack lines vertically; `split layout: rows`;
landscape footage → `fit: blur_fill`, or `focus` crop to the subject, or a 4:3 `box` with type above/below
(magazine layout), or `window` frame. Collage cards bigger (size 0.55–0.65).

**横屏 16:9 / 21:9:** cinematic; words can sit left/right of a subject (poster_stack side words); triptychs
(`split layout: cols`); `letterbox` 2.35 for film feel; type can be huge (ghost words 0.9 of height).

**Both:** if the user wants both versions, build the spec once with relative positions, then make a second spec
that changes `canvas.preset`, `split layout`, text `y`, `size` and `focus` — don't just crop.

## 5. Text & sound
- Text says something the picture doesn't: a lyric word, a question, a date, a pun (失LOST了). One idea per beat.
- Choose 1 display face + 1 small face. Contrast in size (huge vs tiny) is more stylish than many fonts — except in
  a deliberate `font_cycle` burst.
- Music decides structure: run `beats.py`, look at energy segments and `drop`. Put the hook on the first strong beat
  (often b0–b1) and the densest section on the drop. If BPM is >130, consider cutting every 2 beats ("half-time")
  for calm parts.
- If cuts in the reference land on half-beats, the tracker may have locked onto off-beats: shift by `0.5b`.

## Worked examples（同一套工具，不同的选择）

1. **"一个人去了12个城市" (9:16, 20 s, 128 BPM, 40 clips + a selfie cut-out):** backbone A. Hook: cut-out in front of
   a giant ghost "ALONE" with backgrounds swapping on beats b0–b8; collage of tickets at b8–b12; drop b16:
   montage `cut 0.25b` with the word "去" font-cycling; release: black + `chapter bilingual` "一个人 ALONE";
   end on the first city again (loop). Grade vivid, punch on downbeats only during the build.
2. **"毕业了" (16:9, 30 s, 76 BPM, photos + a few clips):** backbone F with C's chapter cards ("第一章 相遇"…).
   Polaroid `collage stack` per chapter, film frame, typewriter dates; final group photo freezes, iris out.
3. **"香水新品" (9:16, 12 s, 95 BPM, 3 product photos):** backbone B. One cut-out bottle on brand colour, `blocks`
   slide on beats, staircase type of three notes ("bergamot / iris / musk"), camera push via `group`, blur exit,
   bottle returns with gold ornament drifting. No hard cuts at all.
4. **"打工人的一天" (9:16, 15 s, 140 BPM, phone clips):** backbone E + K. Silhouette walker, clock `swap` 07:00 → 09:00 →
   … → 23:59 every beat with background colour flips, `invert` on snares, ends exactly where it began.
5. **"城市夜骑" (16:9, 18 s, 90 BPM):** backbone D + H. Shutter montage colour-ordered, speed ramp on the one hero
   shot, triptych intro, title letters, B&W print-border ending.
6. **"江南三日" (9:16, 25 s, slow guqin):** backbone I + L. Long holds, brush transitions, vertical brush captions,
   one `strip` reveal at the climax, ink duotone on the last shot.
7. **"抽象画展" ("帮我剪个抽象画风格的"):** backbone G with B's camera. Paintings as cut-out/flat material, footage
   inside letters of the exhibition name, mondrian blocks on beats, `halftone` on visitor shots, mirror symmetry
   once, title in thin tracked caps.

## Anti-patterns
- Same transition on every cut; same shot length throughout; beat_fx on every beat for 30 s.
- Effects that don't serve the idea (glitch on a wedding).
- Text covering faces or sitting under Douyin UI.
- A burst longer than ~4 s, or bursts without an anchor element.
- Ending on a random frame — end on a hold, black + type, freeze, or a loop.
