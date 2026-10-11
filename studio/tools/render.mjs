#!/usr/bin/env node
/* ============================================================
   逐帧确定性渲染：HTML 动画 → MP4（无掉帧、无录屏 UI、可重复渲染）
   用法（在仓库根目录运行 node studio/tools/render.mjs …，或在 studio/ 下运行 node tools/render.mjs …，效果相同）：
     node tools/render.mjs videos/<名>              正式渲染 1920x1080@30 → videos/<名>/out/<名>.mp4
     node tools/render.mjs videos/<名> --preview    快速预览 960x540@15  → out/preview.mp4
     node tools/render.mjs videos/<名> --sheet      关键帧联系表（每个节拍 1 格）→ out/sheet-1.jpg …
     node tools/render.mjs videos/<名> --sheet --at 3,8.5,12 --w 960   指定时间点、放大单格看细节
     node tools/render.mjs videos/<名> --from 10 --to 20      只渲染一段（改完局部时用）
     node tools/render.mjs videos/<名> --fps 60                60 帧
     node tools/render.mjs videos/<名> --timing     只打印节拍时间表（不截图，最省）
     node tools/render.mjs videos/<名> --cover      导出封面 out/cover.jpg（默认取标题卡定格）
     node tools/render.mjs --serve [--port 8020]     浏览器实时预览（空格播放，←→ 跳 1 秒）
   ============================================================ */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const argv = process.argv.slice(2);
const flag = k => argv.includes('--' + k);
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : d; };
const proj = argv.find(a => !a.startsWith('--') && !/^[\d.,]+$/.test(a));

/* ---------- 静态服务器 ---------- */
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.webp': 'image/webp' };
function serve(port = 0) {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      const f = path.join(ROOT, path.normalize(p));
      if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { rsp.writeHead(404); return rsp.end('404'); }
      rsp.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      fs.createReadStream(f).pipe(rsp);
    }).listen(port, '127.0.0.1', () => res(srv));
  });
}

if (flag('serve')) {
  const srv = await serve(+opt('port', 8020));
  const port = srv.address().port;
  const list = fs.existsSync(path.join(ROOT, 'videos')) ? fs.readdirSync(path.join(ROOT, 'videos')).filter(d => fs.existsSync(path.join(ROOT, 'videos', d, 'script.json'))) : [];
  console.log('预览地址（空格播放/暂停，←→ 跳 1 秒，拖动进度条）：');
  list.forEach(d => console.log(`  http://127.0.0.1:${port}/engine/index.html?p=videos/${d}`));
  await new Promise(() => {});
}
if (!proj) { console.error('用法：node tools/render.mjs videos/<项目名> [--preview|--sheet|--timing]'); process.exit(1); }
const projDir = path.join(ROOT, proj), name = path.basename(projDir), outDir = path.join(projDir, 'out');
if (!fs.existsSync(path.join(projDir, 'script.json'))) { console.error('找不到 ' + path.join(proj, 'script.json')); process.exit(1); }
fs.mkdirSync(outDir, { recursive: true });

