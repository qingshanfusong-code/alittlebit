# Vibe Studio：知识短片生产线

**HTML 动画 → 逐帧确定性渲染 → MP4**。风格规则和流程写在 skill 里：`.claude/skills/vibe-knowledge-video/`。

```
studio/
├─ engine/        引擎：index.html + engine.js + engine.css（Claude 不需要读）
├─ tools/
│  ├─ render.mjs     渲染 / 预览 / 联系表 / 封面
│  ├─ make_sfx.py    生成基础音效库
│  └─ analyze_ref.sh 学习新参考视频（联系表 + 音频报告）
├─ sfx/           音效库（tick whoosh shimmer boom stamp crack shatter riser heart）
└─ videos/
   ├─ brachistochrone/  完整范例《最速降线》(53s)
   ├─ _showcase/        风格样片：五种色调 + 全部组件（40s）
   └─ <你的新视频>/     script.json（文案+分镜） + scenes.js（画面）
```

## 安装

**云端 Claude Code（claude.ai/code）**：在 `studio/` 下运行 `npm install`，其他都已经装好。

**本地电脑**（Mac / Windows / Linux）：需要 Node 20 以上和 ffmpeg。
```bash
cd studio
npm install                       # 国内慢的话：npm config set registry https://registry.npmmirror.com
npx playwright install chromium   # 国内可以先设置 PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
```
字体（思源宋体、Cormorant Garamond）和 GSAP 都从 npm 本地加载，不依赖 Google Fonts 或 CDN。

## 每个视频怎么做：三个 session，每个阶段复制一句话

**① 脚本**（新开 session）
> 用 vibe-knowledge-video skill 做一期新视频，选题：贝叶斯定理（“听劝”的数学）。先只做阶段 A：写 studio/videos/bayes/script.json，给我看文案和时长表。

改文案就直接说：“q2 换成更口语的说法”“结尾金句再狠一点”。定稿后进入下一步。

**② 画面**（新开 session）
> 用 vibe-knowledge-video skill，做 videos/bayes 的阶段 B：按 script.json 写 scenes.js，自检联系表，然后出预览给我。

**③ 改稿 + 成片**（可以接着 ② 的 session）
> c3 的天平太小；0:24 停太久；e2 换成 crimson 色调。改完出预览。

> 可以了，渲染正式版和封面。

## 常用命令（在 studio/ 下运行）

```bash
node tools/render.mjs --serve                          # 浏览器实时预览所有项目（空格播放）
node tools/render.mjs videos/bayes --timing            # 时间表
node tools/render.mjs videos/bayes --sheet             # 联系表 out/sheet-1.jpg
node tools/render.mjs videos/bayes --preview           # 快速预览 out/preview.mp4
node tools/render.mjs videos/bayes                     # 正式版 out/bayes.mp4（1080p30）
node tools/render.mjs videos/bayes --cover             # 封面 out/cover.jpg
bash tools/analyze_ref.sh 新参考.mp4                    # 学习新参考视频
```

## 发布

1. 上传 `out/<名>.mp4`（16:9 横屏）和 `out/cover.jpg`。
2. 在抖音里加 BGM：参考视频里有 4 个用的是同一首钢琴曲，点参考视频的音乐，选“使用同款”。原声（音效）音量调到 50–70%。
3. 标题参考：`Vibe知识大赏｜<钩子句>`，加相关话题标签。活动规则以 App 里当期话题为准。
