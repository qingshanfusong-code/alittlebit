---
name: vibe-knowledge-video
description: 制作“Vibe知识大赏”风格的抖音知识短片（黑金暗场、衬线字、粒子标题、视觉隐喻、字幕代替配音、舒缓配乐、16:9），覆盖选题、文案、分镜（script.json）、画面代码（scenes.js）、渲染 MP4、迭代改稿的全流程。当用户要做知识类短视频、写视频选题/文案/脚本/分镜、把脚本做成视频、继续做视频（“进入阶段B”“进阶段C”“继续”“出预览”“渲染正式版”）、修改或重渲已有视频、学习新的参考视频风格时使用。
---

# Vibe 知识短片

**路径约定**：
- `$SKILL` = 本 skill 所在目录的绝对路径，也就是加载 skill 时显示的 Base directory。**直接用这个路径，绝不全盘搜索 skill。**写命令时换成真实的绝对路径，路径加引号。
- 用户的视频项目 = 当前工作文件夹里的 `videos/<名>/`（启动 Claude Code 的那个文件夹）。不要放进 skill 目录。
- RENDER = `"$SKILL/studio/tools/render.mjs"`。

## 第 0 步：找到项目（每次被调用都先做，几秒钟就要完成）

1. **只看当前文件夹的 `videos/`**：用 Glob `videos/*/STATUS.md` 和 `videos/*/script.json` 查找。**禁止**在当前文件夹以外搜索，禁止 `find /`、`dir /s`、全盘 Glob。
2. 用户说了项目名就用那个。没说的话：只有一个项目就直接用；有多个就选 STATUS.md 最新的那个，并在回复第一句说明“继续 videos/xxx”。
3. 有 STATUS.md 时先读它（10 行以内）：它写着当前阶段和下一步。用户说“进阶段B”“继续”时，照它接着做，不需要再问。
4. `videos/` 不存在、或者里面没有项目，说明是新视频，从阶段 A 开始。

**首次使用**：如果 `$SKILL/studio/node_modules` 不存在，或者渲染时报“还没安装依赖”“找不到浏览器”，就运行 `node "$SKILL/studio/tools/setup.mjs"`（timeout 设成 600000）。它输出带 ✗ 的项目时，把提示原样转告用户。

## 流程：一个视频 = 一个对话窗口，A → B → C 连着做

**阶段之间不要 /clear。** 同一个对话里连着做，上下文会被缓存，成本不高；清空反而会丢掉进度。只有开始**下一个视频**时，才建议用户新开对话或 /clear。

每个阶段结束、每轮改稿之后，都要更新 `videos/<名>/STATUS.md`（10 行以内），格式如下：

```
阶段：A 完成，文案已定稿（或 B 进行中 / C 第 2 轮）
已完成：script.json 14 拍 53s；scenes.js 3 个场景；最新预览 out/preview.mp4
下一步：阶段 B（写 scenes.js）
用户偏好：……（用户在这期提过的要求）
```

### A. 选题 + 文案 + 分镜 → `videos/<名>/script.json`
1. 读 `$SKILL/references/script-guide.md`，以及 `$SKILL/references/style-dna.md` 的第 2 节。
2. 写 script.json。每个节拍都要有 `say`（文案）和 `v`（画面备注）。
3. 运行 `node RENDER videos/<名> --timing`，把文案和时长表给用户确认。
4. **用户确认文案之前，不写画面代码。** 定稿后写 STATUS.md，并告诉用户：“直接说『进入阶段 B』就行”。

