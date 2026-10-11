/* ============================================================
   Vibe 知识短片引擎（确定性时间轴）
   - 一切画面都是时间 t 的纯函数：window.__seek(t) → 渲染那一帧
   - script.json 负责“说什么、何时说”；scenes.js 只负责“画什么”
   - API 速查见 .claude/skills/vibe-knowledge-video/references/engine-api.md
   ============================================================ */
(() => {
'use strict';
const W = 1920, H = 1080, XF = 0.8;           // 画布尺寸、场景交叉淡化时长
const QS = new URLSearchParams(location.search);
const RENDER = QS.has('render');
window.SCENES = window.SCENES || {};

/* ---------------- 工具 ---------------- */
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, p) => a + (b - a) * p;
const EASE = {
  linear: p => p,
  in: p => p * p * p,
  out: p => 1 - Math.pow(1 - p, 3),
  inOut: p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  outBack: p => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
  outExpo: p => (p === 1 ? 1 : 1 - Math.pow(2, -10 * p)),
};
const prog = (t, at, dur, ease = 'linear') => (typeof ease === 'function' ? ease : EASE[ease])(clamp((t - at) / dur));
function rng(seed = 1) {
  let a = (seed * 2654435761) >>> 0;
  return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const hash = s => { let h = 7; for (const ch of String(s)) h = (h * 31 + ch.codePointAt(0)) >>> 0; return h; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const plainLen = s => (s || '').replace(/\*\*/g, '').replace(/\s/g, '').length;
const isSvg = el => el instanceof SVGElement;
function mk(tag, cls, parent, html) {
  const e = document.createElement(tag); if (cls) e.className = cls;
  if (html != null) e.innerHTML = html; if (parent) parent.appendChild(e); return e;
}
function loadScript(src) {
  return new Promise(res => { const s = document.createElement('script'); s.src = src;
    s.onload = () => res(true); s.onerror = () => res(false); document.head.appendChild(s); });
}

/* ---------------- 全局状态 ---------------- */
let floorEl, stage, scenesRoot, titlesRoot, chromeRoot, subsRoot, fxCanvas, grainCanvas, flashEl, bgPaper;
let tl, meta, beats, byId = {}, groups = [], duration = 0, S = 1;
const frameFns = [];      // (t) => void，每帧调用
const sceneCanvases = []; // {g, cv, drawers}
const measures = [];      // {at, fn} 字体就绪后、在时间 at 处测量布局
const fontNeeds = [];     // {weight, text}
const cues = [];          // 音效 {t, name, gain}
const themeSwitches = []; // {at, theme}
let colorCache = {};

function cssColor(c) {    // 支持 'var(--accent)' 这类写法
  if (!c) return '#fff';
  const m = /^var\((--[\w-]+)\)$/.exec(c.trim());
  if (!m) return c;
  return colorCache[m[1]] || (colorCache[m[1]] = getComputedStyle(stage).getPropertyValue(m[1]).trim() || '#fff');
}
function stageRect(el) {
  const r = el.getBoundingClientRect(), s = stage.getBoundingClientRect();
  return { x: (r.left - s.left) / S, y: (r.top - s.top) / S, w: r.width / S, h: r.height / S };
}
// 音效分级：key=关键时刻（标题/盖章/碎裂）、detail=细节（嘀嗒/裂纹/化灰/反转）、manual=场景里手动指定
// meta.sfx："soft"（默认：key+manual）| "full"（全部）| "manual"（只要手动的）| "off"（无音效）
function sfx(name, at, gain = 1, tier = 'manual') {
  const mode = meta.sfx ?? (meta.autoSfx === false ? 'manual' : 'soft');
  if (!name || mode === 'off' || (tier === 'detail' && mode !== 'full') || (tier === 'key' && mode === 'manual')) return;
  cues.push({ t: Math.max(0, at), name, gain });
}

/* ---------------- 节拍时长：字数自动计算 ---------------- */
function beatDur(b) {
  let d = b.dur;
  if (d == null) {
    if (b.type === 'title') d = 4.6;
    else if (b.say) d = clamp(0.8 + 0.13 * plainLen(b.say), 2.0, 6.5);
    else d = 2.0;
  }
  return d + (b.hold || 0);
}

/* ---------------- 场景上下文 ctx（scenes.js 使用） ---------------- */
function makeCtx(g, layer) {
  let cv = null, fxsvg = null;
  const q = el => (typeof el === 'string' ? [...layer.querySelectorAll(el)] : Array.isArray(el) ? el : el instanceof NodeList ? [...el] : [el]);
  const canvas = () => {
    if (!cv) { const e = mk('canvas', 'layer', layer); e.width = W; e.height = H;
      cv = { g, el: e, g2d: e.getContext('2d'), drawers: [] }; sceneCanvases.push(cv); }
    return cv;
  };
  const fxSvg = () => {
    if (!fxsvg) { fxsvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      fxsvg.setAttribute('viewBox', `0 0 ${W} ${H}`); fxsvg.setAttribute('class', 'layer'); layer.appendChild(fxsvg); }
    return fxsvg;
  };
  const c = {
    W, H, meta, tl, layer, gsap, EASE, prog, lerp, clamp, rng,
    t0: g.start, t1: g.end, beats: g.beats,
    rand: rng(hash(g.id)),
    at(id, off = 0) { const b = byId[id]; if (!b) throw new Error(`[scene ${g.id}] 未知 beat id: ${id}`); return b.start + off; },
    end(id, off = 0) { const b = byId[id]; if (!b) throw new Error(`[scene ${g.id}] 未知 beat id: ${id}`); return b.end + off; },
    b(i, off = 0) { const b = g.beats[i < 0 ? g.beats.length + i : i]; return b.start + off; },
    q, $: sel => layer.querySelector(sel), $$: sel => [...layer.querySelectorAll(sel)],
    h(html, parent = layer) {
      const tpl = document.createElement('template'); tpl.innerHTML = html.trim();
      const nodes = [...tpl.content.children]; nodes.forEach(n => parent.appendChild(n));
      return nodes.length === 1 ? nodes[0] : nodes;
    },
    svg(inner = '', parent = layer) {
      const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      s.setAttribute('viewBox', `0 0 ${W} ${H}`); s.setAttribute('class', 'layer'); s.innerHTML = inner;
      parent.appendChild(s); return s;
    },
    set(el, v) { gsap.set(q(el), v); return c; },
    to(el, v, at) { tl.to(q(el), v, at); return c; },
    fromTo(el, a, b, at) { tl.fromTo(q(el), a, { ...b, immediateRender: false }, at); return c; },
    place(el, x, y, anchor = 'center') {
      const A = { center: [-50, -50], left: [0, -50], right: [-100, -50], top: [-50, 0], bottom: [-50, -100], tl: [0, 0] }[anchor];
      gsap.set(q(el), { position: 'absolute', left: x, top: y, xPercent: A[0], yPercent: A[1] }); return c;
    },
    show(el, at, dur = 0.8, o = {}) {
      const els = q(el), svg = isSvg(els[0]);
      gsap.set(els, { opacity: 0 });
      const from = { opacity: 0 }, to = { opacity: o.opacity ?? 1, duration: dur, ease: o.ease || 'power2.out', stagger: o.stagger || 0, immediateRender: false };
      // 带 transform 属性的 SVG 元素不能补间 y（GSAP 会覆盖原有平移，元素会飞到顶部）
      if (!(svg && els.some(e => e.hasAttribute('transform')))) { from.y = o.y ?? 18; to.y = 0; }
      if (!svg && o.blur !== false) { from.filter = 'blur(8px)'; to.filter = 'blur(0px)'; }
      if (o.scale) { from.scale = o.scale; to.scale = 1; }
      tl.fromTo(els, from, to, at); return c;
    },
    hide(el, at, dur = 0.6, o = {}) {
      const els = q(el), to = { opacity: 0, duration: dur, ease: o.ease || 'power1.in', stagger: o.stagger || 0 };
      if (!isSvg(els[0]) && o.blur !== false) to.filter = 'blur(8px)';
      if (o.y && !(isSvg(els[0]) && els.some(e => e.hasAttribute('transform')))) to.y = o.y;
      tl.to(els, to, at); return c;
    },
    draw(el, at, dur = 1.4, o = {}) {
      q(el).forEach((p, i) => {
        const len = p.getTotalLength ? p.getTotalLength() + 1 : 2000;
        gsap.set(p, { strokeDasharray: len, strokeDashoffset: o.reverse ? -len : len });
        tl.to(p, { strokeDashoffset: 0, duration: dur, ease: o.ease || 'power2.inOut' }, at + i * (o.stagger || 0));
      });
      return c;
    },
    camera(at, dur, o = {}) {
      tl.to(o.target ? q(o.target) : layer, { scale: o.scale ?? 1.12, x: o.x ?? 0, y: o.y ?? 0, rotation: o.rotation ?? 0,
        transformOrigin: o.origin || '50% 50%', duration: dur, ease: o.ease || 'power2.inOut' }, at);
      return c;
    },
    counter(el, from, to, at, dur = 1.2, o = {}) {
      const e = q(el)[0], d = o.decimals || 0;
      const fmt = v => (o.prefix || '') + (o.sep ? Number(v.toFixed(d)).toLocaleString('en-US', { minimumFractionDigits: d }) : v.toFixed(d)) + (o.suffix || '');
      e.textContent = fmt(from);
      frameFns.push({ g, fn: t => { e.textContent = fmt(lerp(from, to, prog(t, at, dur, o.ease || 'out'))); } });
      return c;
    },
    rollChars(el, chars, at, dur = 1.4, o = {}) {
      const e = q(el)[0], n = chars.length;
      e.innerHTML = `<span style="display:inline-block;height:1.25em;line-height:1.25em;overflow:hidden;vertical-align:bottom"><span style="display:block">${chars.map(ch => `<span style="display:block;height:1.25em">${esc(ch)}</span>`).join('')}</span></span>`;
      const strip = e.firstChild.firstChild;
      frameFns.push({ g, fn: t => { strip.style.transform = `translateY(${-prog(t, at, dur, o.ease || 'out') * (n - 1) * 1.25}em)`; } });
      if (o.sfx !== false) for (let i = 1; i < n; i++) {
        // 每换一个字一声 tick：反解 out 缓动的时间点
        const p = i / (n - 1), u = 1 - Math.cbrt(1 - p); sfx(o.sfx || 'tick', at + u * dur, 0.5, o.sfx ? 'manual' : 'detail');
      }
      return c;
    },
    stamp(text, x, y, at, o = {}) {
      const e = mk('div', 'stamp' + (o.solid ? ' solid' : ''), layer, esc(text).replace(/\n/g, '<br>'));
      if (o.size) e.style.fontSize = o.size + 'px';
      c.place(e, x, y); gsap.set(e, { rotation: o.rotate ?? -8, opacity: 0 });
      tl.fromTo(e, { opacity: 0, scale: 2.6 }, { opacity: 1, scale: 1, duration: .2, ease: 'power4.in', immediateRender: false }, at);
      tl.to(scenesRoot, { keyframes: [{ x: -9, y: 4, duration: .04 }, { x: 7, y: -3, duration: .04 }, { x: -3, y: 1, duration: .05 }, { x: 0, y: 0, duration: .05 }] }, at + .2);
      if (o.sfx !== false) sfx('stamp', at + .17, 1, 'key');
      return e;
    },
    ripple(x, y, at, o = {}) {
      const s = fxSvg(), n = o.count ?? 3;
      for (let i = 0; i < n; i++) {
        const ci = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        ci.setAttribute('cx', x); ci.setAttribute('cy', y); ci.setAttribute('r', 4); ci.setAttribute('fill', 'none');
        ci.setAttribute('style', `stroke:${o.color || 'var(--accent)'};stroke-width:${o.width ?? 2}`); s.appendChild(ci);
        gsap.set(ci, { opacity: 0 });
        tl.fromTo(ci, { attr: { r: 4 }, opacity: .9 }, { attr: { r: o.r ?? 160 }, opacity: 0, duration: o.dur ?? 1.6, ease: 'power2.out', immediateRender: false }, at + i * (o.gap ?? .22));
      }
      if (o.sfx) sfx(o.sfx, at, o.gain ?? .8);
      return c;
    },
    burst(x, y, at, o = {}) {
      const R = rng(o.seed ?? hash(g.id + at)), n = o.count ?? 160, dur = o.dur ?? 2.4, kind = o.kind || 'dust';
      const colors = o.colors || ['var(--accent)', 'var(--ink)'], sp = o.speed || [180, 720], sz = o.size || [1.5, 4];
      const P = Array.from({ length: n }, () => {
        const a = (o.angle ?? 0) + (R() - .5) * (o.spread ?? Math.PI * 2), v = lerp(sp[0], sp[1], R());
        return { vx: Math.cos(a) * v, vy: Math.sin(a) * v, s: lerp(sz[0], sz[1], R()), c: colors[(R() * colors.length) | 0],
          r0: R() * 6.28, vr: (R() - .5) * 14, life: lerp(.55, 1, R()) * dur };
      });
      const k = 1.8, gy = o.gravity ?? 240;
      canvas().drawers.push((t, x2) => {
        const tau = t - at; if (tau < 0 || tau > dur) return;
        for (const p of P) {
          if (tau > p.life) continue;
          const f = (1 - Math.exp(-k * tau)) / k, px = x + p.vx * f, py = y + p.vy * f + .5 * gy * tau * tau;
          x2.globalAlpha = Math.pow(1 - tau / p.life, 1.4); x2.fillStyle = cssColor(p.c);
          if (kind === 'dust') { x2.beginPath(); x2.arc(px, py, p.s, 0, 6.283); x2.fill(); }
          else {
            x2.save(); x2.translate(px, py); x2.rotate(p.r0 + p.vr * tau);
            if (kind === 'confetti') x2.fillRect(-p.s * 1.6, -p.s * .7, p.s * 3.2, p.s * 1.4);
            else { x2.beginPath(); x2.moveTo(0, -p.s * 3); x2.lineTo(p.s * 1.6, p.s * 2); x2.lineTo(-p.s * 1.8, p.s * 1.2); x2.closePath(); x2.fill(); }
            x2.restore();
          }
        }
        x2.globalAlpha = 1;
      });
      if (o.sfx) sfx(o.sfx, at, o.gain ?? .8);
      return c;
    },
    dissolve(el, at, o = {}) {
      const e = q(el)[0], dur = o.dur ?? 2.0, n = o.count ?? 520, R = rng(o.seed ?? hash(g.id + 'dz' + at));
      let P = null;
      measures.push({ at, fn: () => {
        const r = stageRect(e);
        P = Array.from({ length: n }, () => {
          const px = r.x + R() * r.w, py = r.y + R() * r.h;
          return { x: px, y: py, d: ((px - r.x) / Math.max(1, r.w)) * (o.sweep ?? .5), vx: (R() - .5) * 90 + (o.drift?.[0] ?? 30),
            vy: -(R() * 120 + 30) + (o.drift?.[1] ?? 0), s: lerp(1, 2.6, R()) };
        });
      } });
      tl.to(e, isSvg(e) ? { opacity: 0, duration: .9 } : { opacity: 0, filter: 'blur(10px)', duration: .9 }, at);
      canvas().drawers.push((t, x2) => {
        if (!P) return; const tau0 = t - at; if (tau0 < 0 || tau0 > dur + .6) return;
        x2.fillStyle = cssColor(o.color || 'var(--ink)');
        for (const p of P) {
          const tau = tau0 - p.d; if (tau < 0) continue; const a = 1 - tau / dur; if (a <= 0) continue;
          x2.globalAlpha = a * .9; x2.beginPath();
          x2.arc(p.x + p.vx * tau, p.y + p.vy * tau - 20 * tau * tau, p.s, 0, 6.283); x2.fill();
        }
        x2.globalAlpha = 1;
      });
      if (o.sfx !== false) sfx(o.sfx || 'whoosh', at, .6, o.sfx ? 'manual' : 'detail');
      return c;
    },
    shatter(el, at, o = {}) {
      const e = q(el)[0], cols = o.cols ?? 4, rows = o.rows ?? 3, dur = o.dur ?? 1.8, R = rng(o.seed ?? hash(g.id + 'sh' + at));
      const ix = o.cx ?? 50, iy = o.cy ?? 45; // 撞击点（百分比）
      if (o.crack !== false) {           // 先出现裂纹
        const cs = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        cs.setAttribute('viewBox', '0 0 100 100'); cs.setAttribute('preserveAspectRatio', 'none');
        cs.setAttribute('style', 'position:absolute;inset:0;width:100%;height:100%;overflow:visible');
        let d = '';
        for (let i = 0; i < 9; i++) {
          const a = i / 9 * 6.283 + R() * .5; let x = ix, y = iy; d += `M${x} ${y}`;
          for (let k = 0; k < 4; k++) { const L = 10 + R() * 14; x += Math.cos(a + (R() - .5) * .6) * L; y += Math.sin(a + (R() - .5) * .6) * L; d += ` L${x.toFixed(1)} ${y.toFixed(1)}`; }
        }
        cs.innerHTML = `<path d="${d}" fill="none" stroke="rgba(255,255,255,.95)" stroke-width="1.6" vector-effect="non-scaling-stroke"/><circle cx="${ix}" cy="${iy}" r="1.2" fill="#fff"/>`;
        e.appendChild(cs);
        const p = cs.firstChild; gsap.set(p, { strokeDasharray: 1200, strokeDashoffset: 1200 }); gsap.set(cs.lastChild, { opacity: 0 });
        tl.to(p, { strokeDashoffset: 0, duration: .35, ease: 'power3.out' }, at - .7);
        tl.to(cs.lastChild, { opacity: 1, duration: .1 }, at - .7);
        sfx('crack', at - .7, .8, 'detail');
      }
      // 三角碎片：抖动网格 → clip-path 克隆
      const pts = []; for (let j = 0; j <= rows; j++) for (let i = 0; i <= cols; i++) {
        const edgeX = i === 0 || i === cols, edgeY = j === 0 || j === rows;
        pts.push([i / cols * 100 + (edgeX ? 0 : (R() - .5) * 60 / cols), j / rows * 100 + (edgeY ? 0 : (R() - .5) * 60 / rows)]);
      }
      const P = (i, j) => pts[j * (cols + 1) + i], tris = [];
      for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
        tris.push([P(i, j), P(i + 1, j), P(i + 1, j + 1)], [P(i, j), P(i + 1, j + 1), P(i, j + 1)]);
      }
      const shards = tris.map(tri => {
        const k = e.cloneNode(true); k.removeAttribute('id');
        k.style.clipPath = `polygon(${tri.map(p => `${p[0]}% ${p[1]}%`).join(',')})`;
        e.parentNode.appendChild(k);
        k.querySelectorAll('path').forEach(p => gsap.set(p, { strokeDashoffset: 0 }));
        gsap.set(k, { opacity: 0 });
        const cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3, cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3;
        return { k, dx: cx - ix, dy: cy - iy };
      });
      tl.set(e, { opacity: 0 }, at);
      shards.forEach(({ k, dx, dy }) => {
        const L = Math.hypot(dx, dy) || 1, f = (o.force ?? 9) * (0.6 + R());
        tl.set(k, { opacity: 1 }, at);
        tl.to(k, { x: `+=${dx / L * f * 30}`, rotation: `+=${(R() - .5) * 120}`, duration: dur, ease: 'power3.out' }, at);
        tl.to(k, { y: `+=${dy / L * f * 18 + 420 + R() * 300}`, duration: dur, ease: 'power2.in' }, at);
        tl.to(k, { opacity: 0, duration: dur * .45, ease: 'power1.in' }, at + dur * .55);
      });
      if (o.sfx !== false) sfx('shatter', at, 1, 'key');
      return c;
    },
    particlesText(text, o = {}) {
      const at = o.at ?? g.start, dur = o.dur ?? 1.6, weight = o.weight ?? 900, size = o.size ?? 150;
      const R = rng(o.seed ?? hash(text + at)), colorV = o.color || 'var(--accent)';
      fontNeeds.push({ weight, text });
      mk('span', '', layer, esc(text)).setAttribute('style', `position:absolute;left:-9999px;font-weight:${weight};font-size:${size}px`);
      let P = null;
      const sample = () => {
        const oc = document.createElement('canvas'); oc.width = W; oc.height = H; const x = oc.getContext('2d');
        x.fillStyle = '#fff'; x.textBaseline = 'middle'; x.textAlign = 'center';
        const fam = `"Noto Serif SC","Source Han Serif SC","Songti SC",serif`;
        if (o.el) {     // 按 DOM 中每个字的位置采样，保证与真实文字重合
          q(o.el)[0].querySelectorAll('.ch').forEach(sp => {
            const r = stageRect(sp), cs = getComputedStyle(sp);
            x.font = `${cs.fontWeight} ${parseFloat(cs.fontSize)}px ${fam}`;
            x.fillText(sp.textContent, r.x + r.w / 2 - parseFloat(cs.letterSpacing || 0) / 2, r.y + r.h / 2);
          });
        } else { x.font = `${weight} ${size}px ${fam}`; x.letterSpacing = `${o.spacing ?? .14}em`;
          x.fillText(text, (o.x ?? W / 2) + size * (o.spacing ?? .14) / 2, o.y ?? H / 2); }
        const img = x.getImageData(0, 0, W, H).data, step = o.step ?? Math.max(3, Math.round(size / 26)), pts = [];
        for (let yy = 0; yy < H; yy += step) for (let xx = 0; xx < W; xx += step) if (img[(yy * W + xx) * 4 + 3] > 140) pts.push([xx, yy]);
        const max = o.count ?? 3200; while (pts.length > max) pts.splice((R() * pts.length) | 0, 1);
        P = pts.map(([tx, ty]) => { const a = R() * 6.283, d = 300 + R() * 900;
          return { tx, ty, sx: tx + Math.cos(a) * d, sy: ty + Math.sin(a) * d * .6, d: R() * .35, s: lerp(1.1, 2.3, R()), w: (R() - .5) * 2 }; });
      };
      measures.push({ at, fn: sample });
      const fadeAt = o.fadeAt ?? (o.dotted ? Infinity : at + dur), fadeDur = o.fadeDur ?? .8;
      canvas().drawers.push((t, x2) => {
        if (!P || t < at || t > fadeAt + fadeDur) return;
        const base = prog(t, at, dur), fade = 1 - prog(t, fadeAt, fadeDur);
        x2.fillStyle = cssColor(colorV);
        for (const p of P) {
          const u = EASE.inOut(clamp((base - p.d) / (1 - .35))), sw = Math.sin(u * 3.1416) * 60 * p.w;
          x2.globalAlpha = (0.15 + 0.85 * u) * fade;
          x2.beginPath(); x2.arc(lerp(p.sx, p.tx, u) + sw, lerp(p.sy, p.ty, u) - sw * .5, o.dotted ? p.s * .9 : p.s, 0, 6.283); x2.fill();
        }
        x2.globalAlpha = 1;
      });
      return c;
    },
    bgWord(text, o = {}) {
      const e = mk('div', 'bgword', layer, esc(text));
      e.style.top = (o.y ?? 230) + 'px'; if (o.size) e.style.fontSize = o.size + 'px';
      const at = o.at ?? g.start;
      tl.fromTo(e, { opacity: 0, scale: 1.06 }, { opacity: o.opacity ?? .07, scale: 1, duration: o.dur ?? 1.6, ease: 'power2.out', immediateRender: false }, at);
      return e;
    },
    shadow(x, y, w = 240, o = {}) {   // 物体落在“桌面”上的接触阴影
      const e = mk('div', 'shadow', layer); e.style.width = w + 'px'; e.style.height = (o.h ?? w * .16) + 'px';
      c.place(e, x, y); gsap.set(e, { opacity: o.at == null ? (o.opacity ?? .8) : 0 });
      if (o.at != null) tl.to(e, { opacity: o.opacity ?? .8, duration: o.dur ?? .8, ease: 'power2.out' }, o.at);
      return e;
    },
    sfx(name, at, gain = 1) { sfx(name, at, gain); return c; },
    onFrame(fn) { frameFns.push({ g, fn }); return c; },
    drawCanvas(fn) { canvas().drawers.push(fn); return c; },   // fn(t, ctx2d)：自绘画布，必须是 t 的纯函数
    measure(at, fn) { measures.push({ at, fn }); return c; },
    rect: stageRect,
    color: cssColor,   // 'var(--accent)' → 实际颜色（GSAP 不能直接补间 CSS 变量）
    fig, lamp,
  };
  c._finish = () => {   // 特效画布、涟漪层置顶
    if (cv) layer.appendChild(cv.el);
    if (fxsvg) layer.appendChild(fxsvg);
  };
  return c;
}

/* ---------------- SVG 母题：小人、吊灯 ---------------- */
function fig(x, y, h = 140, pose = 'stand', o = {}) {
  const r = h * .095, col = o.color || 'var(--ink)', tw = h * .13, lw = h * .085, aw = h * .07;
  const neck = -h + 2 * r + h * .03, hip = -h * .44, sh = neck + h * .06;
  const L = {
    stand: [[0, hip, -h * .07, 0], [0, hip, h * .07, 0], [0, sh, -h * .13, -h * .47], [0, sh, h * .13, -h * .47]],
    walk:  [[0, hip, -h * .2, 0], [0, hip, h * .17, 0], [0, sh, -h * .2, -h * .52], [0, sh, h * .2, -h * .56]],
    raise: [[0, hip, -h * .07, 0], [0, hip, h * .07, 0], [0, sh, -h * .13, -h * .47], [0, sh, h * .2, -h * 1.02]],
  }[pose] || [];
  const lines = L.map(([x1, y1, x2, y2], i) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="${i < 2 ? lw : aw}"/>`).join('');
  // 外层 <g> 负责定位，内层 <g class="fig"> 供动画使用（可安全补间 x/y/scale）
  return `<g transform="translate(${x},${y})"><g class="fig ${o.cls || ''}" style="stroke:${col};fill:${col};opacity:${o.opacity ?? 1}" stroke-linecap="round">`
    + `<circle cx="0" cy="${-h + r}" r="${r}" stroke="none"/><line x1="0" y1="${neck}" x2="0" y2="${hip}" stroke-width="${tw}"/>${lines}</g></g>`;
}
let lampN = 0;
function lamp(x, y, o = {}) {
  const id = 'lamp' + (lampN++), cord = o.cord ?? 220, w = o.w ?? 110, cone = o.cone ?? 520, len = o.len ?? 700;
  const col = o.color || '#ffd9a0';
  return `<defs><radialGradient id="${id}g"><stop offset="0" stop-color="${col}" stop-opacity=".95"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></radialGradient>`
    + `<linearGradient id="${id}c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity="${o.beam ?? .28}"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>`
    + `<g class="lamp">`
    + `<polygon class="beam" points="${x - w * .45},${y + 4} ${x + w * .45},${y + 4} ${x + cone / 2},${y + len} ${x - cone / 2},${y + len}" fill="url(#${id}c)"/>`
    + `<line x1="${x}" y1="${y - cord}" x2="${x}" y2="${y - w * .35}" stroke="#666" stroke-width="2"/>`
    + `<path d="M${x - w / 2} ${y} Q${x - w * .42} ${y - w * .42} ${x} ${y - w * .42} Q${x + w * .42} ${y - w * .42} ${x + w / 2} ${y} Z" fill="#1c1f26" stroke="#3a3f4a" stroke-width="1.5"/>`
    + `<circle class="glow" cx="${x}" cy="${y + 6}" r="${w * 1.1}" fill="url(#${id}g)"/>`
    + `<ellipse cx="${x}" cy="${y + 2}" rx="${w * .2}" ry="${w * .08}" fill="#fff8e8"/></g>`;
}

/* ---------------- 字幕 ---------------- */
function subHtml(say) {
  return say.split('**').map((part, k) => {
    let inner = ''; for (const ch of part) inner += ch === '\n' ? '<br>' : `<span class="ch">${esc(ch)}</span>`;
    return k % 2 ? `<span class="hl">${inner}</span>` : inner;
  }).join('');
}
function buildSub(b) {
  const pos = b.pos || meta.subPos;
  const el = mk('div', `sub ${pos}`, subsRoot, subHtml(b.say) + (b.en ? `<span class="en">${esc(b.en)}</span>` : ''));
  const chars = [...el.querySelectorAll('.ch')], en = el.querySelector('.en');
  const reveal = b.reveal || (pos === 'center' ? 'type' : meta.reveal || 'type');
  gsap.set(el, { opacity: 0 }); const t0 = b.start + (b.subDelay || 0);
  tl.set(el, { opacity: 1 }, t0);
  let typed = t0;
  if (reveal === 'type') {
    const step = pos === 'center' ? .11 : clamp(1.0 / chars.length, .025, .05);
    gsap.set(chars, { opacity: 0 });
    tl.fromTo(chars, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: pos === 'center' ? .5 : .28, stagger: step, ease: 'power1.out', immediateRender: false }, t0 + .05);
    typed = t0 + .05 + step * chars.length;
  } else if (reveal === 'fade') {
    tl.fromTo(el, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: .6, ease: 'power2.out', immediateRender: false }, t0);
    typed = t0 + .4;
  }
  if (en) { gsap.set(en, { opacity: 0 }); tl.to(en, { opacity: 1, duration: .6 }, typed); }
  const last = b.subUntil ? byId[b.subUntil].end : b.end;
  if (last < duration - .7) tl.to(el, { opacity: 0, filter: 'blur(4px)', duration: .35, ease: 'power1.in' }, last - .35);
}

/* ---------------- 包装元素：章节 / 文献 / 年代 ---------------- */
function segments(key, auto) {
  const out = []; let cur = null;
  beats.forEach((b, i) => {
    let v = b[key]; if (v === undefined && auto) v = auto(b, i); if (v === undefined) return;
    if (cur) cur.end = b.start;
    cur = v === null ? null : { start: b.start, end: duration, v }; if (cur) out.push(cur);
  });
  return out;
}
function segFade(el, s) {
  gsap.set(el, { opacity: 0 });
  tl.fromTo(el, { opacity: 0, x: -10 }, { opacity: 1, x: 0, duration: .8, ease: 'power2.out', immediateRender: false }, s.start + .15);
  if (s.end < duration) tl.to(el, { opacity: 0, duration: .5 }, s.end - .3);
}
function buildChrome() {
  if (meta.brand) mk('div', meta.brandPos === 'br' ? 'br' : '', chromeRoot, esc(meta.brand)).id = 'brand';
  // 章节标签：标题卡结束后自动出现 = 标题；标题卡期间隐藏
  segments('chapter', (b, i) => {
    if (meta.chapter === false) return undefined;
    if (b.type === 'title') return null;
    const p = beats[i - 1]; if (p && p.type === 'title') return { zh: p.title, la: p.latin };
  }).forEach(s => {
    const v = typeof s.v === 'string' ? { zh: s.v } : s.v;
    const el = mk('div', 'chapter', chromeRoot, `<div class="zh">${esc(v.zh)}</div>${v.la ? `<div class="la">${esc(v.la)}</div>` : ''}<div class="rule"></div>`);
    if (meta.chapterStyle === 'bracket') el.firstChild.textContent = `【${v.zh}】`;
    segFade(el, s);
  });
  segments('cite').forEach(s => {
    const v = s.v; const el = mk('div', 'cite', chromeRoot,
      `${v.la ? `<div class="la">${esc(v.la)}</div>` : ''}${v.zh ? `<div class="zh">${esc(v.zh)}</div>` : ''}${v.note ? `<div class="note">${esc(v.note)}</div>` : ''}${v.seal !== false ? `<div class="seal">${esc(v.seal || '文献')}</div>` : ''}`);
    segFade(el, s);
  });
  let prevYear = null;
  segments('era').forEach(s => {
    const v = s.v, year = String(v.year), el = mk('div', 'era', chromeRoot), yEl = mk('div', 'year', el);
    if (/^\d+$/.test(year)) {
      // 里程表式滚动：个位连续转动，高位在进位时才转
      const to = +year, from = prevYear ?? Math.max(0, to - 137), n = year.length; prevYear = to;
      const strips = [...year].map(() => mk('span', '', mk('span', 'digit', yEl), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0].map(d => `<span>${d}</span>`).join('')));
      frameFns.push({ fn: t => {
        const val = lerp(from, to, prog(t, s.start + .2, 1.4, 'out'));
        strips.forEach((st, i) => {
          const unit = 10 ** (n - 1 - i), whole = Math.floor(val / unit), rem = val - whole * unit;
          const pos = unit === 1 ? val % 10 : (whole % 10) + Math.max(0, rem - (unit - 1));
          st.style.transform = `translateY(${-pos}em)`;
        });
      } });
    } else yEl.textContent = year;
    if (v.place) mk('div', 'place', el, esc(v.place));
    segFade(el, s);
  });
}

