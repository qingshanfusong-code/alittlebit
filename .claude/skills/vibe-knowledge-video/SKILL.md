---
name: vibe-knowledge-video
description: 制作“Vibe知识大赏”风格的抖音知识短片（黑金暗场、衬线字、粒子标题、视觉隐喻、字幕代替配音、舒缓配乐、16:9），覆盖选题、文案、分镜（script.json）、画面代码（scenes.js）、渲染 MP4、迭代改稿的全流程。当用户要做知识类短视频、写视频选题/文案/脚本/分镜、把脚本做成视频、修改或重渲已有视频、学习新的参考视频风格时使用。
---

# Vibe 知识短片

风格规则已经从参考视频里提炼好了，在 `references/style-dna.md`。生产工具在仓库的 `studio/` 目录：引擎（HTML/GSAP）、逐帧渲染器（Playwright + ffmpeg）、配乐生成器、音效库、范例项目。

**账号偏好（用户明确要求）**：
- 默认用暖色暗场：`gilt` 黑棕鎏金，带桌面舞台和光池；或 `ember` 炭黑琥珀。
- **不要用蓝色背景**（`night`、`abyss`）。
- 声音要舒缓：自动配乐加少量柔和音效，不要密集音效。

## 流程：一个视频 = 一个对话窗口，分三个阶段

所有命令都在**仓库根目录**运行（项目已经允许这些命令免确认）：`node studio/tools/render.mjs videos/<名> …`

### A. 选题 + 文案 + 分镜 → `studio/videos/<名>/script.json`
1. 读 `references/script-guide.md`，以及 `references/style-dna.md` 的第 2 节。
2. 写 script.json。每个节拍都要有 `say`（文案）和 `v`（画面备注）。
3. 运行 `--timing`，把文案和时长表给用户确认。
4. **用户确认文案之前，不写任何画面代码。**
5. 文案定稿后，提醒用户：可以输入 `/clear` 清空上下文，再进入阶段 B。script.json 已经保存了全部信息，清空后不会丢东西。

### B. 画面 → `studio/videos/<名>/scenes.js`
1. 读 `references/engine-api.md`，以及 `references/style-dna.md` 的第 3、4、6 节。用到某个组件时，去 `studio/videos/_showcase/scenes.js` 或 `studio/videos/brachistochrone/scenes.js` 里 grep 写法。
2. 按 script.json 里的 `v`，逐个场景写 scenes.js。
3. **强制自检（每次写完或改完画面都要做，不需要用户提醒）**：
   - 运行 `--sheet` 出联系表，然后 Read 这张图。
   - 对照 style-dna 第 6 节的清单逐条检查：钩子、标题时间、焦点、安全区、遮挡、文字溢出、没有蓝色。
   - 有问题就修，修完再出一次联系表确认。最多 2 轮。
   - 自检通过后，用一两句话告诉用户你检查了什么、修了什么。
4. 运行 `--preview`（约 15–30 秒出片，带配乐），然后告诉用户预览文件的路径。

### C. 迭代 + 成片（接着 B 的对话继续）
1. 用户按**节拍 id 或时间点**提意见。
2. 只改对应的位置：文案和时长改 script.json，画面用 Edit 改 scenes.js 里对应的几行。
3. 改完照样自检，但只看改动的地方：`--sheet --at <那几个时间点>`。然后再出 `--preview`。
4. 用户确认后：先正式渲染，再 `--cover` 出封面。交付 `studio/videos/<名>/out/<名>.mp4` 和 `out/cover.jpg`。

## 省 token 硬规则

1. **不读** `engine.js`、`engine.css`、`render.mjs`、`music.mjs` 的源码，API 都在 engine-api.md 里。
2. **不看**参考视频，也不重新分析风格。只有用户明确要“学习新参考”时，才用 `studio/tools/analyze_ref.sh`，并且只看它生成的联系表。
3. **不整文件重写** scenes.js 或 script.json，用 Edit 做局部修改。
4. **看图只看联系表**：一张联系表约 1.5k token。不逐帧截图，不看 mp4。查细节用 `--sheet --at t1,t2 --w 960`。
5. 先 `--timing`（纯文本），确实需要时才 `--sheet`（出图）。正式渲染只在用户确认之后做一次。
6. **复用组件**，不发明新特效，现有组件已经覆盖参考视频的手法（style-dna 3.2 节）。
7. 回复要简短：说清楚改了什么，附上文件路径，不要把代码贴回对话里。

## 声音（script.json 的 meta 里配置，默认值已经可用）

- `music`：默认 `"piano"`，会按视频时长自动生成毛毡钢琴加弦乐铺底的舒缓配乐。标题卡处有轻微的“绽放”，结尾落在主和弦上。可以改成 `"ambient"`（更空灵、没有琶音），或 `"none"`（不要配乐）。
  - `musicSeed: <数字>` 可以换一段旋律。
- `bgm: "music.mp3"`：用你自己的音乐文件（放在项目目录里），优先级高于自动配乐。`bgmGain` 调音量，默认 0.6。
- `sfx`：默认 `"soft"`，只在标题、盖章、碎裂这几处有轻柔音效。可选 `"off"`（无音效）、`"manual"`（只要手动加的）、`"full"`（全部）。
- 成片会自动做响度标准化，到 -16 LUFS。

## 发布建议（交付时提醒用户）

- 视频是 16:9 横屏，1080p，自带配乐，可以直接发。如果想用抖音热门 BGM，发布时选“使用同款”音乐，把原声调到 0–30%。
- 标题格式参考：`Vibe知识大赏｜<钩子句>`，再加话题标签。具体规则以抖音 App 里的当期活动为准。
- 封面用 `out/cover.jpg`，也就是标题卡定格。

## 环境

- 第一次使用：在 `studio/` 下运行 `npm install`。本地电脑还要运行 `npx playwright install chromium`，并安装 ffmpeg（详见仓库根目录的 `使用指南.md`）。
- 新项目：复制 `studio/videos/brachistochrone/` 改名，或者直接新建 `script.json` 和 `scenes.js`。
- 音效不够用时：把同名 wav 放进 `studio/videos/<名>/sfx/`，可以覆盖全局音效。
