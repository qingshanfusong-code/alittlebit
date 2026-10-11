# 第三步：写 scenes.js（引擎 API 速查）

**不要读 `studio/engine/engine.js` 源码**，这份速查已经够用。
完整范例：`studio/videos/brachistochrone/scenes.js`（一个完整视频）和 `studio/videos/_showcase/scenes.js`（全部组件、五种色调各一段）。要用某个组件时，先 grep 范例里的用法，照着写。

## 0. 心智模型

- 字幕、标题卡、章节标签、年代牌、出处、水印、浮尘、颗粒、色调切换、场景交叉淡化，**全部由引擎根据 script.json 自动完成**。scenes.js 只写“画面隐喻”。
- 每个场景名对应一个函数 `SCENES.<名> = c => { … }`，在启动时执行一次，作用是**把元素建好，把动画排进时间轴**。不是逐帧回调。
- 时间一律用**绝对秒数**，从节拍取：`c.at('q3', .7)` 表示节拍 q3 开始后 0.7 秒。
- 画布是 1920×1080，坐标用 px。场景层在字幕和外壳层的下面。
- **确定性**：同一个 t 必须渲染出同一帧。禁止使用 `Math.random`（用 `c.rand()`）、`setTimeout`、`requestAnimationFrame`、CSS transition / animation、`Date.now()`。

## 1. 建元素

| API | 说明 |
|---|---|
| `c.h(html)` | 把 HTML 字符串插进场景层，返回元素（多个根节点时返回数组）。元素用 `position:absolute` 加 left/top 定位 |
| `c.svg(markup)` | 插一张全屏 SVG（viewBox 0 0 1920 1080），返回 svg 元素。查子元素用 `s.querySelector('#id')` |
| `c.place(el, x, y, anchor='center')` | 把元素的锚点放到 (x, y)。anchor 可选 center、left、right、top、bottom、tl |
| `c.$(sel)` / `c.$$(sel)` | 在本场景内查找元素 |
| `c.fig(x, y, h=140, pose, {color, cls, opacity})` | 返回小人的 SVG 字符串。pose 可选 `stand`、`walk`、`raise`（举手） |
| `c.lamp(x, y, {cord, w, cone, len, color, beam})` | 返回吊灯加光锥的 SVG 字符串（R1 母题） |
| `c.bgWord(text, {y, at, opacity=.07, size})` | 背景里的巨型外文铭文 |

常用 CSS 类：`.big`（Cormorant 大数字或外文）、`.label`（小注释）、`.label.la`（斜体外文注释）、`.card`（羊皮纸卡片）、`.glowdot`（发光点）、`.stamp`（印章，一般用 `c.stamp()`）。
颜色用主题变量：`var(--ink)` 正文色、`--dim` 次要色、`--accent` 强调色、`--accent2` 次强调色、`--seal` 印章红、`--glow` 光晕色。**SVG 里写成 `style="stroke:var(--accent)"`**，属性 `stroke="var(--…)"` 不生效。

## 2. 动画（全部返回 c，可以链式调用）

| API | 说明 |
|---|---|
| `c.show(el, at, dur=.8, {y=18, blur, scale, stagger, opacity})` | 淡入，同时从下方升起并去模糊 |
| `c.hide(el, at, dur=.6, {stagger, y})` | 淡出加模糊 |
| `c.draw(pathEls, at, dur=1.4, {stagger, ease, reverse})` | 描出 SVG 线条（line、path、circle、polyline 都可以） |
| `c.to(el, vars, at)` / `c.fromTo(el, from, to, at)` / `c.set(el, vars)` | 原生 GSAP 补间，vars 里写 `duration` 和 `ease` |
| `c.camera(at, dur, {scale=1.12, x, y, rotation, origin, ease, target})` | 推镜头，默认作用于整个场景层 |
| `c.counter(el, from, to, at, dur=1.2, {decimals, prefix, suffix, ease, sep})` | 数字滚动 |
| `c.rollChars(el, ['雨','雪',…,'光'], at, dur=1.4)` | 竖排滚字，停在最后一个字，自动带嘀嗒声 |
| `c.stamp(text, x, y, at, {rotate=-8, size, solid})` | 红色印章砸下，屏幕轻震，自动带音效。返回印章元素 |
| `c.ripple(x, y, at, {count=3, r=160, color, width, sfx})` | 涟漪圈 |
| `c.burst(x, y, at, {kind:'dust'|'confetti'|'shards', count, colors, speed, spread, angle, gravity, dur, sfx})` | 粒子爆发：尘埃、彩屑或碎片 |
| `c.dissolve(el, at, {dur=2, count, color, sweep, drift, sfx})` | 元素从左到右化成灰烬（R1/R3） |
| `c.shatter(el, at, {cx, cy, cols, rows, dur, crack, force})` | 先出裂纹（提前 0.7 秒）再碎成三角碎片。**只能用于 HTML 绝对定位元素** |
| `c.particlesText(text, {x, y, size, weight, at, dur, color, dotted, fadeAt})` | 粒子聚成文字（标题卡已自动做，这里是给其他大字用的） |
| `c.sfx(name, at, gain=1)` | 在 at 秒放音效：tick、whoosh、shimmer、boom、stamp、crack、shatter、riser、heart |
| `c.onFrame(t => {…})` | 每帧回调（t 是绝对秒数），用来做物理运动、路径生长、钟表。**必须是 t 的纯函数** |
| `c.drawCanvas((t, ctx2d) => {…})` | 在场景画布上自绘（画布每帧会先清空） |
| `c.prog(t, at, dur, ease)` | onFrame 里常用：返回 0→1 的进度。ease 可选 linear、in、out、inOut、outBack、outExpo |
| `c.color('var(--accent)')` | 把主题变量解析成实际颜色。**GSAP 不能直接补间 `var(--x)`**，要先用它转换 |
| `c.rand()` | 用场景名做种子的确定性随机数 |