/* ---------------- 标题卡 ---------------- */
function buildTitle(b) {
  const box = mk('div', 'layer', titlesRoot);
  const warm = b.rays ?? meta.rays ?? ['gilt', 'ember'].includes(meta.theme);
  const glow = warm ? [mk('div', 'halo', box), mk('div', 'rays', box)] : null;
  const card = mk('div', 'titlecard', box,
    `${b.latin ? `<div class="la">${esc(b.latin)}</div>` : ''}<div class="main">${[...b.title].map(ch => `<span class="ch">${esc(ch)}</span>`).join('')}</div>`
    + `<div class="line"><i></i></div>${b.sub ? `<div class="sub2">${esc(b.sub)}</div>` : ''}`
    + `${(b.by ?? (meta.brand ? `— ${meta.brand} 出品 —` : '')) ? `<div class="by">${esc(b.by ?? `— ${meta.brand} 出品 —`)}</div>` : ''}`);
  const s = b.start, main = card.querySelector('.main'), dotted = (b.titleStyle || meta.titleStyle) === 'dots';
  const fake = { id: '@t' + b.i, start: s, end: b.end, beats: [b] };
  const c = makeCtx(fake, box);
  gsap.set(card, { opacity: 1 }); gsap.set(card.children, { opacity: 0 });
  c.particlesText(b.title, { el: main, at: s, dur: 1.5, dotted, fadeAt: dotted ? b.end - .7 : s + 1.45, fadeDur: dotted ? .7 : .7,
    color: dotted ? 'var(--ink)' : 'var(--accent)', step: dotted ? 7 : undefined, count: dotted ? 1200 : undefined });
  if (!dotted) tl.fromTo(main, { opacity: 0, filter: 'blur(12px)' }, { opacity: 1, filter: 'blur(0px)', duration: .8, ease: 'power2.out', immediateRender: false }, s + 1.3);
  const la = card.querySelector('.la'), line = card.querySelector('.line'), sub2 = card.querySelector('.sub2'), by = card.querySelector('.by');
  if (la) tl.fromTo(la, { opacity: 0, letterSpacing: '.9em' }, { opacity: 1, letterSpacing: '.55em', duration: 1.4, ease: 'power2.out', immediateRender: false }, s + .5);
  tl.fromTo(line, { opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, duration: 1, ease: 'power2.inOut', immediateRender: false }, s + 1.6);
  tl.fromTo(line.firstChild, { left: '0%' }, { left: '100%', duration: Math.max(1.2, b.dur - 2.6), ease: 'power1.inOut', immediateRender: false }, s + 1.8);
  if (sub2) c.show(sub2, s + 2.0, .8);
  if (by) c.show(by, s + 2.3, .8);
  tl.to(card, { opacity: 0, scale: 1.04, filter: 'blur(10px)', duration: .7, ease: 'power1.in' }, b.end - .7);
  if (glow) {   // 标题背后的光晕与放射光线，缓慢旋转
    tl.fromTo(glow, { opacity: 0 }, { opacity: 1, duration: 1.4, ease: 'power2.out', immediateRender: false }, s + .6);
    tl.fromTo(glow[1], { rotation: -5 }, { rotation: 5, duration: b.dur, ease: 'none', immediateRender: false }, s);
    tl.to(glow, { opacity: 0, duration: .7, ease: 'power1.in' }, b.end - .7);
  }
  c._finish();
  sfx('shimmer', s + .05, .8, 'key');
  frameFns.push({ fn: t => { box.style.visibility = t >= s - .1 && t <= b.end + .1 ? 'visible' : 'hidden'; } });
}