### B. 画面 → `videos/<名>/scenes.js`
1. 读 `$SKILL/references/engine-api.md`，以及 style-dna 的第 3、4、6 节。用到某个组件时，在 `$SKILL/studio/examples/` 里 grep 范例写法。
2. 按 script.json 里的 `v`，逐个场景写 scenes.js。一次写完整个文件，后续只用 Edit 局部修改。
3. **强制自检（每次写完或改完画面都要做，不需要用户提醒）**：
   - 运行 `--sheet` 出联系表，然后 Read 这张图。
   - 对照 style-dna 第 6 节的清单逐条检查：钩子、标题时间、焦点、安全区、遮挡、文字溢出、没有蓝色。
   - 有问题就修，修完再出一次联系表确认。最多 2 轮。
   - 自检通过后，用一两句话告诉用户你检查了什么、修了什么。
4. 运行 `--preview`（带配乐），告诉用户预览路径，然后更新 STATUS.md。

### C. 迭代 + 成片
1. 用户按**节拍 id 或时间点**提意见。
2. 只改对应的位置：文案和时长改 script.json，画面用 Edit 改 scenes.js 里对应的几行。
3. 改完照样自检，但只看改动的地方：`--sheet --at <那几个时间点>`。然后再出 `--preview`，更新 STATUS.md。
4. 用户确认后：先正式渲染（`node RENDER videos/<名>`），再 `--cover` 出封面。交付 `videos/<名>/out/<名>.mp4` 和 `out/cover.jpg`。

## 命令执行规则（避免卡住）

- `--timing`、`--sheet`、`--cover`：前台运行，几秒到几十秒。
- `--preview`：前台运行，Bash 的 timeout 设成 600000。
- **正式渲染**：耗时约为视频时长的 4 倍，可能超过 10 分钟。**用后台运行（run_in_background）**，完成后再交付。
- **绝不自己运行 `--serve`**：它是给用户在另一个终端边看边定位用的，不会自动结束，会把对话卡住。
- 命令报错时会打印 JS 错误栈和行号，按报错修，不要反复重跑同一条命令。

## 省 token 硬规则

1. **不读** `$SKILL/studio` 里 engine、tools 的源码，API 都在 engine-api.md 里。
2. **不看**参考视频，也不重新分析风格。只有用户明确要“学习新参考”时，才运行 `node "$SKILL/studio/tools/analyze_ref.mjs" 视频.mp4`，并且只看它生成的联系表和 report.txt。
3. **不整文件重写** scenes.js 或 script.json，用 Edit 做局部修改。
4. **看图只看联系表**：一张约 1.5k token。不逐帧截图，不看 mp4。查细节用 `--sheet --at t1,t2 --w 960`。
5. 先 `--timing`（纯文本），确实需要时才 `--sheet`（出图）。正式渲染只在用户确认之后做一次。
6. **复用组件**，不发明新特效（style-dna 3.2 节列出了全部可用组件）。
7. 回复要简短：说清楚改了什么，附上文件路径，不要把代码贴回对话里。

## 账号偏好（用户明确要求）

- 默认用暖色暗场：`gilt` 黑棕鎏金加桌面光池，或 `ember` 炭黑琥珀。**不要用蓝色背景。**
- 声音要舒缓：自动配乐，加极少量柔和音效。

## 声音（script.json 的 meta 里配置，默认值已经可用）

- `music`：默认 `"piano"`，按视频时长自动生成舒缓配乐。可以改成 `"ambient"` 或 `"none"`。`musicSeed: <数字>` 可以换一段旋律。
- `bgm: "music.mp3"`：用用户自己的音乐（放在项目目录里），优先级高于自动配乐。`bgmGain` 调音量，默认 0.6。
- `sfx`：默认 `"soft"`，只在标题、盖章、碎裂处有轻柔音效。可选 `"off"`、`"manual"`、`"full"`。
- 成片会自动响度标准化，到 -16 LUFS。

## 发布建议（交付时提醒用户）

- 视频是 16:9 横屏，1080p，自带配乐。想用抖音热门 BGM 的话，发布时选“使用同款”，把原声调到 0–30%。
- 标题参考：`Vibe知识大赏｜<钩子句>`，再加话题标签。具体规则以抖音 App 当期活动为准。封面用 `out/cover.jpg`。
