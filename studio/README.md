# Vibe Studio：知识短片生产线

**Claude 写 HTML 动画 → 无头浏览器逐帧截图 → ffmpeg 合成 MP4（自动配乐 + 柔和音效）。**
风格规则和流程在 skill 里：`.claude/skills/vibe-knowledge-video/`。本地怎么用，看仓库根目录的 **`使用指南.md`**。

```
studio/
├─ engine/        引擎：index.html + engine.js + engine.css（Claude 不需要读源码）
├─ tools/
│  ├─ render.mjs     渲染 / 预览 / 联系表 / 封面（会自动调用 music.mjs）
│  ├─ music.mjs      舒缓配乐生成器（纯 Node，按视频时长生成）
│  ├─ make_sfx.py    重新生成柔和音效库（一般用不到）
│  └─ analyze_ref.sh 学习新参考视频（联系表 + 音频报告）
├─ sfx/           柔和音效库
└─ videos/
   ├─ brachistochrone/  完整范例《最速降线》(53s)
   ├─ _showcase/        风格样片：几种暖色调 + 全部特效（40s）
   └─ <你的新视频>/     script.json（文案+分镜） + scenes.js（画面） + out/（产物）
```

## “无头浏览器逐帧截图”具体是怎么回事

“无头浏览器”就是**没有窗口的 Chrome**：它照样能打开网页、排版、画动画，只是不显示在屏幕上，由程序控制。运行 `node studio/tools/render.mjs videos/xxx` 时，背后依次发生这些事：

1. 在本机启动一个小网页服务器，把 `engine/index.html` 和你的 `script.json`、`scenes.js` 组装成一个动画网页。
2. 用 Playwright 打开一个看不见的 Chromium 浏览器，窗口固定为 1920×1080，加载这个网页。
3. **逐帧截图**：动画本身不会“自己播放”。程序先说“跳到第 0.000 秒”，截一张图；再说“跳到第 0.033 秒”，再截一张。30 帧/秒的视频，1 分钟就是 1800 张。
4. 截图一边产生，一边交给 ffmpeg 编码成 H.264 视频。
5. 生成配乐（长度和视频对齐），叠加柔和音效，统一响度，输出 `out/<名>.mp4`。

和“自己录屏”比：每一帧都是精确算出来的，不会掉帧，没有鼠标和浏览器边框，分辨率固定。改一个字之后重跑一条命令就能出新片，不用再录一遍。这一切由 Claude 执行命令完成，你不需要手动操作浏览器。

## 常用命令（在仓库根目录运行）

```bash
node studio/tools/render.mjs --serve                     # 浏览器实时预览（空格播放，←→ 跳 1 秒，底部显示节拍 id）
node studio/tools/render.mjs videos/bayes --timing       # 时间表
node studio/tools/render.mjs videos/bayes --sheet        # 联系表 out/sheet-1.jpg
node studio/tools/render.mjs videos/bayes --preview      # 快速预览 out/preview.mp4（带配乐）
node studio/tools/render.mjs videos/bayes                # 正式版 out/bayes.mp4（1080p30）
node studio/tools/render.mjs videos/bayes --cover        # 封面 out/cover.jpg
bash studio/tools/analyze_ref.sh 新参考.mp4               # 学习新参考视频
```

## 声音设置（写在 script.json 的 meta 里，不写就用默认值）

| 字段 | 默认 | 说明 |
|---|---|---|
| `music` | `"piano"` | 自动生成的舒缓钢琴配乐。可选 `"ambient"`（更空灵）、`"none"`（不要配乐） |
| `musicSeed` | 按项目名生成 | 换一个数字，就换一段旋律 |
| `bgm` | 无 | 用自己的音乐文件（放在项目目录里），优先级高于自动配乐 |
| `sfx` | `"soft"` | 只在标题、盖章、碎裂时有轻柔音效。可选 `"off"`、`"manual"`、`"full"` |
