---
name: vibe-knowledge-video
description: 制作“Vibe知识大赏”风格的抖音知识短片（暗场、衬线字、粒子标题、视觉隐喻、字幕代替配音、16:9），覆盖选题、文案、分镜（script.json）、画面代码（scenes.js）、渲染 MP4、迭代改稿的全流程。当用户要做知识类短视频、写视频选题/文案/脚本/分镜、把脚本做成视频、修改或重渲已有视频、学习新的参考视频风格时使用。
---

# Vibe 知识短片

风格规则已经从 5 个参考视频（叁号暗房、电子智人、Iwanau）里提炼好了，放在 `references/style-dna.md`。生产工具在仓库的 `studio/` 目录：引擎（HTML/GSAP）、逐帧渲染器（Playwright + ffmpeg）、音效库、范例项目。

## 流程：三个阶段，每个阶段一个 session

阶段之间只靠文件交接，所以**每个阶段新开一个 session（或先 /clear）**，上下文最小。

### A. 选题 + 文案 + 分镜 → `studio/videos/<名>/script.json`
1. 读 `references/script-guide.md`，以及 `references/style-dna.md` 的第 2 节。
2. 写 script.json：每个节拍都要有 `say`（文案）和 `v`（画面备注）。
3. 运行 `node tools/render.mjs videos/<名> --timing`，把文案和时长表交给用户确认。
4. **用户确认文案之前，不写任何画面代码。**

### B. 画面 → `studio/videos/<名>/scenes.js`
1. 读 `references/engine-api.md`，以及 `references/style-dna.md` 的第 3、4、6 节。用到某个组件时，去 `videos/_showcase/scenes.js` 或 `videos/brachistochrone/scenes.js` 里 grep 写法。
2. 按 script.json 里的 `v` 逐个场景写。
3. 自检：先 `--sheet` 出联系表，只看这一张图，对照 style-dna 第 6 节，改问题。最多自检 2 轮。
4. 运行 `--preview`（约 15 秒出片），把 `out/preview.mp4` 发给用户看。

### C. 迭代 + 成片
1. 用户按**节拍 id 或时间点**提意见，例如“c3 的时钟太小”“0:25 那里停太久”。
2. 只改对应的位置：文案和时长改 script.json，画面用 Edit 改 scenes.js 里对应的那几行。
3. 验证时只看改过的地方：`--sheet --at <那几个时间点>`，或者 `--from a --to b` 渲染一小段。
4. 用户点头后：先正式渲染，再 `--cover` 出封面，然后交付 `out/<名>.mp4` 和 `out/cover.jpg`。

## 省 token 硬规则

1. **不读** `engine.js`、`engine.css`、`render.mjs` 的源码。API 都在 engine-api.md 里。
2. **不看**参考视频，也不重新分析风格，结论都在 style-dna.md 里。只有用户明确要“学习新参考”时，才用 `tools/analyze_ref.sh`，并且只看它生成的联系表。
3. **不整文件重写** scenes.js 或 script.json，用 Edit 做局部修改。
4. **看图只看联系表**：一张联系表 16 格，约 1.5k token。不要逐帧截图，不要看 mp4。查细节用 `--sheet --at t1,t2 --w 960`。
5. 先 `--timing`（纯文本），确实需要时才 `--sheet`（出图）。正式渲染只在用户确认之后做一次。
6. **复用组件**，不发明新特效。现有组件已经覆盖参考视频里的全部手法（style-dna 3.2 节）。
7. 给用户的回复要简短：说清楚改了什么，附上文件路径。不要把代码贴回对话里。

## 发布建议（交付时提醒用户）

- 视频是 16:9 横屏，1080p。BGM 在抖音里加：找到参考视频用的同款热门钢琴曲，点“使用同款”，原声（音效）音量调到 50–70%。
- 标题格式可以参考参考视频：`Vibe知识大赏｜<钩子句>`，再带上相关话题标签。具体的活动规则以抖音 App 里当期话题为准。
- 封面用 `out/cover.jpg`，也就是标题卡定格。

## 环境

- 首次使用：在 `studio/` 下运行 `npm install`。本地电脑还要运行一次 `npx playwright install chromium`，并且装好 ffmpeg。云端 Claude Code 环境里 Chromium 和 ffmpeg 已经装好。
- 新项目：复制 `videos/brachistochrone/` 改名，或者直接新建 `script.json` 和 `scenes.js` 两个文件。
- 音效不够用时：把同名 wav 放进 `videos/<名>/sfx/`，可以覆盖全局音效；`python3 tools/make_sfx.py` 会重新生成基础音效库。