/* ---------------- 氛围层：浮尘 + 胶片颗粒 + 主题切换 ---------------- */
let dust = [], grainFrames = [];
function buildAmbient() {
  const R = rng(42);
  dust = Array.from({ length: meta.dust === false ? 0 : 70 }, () => ({ x: R() * W, y: R() * H, vx: (R() - .5) * 14, vy: -4 - R() * 10,
    r: R() < .15 ? 1.6 + R() * 1.6 : .6 + R(), a: .12 + R() * .4, w: .4 + R() * 1.4, ph: R() * 6.28 }));
  if (meta.grain !== false) {
    const g2 = grainCanvas.getContext('2d');
    for (let k = 0; k < 6; k++) {
      const id = g2.createImageData(960, 540), d = id.data, Rg = rng(100 + k);
      for (let i = 0; i < d.length; i += 4) { const v = (Rg() * 255) | 0; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
      grainFrames.push(id);
    }
  }
  beats.forEach(b => { if (b.theme) themeSwitches.push({ at: b.start, theme: b.theme, flash: b.flash !== false }); });
  themeSwitches.forEach(sw => {
    if (!sw.flash) return;
    tl.fromTo(flashEl, { opacity: 0 }, { opacity: .9, duration: .22, ease: 'power2.in', immediateRender: false }, sw.at);
    tl.to(flashEl, { opacity: 0, duration: .7, ease: 'power2.out' }, sw.at + .22);
    sfx('boom', sw.at + .1, .9, 'detail');
  });
}
let curTheme = null;
function applyTheme(t) {
  let th = meta.theme;
  for (const sw of themeSwitches) if (t >= sw.at + (sw.flash ? .22 : 0)) th = sw.theme;
  if (th !== curTheme) {
    curTheme = th; stage.className = `theme-${th}` + (th === 'paper' ? ' inverted' : '');
    flashEl.style.background = th === 'paper' ? '#fff' : '#000'; colorCache = {};
  }
}
function drawAmbient(t) {
  const x = fxCanvas.getContext('2d'); x.clearRect(0, 0, W, H);
  x.fillStyle = cssColor('var(--dust)');
  for (const p of dust) {
    const px = ((p.x + p.vx * t) % W + W) % W, py = ((p.y + p.vy * t) % H + H) % H;
    x.globalAlpha = p.a * (.55 + .45 * Math.sin(t * p.w + p.ph)); x.beginPath(); x.arc(px, py, p.r, 0, 6.283); x.fill();
  }
  x.globalAlpha = 1;
  if (grainFrames.length) grainCanvas.getContext('2d').putImageData(grainFrames[Math.floor(t * 24) % grainFrames.length], 0, 0);
}

/* ---------------- 帧求值 ---------------- */
function seek(t) {
  t = clamp(t, 0, duration);
  applyTheme(t);
  tl.seek(t, false);
  for (const g of groups) {
    const vis = t >= g.start - XF && t <= g.end + XF; g.layer.style.visibility = vis ? 'visible' : 'hidden'; g.vis = vis;
  }
  for (const f of frameFns) if (!f.g || f.g.vis !== false) f.fn(t);
  for (const cv of sceneCanvases) {
    if (cv.g.vis === false) continue; const x = cv.g2d; x.clearRect(0, 0, W, H);
    for (const d of cv.drawers) d(t, x);
  }
  drawAmbient(t);
  window.__t = t;
}

/* ---------------- 启动 ---------------- */
async function boot(proj) {
  const base = (proj || '').replace(/\/$/, '');
  const script = await (await fetch(`../${base}/script.json?_=${Date.now()}`)).json();
  meta = Object.assign({ theme: 'gilt', brand: '', brandPos: 'tr', subPos: 'bottom', fps: 30, tail: 1.0, title: '' }, script.meta || {});
  document.title = meta.title || base;
  await loadScript(`../${base}/scenes.js?_=${Date.now()}`);

  // 舞台
  stage = mk('div', `theme-${meta.theme}`, document.body); stage.id = 'stage';
  mk('div', 'layer', stage).id = 'bg';
  bgPaper = mk('div', 'layer', stage); bgPaper.id = 'bgPaper';
  floorEl = mk('div', '', stage, '<div class="surf"></div><div class="pool"></div><div class="edge"></div>'); floorEl.id = 'floor';
  floorEl.style.top = Math.round(H * (meta.floorY ?? .64)) + 'px';
  fxCanvas = mk('canvas', 'layer', stage); fxCanvas.width = W; fxCanvas.height = H;
  scenesRoot = mk('div', 'layer', stage); scenesRoot.id = 'scenes';
  titlesRoot = mk('div', 'layer', stage);
  mk('div', 'layer', stage).id = 'vignette';
  chromeRoot = mk('div', 'layer', stage);
  subsRoot = mk('div', 'layer', stage);
  flashEl = mk('div', 'layer', stage); flashEl.style.opacity = 0;
  grainCanvas = mk('canvas', 'layer', stage); grainCanvas.width = 960; grainCanvas.height = 540;
  Object.assign(grainCanvas.style, { opacity: meta.grainOpacity ?? .06, mixBlendMode: 'overlay', width: W + 'px', height: H + 'px' });
  mk('div', '', stage).id = 'label';
  fit(); addEventListener('resize', fit);

  // 节拍时间
  let t = 0;
  beats = script.beats.map((b, i) => { const o = { ...b, i, id: b.id || `b${i + 1}` }; o.start = t; o.dur = beatDur(b); o.end = t + o.dur; t = o.end; return o; });
  beats.forEach(b => { if (byId[b.id]) throw new Error('重复的 beat id: ' + b.id); byId[b.id] = b; });
  duration = t + meta.tail;
  tl = gsap.timeline({ paused: true });
  tl.set({}, {}, duration);  // 撑满时长
  // 地板（桌面舞台）：暖色主题默认开启；节拍上写 "floor": false/true 切换
  let fOn = meta.floor ?? ['gilt', 'ember'].includes(meta.theme);
  gsap.set(floorEl, { opacity: fOn ? 1 : 0 });
  beats.forEach(b => { if (typeof b.floor === 'boolean' && b.floor !== fOn) { fOn = b.floor;
    tl.to(floorEl, { opacity: fOn ? 1 : 0, duration: .8, ease: 'power1.inOut' }, Math.max(0, b.start - .4)); } });

  // 场景分组：连续相同 scene 归为一组；无 scene 的节拍沿用上一个非标题节拍的 scene
  let prev = '@none', cur = null;
  beats.forEach(b => {
    const sc = b.scene ?? (b.type === 'title' ? `@title${b.i}` : prev);
    b.scene = sc; if (b.type !== 'title' || b.scene !== `@title${b.i}`) prev = sc;
    if (!cur || cur.id !== sc) { cur = { id: sc, beats: [], start: b.start, enter: b.enter || 'fade' }; groups.push(cur); }
    cur.beats.push(b); cur.end = b.end;
  });
  groups.forEach((g, gi) => {
    const layer = mk('div', 'layer scene', scenesRoot); layer.dataset.scene = g.id; g.layer = layer;
    const ctx = makeCtx(g, layer);
    const builder = SCENES[g.id];
    if (builder) builder(ctx); else if (!g.id.startsWith('@')) console.warn('scenes.js 里没有场景：', g.id);
    ctx._finish();
    const first = gi === 0, last = gi === groups.length - 1;
    gsap.set(layer, { opacity: first ? 1 : 0 });
    if (!first) {
      if (g.enter === 'cut') tl.set(layer, { opacity: 1 }, g.start);
      else tl.fromTo(layer, { opacity: 0 }, { opacity: 1, duration: XF, ease: 'power1.inOut', immediateRender: false }, g.start - XF / 2);
    }
    if (!last) {
      if (groups[gi + 1].enter === 'cut') tl.set(layer, { opacity: 0 }, g.end);
      else tl.to(layer, { opacity: 0, duration: XF, ease: 'power1.inOut' }, g.end - XF / 2);
    }
  });
  beats.forEach(b => { if (b.type === 'title') buildTitle(b); if (b.say) buildSub(b); });
  buildChrome();
  buildAmbient();
  beats.forEach(b => {   // 节拍上声明的音效
    const list = b.sfx == null ? [] : Array.isArray(b.sfx) ? b.sfx : [b.sfx];
    list.forEach(s => (typeof s === 'string' ? sfx(s, b.start, 1) : sfx(s.name, b.start + (s.at || 0), s.gain ?? 1)));
  });

  // 字体就绪 → 测量布局 → 回到 0 秒
  document.body.offsetHeight;
  await Promise.all(fontNeeds.map(f => document.fonts.load(`${f.weight} 100px "Noto Serif SC"`, f.text).catch(() => {})));
  await document.fonts.ready;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  await document.fonts.ready;
  measures.sort((a, b) => a.at - b.at).forEach(m => { seek(m.at); m.fn(); });
  seek(+QS.get('t') || 0);

  cues.sort((a, b) => a.t - b.t);
  Object.assign(window, {
    __duration: duration, __fps: meta.fps, __cues: cues, __meta: meta,
    __beats: beats.map(b => ({ id: b.id, type: b.type || '', scene: b.scene, start: +b.start.toFixed(3), end: +b.end.toFixed(3), say: b.say || b.title || '' })),
    __seek: seek,
    __label: txt => { const l = document.getElementById('label'); l.style.display = txt ? 'block' : 'none'; l.textContent = txt || ''; },
  });
  if (!RENDER) hud();
  return true;
}

function fit() {
  const hudH = RENDER ? 0 : 34;
  S = Math.min(innerWidth / W, (innerHeight - hudH) / H);
  stage.style.transform = `scale(${S})`;
  stage.style.left = (innerWidth - W * S) / 2 + 'px'; stage.style.top = RENDER ? '0px' : Math.max(0, (innerHeight - hudH - H * S) / 2) + 'px';
}

/* ---------------- 预览播放条（浏览器里直接看） ---------------- */
function hud() {
  document.body.classList.remove('render');
  const bar = mk('div', '', document.body, `<button id="pp">▶</button><span id="tc">0.00</span><input id="sc" type="range" min="0" max="${duration}" step="0.01" value="0"><span id="bt"></span>`);
  bar.id = 'hud';
  const pp = bar.querySelector('#pp'), sc = bar.querySelector('#sc'), tc = bar.querySelector('#tc'), bt = bar.querySelector('#bt');
  let playing = false, t0 = 0, wall = 0, lastT = window.__t || 0;
  const audioCache = {};
  const play = name => { const a = (audioCache[name] ||= new Audio(`../sfx/${name}.wav`)).cloneNode(); a.volume = .7; a.play().catch(() => {}); };
  const show = t => { sc.value = t; tc.textContent = t.toFixed(2); const b = beats.find(b => t >= b.start && t < b.end); bt.textContent = b ? `${b.id} · ${b.scene} · ${(b.say || b.title || '').replace(/\*\*/g, '')}` : ''; };
  const tick = () => {
    if (!playing) return;
    const t = t0 + (performance.now() - wall) / 1000;
    if (t >= duration) { playing = false; pp.textContent = '▶'; seek(duration); show(duration); return; }
    for (const c of cues) if (c.t > lastT && c.t <= t) play(c.name);
    lastT = t; seek(t); show(t); requestAnimationFrame(tick);
  };
  const toggle = () => { playing = !playing; pp.textContent = playing ? '❚❚' : '▶'; if (playing) { t0 = window.__t; lastT = t0; wall = performance.now(); tick(); } };
  pp.onclick = toggle;
  sc.oninput = () => { playing = false; pp.textContent = '▶'; seek(+sc.value); show(+sc.value); };
  addEventListener('keydown', e => {
    if (e.code === 'Space') { e.preventDefault(); toggle(); }
    if (e.code === 'ArrowRight' || e.code === 'ArrowLeft') { playing = false; pp.textContent = '▶'; const t = clamp(window.__t + (e.code === 'ArrowRight' ? 1 : -1), 0, duration); seek(t); show(t); }
  });
  show(window.__t || 0);
}

window.Engine = { boot, fig, lamp };
window.__ready = (async () => {
  if (RENDER) document.body.classList.add('render');
  try { return await boot(QS.get('p')); }
  catch (e) { console.error(e); document.body.insertAdjacentHTML('beforeend', `<pre style="color:#f66;position:fixed;top:0;left:0;z-index:999;font:16px monospace;white-space:pre-wrap">${esc(e.stack || e)}</pre>`); window.__error = String(e.stack || e); return false; }
})();
})();
