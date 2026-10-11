// 《最速降线》画面层：只写“画什么”，台词与时间都在 script.json
// 每个场景函数拿到 c（见 engine-api.md），时间一律用 c.at('节拍id', 偏移秒)

/* ---------- 场景 1：比赛（直线 vs 摆线） ---------- */
SCENES.race = c => {
  const R = 190, A = [660, 380], B = [A[0] + Math.PI * R, A[1] + 2 * R];
  const cyc = th => [A[0] + R * (th - Math.sin(th)), A[1] + R * (1 - Math.cos(th))];
  const cycD = 'M' + Array.from({ length: 91 }, (_, i) => cyc(Math.PI * i / 90).map(v => v.toFixed(1)).join(' ')).join(' L');

  const s = c.svg(`
    <defs><filter id="glR" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter>
      <radialGradient id="ivory" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#fffaf0"/><stop offset=".55" stop-color="#d8cdb6"/><stop offset="1" stop-color="#6d6250"/></radialGradient>
      <radialGradient id="goldball" cx=".35" cy=".3" r=".75"><stop offset="0" stop-color="#fff2c8"/><stop offset=".5" stop-color="#d9a94e"/><stop offset="1" stop-color="#6a4a17"/></radialGradient></defs>
    <path id="line" d="M${A} L${B}" fill="none" style="stroke:var(--ink);stroke-width:3" opacity=".6"/>
    <path id="cycGlow" d="${cycD}" fill="none" style="stroke:var(--accent);stroke-width:12" filter="url(#glR)" opacity="0"/>
    <path id="cyc" d="${cycD}" fill="none" style="stroke:var(--accent);stroke-width:4"/>
    <circle id="pA" cx="${A[0]}" cy="${A[1]}" r="8" style="fill:var(--ink)"/>
    <circle id="pB" cx="${B[0]}" cy="${B[1]}" r="8" style="fill:var(--ink)"/>
    <circle id="ballL" cx="${A[0]}" cy="${A[1]}" r="16" fill="url(#ivory)" opacity="0"/>
    <circle id="ballC" cx="${A[0]}" cy="${A[1]}" r="16" fill="url(#goldball)" opacity="0"/>`);
  const $ = id => s.querySelector('#' + id);

  const la = c.h(`<div class="big" style="font-size:52px;font-style:italic">A</div>`); c.place(la, A[0] - 46, A[1] - 34);
  const lb = c.h(`<div class="big" style="font-size:52px;font-style:italic">B</div>`); c.place(lb, B[0] + 46, B[1] + 10);
  const steep = c.h(`<div class="label">先陡</div>`); c.place(steep, cyc(.75)[0] - 70, cyc(.75)[1]);
  const flat = c.h(`<div class="label">后缓</div>`); c.place(flat, cyc(2.7)[0] - 10, cyc(2.7)[1] + 44);
  const tC = c.h(`<div class="label" style="font-size:30px;color:var(--accent)">摆线 <span class="v" style="font-family:var(--la);font-size:40px">0.00 s</span></div>`);
  const tL = c.h(`<div class="label" style="font-size:30px;color:var(--ink)">直线 <span class="v" style="font-family:var(--la);font-size:40px">0.00 s</span></div>`);
  c.place(tC, 1430, 470, 'left'); c.place(tL, 1430, 540, 'left');

  // q1：两点 → 直线 → 曲线
  c.show([$('pA'), $('pB')], c.at('q1', .2), .6).show([la, lb], c.at('q1', .3), .8);
  c.draw($('line'), c.at('q1', .8), 1.0).draw($('cyc'), c.at('q1', 1.5), 1.6);
  // q2：直线“最短”——提亮
  c.to($('line'), { opacity: 1, duration: .5 }, c.at('q2', .2));
  // q3：比赛。摆线 2.0s 到达，直线 2.37s（真实物理比例，按半径 1 米折算成秒）
  const g = R * (Math.PI / 2) ** 2, L = Math.hypot(B[0] - A[0], B[1] - A[1]), acc = g * (B[1] - A[1]) / L, TL = Math.sqrt(2 * L / acc);
  const go = c.at('q3', .7);
  c.to([$('ballL'), $('ballC')], { opacity: 1, duration: .4 }, c.at('q3', .1)).to($('line'), { opacity: .6, duration: .4 }, c.at('q3', .1));
  c.show([tC, tL], c.at('q3', .2), .6, { stagger: .1 });
  c.onFrame(t => {
    const tau = Math.max(0, t - go), [x, y] = cyc(Math.min(Math.PI, tau * Math.PI / 2));
    $('ballC').setAttribute('cx', x); $('ballC').setAttribute('cy', y);
    const u = Math.min(L, .5 * acc * tau * tau) / L;
    $('ballL').setAttribute('cx', A[0] + (B[0] - A[0]) * u); $('ballL').setAttribute('cy', A[1] + (B[1] - A[1]) * u);
  });
  c.counter(tC.querySelector('.v'), 0, 1, go, 2, { decimals: 2, suffix: ' s', ease: 'linear' });
  c.counter(tL.querySelector('.v'), 0, TL / 2, go, TL, { decimals: 2, suffix: ' s', ease: 'linear' });
  c.ripple(B[0], B[1], go + 2, { r: 120 });
  c.ripple(B[0], B[1], go + TL, { color: 'var(--ink)', count: 1, r: 90 });
  // q4：输家变暗，赢家发光，标注“先陡、后缓”
  c.to([$('line'), $('ballL'), tL], { opacity: .22, duration: .8 }, c.at('q4'));
  c.to($('cycGlow'), { opacity: .9, duration: .8 }, c.at('q4'));
  c.show(steep, c.at('q4', .3), .7).show(flat, c.at('q4', .9), .7);
};

