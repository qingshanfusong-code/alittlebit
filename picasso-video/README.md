# 毕加索 · 画框穿越（16:9 横屏）

成片：`picasso_frames_16x9.mp4`（1920×1080，30 fps，14.9 秒，H.264 + AAC）
封面：`cover.jpg`

参考了两个"名画画框穿越"视频（梵高《星月夜》《向日葵》），剪辑手法和音频节奏一比一复刻，画作换成了毕加索。

## 剪辑思路

- **母题：画中有画，画外还有画。** 先让人钻进《缪斯》里，画里飘着另一幅画；镜头一拉远，原来整幅《缪斯》只是挂在"毕加索蓝"墙上的一幅画；再横移到他 1907 年的自画像，头发从画框里探出来；最后画飞走，立体主义碎片和画家本人从底部升起。
- **节奏完全按参考：** 96 BPM，每小节 2.5 秒，重拍落在 1.75 + 2.5k 秒；1.9–3.0 秒全静音"急停"，4.25 秒进入 drop。每个大动作都比重拍提前约 0.2 秒起步，正好落在拍子上。
- **墙面选"毕加索蓝"：** 和《自画像》的赭黄色互补（参考里是红墙衬蓝色《星月夜》），也呼应他的"蓝色时期"。
- **结尾拼贴用立体主义碎片代替参考里的向日葵：** 碎片从三幅画上切下来，描黑色轮廓线，还混进了毕加索拼贴画真实用过的材料：报纸"JOU(RNAL)"、仿木纹纸、藤椅编织纹。

## 分镜表

| 时间 | 拍点 | 画面 | 手法 |
|---|---|---|---|
| 0.00–0.55 | 前奏起 | 《缪斯》(1935) 满屏，缓慢推近 | 慢推 (Ken Burns) |
| 0.55–1.05 | — | 小画框《坐着的裸女》(1909–10) 从左下浮入画中 | 3D 透视 + 投影 + 淡入回弹 |
| 1.05–4.05 | 1.75 重拍 → 急停 → 3.0 回来 | 小画框在画中缓慢转动，露出木框厚度 | 3D 旋转（Y 轴 −30°→−52°） |
| 4.05–6.42 | 4.25 drop | 急速拉远：《缪斯》原来挂在蓝墙上的金色雕花画框里；左上角浮现 "LA MUSE · 1935" | 对数缩放 + 缩放动态模糊 + whoosh |
| 6.42–7.45 | 6.75 第 2 小节 | 横移换画：《自画像》(1907) 进入，头发冲出黑漆金边画框 | 甩镜横移 + 运动模糊 + 出框 (out of bounds) |
| 7.45–8.98 | — | 自画像停住，竖排 "PABLO PICASSO"、"AUTOPORTRAIT · 1907" | 缓慢漂移 |
| 8.98–9.62 | 9.25 第 3 小节 | 自画像旋转飞出右上；碎片从左到右依次升起，画家从左下升起 | 加速飞出 + 错峰回弹 |
| 10.42–11.2 | 10.5 军鼓 | 标题 PABLO / **PICASSO** / 1881 — 1973 逐字升起 | 逐字错峰 + 字距展开 + 线条延伸 + 叮声 |
| 11.2–14.43 | 11.75、14.25 | 拼贴定格，整体缓慢推近，碎片轻微浮动 | 慢推 |
| 14.43–14.9 | 循环 | 切回《缪斯》特写并拉远到开场构图 | 无缝循环 |

## 音频

参考里的 BGM 是一首有版权的人声歌曲，所以这里没有直接使用，而是按它的结构原创合成了一首（`tools/music.py`）：

- 96 BPM，A 大调 / 升 f 小调（和原曲同调）
- 0.2 秒起拍的人声感旋律 → 1.75 秒重拍 → **1.9–3.0 秒全静音急停** → 808 下滑过门 → 4.25 秒 drop
- drop 四小节 F#m–D–A–E：808 + 底鼓，第三拍拍手（half-time），八分/十六分踩镲，Rhodes 电钢琴和弦，共振峰合成的"人声"主旋律
- 音效和画面对齐：小画框浮入、拉远、横移、飞出各有一个 whoosh，碎片落位有轻微 thump，标题出现时有一声叮
- 频段能量和参考曲对比，各段差距都在 2 dB 以内

**想用原曲？** 发布时在抖音里点"使用同款音乐"换上参考视频的原声就行。时间轴是按原曲的节拍网格做的（重拍 1.75 + 2.5k 秒、1.9–3.0 秒急停），换上后剪辑点依然全部对齐。

## 画作与版权

| 画作 | 年份 | 用途 |
|---|---|---|
| 《缪斯》La Muse，蓬皮杜中心 | 1935 | 开场主画 / 墙上第一幅 |
| 《坐着的裸女》Seated Nude，泰特美术馆 | 1909–10 | 画中漂浮的小画框、碎片 |
| 《自画像》Self-Portrait，布拉格国家美术馆 | 1907 | 墙上第二幅（头发出框）、结尾抠像 |

图片取自公开的风格迁移示例仓库（jcjohnson/fast-neural-style、jcjohnson/neural-style、xunhuang1995/AdaIN-style），并用 EDSR 超分模型放大 2 倍（`tools/upscale.py`）。

毕加索于 1973 年去世。中国大陆的著作权保护期是作者终生加 50 年，所以他的作品在大陆已于 2024 年进入公有领域，发抖音没有问题。欧盟和美国的保护期更长（《缪斯》在欧盟要到 2043 年才过期），如果要发到 TikTok、YouTube 等海外平台，请自行评估风险。

## 重新渲染

需要 Python 3（numpy、Pillow、opencv-contrib-python-headless、scipy）和 ffmpeg。素材放在 `work/`（也可以用环境变量 `PICASSO_WORK` 指定其他目录）：

```
work/dl/la_muse_fns.jpg          # fast-neural-style/images/styles/la_muse.jpg
work/dl/seated_nude_hr.jpg       # AdaIN-style/input/style/picasso_seated_nude_hr.jpg
work/dl/self_portrait_adain.jpg  # AdaIN-style/input/style/picasso_self_portrait.jpg
work/models/EDSR_x2.pb           # Saafke/EDSR_Tensorflow/models/EDSR_x2.pb
work/fonts/{oswald,playfair-display}/package/...   # npm: @fontsource/oswald, @fontsource/playfair-display
```

```bash
python3 tools/upscale.py work/models/EDSR_x2.pb work/dl/self_portrait_adain.jpg work/assets/selfport_adain_x2.png \
                                                work/dl/la_muse_fns.jpg work/assets/muse_x2.png
python3 tools/assets.py cutout                  # 自画像抠像 -> work/assets/selfport_cut.png
python3 tools/music.py work/music.wav           # 原创配乐
python3 tools/render.py --sheet check.jpg --at 0.8,4.4,7.9,12   # 预览关键帧
python3 tools/render.py --out out.mp4 --audio work/music.wav    # 成片（约 10 分钟）
```

`tools/render.py` 开头的 `T_*` 常量就是全部转场时间点，想改节奏只需要改这几个数。
