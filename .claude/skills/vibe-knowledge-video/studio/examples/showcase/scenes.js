// 风格样片：每个场景演示一种色调 + 若干组件，可当作写新场景时的参考实现

// night · 吊灯、剪影、暖色照片 → 裂纹 → 碎裂（shatter）
SCENES.party = c => {
  c.svg(`${c.lamp(960, 230, { cord: 260, cone: 760, len: 820 })}
    ${[700, 820, 1100, 1220].map((x, i) => c.fig(x, 760, 190 + (i % 2) * 14, 'stand', { color: '#05070c' })).join('')}`);
  const photo = c.h(`<div style="position:absolute;left:600px;top:250px;width:720px;height:440px;border:10px solid #efe6d2;
    background:radial-gradient(ellipse at 50% 20%,#f3c27a,#9a5a2c 60%,#3a2010);box-shadow:0 30px 80px rgba(0,0,0,.6)">
    <svg viewBox="0 0 720 440" style="width:100%;height:100%">${[180, 300, 420, 540].map((x, i) => c.fig(x, 420, 200 + (i % 2) * 20, i % 2 ? 'raise' : 'stand', { color: 'rgba(40,20,8,.85)' })).join('')}</svg></div>`);
  c.set(photo, { rotation: -4 });
  c.show(photo, c.at('n1', .2), 1, { scale: .92 });
  c.shatter(photo, c.at('n2', 1.1), { cx: 52, cy: 40 });
  c.burst(960, 440, c.at('n2', 1.1), { kind: 'shards', count: 60, colors: ['#f3c27a', '#efe6d2'], speed: [200, 600], gravity: 600 });
};

// mono · 一排小人 → 化为灰烬（dissolve）
SCENES.puppets = c => {
  const s = c.svg(`<line x1="200" y1="820" x2="1720" y2="820" style="stroke:var(--dim);stroke-width:2"/>
    ${Array.from({ length: 9 }, (_, i) => c.fig(400 + i * 140, 820, 150, i % 3 === 1 ? 'walk' : 'stand', { cls: 'p' })).join('')}`);
  c.show(s.querySelectorAll('.p'), c.at('m1', .2), .6, { stagger: .08 });
  s.querySelectorAll('.p').forEach((p, i) => c.dissolve(p, c.at('m2', .6 + i * .12), { sfx: i ? false : 'whoosh' }));
};

// abyss · 竖排滚字（rollChars）+ 惊奇度进度条
SCENES.poem = c => {
  const line = c.h(`<div style="position:absolute;left:0;right:0;top:400px;text-align:center;font-size:72px;font-weight:300;letter-spacing:.18em">
    那天夜里，窗外下起了<span class="roll" style="color:var(--accent);text-shadow:0 0 24px var(--glow)">雨</span></div>`);
  c.show(line, c.at('a1'), 1);
  c.rollChars(line.querySelector('.roll'), ['雨', '雪', '鱼', '星', '花', '灰', '火', '光'], c.at('a1', 1.0), 2.4);
  const bar = c.h(`<div style="position:absolute;left:760px;top:560px;width:400px;height:2px;background:rgba(255,255,255,.15)">
    <div class="fill" style="height:2px;width:0;background:var(--accent);box-shadow:0 0 12px var(--glow)"></div>
    <div class="label" style="top:-34px;left:0;font-size:16px">惊奇 SURPRISE</div><div class="label la v" style="top:-38px;right:0;font-size:20px">0 bits</div></div>`);
  c.show(bar, c.at('a1', .6), .6);
  c.to(bar.querySelector('.fill'), { width: '86%', duration: 2.4, ease: 'power2.out' }, c.at('a1', 1.0));
  c.counter(bar.querySelector('.v'), 0, 7, c.at('a1', 1.0), 2.4, { suffix: ' bits' });
};