/* ---------- 场景 2：战书 → 六个月 → 一夜 → 匿名 → 狮子 ---------- */
SCENES.letter = c => {
  const card = c.h(`<div class="card" style="left:560px;top:250px;width:800px;height:470px">
    <div style="font-family:var(--la);font-style:italic;font-size:34px;letter-spacing:.06em;color:#6b5434">Problema novum</div>
    <div style="font-size:16px;color:#8a7350;letter-spacing:.3em;margin:2px 0 26px">新问题 · 敬请数学家们解答</div>
    <div>已知竖直平面上的两点 A 与 B，<br>求一条曲线，使质点只受重力、<br>从 A 沿它滑到 B，<b style="color:#8b2a20">用时最短</b>。</div>
    <div style="position:absolute;left:48px;bottom:34px;font-family:var(--la);font-style:italic;font-size:24px;color:#6b5434">— Johann Bernoulli</div>
    <svg viewBox="0 0 220 110" style="position:absolute;right:44px;bottom:30px;width:200px">
      <path d="M20 15 L200 95" stroke="#9c8862" stroke-width="2" stroke-dasharray="5 5" fill="none"/>
      <circle cx="20" cy="15" r="4" fill="#4a3a26"/><circle cx="200" cy="95" r="4" fill="#4a3a26"/>
      <text x="6" y="12" font-size="14" font-style="italic" fill="#4a3a26">A</text><text x="204" y="108" font-size="14" font-style="italic" fill="#4a3a26">B</text>
      <text x="100" y="40" font-size="26" fill="#8b2a20">?</text></svg></div>`);
  c.set(card, { rotation: -2 });
  c.show(card, c.at('c1', .2), 1.0, { y: 50 });
  const seal = c.stamp('战书', 1325, 300, c.at('c1', 1.9), { rotate: -12, size: 46 });

  // c2：信推到左边；右边六个月逐一点亮
  c.to([card, seal], { x: -330, scale: .78, duration: 1.0, ease: 'power2.inOut' }, c.at('c2'));
  const months = c.h(`<div style="position:absolute;left:1180px;top:470px;display:flex;gap:44px">${['I', 'II', 'III', 'IV', 'V', 'VI'].map(m =>
    `<div style="text-align:center"><div class="dot" style="width:22px;height:22px;border-radius:50%;margin:0 auto;border:2px solid var(--accent)"></div><div style="font-family:var(--la);font-size:26px;color:var(--dim);margin-top:12px">${m}</div></div>`).join('')}</div>`);
  c.show(months, c.at('c2', .4), .6);
  c.$$('.dot').forEach((d, i) => { c.to(d, { backgroundColor: c.color('var(--accent)'), boxShadow: `0 0 18px ${c.color('var(--glow)')}`, duration: .2 }, c.at('c2', .8 + i * .25)); });

  // c3：六个月 → 一个晚上（16:00 → 次日 04:00）
  c.hide(months, c.at('c3'), .5);
  const clock = c.h(`<div class="big" style="font-size:150px;color:var(--accent);text-shadow:0 0 30px var(--glow)">16:00</div>`); c.place(clock, 1420, 470);
  const night = c.h(`<div class="label" style="font-size:26px">收到信 → 天亮之前</div>`); c.place(night, 1420, 590);
  c.show([clock, night], c.at('c3', .3), .7);
  const h0 = c.at('c3', .8);
  c.onFrame(t => { clock.textContent = String((16 + Math.floor(c.prog(t, h0, 2.2, 'inOut') * 12)) % 24).padStart(2, '0') + ':00'; });

  // c4：匿名答卷
  c.hide([clock, night], c.at('c4'), .5);
  const ans = c.h(`<div class="card" style="left:1130px;top:300px;width:470px;height:330px;padding:32px 38px">
    <div style="font-family:var(--la);font-style:italic;font-size:30px;color:#6b5434">Anonymous</div>
    <div style="font-size:15px;color:#8a7350;letter-spacing:.3em">寄自英格兰 · 未署名</div>
    <svg viewBox="0 0 400 170" style="width:100%;margin-top:18px"><path class="sol" d="M10 10 C 40 150, 160 168, 390 120" fill="none" stroke="#8b2a20" stroke-width="3"/>
      <circle cx="10" cy="10" r="4" fill="#4a3a26"/><circle cx="390" cy="120" r="4" fill="#4a3a26"/></svg></div>`);
  c.set(ans, { rotation: 3 });
  c.show(ans, c.at('c4', .2), .9, { y: 40 });
  c.draw(ans.querySelector('.sol'), c.at('c4', .9), 1.2);

  // c5：利爪与狮子
  c.hide([card, seal], c.at('c5'), .8);
  c.to(ans, { x: -380, scale: 1.08, rotation: 0, duration: 1.2, ease: 'power2.inOut' }, c.at('c5'));
  c.bgWord('EX UNGUE LEONEM', { y: 760, at: c.at('c5', .4), opacity: .09, size: 120 });
};

