# 油画活化（细腻化 + 动起来）

从参考视频（墨尔温的梵高《星月夜》《向日葵》画框穿越）学到的画面风格，做成了可复用的工具 `livepaint.py`。

## 学到的风格

1. **细腻化 / AI 重绘感**：笔触是干净、顺滑、饱满的长条厚涂，没有原图的噪点和画布颗粒；每一笔有柔和的立体高光；整体偏亮（high-key），白色像奶油，暗部偏冷但保留深蓝。
2. **会动的是笔触本身**：去掉镜头运动后，《星月夜》整片天空仍在沿漩涡方向流动（约 15–20 px/0.25 s @1080p），月亮和星星在旋转；拼贴里的向日葵左右轻摆。房屋、人物等实体保持不动。
3. **循环**：结尾切回开头特写，画面本身的动态也要能无缝循环。

## 做法

| 步骤 | 实现 |
|---|---|
| 去 JPEG 噪点 | `fastNlMeansDenoisingColored` |
| 超分 | EDSR ×2 / ×4（OpenCV dnn_superres，分块） |
| 笔触重绘 | 结构张量求每个像素的笔触方向，沿方向做线积分卷积（LIC），让笔触变成顺滑的长条 |
| 厚涂光影 | 沿笔触平滑的高度场 → 法线 → 左上方打光 + 柔和高光 |
| 调色 | `natural`（干净鲜艳）/ `luminous`（参考同款：高调、奶白、冷暗部） |
| 动态 | 按区域配置：`flow` 沿笔触流动（flow-map 双相位交叉淡化，无缝循环），`sway` 植物摇摆，`ripple` 水波，`breathe` 呼吸缩放，`twinkle` 星光/灯光闪烁 |

## 用法

```bash
# 模型：Saafke/EDSR_Tensorflow 的 models/EDSR_x2.pb、EDSR_x4.pb 放到 living-painting/models/
python3 livepaint.py enhance 原画.jpg 细化.png --long 2560 --preset luminous   # 细腻化
python3 livepaint.py field   细化.png spec.json field.jpg --layer 0              # 检查流向
python3 livepaint.py animate 细化.png spec.json 活化.mp4 --width 1920 --seconds 6
```

`examples/starry_night.json` 是《星月夜》的动态配置：天空沿漩涡流动，月亮和大星星单独旋转，山丘缓慢右移，柏树向上流动并轻摆，星光和窗灯闪烁。每幅新画都要按它的内容画区域（归一化坐标多边形）、选动态类型。