GSAP 常用 ease：`power2.out`（进场）、`power2.inOut`（移动）、`power1.in`（离场）、`none`（匀速）。

## 3. 常用写法

```js
// 场景函数：c.at() 取节拍时间，元素建好后排动画
SCENES.race = c => {
  const s = c.svg(`<path id="cyc" d="M660 380 C …" fill="none" style="stroke:var(--accent);stroke-width:4"/>
                   <circle id="ball" r="14" style="fill:var(--accent)" opacity="0"/>`);
  c.draw(s.querySelector('#cyc'), c.at('q1', 1.5), 1.6);                 // 描线
  const tag = c.h(`<div class="label">先陡</div>`); c.place(tag, 700, 420);
  c.show(tag, c.at('q4', .3));
  const go = c.at('q3', .7);
  c.onFrame(t => {                                                          // 物理运动：纯函数
    const th = Math.min(Math.PI, Math.max(0, t - go) * Math.PI / 2);
    s.querySelector('#ball').setAttribute('cx', 660 + 190 * (th - Math.sin(th)));
  });
};
```

## 4. 坑（都踩过）

1. **带 `transform` 属性的 SVG 元素不要补间 x、y**，GSAP 会覆盖原有的平移，元素会飞走。外面包一层 `<g>`，动画加在没有 transform 属性的那一层上（`c.fig()` 已经这样处理）。
2. SVG 里 `<defs>` 的 id（滤镜、渐变）在整个页面是全局的，**不同场景要用不同的 id**，比如 `glR`、`glV`。
3. `c.shatter()` 只能用于 HTML 元素：照片、卡片用 div 来做。
4. 同一个场景名如果不连续出现（中间夹了别的场景），函数会被执行两次，生成两套元素。
5. 不要让主体压到安全区：底部字幕 880–1010px；headline 大字 150–430px；左上 64–420 × 40–260；右上 1500–1860 × 40–230。
6. 新元素默认就是可见的。需要入场动画的元素，用 `c.show()`（它会先把元素设成透明），或者先 `c.set(el, {opacity:0})`。

## 5. 命令（在 `studio/` 目录下运行）

```bash
node tools/render.mjs videos/<名> --timing            # 节拍时间表（纯文本，最省）
node tools/render.mjs videos/<名> --sheet             # 每个节拍一格的联系表 → out/sheet-1.jpg（16 格一张）
node tools/render.mjs videos/<名> --sheet --at 9.5,10.2,11 --w 960   # 指定时间点，放大看细节
node tools/render.mjs videos/<名> --preview           # 960×540@15fps 预览，约 15 秒出片
node tools/render.mjs videos/<名> --from 20 --to 32   # 只渲染一段
node tools/render.mjs videos/<名>                     # 正式版 1080p30（约为视频时长的 4 倍时间）
node tools/render.mjs videos/<名> --cover             # 封面图（标题卡定格）
node tools/render.mjs --serve                         # 浏览器实时预览：空格播放，←→ 跳 1 秒
```

页面报错时，渲染命令会打印出 JS 错误栈和行号。直接按报错去修，不要猜。