/* ---------- 场景 3：摆线的诞生 → 变分 → 拉格朗日 ---------- */
SCENES.variation = c => {
  const R = 150, X0 = 600, Y0 = 330, A = [X0, Y0], B = [X0 + Math.PI * R, Y0 + 2 * R];
  const pt = th => [X0 + R * (th - Math.sin(th)), Y0 + R * (1 - Math.cos(th))];
  const s = c.svg(`
    <defs><filter id="glV" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter></defs>
    <line id="ceil" x1="${X0 - 80}" y1="${Y0}" x2="${X0 + 620}" y2="${Y0}" style="stroke:var(--dim);stroke-width:2"/>
    <g id="family" fill="none" style="stroke:var(--ink);stroke-width:2"></g>
    <circle id="wheel" r="${R}" fill="none" style="stroke:var(--dim);stroke-width:2"/>
    <line id="spoke" style="stroke:var(--dim);stroke-width:2"/>
    <path id="traceGlow" fill="none" style="stroke:var(--accent);stroke-width:12" filter="url(#glV)" opacity="0"/>
    <path id="trace" fill="none" style="stroke:var(--accent);stroke-width:4"/>
    <circle id="pen" r="9" style="fill:#fff"/>
    <circle cx="${A[0]}" cy="${A[1]}" r="8" style="fill:var(--ink)"/>
    <circle id="endB" cx="${B[0]}" cy="${B[1]}" r="8" style="fill:var(--ink)" opacity="0"/>`);
  const $ = id => s.querySelector('#' + id);

  // e1：圆在“天花板”下滚动，圆上一点划出摆线
  const r0 = c.at('e1', .4), rd = 3.2;
  const d = th => 'M' + Array.from({ length: 61 }, (_, i) => pt(th * i / 60).map(v => v.toFixed(1)).join(' ')).join(' L');
  c.set([$('wheel'), $('spoke'), $('pen')], { opacity: 0 }).show([$('wheel'), $('spoke'), $('pen')], c.at('e1', .1), .5);
  c.onFrame(t => {
    const th = Math.PI * c.prog(t, r0, rd, 'inOut'), [px, py] = pt(th), cx = X0 + R * th, cy = Y0 + R;
    $('wheel').setAttribute('cx', cx); $('wheel').setAttribute('cy', cy);
    $('spoke').setAttribute('x1', cx); $('spoke').setAttribute('y1', cy); $('spoke').setAttribute('x2', px); $('spoke').setAttribute('y2', py);
    $('pen').setAttribute('cx', px); $('pen').setAttribute('cy', py);
    $('trace').setAttribute('d', d(Math.max(th, 1e-3))); $('traceGlow').setAttribute('d', d(Math.max(th, 1e-3)));
  });
  c.to($('endB'), { opacity: 1, duration: .4 }, r0 + rd);

  // e2：所有“可能的路”（端点不动的扰动曲线）
  c.hide([$('wheel'), $('spoke'), $('pen'), $('ceil')], c.at('e2'), .6);
  const fam = $('family'), ks = [-2.2, -1.4, -.7, .6, 1.2, 1.9];
  fam.innerHTML = ks.map(k => `<path d="M${Array.from({ length: 61 }, (_, i) => { const th = Math.PI * i / 60, [x, y] = pt(th);
    return `${x.toFixed(1)} ${(y + k * 42 * Math.sin(th) * (1 - .3 * Math.cos(th))).toFixed(1)}`; }).join(' L')}" opacity=".45"/>`).join('')
    + `<path d="M${A} L${B}" opacity=".45"/>`;
  c.draw(fam.querySelectorAll('path'), c.at('e2', .3), 1.3, { stagger: .12 });

  // e3：其他路一条条熄灭，只剩最优；δT = 0
  c.hide(fam.querySelectorAll('path'), c.at('e3', .2), .5, { stagger: .14 });
  c.to($('traceGlow'), { opacity: .9, duration: .8 }, c.at('e3', 1.0));
  const eq = c.h(`<div class="big" style="font-size:110px;font-style:italic;color:var(--ink)">δT = 0</div>`); c.place(eq, 1490, 470);
  const eqn = c.h(`<div class="label" style="font-size:24px">让“总用时”取极值</div>`); c.place(eqn, 1490, 560);
  c.show(eq, c.at('e3', 1.0), 1.0).show(eqn, c.at('e3', 1.5), .8);

  // e4：δ 放大——拉格朗日的符号
  c.to([$('trace'), $('traceGlow'), $('endB'), eqn], { opacity: .25, duration: .8 }, c.at('e4'));
  c.to(eq, { left: 960, top: 470, scale: 1.6, color: c.color('var(--accent)'), textShadow: `0 0 40px ${c.color('var(--glow)')}`, duration: 1.4, ease: 'power2.inOut' }, c.at('e4', .2));
  const sig = c.h(`<div class="label la" style="font-size:30px">Joseph-Louis Lagrange · 1755</div>`); c.place(sig, 960, 640);
  c.show(sig, c.at('e4', 1.2), .9);
  c.sfx('shimmer', c.at('e4', .3), .5);
};