// crimson · 透视跑道（draw）+ 终点彩屑（burst confetti）
SCENES.track = c => {
  const vx = 960, vy = 470;
  const s = c.svg(`<defs><linearGradient id="trk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a0909"/><stop offset="1" stop-color="#7a2420"/></linearGradient></defs>
    <polygon points="${vx},${vy} 1920,1080 0,1080" fill="url(#trk)" opacity=".9"/>
    ${[-3, -2, -1, 0, 1, 2, 3].map(k => `<line class="ln" x1="${vx}" y1="${vy}" x2="${vx + k * 330}" y2="1080" style="stroke:#f4e9e4;stroke-width:${k === 0 ? 0 : 3}" opacity=".85"/>`).join('')}
    ${[0, 1, 2, 3, 4, 5, 6, 7, 8].map(i => `<circle cx="${180 + i * 195}" cy="${vy - 30 - (i % 2) * 14}" r="${10 + (i % 3) * 5}" fill="#fff" opacity=".18"/>`).join('')}`);
  c.draw(s.querySelectorAll('.ln'), c.at('r1', .2), 1.4, { stagger: .05 });
  c.camera(c.at('r1'), 6, { scale: 1.12, y: 30, ease: 'none' });
  c.burst(960, 640, c.at('r1', 3.2), { kind: 'confetti', count: 140, colors: ['#f4e9e4', '#e58e84', '#ffd9a0'], angle: -Math.PI / 2, spread: 2.2, speed: [300, 900], gravity: 520, sfx: 'shimmer' });
};

// paper · 反转为白底 → 疯子提灯 → 大字
SCENES.madman = c => {
  const s = c.svg(`<line x1="160" y1="760" x2="1760" y2="760" style="stroke:var(--ink);stroke-width:2"/>
    ${[300, 380, 460, 1300, 1380, 1460, 1540].map(x => c.fig(x, 760, 110, 'stand', { color: '#8a8a8a' })).join('')}
    <g class="mad">${c.fig(820, 760, 200, 'walk', { color: '#111' })}<circle cx="864" cy="660" r="9" fill="none" stroke="#111" stroke-width="3"/></g>`);
  c.show(s.querySelector('.mad'), c.at('p1', .3), .8);
  c.to(s.querySelector('.mad'), { x: 120, duration: 4, ease: 'none' }, c.at('p1', .3));
  const big = c.h(`<div style="position:absolute;left:0;right:0;top:230px;text-align:center;font-size:150px;font-weight:900;letter-spacing:.12em;color:#111">上帝已死</div>`);
  const la = c.h(`<div class="label la" style="left:0;right:0;top:420px;text-align:center;font-size:30px;color:#555">Gott ist tot.</div>`);
  c.show(big, c.at('p2'), .25, { scale: 1.25, blur: false }).show(la, c.at('p2', .5), .8);
  c.sfx('boom', c.at('p2'), 1);
};

// gilt · 记分牌：计数（counter）+ 盖章（stamp）+ 背景拉丁铭文
SCENES.dice = c => {
  c.bgWord('ALEA IACTA EST', { y: 610, at: c.at('g1'), opacity: .06 });
  const board = c.h(`<div style="position:absolute;left:560px;top:380px;width:800px;display:flex;justify-content:space-between;text-align:center">
    <div><div class="label" style="position:static;color:var(--accent)">甲</div><div class="big a" style="position:static;font-size:130px">0</div></div>
    <div class="big" style="position:static;font-size:90px;color:var(--dim);margin-top:60px">:</div>
    <div><div class="label" style="position:static;color:var(--seal)">乙</div><div class="big b" style="position:static;font-size:130px">0</div></div></div>`);
  c.show(board, c.at('g1', .2), .8);
  c.counter(board.querySelector('.a'), 0, 50, c.at('g1', .4), 1.4);
  c.counter(board.querySelector('.b'), 0, 20, c.at('g1', .4), 1.4);
  c.stamp('中断', 960, 470, c.at('g1', 2.2), { solid: true, rotate: 8, size: 42 });
};