/* ---------- 浏览器 ---------- */
const { chromium } = await import('playwright');
async function launch() {
  const args = ['--font-render-hinting=none', '--disable-lcd-text', '--force-color-profile=srgb', '--autoplay-policy=no-user-gesture-required'];
  try { return await chromium.launch({ args }); }
  catch (e) {
    for (const p of [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'].filter(Boolean))
      if (fs.existsSync(p)) return chromium.launch({ args, executablePath: p });
    console.error('启动 Chromium 失败。本机首次使用请运行：npx playwright install chromium'); throw e;
  }
}
const PREVIEW = flag('preview'), SHEET = flag('sheet') || flag('cover'), COVER = flag('cover'), TIMING = flag('timing');
const SW = COVER ? 1920 : +opt('w', 480);   // 联系表单格宽度；看细节时用 --w 960 或 1920
const [VW, VH] = SHEET ? [SW, Math.round(SW * 9 / 16)] : PREVIEW ? [960, 540] : [1920, 1080];
const srv = await serve();
const browser = await launch();
const page = await browser.newPage({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 });
const logs = [];
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
await page.goto(`http://127.0.0.1:${srv.address().port}/engine/index.html?p=${encodeURIComponent(proj.replace(/\\/g, '/'))}&render=1`);
const ok = await page.evaluate(() => window.__ready);
if (!ok) { const err = await page.evaluate(() => window.__error); console.error(err, '\n' + logs.filter(l => !l.includes(err.split('\n')[0])).join('\n')); await browser.close(); process.exit(1); }
const info = await page.evaluate(() => ({ duration: window.__duration, fps: window.__fps, cues: window.__cues, beats: window.__beats, meta: window.__meta }));
if (logs.length) console.warn(logs.join('\n'));

const fmt = s => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`;
console.log(`《${info.meta.title || name}》 总长 ${fmt(info.duration)}（${info.duration.toFixed(1)}s），${info.beats.length} 个节拍，${info.cues.length} 个音效`);
if (TIMING || SHEET) for (const b of info.beats) console.log(`  ${fmt(b.start).padStart(6)}  ${(b.end - b.start).toFixed(1).padStart(4)}s  ${b.id.padEnd(8)} ${b.scene.padEnd(12)} ${b.say.replace(/\*\*/g, '').replace(/\n/g, ' / ')}`);
if (TIMING) { await browser.close(); srv.close(); process.exit(0); }

/* ---------- 工具 ---------- */
function run(cmd, args, stdin) {
  return new Promise((res, rej) => {
    const p = spawn(cmd, args, { stdio: [stdin ? 'pipe' : 'ignore', 'ignore', 'pipe'] });
    let err = ''; p.stderr.on('data', d => { err += d; });
    p.on('close', c => (c === 0 ? res() : rej(new Error(`${cmd} 退出码 ${c}\n${err.slice(-1500)}`))));
    if (stdin) stdin(p);
  });
}

/* ---------- 封面：标题卡定格（或 --at 指定时间），无标注 1920x1080 ---------- */
if (COVER) {
  const tb = info.beats.find(b => b.id === 'title') || info.beats.find(b => b.scene.startsWith('@title')) || info.beats[0];
  const t = +opt('at', tb.start + Math.min(3.2, (tb.end - tb.start) - .8));
  await page.evaluate(t => window.__seek(t), t);
  const out = path.join(outDir, 'cover.jpg');
  fs.writeFileSync(out, await page.screenshot({ type: 'jpeg', quality: 95 }));
  console.log(`封面（${t.toFixed(1)}s）：${path.relative(ROOT, out)}`);
  await browser.close(); srv.close(); process.exit(0);
}

/* ---------- 联系表：每个节拍 1 格，供 Claude/你快速审阅构图 ---------- */
if (SHEET) {
  const custom = opt('at', null) ?? argv.find(a => /^[\d.,]+$/.test(a) && argv[argv.indexOf(a) - 1] === '--at');
  const times = custom ? custom.split(',').map(Number).map(t => ({ t, id: '' }))
    : info.beats.map(b => ({ id: b.id, t: Math.min(b.end - .4, b.start + Math.max(1.2, (b.end - b.start) * .7)) }));
  const tmp = path.join(outDir, '.sheet'); fs.rmSync(tmp, { recursive: true, force: true }); fs.mkdirSync(tmp);
  for (let i = 0; i < times.length; i++) {
    await page.evaluate(([t, l]) => { window.__seek(t); window.__label(l); }, [times[i].t, `${times[i].id} ${times[i].t.toFixed(1)}s`]);
    fs.writeFileSync(path.join(tmp, `f${String(i).padStart(3, '0')}.jpg`), await page.screenshot({ type: 'jpeg', quality: 82 }));
  }
  const cols = +opt('cols', 4), per = cols * +opt('rows', 4);
  fs.readdirSync(outDir).filter(f => /^sheet-\d+\.jpg$/.test(f)).forEach(f => fs.rmSync(path.join(outDir, f)));
  const sheets = [];
  for (let s = 0; s * per < times.length; s++) {
    const n = Math.min(per, times.length - s * per), rows = Math.ceil(n / cols), out = path.join(outDir, `sheet-${s + 1}.jpg`);
    await run('ffmpeg', ['-y', '-v', 'error', '-start_number', String(s * per), '-i', path.join(tmp, 'f%03d.jpg'), '-frames:v', '1',
      '-vf', `tile=${cols}x${rows}:padding=4:color=0x333333`, '-q:v', '3', out]);
    sheets.push(path.relative(ROOT, out));
  }
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log('联系表：' + sheets.join('  '));
  await browser.close(); srv.close(); process.exit(0);
}

/* ---------- 视频 ---------- */
const fps = +opt('fps', PREVIEW ? 15 : info.fps || 30);
const from = +opt('from', 0), to = Math.min(+opt('to', info.duration), info.duration);
const nFrames = Math.ceil((to - from) * fps);
const tag = PREVIEW ? 'preview' : (from > 0 || to < info.duration) ? `${name}_${from}-${to}` : name;
const silent = path.join(outDir, `.${tag}.silent.mp4`), final = path.join(outDir, `${tag}.mp4`);
const t0 = Date.now();
await run('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', PREVIEW ? 'veryfast' : 'slow', '-crf', PREVIEW ? '26' : '17', '-pix_fmt', 'yuv420p', '-r', String(fps), silent], async p => {
  for (let i = 0; i < nFrames; i++) {
    await page.evaluate(t => window.__seek(t), from + i / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: PREVIEW ? 80 : 95 });
    if (!p.stdin.write(buf)) await new Promise(r => p.stdin.once('drain', r));
    if (i % (fps * 5) === 0) process.stdout.write(`\r  渲染 ${i}/${nFrames} 帧  ${((Date.now() - t0) / 1000).toFixed(0)}s `);
  }
  p.stdin.end();
});
process.stdout.write(`\r  渲染 ${nFrames}/${nFrames} 帧  ${((Date.now() - t0) / 1000).toFixed(0)}s\n`);
await browser.close(); srv.close();

/* ---------- 混音：配乐 + 柔和音效 → 响度标准化到 -16 LUFS ---------- */
const sfxPath = n => [path.join(projDir, 'sfx', n + '.wav'), path.join(projDir, 'sfx', n + '.mp3'), path.join(ROOT, 'sfx', n + '.wav'), path.join(ROOT, 'sfx', n + '.mp3')].find(f => fs.existsSync(f));
const inputs = [], filters = [], labels = [];
const missing = new Set();
for (const c of info.cues) {
  if (c.t < from || c.t >= to) continue;
  const f = sfxPath(c.name); if (!f) { missing.add(c.name); continue; }
  const k = inputs.length / 2 + 1; inputs.push('-i', f);   // 0 号输入是无声视频
  const ms = Math.round((c.t - from) * 1000);
  filters.push(`[${k}:a]aresample=48000,aformat=channel_layouts=stereo,volume=${(c.gain * (info.meta.sfxGain ?? .5)).toFixed(3)},adelay=delays=${ms}:all=1[a${k}]`);
  labels.push(`[a${k}]`);
}
if (missing.size) console.warn('  缺少音效文件（已跳过）：' + [...missing].join(', '));
// 配乐：meta.bgm（自己的音乐文件）优先；否则按 meta.music 自动生成（"piano" 默认 | "ambient" | "none" 不要配乐）
let music = info.meta.bgm ? path.join(projDir, info.meta.bgm) : null, musicGain = info.meta.bgmGain ?? .6;
if (music && !fs.existsSync(music)) { console.warn('  找不到 bgm 文件：' + info.meta.bgm + '，改用自动配乐'); music = null; }
const style = info.meta.music ?? 'piano';
if (!music && style !== 'none') {
  const { makeMusic, writeWav } = await import('./music.mjs');
  const params = { dur: +info.duration.toFixed(2), style, bpm: info.meta.musicBpm ?? 72,
    seed: info.meta.musicSeed ?? [...name].reduce((h, ch) => (h * 31 + ch.codePointAt(0)) >>> 0, 7) % 1000,
    accents: info.beats.filter(b => b.type === 'title').map(b => +b.start.toFixed(2)) };
  music = path.join(outDir, '.music.wav'); const key = path.join(outDir, '.music.json');
  if (!fs.existsSync(music) || !fs.existsSync(key) || fs.readFileSync(key, 'utf8') !== JSON.stringify(params)) {
    writeWav(music, makeMusic(params)); fs.writeFileSync(key, JSON.stringify(params));
  }
  musicGain = info.meta.musicGain ?? 1;
}
if (music) {
  const k = inputs.length / 2 + 1; inputs.push('-i', music);
  const len = to - from, fadeOwn = info.meta.bgm ? `,afade=t=out:st=${Math.max(0, len - 2.5)}:d=2.5` : '';
  filters.push(`[${k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=${from}:${to},asetpts=PTS-STARTPTS,volume=${musicGain}${fadeOwn}[bgm]`);
  labels.push('[bgm]');
}
const dur = (to - from).toFixed(3);
if (labels.length) {
  filters.push(`${labels.join('')}amix=inputs=${labels.length}:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,apad[aout]`);
  await run('ffmpeg', ['-y', '-v', 'error', '-i', silent, ...inputs, '-filter_complex', filters.join(';'), '-map', '0:v', '-map', '[aout]',
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', dur, '-movflags', '+faststart', final]);
} else {
  await run('ffmpeg', ['-y', '-v', 'error', '-i', silent, '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v', '-map', '1:a',
    '-c:v', 'copy', '-c:a', 'aac', '-t', dur, '-movflags', '+faststart', final]);
}
fs.rmSync(silent, { force: true });
console.log(`完成：${path.relative(ROOT, final)}  （${fmt(to - from)}，${fps}fps，用时 ${((Date.now() - t0) / 1000).toFixed(0)}s）`);
