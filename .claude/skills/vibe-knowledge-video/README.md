# Vibe 知识短片 skill：安装与使用

用 Claude Code 做“Vibe知识大赏”风格的抖音知识短片：黑金暗场、衬线字、粒子标题、字幕代替配音、舒缓配乐，16:9 横屏。
这个文件夹是完整的 skill，引擎、渲染器、配乐、音效、范例都在里面，**不需要 GitHub**。

---

## 一、装 3 个软件（只做一次）

| 软件 | Windows（PowerShell 里运行） | Mac（终端里运行） |
|---|---|---|
| Node.js | `winget install OpenJS.NodeJS.LTS` | `brew install node` |
| ffmpeg | `winget install Gyan.FFmpeg` | `brew install ffmpeg` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` | 同左 |

- Mac 没有 brew 的话，先到 https://brew.sh 安装。
- 装完**关掉终端重新打开**。
- 国内装 npm 包慢的话，先运行：`npm config set registry https://registry.npmmirror.com`

## 二、把 skill 放到 Claude Code 的个人 skill 目录（只做一次）

假设 zip 下载到了“下载”文件夹：

**Windows（PowerShell）**
```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Expand-Archive "$HOME\Downloads\vibe-knowledge-video.zip" -DestinationPath "$HOME\.claude\skills" -Force
```

**Mac（终端）**
```bash
mkdir -p ~/.claude/skills
unzip -o ~/Downloads/vibe-knowledge-video.zip -d ~/.claude/skills
```

放好之后，下面这个文件必须存在。注意不要多套一层文件夹：
- Windows：`C:\Users\<你的用户名>\.claude\skills\vibe-knowledge-video\SKILL.md`
- Mac：`~/.claude/skills/vibe-knowledge-video/SKILL.md`

## 三、第一次使用

1. 新建一个专门放视频的文件夹，比如 `D:\抖音视频` 或 `~/抖音视频`。
2. 在终端里进入这个文件夹，启动 Claude Code：
   ```
   cd D:\抖音视频        （Mac：cd ~/抖音视频）
   claude
   ```
3. 输入 `/model`，选 Opus 5.5。
4. 输入：
   ```
   /vibe-knowledge-video 初始化：运行安装自检，并渲染内置范例的预览给我看
   ```
   Claude 会自动安装依赖（字体、动画库等，约 100MB；本机有 Chrome 或 Edge 就不用另外下载浏览器），然后渲染一个范例。
   - 弹出“是否允许运行命令”时，选 **Yes, and don't ask again**，以后渲染就不会再问了。
   - 如果提示缺 ffmpeg，按提示装好后再说一次“重新运行安装自检”。

## 四、每期视频怎么做

在你的视频文件夹里运行 `claude`，然后：

**① 写文案**
```
/vibe-knowledge-video 做一期新视频，选题：贝叶斯定理，项目名 bayes。先只做阶段 A。
```
Claude 会给你看文案和时长表。直接用中文改，满意后说“文案定稿”。

**② 清空上下文**：输入 `/clear`。文案已经存进 `videos/bayes/script.json`，不会丢。

**③ 做画面**
```
/vibe-knowledge-video 做 videos/bayes 的阶段 B
```
Claude 会写画面、自己出拼图检查并修改，然后渲染预览。打开 `videos/bayes/out/preview.mp4` 看效果。

**④ 改稿**：用时间点或节拍编号，一次把意见说完。例如：
```
0:24 停太久；c3 的图放大一倍；结尾换一段旋律
```

**⑤ 成片**：说“可以了，渲染正式版和封面”，然后到 `videos/bayes/out/` 里拿 `bayes.mp4` 和 `cover.jpg`。

**边看边定位**（可选）：另开一个终端，在视频文件夹里运行下面的命令（Mac 路径换成 `~/.claude/skills/...`）：
```
node "C:\Users\<你>\.claude\skills\vibe-knowledge-video\studio\tools\render.mjs" --serve
```
浏览器打开它打印出来的地址，底部会显示当前节拍编号和字幕。

## 五、常见问题

| 现象 | 解决 |
|---|---|
| 输入 `/vibe` 看不到这个 skill | 检查 `SKILL.md` 的位置是否和第二节说的完全一致，然后重启 `claude` |
| 提示缺 ffmpeg / 找不到浏览器 | 跟 Claude 说“重新运行安装自检”，按提示处理 |
| 画面上的字是方块 | 依赖没装好，重新运行安装自检 |
| 想用自己的音乐 | 把 mp3 放进 `videos/<名>/`，跟 Claude 说“用 xxx.mp3 当配乐” |
| 想换 skill 新版本 | 用新 zip 覆盖解压即可。`studio/node_modules` 可以保留，不用重装 |

## 六、文件夹里有什么

```
vibe-knowledge-video/
├─ SKILL.md            给 Claude 看的流程和规则
├─ README.md           本说明（给你看）
├─ references/         风格基因、文案指南、引擎 API（Claude 按需读取）
└─ studio/
   ├─ engine/          动画引擎
   ├─ tools/           render.mjs 渲染 · music.mjs 配乐 · setup.mjs 安装自检 · analyze_ref.mjs 学习新参考
   ├─ sfx/             柔和音效
   └─ examples/        范例：brachistochrone《最速降线》、showcase 风格样片
```
