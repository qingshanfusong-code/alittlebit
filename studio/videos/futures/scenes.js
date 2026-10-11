// 《期货》画面层：只写“画什么”，台词与时间都在 script.json
// 画法统一为“桌面拟物小道具 + 金色线描”：麦袋、契约纸、价格牌、金币、油桶
(() => {
/* ---------- 共用道具（SVG 片段坐标都是“底边中心”，外层 <g> 不带 transform，便于补间） ---------- */
const defs = k => `<defs>
  <linearGradient id="burlap${k}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9ac62"/><stop offset=".55" stop-color="#9a6c34"/><stop offset="1" stop-color="#4a3418"/></linearGradient>
  <linearGradient id="flour${k}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f6efe0"/><stop offset=".55" stop-color="#cfc2a2"/><stop offset="1" stop-color="#7d7058"/></linearGradient>
  <radialGradient id="coin${k}" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#fff2c8"/><stop offset=".55" stop-color="#dcb36a"/><stop offset="1" stop-color="#7a5520"/></radialGradient>
  <radialGradient id="risk${k}" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#f08a72"/><stop offset=".5" stop-color="#a8352a"/><stop offset="1" stop-color="#3a0e0a"/></radialGradient>
  <linearGradient id="soil${k}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2512"/><stop offset="1" stop-color="#1c1208"/></linearGradient>
  <filter id="gl${k}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8"/></filter></defs>`;

const shade = (k, x, y, w) => `<ellipse cx="${x}" cy="${y}" rx="${w / 2}" ry="${w / 10}" fill="#000" opacity=".55" filter="url(#gl${k})"/>`;

// 麦袋（burlap）/ 面粉袋（flour），宽约 210·s
const sack = (k, x, y, s = 1, kind = 'burlap', a = '') => `<g ${a}><g transform="translate(${x} ${y}) scale(${s})">
  <path d="M-92 0 Q-106 0 -105 -16 C-110 -84 -86 -148 -46 -172 L46 -172 C86 -148 110 -84 105 -16 Q106 0 92 0 Z" fill="url(#${kind}${k})" style="stroke:var(--accent);stroke-width:2;stroke-opacity:.5"/>
  ${kind === 'burlap'
    ? '<path d="M-28 -174 C-40 -200 -26 -222 -12 -206 M0 -176 C-2 -206 10 -226 16 -208 M26 -174 C40 -198 30 -218 14 -204" fill="none" stroke="#e6c27a" stroke-width="6" stroke-linecap="round"/>'
    : '<path d="M-40 -172 Q0 -198 40 -172 Z" fill="#f4ecdc"/>'}
  <path d="M-46 -172 Q0 -160 46 -172" fill="none" stroke="#3a2812" stroke-width="6" stroke-linecap="round"/>
  <text y="-62" text-anchor="middle" font-size="58" font-weight="700" fill="${kind === 'burlap' ? '#3a2410' : '#6b5a40'}" opacity=".8">${kind === 'burlap' ? '麦' : '面'}</text></g></g>`;

// 一摞金币，第 i 枚上移 11px；每枚是 .cn（带 transform，只能补间不透明度）
const coins = (k, x, y, n, a = '') => `<g ${a}>${Array.from({ length: n }, (_, i) => `<g class="cn" transform="translate(${x} ${y - i * 11})">
  <path d="M-40 -6 L-40 0 A40 12 0 0 0 40 0 L40 -6 Z" fill="#7a5520"/><ellipse cy="-6" rx="40" ry="12" fill="url(#coin${k})" stroke="#5a3e14" stroke-width="1.5"/></g>`).join('')}</g>`;

const arrow = (x, y, up, col, a = '', len = 90) => { const d = up ? -1 : 1, y2 = y + d * len;
  return `<g ${a}><line x1="${x}" y1="${y}" x2="${x}" y2="${y2}" style="stroke:${col};stroke-width:7" stroke-linecap="round"/>
    <path d="M${x - 22} ${y2 - d * 24} L${x} ${y2} L${x + 22} ${y2 - d * 24}" fill="none" style="stroke:${col};stroke-width:7" stroke-linecap="round" stroke-linejoin="round"/></g>`; };

// 麦苗：.young 嫩苗（暖黄绿）+ .ripe 金色麦穗（默认隐藏）
const sprout = (x, y) => `<g class="sp"><g transform="translate(${x} ${y})">
  <g class="young"><path d="M0 0 C2 -20 -2 -40 0 -60" fill="none" stroke="#b3ad4a" stroke-width="4" stroke-linecap="round"/>
    <path d="M0 -24 C-18 -30 -28 -44 -26 -54 C-12 -48 -3 -38 0 -26Z M0 -36 C16 -42 26 -56 24 -64 C11 -58 3 -48 0 -38Z" fill="#c2b452"/></g>
  <g class="ripe" opacity="0"><path d="M0 0 C3 -40 -3 -90 0 -128" fill="none" style="stroke:var(--accent);stroke-width:4" stroke-linecap="round"/>
    <path d="M0 -40 C-20 -50 -30 -70 -28 -84 C-14 -74 -4 -60 0 -44Z" style="fill:var(--accent)" opacity=".75"/>
    ${[0, 1, 2, 3, 4].map(j => { const ex = j % 2 ? 6 : -6, ey = -136 - j * 12;
      return `<ellipse cx="${ex}" cy="${ey}" rx="6" ry="11" transform="rotate(${j % 2 ? 22 : -22} ${ex} ${ey})" style="fill:var(--accent)"/>`; }).join('')}
    <path d="M0 -190 L0 -214 M-8 -176 L-18 -200 M8 -170 L18 -196" style="stroke:var(--accent2);stroke-width:2"/></g></g></g>`;

// 一小方田垄（透视梯形 + 金线沟垄）+ 三株麦苗
const field = (k, cx, by) => `<g class="plot"><path d="M${cx - 160} ${by - 70} L${cx + 160} ${by - 70} L${cx + 230} ${by} L${cx - 230} ${by} Z" fill="url(#soil${k})" style="stroke:var(--accent);stroke-width:2"/>
  ${[-2, -1, 0, 1, 2].map(j => `<path class="fur" d="M${cx + j * 64} ${by - 70} L${cx + j * 92} ${by}" fill="none" style="stroke:var(--accent);stroke-width:1.5" opacity=".55"/>`).join('')}</g>
  ${[-1, 0, 1].map(j => sprout(cx + j * 78, by - 35)).join('')}`;

const barrel = (x, y, s = 1, a = '') => `<g ${a}><g transform="translate(${x} ${y}) scale(${s})">
  <path d="M-72 -180 L-72 -12 A72 16 0 0 0 72 -12 L72 -180 Z" style="fill:var(--bg2);stroke:var(--ink);stroke-width:3"/>
  <path d="M-72 -124 A72 16 0 0 0 72 -124 M-72 -64 A72 16 0 0 0 72 -64" fill="none" style="stroke:var(--accent);stroke-width:3"/>
  <ellipse cy="-180" rx="72" ry="16" style="fill:var(--bg1);stroke:var(--ink);stroke-width:3"/>
  <ellipse cx="34" cy="-182" rx="9" ry="4" fill="none" style="stroke:var(--ink);stroke-width:2"/></g></g>`;

// 柱廊式交易所线描（路径带 .tp，可逐条描出）
const temple = (x, y, s = 1, a = '') => `<g ${a}><g transform="translate(${x} ${y}) scale(${s})" fill="none" style="stroke:var(--accent);stroke-width:3">
  <path class="tp" d="M-200 0 L200 0 M-185 -16 L185 -16 M-170 -32 L170 -32"/>
  ${[-140, -84, -28, 28, 84, 140].map(cx => `<path class="tp" d="M${cx - 14} -32 L${cx - 14} -230 M${cx + 14} -32 L${cx + 14} -230"/>`).join('')}
  <path class="tp" d="M-180 -230 L180 -230 L180 -264 L-180 -264 Z"/>
  <path class="tp" d="M-196 -264 L0 -340 L196 -264 Z"/>
  <text class="tt" y="-240" text-anchor="middle" font-size="19" letter-spacing="5" style="fill:var(--accent);stroke:none;font-family:var(--la)">BOARD OF TRADE</text></g></g>`;

// 价格牌（HTML），.num 是数字
const board = (c, x, y, v, label, w = 260) => { const el = c.h(`<div style="position:absolute;width:${w}px;box-sizing:border-box;padding:12px 0 10px;text-align:center;border:2px solid var(--accent);border-radius:6px;background:var(--bg1);box-shadow:0 0 28px var(--glow),0 18px 40px rgba(0,0,0,.45)">
    <div class="label" style="position:static;font-size:19px">${label}</div>
    <div class="big num" style="position:static;font-size:86px;line-height:1.05;color:var(--ink)">${v}</div></div>`); c.place(el, x, y); return el; };

const card = (c, x, y, w, h, inner, extra = '') => { const el = c.h(`<div class="card" style="box-sizing:border-box;width:${w}px;height:${h}px;padding:22px 28px;${extra}">${inner}</div>`); c.place(el, x, y); return el; };

// 农民—磨坊主的契约：条款 .ln、价格 .p100、签名 .sigA / .sigB
const pactInner = (z = 1) => `<div style="text-align:center;font-size:${30 * z}px;letter-spacing:.6em;padding-left:.6em;color:#6b5434">契约</div>
  <div style="height:1px;background:#9c8862;margin:${8 * z}px 0 ${16 * z}px"></div>
  <div class="ln" style="text-align:center;font-size:${28 * z}px">小麦 · 一袋</div>
  <div class="ln" style="text-align:center;font-size:${28 * z}px">秋季交货</div>
  <div class="ln" style="text-align:center;font-size:${28 * z}px">价格 <b class="p100" style="font-family:var(--la);font-size:${52 * z}px;line-height:1;color:#8b2a20">100</b></div>
  <svg viewBox="0 0 300 84" style="position:absolute;left:${28 * z}px;bottom:${16 * z}px;width:calc(100% - ${56 * z}px)">
    <path class="sigA" d="M10 50 C30 20 40 70 60 40 S90 30 100 52 S120 60 130 40" fill="none" stroke="#3a2a18" stroke-width="2.5" stroke-linecap="round"/>
    <path class="sigB" d="M170 52 C185 25 200 60 215 35 C228 15 240 62 262 42 S285 40 292 50" fill="none" stroke="#3a2a18" stroke-width="2.5" stroke-linecap="round"/>
    <text class="sigA" x="70" y="80" font-size="15" fill="#8a7350" text-anchor="middle">农民</text>
    <text x="230" y="80" font-size="15" fill="#8a7350" text-anchor="middle">磨坊主</text></svg>`;

// 标准化合约卡：四个字段 .f
const stdInner = `<div style="display:flex;justify-content:space-between;align-items:baseline"><span style="font-size:26px;letter-spacing:.3em;color:#6b5434">小麦合约</span><span style="font-family:var(--la);font-style:italic;font-size:21px;color:#8a7350">Standard</span></div>
  <div style="height:1px;background:#9c8862;margin:6px 0 10px"></div>
  ${[['品级', '二号小麦'], ['数量', '5000 蒲式耳'], ['交割月', '十二月'], ['交割地', '芝加哥']].map(([a, b]) =>
    `<div class="f" style="display:flex;justify-content:space-between;font-size:24px;line-height:1.75;padding:0 8px;border-radius:3px"><span style="color:#8a7350">${a}</span><span>${b}</span></div>`).join('')}`;

/* ---------- 场景 1：春天的麦田 → 丰收 → 价格崩 → 能不能先说定 ---------- */
SCENES.field = c => {
  const k = 'F', s = c.svg(`${defs(k)}
    <g id="fld">${field(k, 960, 800)}</g>
    <g id="seed"><ellipse cx="960" cy="762" rx="7" ry="10" style="fill:var(--accent)"/></g>
    <g id="skg">${shade(k, 1010, 800, 230)}${sack(k, 1010, 800, .9)}</g>
    <g id="post">${shade(k, 1390, 800, 90)}<line x1="1390" y1="600" x2="1390" y2="800" style="stroke:var(--accent);stroke-width:5"/></g>
    ${arrow(1560, 470, false, 'var(--seal)', 'id="dn"', 110)}`);
  const $ = id => s.querySelector('#' + id), h1 = c.at('h1'), h2 = c.at('h2'), h3 = c.at('h3');

  // h1：田垄描出 → 一粒麦种落下 → 三株嫩苗
  c.show(s.querySelector('.plot'), h1 + .1, .8, { y: 10 });
  c.draw(s.querySelectorAll('.fur'), h1 + .4, .9, { stagger: .08 });
  c.set($('seed'), { opacity: 0 }).set(s.querySelectorAll('.sp'), { scaleY: 0, transformOrigin: '50% 100%' });
  c.fromTo($('seed'), { y: -300, opacity: 0 }, { y: 0, opacity: 1, duration: .6, ease: 'power2.in' }, h1 + .6);
  c.to($('seed'), { opacity: 0, duration: .3 }, h1 + 1.3);
  c.fromTo(s.querySelectorAll('.sp'), { scaleY: 0, transformOrigin: '50% 100%' }, { scaleY: 1, duration: .6, ease: 'power2.out', stagger: .15 }, h1 + 1.25);

  // h2：田挪到左边，麦苗长高转金 → 麦袋 → 价格牌 100 → 60
  c.to($('fld'), { x: -360, duration: 1, ease: 'power2.inOut' }, h2 + .1);
  c.to(s.querySelectorAll('.young'), { opacity: 0, duration: .6 }, h2 + .6);
  c.fromTo(s.querySelectorAll('.ripe'), { opacity: 0, scaleY: .4, transformOrigin: '50% 100%' }, { opacity: 1, scaleY: 1, duration: 1, ease: 'power2.out', stagger: .1 }, h2 + .5);
  c.show($('skg'), h2 + 1.3, .8, { y: 30 });
  const bd = board(c, 1390, 525, 100, '秋季麦价'), num = bd.querySelector('.num');
  c.show([bd, $('post')], h2 + 1.7, .6);
  c.counter(num, 100, 60, h2 + 2.4, 1.0, { ease: 'in' });
  c.to(num, { color: c.color('var(--seal)'), duration: .4 }, h2 + 2.9);
  c.show($('dn'), h2 + 2.6, .5, { y: -24 });

  // h3：价格滚回 100 并“冻住” → 一张空白契约纸飘落
  c.to($('dn'), { opacity: 0, duration: .4 }, h3);
  c.counter(num, 60, 100, h3 + .2, .9, { ease: 'out' });
  c.to(num, { color: c.color('var(--accent)'), textShadow: `0 0 26px ${c.color('var(--glow)')}`, duration: .5 }, h3 + 1.0);
  c.to(bd, { boxShadow: `0 0 60px ${c.color('var(--glow)')}, 0 18px 40px rgba(0,0,0,.45)`, duration: .5 }, h3 + 1.0);
  const paper = card(c, 1190, 718, 150, 190, '', 'padding:0;background:repeating-linear-gradient(180deg,transparent 0 30px,rgba(120,95,60,.3) 30px 31px) 0 36px/100% 120px no-repeat,linear-gradient(180deg,#efe6d2,#d9cdb3)');
  c.set(paper, { opacity: 0 });
  c.fromTo(paper, { y: -620, x: 280, rotation: 16, opacity: 0 }, { y: 0, x: 0, rotation: -7, opacity: 1, duration: 2.1, ease: 'power1.out' }, h3 + .4);
  c.shadow(1190, 812, 150, { at: h3 + 2.1 });
};

/* ---------- 场景 2：远期合约（契约 → 条款 → 价格乱跳 → 天平对冲 → 盖章） ---------- */
SCENES.pact = c => {
  const k = 'P', P = [960, 380], L = 380;
  const pan = (id, kind) => `<g id="${id}"><path d="M0 0 L-90 170 M0 0 L90 170" style="stroke:var(--accent);stroke-width:2"/>
    <path d="M-104 170 Q0 214 104 170 Z" style="fill:var(--bg2);stroke:var(--accent);stroke-width:3"/>${sack(k, 0, 178, .5, kind)}</g>`;
  const s = c.svg(`${defs(k)}
    <g id="sA">${shade(k, 470, 800, 240)}${sack(k, 470, 800, 1)}</g>
    <g id="sB">${shade(k, 1450, 800, 240)}${sack(k, 1450, 800, 1, 'flour')}</g>
    ${arrow(470, 420, false, 'var(--seal)', 'id="aA"', 110)}${arrow(1450, 530, true, 'var(--accent)', 'id="aB"', 110)}
    <g id="bal" opacity="0">${shade(k, 960, 800, 200)}
      <path d="M900 800 L1020 800 L992 776 L928 776 Z" style="fill:var(--bg2);stroke:var(--accent);stroke-width:2"/>
      <line x1="960" y1="380" x2="960" y2="778" style="stroke:var(--accent);stroke-width:6"/>
      <line id="beam" style="stroke:var(--accent);stroke-width:7" stroke-linecap="round"/>
      <circle cx="960" cy="380" r="11" style="fill:var(--accent)"/>
      ${pan('panL', 'burlap')}${pan('panR', 'flour')}
      ${arrow(360, 500, false, 'var(--seal)', 'id="bA"', 110)}${arrow(1560, 610, true, 'var(--accent)', 'id="bB"', 110)}</g>`);
  const $ = id => s.querySelector('#' + id), a1 = c.at('a1'), a2 = c.at('a2'), a3 = c.at('a3'), a4 = c.at('a4'), a5 = c.at('a5');

  // a1：契约纸居中；左农民（怕跌 ↓），右磨坊主（怕涨 ↑）
  const pc = card(c, 960, 455, 380, 470, pactInner());
  const lA = c.h(`<div class="label">农民 · 怕跌</div>`), lB = c.h(`<div class="label">磨坊主 · 怕涨</div>`);
  c.place(lA, 470, 380); c.place(lB, 1450, 380);
  c.show(pc, a1 + .1, .8, { y: 30 });
  c.show($('sA'), a1 + .2, .7).show($('aA'), a1 + .5, .5, { y: -20 }).show(lA, a1 + .6, .6);
  c.show($('sB'), a1 + 1.0, .7).show($('aB'), a1 + 1.4, .5).show(lB, a1 + 1.6, .6);

  // a2：条款逐行浮现，两个签名依次落下
  c.show(pc.querySelectorAll('.ln'), a2 + .3, .6, { stagger: .5 });
  c.draw(pc.querySelector('path.sigA'), a2 + 2.0, .6).draw(pc.querySelector('path.sigB'), a2 + 2.6, .6);

  // a3：价格牌乱跳，契约上的 100 纹丝不动、发光
  c.to([$('aA'), $('aB'), lA, lB], { opacity: 0, duration: .5 }, a3);
  const bd = board(c, 1450, 440, 100, '秋季麦价'), num = bd.querySelector('.num');
  c.show(bd, a3 + .2, .6);
  const seq = [150, 60, 120, 80], j0 = a3 + .9;
  c.onFrame(t => { const i = Math.floor((t - j0) / .55), v = i < 0 ? 100 : seq[Math.min(i, seq.length - 1)];
    num.textContent = v; num.style.color = v > 100 ? 'var(--accent)' : v < 100 ? 'var(--seal)' : 'var(--ink)'; });
  c.to(pc.querySelector('.p100'), { textShadow: '0 0 18px rgba(220,170,90,.95)', duration: .6 }, a3 + 1.0);
  c.to(pc, { boxShadow: '0 30px 80px rgba(0,0,0,.6), 0 0 50px rgba(220,179,106,.55)', duration: .6 }, a3 + 1.0);

  // a4：变成天平，两只箭头抵消，天平阻尼摆动后回到水平
  c.to([pc, bd, $('sA'), $('sB')], { opacity: 0, duration: .6 }, a4);
  c.to($('bal'), { opacity: 1, duration: .7 }, a4 + .3);
  c.show([$('bA'), $('bB')], a4 + .6, .5);
  c.to([$('bA'), $('bB')], { opacity: 0, scale: .3, transformOrigin: '50% 50%', duration: .7 }, a4 + 1.7);
  c.ripple(960, 380, a4 + 2.4, { r: 110, count: 2 });
  const b0 = a4 + 1.0, th = t => { const u = Math.max(0, t - b0); return .16 * Math.exp(-1.3 * u) * Math.cos(2.6 * u); };
  c.onFrame(t => { const a = th(t), dx = L * Math.cos(a), dy = L * Math.sin(a), bm = $('beam');
    bm.setAttribute('x1', P[0] - dx); bm.setAttribute('y1', P[1] + dy); bm.setAttribute('x2', P[0] + dx); bm.setAttribute('y2', P[1] - dy);
    $('panL').setAttribute('transform', `translate(${P[0] - dx} ${P[1] + dy})`); $('panR').setAttribute('transform', `translate(${P[0] + dx} ${P[1] - dy})`); });

  // a5：天平淡出，契约回到正中，盖章「远期」
  c.to($('bal'), { opacity: 0, duration: .6 }, a5);
  c.to(pc, { opacity: 1, duration: .7 }, a5 + .3);
  c.stamp('远期', 1075, 600, a5 + 1.1, { rotate: -10, size: 46 });
};

/* ---------- 场景 3：堂岛米市（米价木牌 → 今→秋 → 1730） ---------- */
SCENES.dojima = c => {
  const b1 = c.at('b1'), b2 = c.at('b2'), b3 = c.at('b3'), X = i => 510 + i * 150;
  const names = ['加贺', '肥后', '筑前', '播磨', '备前', '长州', '筑后'], base = [62, 58, 60, 57, 61, 59, 63];
  const ax = y => 640 + (y - 1600) * 1.6;
  const s = c.svg(`<defs><filter id="glD" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="9"/></filter></defs>
    <line id="rail" x1="430" y1="292" x2="1490" y2="292" style="stroke:var(--accent);stroke-width:4"/>
    ${names.map((_, i) => `<line class="str" x1="${X(i)}" y1="292" x2="${X(i)}" y2="332" style="stroke:var(--accent);stroke-width:2"/>`).join('')}
    <line id="tline" x1="640" y1="620" x2="1280" y2="620" style="stroke:var(--accent);stroke-width:4"/>
    <path id="thead" d="M1258 604 L1282 620 L1258 636" fill="none" style="stroke:var(--accent);stroke-width:4"/>
    <g id="ticks">${[1600, 1700, 1800, 1900, 2000].map(y => `<line x1="${ax(y)}" y1="610" x2="${ax(y)}" y2="630" style="stroke:var(--accent);stroke-width:3"/>`).join('')}</g>
    <circle id="dg" cx="${ax(1730)}" cy="620" r="22" style="fill:var(--accent)" filter="url(#glD)" opacity="0"/>
    <circle id="dd" cx="${ax(1730)}" cy="620" r="10" style="fill:var(--accent)" opacity="0"/>`);
  const $ = id => s.querySelector('#' + id);

  // b1：契约纸缩小消失 → 一排米价木牌挂起来；背景铭文 DŌJIMA
  const mini = card(c, 960, 470, 190, 240, pactInner(.5), 'padding:12px 14px');
  c.show(mini, b1 + .1, .5);
  c.to(mini, { scale: .3, y: -150, opacity: 0, duration: .7, ease: 'power2.in' }, b1 + .8);
  c.bgWord('DŌJIMA', { y: 700, at: b1 + .5, opacity: .07 });
  c.draw($('rail'), b1 + .8, .8);
  const tags = names.map((n, i) => { const el = c.h(`<div style="position:absolute;width:104px;height:200px;box-sizing:border-box;padding:14px 0 8px;text-align:center;background:linear-gradient(180deg,#9a7444,#5c4020);border:2px solid rgba(220,179,106,.6);border-radius:4px;box-shadow:0 14px 26px rgba(0,0,0,.5);color:#f6e7c4">
      <div style="writing-mode:vertical-rl;margin:0 auto;height:104px;font-size:30px;font-weight:700;letter-spacing:.2em">${n}</div>
      <div class="big v" style="position:static;font-size:46px;line-height:1;color:#ffe9b8">${base[i]}</div></div>`); c.place(el, X(i), 432); return el; });
  c.show(s.querySelectorAll('.str'), b1 + 1.0, .4, { stagger: .1, y: 0 });
  c.show(tags, b1 + 1.1, .6, { stagger: .1 });

  // b2：木牌上的数字一格格翻动；金色时间线从「今」指向「秋」
  const f0 = b2 + .3;
  c.onFrame(t => { const n = Math.max(0, Math.floor((Math.min(t, b3) - f0) / .32));
    tags.forEach((el, i) => { el.querySelector('.v').textContent = t < f0 ? base[i] : base[i] + Math.round(4 * Math.sin(n * 1.7 + i * 2.3)); }); });
  const now = c.h(`<div class="label" style="font-size:30px;color:var(--ink)">今</div>`), aut = c.h(`<div class="label" style="font-size:30px;color:var(--accent)">秋</div>`);
  c.place(now, 600, 620); c.place(aut, 1322, 620);
  c.show(now, b2 + .3, .5).draw($('tline'), b2 + .5, 1.2).show($('thead'), b2 + 1.6, .4, { y: 0 }).show(aut, b2 + 1.6, .5);

  // b3：木牌收拢成一叠；时间线变时间轴，1730 被点亮
  tags.forEach((el, i) => c.to(el, { x: 960 - X(i) + (i - 3) * 7, y: -20 + Math.abs(i - 3) * 3, rotation: (i - 3) * 2, duration: .9, ease: 'power2.inOut' }, b3 + .1));
  c.to([$('rail'), ...s.querySelectorAll('.str'), now, aut, $('thead')], { opacity: 0, duration: .5 }, b3 + .1);
  const yrs = [1600, 1700, 1800, 1900, 2000].map(y => { const el = c.h(`<div class="label la" style="font-size:21px">${y}</div>`); c.place(el, ax(y), 654); return el; });
  c.show($('ticks'), b3 + .6, .5, { y: 0 }).show(yrs, b3 + .6, .5, { stagger: .06 });
  c.to($('dd'), { opacity: 1, duration: .3 }, b3 + 1.4);
  c.fromTo($('dg'), { opacity: 0, scale: .3, transformOrigin: '50% 50%' }, { opacity: .9, scale: 1.6, duration: .8 }, b3 + 1.4);
  c.ripple(ax(1730), 620, b3 + 1.5, { r: 70, count: 2 });
  const big = c.h(`<div class="big" style="font-size:58px;color:var(--accent);text-shadow:0 0 24px var(--glow)">1730</div>`); c.place(big, ax(1730), 572);
  c.show(big, b3 + 1.5, .7, { scale: .8 });
};

/* ---------- 场景 4：赖账 → 交易所 → 标准化合约 → 转手 → 期货 ---------- */
SCENES.exchange = c => {
  const k = 'X', c1 = c.at('c1'), c2 = c.at('c2'), c3 = c.at('c3'), c4 = c.at('c4'), c5 = c.at('c5'), c6 = c.at('c6');
  const FX = [560, 830, 1100, 1370];
  const s = c.svg(`${defs(k)}
    <g id="sA">${shade(k, 420, 800, 200)}${sack(k, 420, 800, .85)}</g>
    <g id="sB">${shade(k, 1500, 800, 200)}${sack(k, 1500, 800, .85, 'flour')}</g>
    ${temple(960, 792, 1, 'id="tp"')}
    <path id="lnA" d="M505 690 C610 640 690 700 762 770" fill="none" style="stroke:var(--accent);stroke-width:3"/>
    <path id="lnB" d="M1415 690 C1310 640 1230 700 1158 770" fill="none" style="stroke:var(--accent);stroke-width:3"/>
    <g id="ppl">${FX.map(x => c.fig(x, 830, 170, 'stand', { cls: 'pp' })).join('')}</g>`);
  const $ = id => s.querySelector('#' + id);

  // c1：契约（左右两半拼成）+ 价格牌涨到 150 → 农民签名褪色 → 裂开一道缝
  const clipL = 'clip-path:polygon(0 0,50% 0,46% 18%,54% 36%,47% 55%,53% 74%,48% 100%,0 100%)';
  const clipR = 'clip-path:polygon(50% 0,100% 0,100% 100%,48% 100%,53% 74%,47% 55%,54% 36%,46% 18%)';
  const hL = card(c, 960, 450, 340, 420, pactInner(.9), clipL), hR = card(c, 960, 450, 340, 420, pactInner(.9), clipR);
  const crack = c.h(`<svg viewBox="0 0 340 420" style="position:absolute;width:340px;height:420px;overflow:visible"><path d="M170 0 L156 76 L184 151 L160 231 L180 311 L163 420" fill="none" stroke="#2a1a0c" stroke-width="3" stroke-linejoin="round"/></svg>`);
  c.place(crack, 960, 450);
  c.show([hL, hR], c1 + .1, .7, { y: 30 });
  c.show($('sA'), c1 + .2, .6).show($('sB'), c1 + .3, .6);
  const bd = board(c, 1500, 430, 100, '秋季麦价'), num = bd.querySelector('.num');
  c.show(bd, c1 + .5, .5);
  c.counter(num, 100, 150, c1 + .9, .9, { ease: 'out' });
  c.to(num, { color: c.color('var(--accent)'), duration: .3 }, c1 + 1.5);
  c.to([...hL.querySelectorAll('.sigA'), ...hR.querySelectorAll('.sigA')], { opacity: .12, duration: 1 }, c1 + 1.6);
  c.draw(crack.querySelector('path'), c1 + 2.5, .7);
  c.sfx('crack', c1 + 2.5, .6);

  // c2：两半被拉开；中间立起交易所，两边各连一条金线
  c.to(hL, { x: -200, rotation: -6, opacity: 0, duration: 1.3, ease: 'power2.inOut' }, c2 + .1);
  c.to(hR, { x: 200, rotation: 6, opacity: 0, duration: 1.3, ease: 'power2.inOut' }, c2 + .1);
  c.to([crack, bd], { opacity: 0, duration: .5 }, c2 + .1);
  c.draw(s.querySelectorAll('#tp .tp'), c2 + .7, 1.4, { stagger: .05 });
  c.show(s.querySelector('#tp .tt'), c2 + 1.8, .6, { y: 0 });
  c.draw([$('lnA'), $('lnB')], c2 + 2.2, .9);

  // c3：一张标准合约 “咔” 地复制成一叠
  c.to([$('tp'), $('lnA'), $('lnB'), $('sA'), $('sB')], { opacity: 0, duration: .5 }, c3);
  const copies = [5, 4, 3, 2, 1].map(i => { const el = card(c, 960, 470, 480, 290, stdInner, 'padding:24px 34px'); c.set(el, { opacity: 0 }); return [el, i]; });
  const top = card(c, 960, 470, 480, 290, stdInner, 'padding:24px 34px');
  c.show(top, c3 + .2, .6, { y: 30 });
  copies.forEach(([el, i]) => c.fromTo(el, { opacity: 0, x: 0, y: 0 }, { opacity: 1 - i * .1, x: i * 16, y: -i * 14, duration: .35, ease: 'power3.out' }, c3 + 1.1));
  c.sfx('tick', c3 + 1.1, .6);

  // c4：四个字段逐项高亮
  top.querySelectorAll('.f').forEach((f, i) => c.to(f, { backgroundColor: 'rgba(220,179,106,.42)', boxShadow: 'inset 4px 0 0 #8b2a20', duration: .3 }, c4 + .3 + i * .6));

  // c5：合约卡像筹码一样在小人之间流转
  c.to([top, ...copies.map(([el]) => el)], { y: 240, scale: .3, opacity: 0, duration: .7, ease: 'power2.in' }, c5);
  c.show(s.querySelectorAll('.pp'), c5 + .2, .6, { stagger: .08 });
  const chip = c.h(`<div class="card" style="box-sizing:border-box;width:96px;height:62px;padding:0;font-size:16px;line-height:62px;text-align:center;letter-spacing:.2em;color:#6b5434">合约</div>`);
  c.place(chip, FX[0], 730);
  c.show(chip, c5 + .5, .4);
  [1, 2, 3].forEach(j => c.to(chip, { x: FX[j] - FX[0], duration: .45, ease: 'power2.inOut' }, c5 + .5 + j * .6));
  c.to(chip, { x: 1300, opacity: 0, duration: .5, ease: 'power2.in' }, c5 + 2.6);

  // c6：一张合约卡回到正中放大，盖章「期货」
  c.to(s.querySelectorAll('.pp'), { opacity: 0, duration: .5 }, c6);
  c.to(top, { y: 170, scale: 1, opacity: 1, duration: .8, ease: 'power2.out' }, c6 + .1);
  c.stamp('期货', 1160, 720, c6 + 1.0, { rotate: -10, size: 50 });
};

/* ---------- 场景 5：保证金 → 逐日结算 → 强制平仓 ---------- */
SCENES.margin = c => {
  const k = 'M', d1 = c.at('d1'), d2 = c.at('d2'), d3 = c.at('d3'), N = 14, XL = 600, XR = 1320, Y = 790;
  const s = c.svg(`${defs(k)}
    <ellipse id="redglow" cx="${XL}" cy="770" rx="80" ry="50" style="fill:var(--seal)" filter="url(#gl${k})" opacity="0"/>
    <g id="stL">${shade(k, 1240, Y, 120)}${coins(k, 1240, Y, N)}</g>
    <g id="stR">${shade(k, XR, Y, 120)}${coins(k, XR, Y, N)}</g>
    <g id="mline"><line x1="${XL - 70}" y1="${Y - 3 * 11 - 6}" x2="${XL + 70}" y2="${Y - 3 * 11 - 6}" style="stroke:var(--seal);stroke-width:3" stroke-dasharray="10 7"/></g>
    <g id="fly" opacity="0">${coins(k, 0, 0, 1)}</g>`);
  const $ = id => s.querySelector('#' + id);

  // d1：合约卡 + 推来一小摞金币；比例条：保证金只占一小截
  const ct = card(c, 760, 470, 400, 240, `<div style="display:flex;justify-content:space-between;align-items:baseline"><span style="font-size:26px;letter-spacing:.3em;color:#6b5434">小麦合约</span><span style="font-family:var(--la);font-style:italic;font-size:20px;color:#8a7350">one lot</span></div>
    <div style="height:1px;background:#9c8862;margin:8px 0 14px"></div>
    <div style="font-size:24px">数量 · 一手</div><div style="font-size:24px">合约价值 <b style="font-family:var(--la);font-size:42px;line-height:1;color:#8b2a20">100</b></div>`);
  c.show(ct, d1 + .1, .7, { y: 30 });
  c.set($('stL'), { opacity: 0 });
  c.fromTo($('stL'), { x: 420, opacity: 0 }, { x: 0, opacity: 1, duration: .9, ease: 'power2.out' }, d1 + .7);
  const bar = c.h(`<div style="position:absolute;left:560px;top:650px;width:800px;height:12px;border:1px solid var(--dim);border-radius:6px">
    <div class="fill" style="width:0;height:100%;background:var(--accent);box-shadow:0 0 14px var(--glow);border-radius:6px"></div>
    <div class="label" style="left:0;top:-36px;font-size:20px;color:var(--accent)">保证金</div>
    <div class="label" style="right:0;top:-36px;font-size:20px">合约价值</div></div>`);
  c.show(bar, d1 + 1.3, .6);
  c.to(bar.querySelector('.fill'), { width: '10%', duration: .8, ease: 'power2.out' }, d1 + 1.8);

  // d2：卡片落到两个账户中间；日历一天一翻，价格跳动，金币在多空之间流动
  c.to(ct, { x: 200, y: 275, scale: .5, duration: .9, ease: 'power2.inOut' }, d2);
  c.to(bar, { opacity: 0, duration: .5 }, d2);
  c.to($('stL'), { x: XL - 1240, duration: .9, ease: 'power2.inOut' }, d2);
  c.show($('stR'), d2 + .4, .6);
  const cal = c.h(`<div style="position:absolute;width:150px;height:170px;box-sizing:border-box;background:linear-gradient(180deg,#efe6d2,#d9cdb3);border-radius:6px;overflow:hidden;box-shadow:0 18px 40px rgba(0,0,0,.5);text-align:center;color:#2a2118">
    <div style="background:#8b2a20;color:#f6e7c4;font-size:22px;letter-spacing:.3em;padding:6px 0 4px">十月</div>
    <div class="big dd" style="position:static;font-size:84px;line-height:1.4;color:#2a2118">12</div></div>`);
  c.place(cal, 830, 380);
  const bd = board(c, 1090, 380, 100, '当日结算价', 250), num = bd.querySelector('.num');
  c.show([cal, bd], d2 + .2, .6, { stagger: .1 });
  const tL = c.h(`<div class="label">多头 · 买方</div>`), tR = c.h(`<div class="label">空头 · 卖方</div>`);
  c.place(tL, XL, 610); c.place(tR, XR, 610);
  c.show([tL, tR], d2 + .5, .6);
  c.set($('mline'), { opacity: 0 });

  const PX = [100, 104, 99, 95, 97, 92, 87], t0 = d2 + .6, st = .6, nL = p => Math.max(0, 6 + Math.round((p - 100) / 2.5));
  const cnL = s.querySelectorAll('#stL .cn'), cnR = s.querySelectorAll('#stR .cn'), fly = $('fly');
  c.onFrame(t => {
    const u = (t - t0) / st, i = u < 0 ? 0 : Math.min(PX.length - 1, Math.floor(u)), f = u - Math.floor(u);
    const moving = u >= 1 && u < PX.length && f < .75, a = moving ? nL(PX[i - 1]) : nL(PX[i]), b = 12 - a;
    cnL.forEach((e, j) => { e.style.opacity = j < a ? 1 : 0; }); cnR.forEach((e, j) => { e.style.opacity = j < b ? 1 : 0; });
    cal.querySelector('.dd').textContent = 12 + i; num.textContent = PX[i];
    num.style.color = i && PX[i] > PX[i - 1] ? 'var(--accent)' : i && PX[i] < PX[i - 1] ? 'var(--seal)' : 'var(--ink)';
    const dl = i ? nL(PX[i]) - nL(PX[i - 1]) : 0;
    if (moving && dl) { const p = f / .75, fr = dl > 0 ? [XR, Y - b * 11] : [XL, Y - a * 11], to = dl > 0 ? [XL, Y - a * 11] : [XR, Y - b * 11];
      fly.setAttribute('transform', `translate(${fr[0] + (to[0] - fr[0]) * p} ${fr[1] + (to[1] - fr[1]) * p - 150 * Math.sin(Math.PI * p)})`); fly.style.opacity = 1;
    } else fly.style.opacity = 0;
  });

  // d3：多头金币跌破维持线、闪红 → 盖章「平仓」→ 合约卡滑出桌面
  const fT = t0 + (PX.length - 1) * st + .5;
  c.to($('mline'), { opacity: 1, duration: .4 }, d3 + .1);
  const ml = c.h(`<div class="label" style="font-size:18px;color:var(--seal)">维持线</div>`); c.place(ml, XL - 120, Y - 39);
  c.show(ml, d3 + .2, .4);
  c.fromTo($('redglow'), { opacity: 0 }, { opacity: .8, duration: .25, repeat: 3, yoyo: true }, fT);
  const sp = c.stamp('平仓', 965, 742, fT + .8, { rotate: -8, size: 40 });
  c.to([ct, sp], { x: '+=1100', rotation: 10, duration: 1.0, ease: 'power2.in' }, fT + 1.6);
};

/* ---------- 场景 6：投机者与杠杆 ---------- */
SCENES.lever = c => {
  const k = 'L', e1 = c.at('e1'), e2 = c.at('e2'), e3 = c.at('e3'), e4 = c.at('e4'), e5 = c.at('e5'), PV = [700, 640];
  const pan = (x, kind) => `<path d="M${x} 400 L${x - 90} 560 M${x} 400 L${x + 90} 560" style="stroke:var(--accent);stroke-width:2"/>
    <path d="M${x - 104} 560 Q${x} 604 ${x + 104} 560 Z" style="fill:var(--bg2);stroke:var(--accent);stroke-width:3"/>${sack(k, x, 566, .5, kind)}`;
  const s = c.svg(`${defs(k)}
    <g id="bal">${shade(k, 960, 800, 200)}
      <path d="M900 800 L1020 800 L992 776 L928 776 Z" style="fill:var(--bg2);stroke:var(--accent);stroke-width:2"/>
      <line x1="960" y1="400" x2="960" y2="778" style="stroke:var(--accent);stroke-width:6"/>
      <line x1="600" y1="400" x2="1320" y2="400" style="stroke:var(--accent);stroke-width:7" stroke-linecap="round"/>
      <circle cx="960" cy="400" r="11" style="fill:var(--accent)"/>${pan(600, 'burlap')}${pan(1320, 'flour')}</g>
    ${c.fig(1170, 800, 190, 'walk', { cls: 'spec' })}
    <g id="sw"><g id="swIn">${arrow(1125, 590, true, 'var(--accent)', 'id="up"', 90)}${arrow(1185, 500, false, 'var(--seal)', 'id="down"', 90)}</g></g>
    <g id="rk"><g id="rkIn"><circle r="34" style="fill:var(--seal)" filter="url(#gl${k})" opacity=".55"/><circle r="20" fill="url(#risk${k})"/>
      <text y="-32" text-anchor="middle" font-size="22" style="fill:var(--seal)">风险</text></g></g>
    <g id="lv" opacity="0">${shade(k, PV[0], 800, 170)}
      <path d="M700 646 L650 800 L750 800 Z" style="fill:var(--bg2);stroke:var(--accent);stroke-width:3"/>
      <g id="arm"><rect x="600" y="634" width="920" height="12" rx="4" style="fill:var(--accent)"/>${sack(k, 645, 634, .5)}</g></g>
    <g id="cg"><g id="cA"><g transform="rotate(7 700 640)">${coins(k, 1460, 634, 3)}</g></g>
      <g id="cB"><g transform="rotate(7 700 640)">${coins(k, 1370, 634, 3)}</g></g></g>`);
  const $ = id => s.querySelector('#' + id), spec = s.querySelector('.spec');

  // e1：天平再现（已平衡），投机者走到支点旁
  c.show($('bal'), e1 + .1, .7);
  c.set(spec, { opacity: 0 }).set($('cA'), { opacity: 0 });
  c.fromTo(spec, { x: 560, opacity: 0 }, { x: 0, opacity: 1, duration: 1.8, ease: 'power1.out' }, e1 + .5);

  // e2：头顶 ↑ ↓ 两只箭头来回摇摆
  c.show($('sw'), e2 + .1, .5);
  c.onFrame(t => { const w = Math.sin(Math.max(0, t - e2) * Math.PI * 1.6);
    $('swIn').setAttribute('transform', `rotate(${12 * w} 1155 595)`);
    $('up').style.opacity = .35 + .65 * Math.max(0, w); $('down').style.opacity = .35 + .65 * Math.max(0, -w); });

  // e3：暗红“风险”小球从麦袋那边滚到投机者手里
  const r0 = e3 + .5, A = [600, 432], C = [880, 220], B = [1205, 700];
  c.show($('rk'), e3 + .1, .5, { y: 0, scale: .5 });
  c.onFrame(t => { const p = c.prog(t, r0, 1.4, 'inOut'), q = 1 - p;
    $('rkIn').setAttribute('transform', `translate(${q * q * A[0] + 2 * q * p * C[0] + p * p * B[0]} ${q * q * A[1] + 2 * q * p * C[1] + p * p * B[1]})`); });

  // e4：变成杠杆：短臂一整袋麦子，长臂一小摞保证金
  c.to([$('bal'), spec, $('sw'), $('rk')], { opacity: 0, duration: .6 }, e4);
  c.to($('lv'), { opacity: 1, duration: .6 }, e4 + .3);
  c.fromTo($('cA'), { y: -160, opacity: 0 }, { y: 0, opacity: 1, duration: .5, ease: 'power2.in' }, e4 + 1.0);
  c.set($('cB'), { opacity: 0 });
  const tC = c.h(`<div class="label" style="color:var(--accent)">保证金</div>`), tS = c.h(`<div class="label">一整袋麦子</div>`);
  c.place(tC, 1460, 520); c.place(tS, 645, 480);
  c.show([tS, tC], e4 + 1.4, .6, { stagger: .2 });

  // e5：杠杆左右摇：长臂一抬，本金翻倍；一沉，本金化为灰烬
  const phi = t => -5 + 5 * c.prog(t, e4 + 1.5, .8, 'inOut') - 7 * c.prog(t, e5 + .2, .8, 'inOut') + 14 * c.prog(t, e5 + 1.9, .7, 'inOut');
  c.onFrame(t => { const p = phi(t); $('arm').setAttribute('transform', `rotate(${p} 700 640)`); $('cg').setAttribute('transform', `rotate(${p - 7} 700 640)`); });
  c.to([tC, tS], { opacity: 0, duration: .4 }, e5);
  c.to($('cB'), { opacity: 1, duration: .4 }, e5 + 1.0);
  const gain = c.h(`<div class="label" style="font-size:28px;color:var(--accent)">价格 +10%　本金 ×2</div>`), loss = c.h(`<div class="label" style="font-size:28px;color:var(--seal)">价格 −10%　本金归零</div>`);
  c.place(gain, 1320, 420); c.place(loss, 1320, 420);
  c.show(gain, e5 + 1.0, .5);
  c.to(gain, { opacity: 0, duration: .4 }, e5 + 1.8);
  c.show(loss, e5 + 2.6, .5);
  c.dissolve($('cA'), e5 + 2.7, { dur: 1.4 });
  c.dissolve($('cB'), e5 + 2.8, { dur: 1.4, sfx: false });
};

/* ---------- 场景 7：交割与负油价 ---------- */
SCENES.oil = c => {
  const k = 'O', f1 = c.at('f1'), f2 = c.at('f2'), f3 = c.at('f3'), f4 = c.at('f4'), f5 = c.at('f5'), f6 = c.at('f6');
  const CX = i => 440 + i * 150, pile = [[330, 800], [450, 800], [570, 800], [390, 650], [510, 650], [630, 650], [450, 500], [570, 500], [510, 350]];
  const s = c.svg(`${defs(k)}<defs><clipPath id="tkO"><rect x="1130" y="470" width="340" height="330"/></clipPath></defs>
    <line id="axis" x1="380" y1="530" x2="1560" y2="530" style="stroke:var(--dim);stroke-width:2"/>
    <line id="due" x1="1540" y1="514" x2="1540" y2="546" style="stroke:var(--accent);stroke-width:4"/>
    <g id="pile">${pile.map(([x, y]) => barrel(x, y, .8, 'class="pb"')).join('')}</g>
    <g id="tank"><rect id="oilf" x="1130" y="800" width="340" height="0" style="fill:var(--ink)" opacity=".85" clip-path="url(#tkO)"/>
      <path d="M1130 470 L1130 800 L1470 800 L1470 470 M1130 580 L1470 580 M1130 690 L1470 690" fill="none" style="stroke:var(--ink);stroke-width:3"/>
      <path d="M1130 470 Q1300 404 1470 470" fill="none" style="stroke:var(--ink);stroke-width:3"/></g>
    <path id="spill" d="M1462 466 C1500 476 1484 560 1490 640 C1494 720 1484 780 1504 798" fill="none" style="stroke:var(--ink);stroke-width:9" stroke-linecap="round"/>
    <ellipse id="pud" cx="1514" cy="802" rx="56" ry="9" style="fill:var(--ink)" opacity="0"/>
    <g id="b0">${shade(k, 960, 800, 170)}${barrel(960, 800, 1)}</g>`);
  const $ = id => s.querySelector('#' + id);

  // f1：一排合约卡，到期前纷纷翻面熄灭；只剩两张走到「交割」
  const cards = Array.from({ length: 7 }, (_, i) => { const el = card(c, CX(i), 410, 110, 150, `<div style="writing-mode:vertical-rl;margin:0 auto;font-size:22px;letter-spacing:.3em;color:#6b5434">合约</div>
      <div class="back" style="position:absolute;inset:0;border-radius:4px;background:#1a120a;border:1px solid rgba(220,179,106,.35);opacity:0"></div>
      <svg class="sil" viewBox="-80 -200 160 210" style="position:absolute;left:15px;top:20px;width:80px;height:110px;opacity:0"><path d="M-72 -180 L-72 -12 A72 16 0 0 0 72 -12 L72 -180 Z M-72 -180 A72 16 0 0 1 72 -180" fill="#2a1a0c"/></svg>`, 'padding:18px 0'); return el; });
  c.show(cards, f1 + .1, .5, { stagger: .05 });
  c.show([$('axis'), $('due')], f1 + .1, .5, { y: 0 });
  const dueL = c.h(`<div class="label" style="font-size:24px;color:var(--accent)">交割</div>`), nowL = c.h(`<div class="label" style="font-size:20px">今</div>`);
  c.place(dueL, 1540, 568); c.place(nowL, 380, 568);
  c.show([nowL, dueL], f1 + .2, .5);
  [0, 5, 2, 6, 3].forEach((i, n) => { const t = f1 + .5 + n * .22;
    c.to(cards[i], { scaleX: 0, duration: .14, ease: 'power1.in' }, t);
    c.to(cards[i].querySelector('.back'), { opacity: 1, duration: .01 }, t + .14);
    c.to(cards[i], { scaleX: 1, opacity: .35, duration: .14, ease: 'power1.out' }, t + .15); });
  c.to(cards[1], { x: 1540 - CX(1) - 14, y: -10, duration: .9, ease: 'power2.inOut' }, f1 + 1.8);
  c.to(cards[4], { x: 1540 - CX(4) + 14, y: 10, duration: .9, ease: 'power2.inOut' }, f1 + 1.9);

  // f2：熄灭的卡退场；一张走到交割的卡背面透出油桶 → 油桶落到桌面
  c.to([...[0, 2, 3, 5, 6].map(i => cards[i]), cards[1], $('axis'), $('due'), dueL, nowL], { opacity: 0, duration: .5 }, f2);
  c.to(cards[4], { x: 960 - CX(4), y: -20, scale: 1.4, duration: .8, ease: 'power2.inOut' }, f2 + .1);
  c.to(cards[4].querySelector('.sil'), { opacity: 1, duration: .6 }, f2 + .9);
  c.to(cards[4], { opacity: 0, duration: .4 }, f2 + 1.9);
  c.set($('b0'), { opacity: 0 });
  c.fromTo($('b0'), { y: -300, opacity: 0 }, { y: 0, opacity: 1, duration: .6, ease: 'power2.in' }, f2 + 1.9);
  c.ripple(960, 800, f2 + 2.5, { r: 120, count: 1 });

  // f3：右侧价格牌一路往下滚；f4：穿过零点到 −37.63，整屏反转白底（主题切换由引擎做）
  const bd = board(c, 1300, 460, '18.27', 'WTI 五月合约 · 美元/桶', 320), num = bd.querySelector('.num');
  c.show(bd, f3 + .2, .6);
  const v0 = f3 + .6, v1 = f4 + .15;
  c.onFrame(t => { const v = t < v1 ? 18.27 - 17.27 * c.prog(t, v0, v1 - v0 - .1, 'out') : 1 - 38.63 * c.prog(t, v1, 1.3, 'out');
    num.textContent = (v < 0 ? '−' : '') + Math.abs(v).toFixed(2); num.style.color = v < 0 ? 'var(--seal)' : 'var(--ink)'; });
  c.to(bd, { x: 960 - 1300, y: 290 - 460, scale: 1.25, duration: .7, ease: 'power2.inOut' }, f4);
  c.to($('b0'), { x: 690 - 960, scale: .8, transformOrigin: '50% 100%', duration: .7, ease: 'power2.inOut' }, f4);

  // f5：油桶越堆越多，塞满储油罐，罐顶溢出
  c.show(s.querySelectorAll('.pb'), f5 + .2, .4, { stagger: .16, y: -40 });
  c.show($('tank'), f5 + .1, .6, { y: 0 });
  const tl = c.h(`<div class="label" style="font-size:22px;color:var(--ink)">库欣储油罐 <span style="font-family:var(--la);font-style:italic;color:var(--dim)">Cushing, Oklahoma</span></div>`);
  c.place(tl, 1300, 400);
  c.show(tl, f5 + .3, .6);
  c.to($('oilf'), { attr: { y: 470, height: 330 }, duration: 1.8, ease: 'power1.inOut' }, f5 + .6);
  c.draw($('spill'), f5 + 2.4, .8);
  c.to($('pud'), { opacity: .85, duration: .5 }, f5 + 3.0);

  // f6：合约卡贴着一摞金币，被推向对面的空位
  c.to([$('pile'), $('tank'), $('spill'), $('pud'), $('b0'), tl], { opacity: .1, duration: .6 }, f6);
  const slot = c.h(`<div style="position:absolute;width:250px;height:160px;box-sizing:border-box;border:3px dashed var(--dim);border-radius:8px"></div>`);
  c.place(slot, 1360, 660);
  const sl = c.h(`<div class="label">对手方</div>`); c.place(sl, 1360, 768);
  const pc = card(c, 500, 660, 230, 150, `<div style="font-size:24px;letter-spacing:.2em;color:#6b5434">原油合约</div>
    <div style="font-family:var(--la);font-style:italic;font-size:19px;color:#8a7350">WTI · May 2020</div>
    <svg viewBox="-60 -80 120 90" style="position:absolute;right:-30px;top:-46px;width:120px;height:90px;overflow:visible">${coins(k, 0, 0, 5)}</svg>`, 'padding:24px 26px');
  c.show([slot, sl], f6 + .2, .5).show(pc, f6 + .3, .6);
  c.to(pc, { x: 860, duration: 1.8, ease: 'power2.inOut' }, f6 + 1.0);
};

/* ---------- 场景 8：回到春天的麦田 ---------- */
SCENES.spring = c => {
  const k = 'S', g1 = c.at('g1'), g2 = c.at('g2'), g3 = c.at('g3'), g4 = c.at('g4');
  const s = c.svg(`${defs(k)}
    <g id="fld">${field(k, 700, 800)}</g>
    <g id="skg">${shade(k, 1060, 800, 200)}${sack(k, 1060, 800, .8)}</g>
    <g id="post">${shade(k, 1380, 800, 90)}<line x1="1380" y1="636" x2="1380" y2="800" style="stroke:var(--accent);stroke-width:5"/></g>
    <g id="ico"><g class="ic">${shade(k, 560, 820, 130)}${sack(k, 560, 820, .45)}</g>
      <g class="ic">${shade(k, 960, 820, 150)}${temple(960, 820, .33)}</g>
      <g class="ic">${shade(k, 1360, 820, 90)}${c.fig(1360, 820, 150, 'stand')}</g></g>
    <g id="rk"><g id="rkIn"><circle r="34" style="fill:var(--seal)" filter="url(#gl${k})" opacity=".55"/><circle r="20" fill="url(#risk${k})"/></g></g>`);
  const $ = id => s.querySelector('#' + id);

  // g1：开场的田垄、嫩麦苗、麦袋，和那张写着 100 的契约纸
  c.show($('fld'), g1 + .1, .8, { y: 10 }).show($('skg'), g1 + .5, .7).set($('post'), { opacity: 0 });
  const pc = card(c, 1380, 570, 230, 290, pactInner(.6), 'padding:14px 18px');
  c.set(pc, { rotation: 4 });
  c.show(pc, g1 + .9, .8, { y: 30 });

  // g2：风险小球在农民、交易所、投机者之间传递，最后停在画面中央
  c.to([$('fld'), $('skg'), pc], { opacity: 0, duration: .6 }, g2);
  c.show(s.querySelectorAll('.ic'), g2 + .2, .6, { stagger: .15 });
  const lbs = [['农民', 560], ['交易所', 960], ['投机者', 1360]].map(([t, x]) => { const el = c.h(`<div class="label">${t}</div>`); c.place(el, x, 856); return el; });
  c.show(lbs, g2 + .3, .6, { stagger: .15 });
  const PT = [[560, 690], [960, 690], [1360, 650], [960, 410], [985, 470]];
  const hops = [[g2 + .9, .6, 110], [g2 + 1.7, .6, 110], [g2 + 2.6, .8, 0], [g3 + .6, .7, 0]];
  c.show($('rk'), g2 + .6, .4, { y: 0, scale: .5 });
  c.onFrame(t => { let [x, y] = PT[0];
    hops.forEach(([h0, d, arc], i) => { if (t >= h0) { const p = c.prog(t, h0, d, 'inOut');
      x = PT[i][0] + (PT[i + 1][0] - PT[i][0]) * p; y = PT[i][1] + (PT[i + 1][1] - PT[i][1]) * p - arc * Math.sin(Math.PI * p); } });
    $('rkIn').setAttribute('transform', `translate(${x} ${y})`); });

  // g3：小球化作契约上的「100」，契约收拢、发光
  c.to([...s.querySelectorAll('.ic'), ...lbs], { opacity: 0, duration: .5 }, g3);
  c.to(pc, { opacity: 1, x: 960 - 1380, y: 470 - 570, rotation: 0, scale: 1.35, duration: .9, ease: 'power2.inOut' }, g3 + .1);
  c.to($('rk'), { scale: 0, opacity: 0, transformOrigin: '985px 470px', duration: .4 }, g3 + 1.2);
  c.to(pc.querySelector('.p100'), { textShadow: '0 0 20px rgba(220,170,90,1)', duration: .5 }, g3 + 1.3);
  c.to(pc, { scale: 1.2, boxShadow: '0 30px 80px rgba(0,0,0,.6), 0 0 60px rgba(220,179,106,.65)', duration: 1.0, ease: 'power2.inOut' }, g3 + 1.8);

  // g4：回到麦苗，价格牌在 100 处轻微闪烁；镜头缓缓推近，淡出
  c.to(pc, { opacity: 0, duration: .7 }, g4);
  c.to([$('fld'), $('skg')], { opacity: 1, duration: .8 }, g4 + .3);
  const bd = board(c, 1380, 560, 100, '秋季麦价'), num = bd.querySelector('.num');
  c.show([bd, $('post')], g4 + .7, .7);
  c.onFrame(t => { num.style.opacity = t < g4 + 1.4 ? 1 : .78 + .22 * Math.cos((t - g4 - 1.4) * Math.PI * 1.4); });
  c.camera(g4 + .3, 4.6, { scale: 1.16, origin: '700px 740px', ease: 'power1.inOut' });
  c.to([$('fld'), $('skg'), $('post'), bd], { opacity: 0, duration: 1.1 }, g4 + 3.9);
};
})();
