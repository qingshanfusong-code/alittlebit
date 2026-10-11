#!/usr/bin/env node
/* ============================================================
   一键安装 / 自检（首次使用运行一次；以后出问题也可以再跑）：
     node <skill目录>/studio/tools/setup.mjs
   做的事：检查 Node → 安装 npm 依赖（失败自动换国内镜像）→ 检查 ffmpeg
           → 找浏览器（Playwright 自带 Chromium / 本机 Chrome / Edge，都没有就下载 Chromium）
           → 用内置范例试跑一次。
   ============================================================ */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WIN = process.platform === 'win32';
const results = [];
const ok = (k, v) => { results.push(['✓', k, v]); console.log(`✓ ${k}${v ? '：' + v : ''}`); };
const bad = (k, v) => { results.push(['✗', k, v]); console.log(`✗ ${k}${v ? '：' + v : ''}`); };
const run = (cmd, args, extra = {}) => spawnSync(cmd, args, { cwd: ROOT, stdio: 'inherit', shell: WIN, timeout: 15 * 60e3, ...extra });

console.log(`Vibe 知识短片 · 安装自检\nskill 工作室目录：${ROOT}\n`);

// 1. Node
const major = +process.versions.node.split('.')[0];
if (major < 18) { bad('Node.js', `当前 v${process.versions.node}，需要 18 以上，请到 https://nodejs.org 安装 LTS 版`); process.exit(1); }
ok('Node.js', 'v' + process.versions.node);

// 2. npm 依赖
const need = ['playwright', 'gsap', '@fontsource/noto-serif-sc', '@fontsource/cormorant-garamond'];
const missing = () => need.filter(p => !fs.existsSync(path.join(ROOT, 'node_modules', ...p.split('/'), 'package.json')));
if (missing().length) {
  console.log('\n→ 安装依赖（字体、动画库、浏览器驱动，约 100MB）…');
  let r = run('npm', ['install', '--no-audit', '--no-fund']);
  if (r.status !== 0 || missing().length) {
    console.log('\n→ 默认源失败，改用国内镜像 registry.npmmirror.com 重试…');
    r = run('npm', ['install', '--no-audit', '--no-fund', '--registry=https://registry.npmmirror.com']);
  }
}
missing().length ? bad('npm 依赖', '安装失败：' + missing().join(', ') + '。请检查网络后重新运行本脚本') : ok('npm 依赖', '字体 / GSAP / Playwright 已就绪');

// 3. ffmpeg
const ff = spawnSync('ffmpeg', ['-version'], { shell: WIN, encoding: 'utf8' });
if (ff.status === 0) ok('ffmpeg', (ff.stdout.split('\n')[0] || '').replace('ffmpeg version ', '').split(' ')[0]);
else bad('ffmpeg', '没找到。安装方法：' + (WIN ? 'PowerShell 运行 winget install Gyan.FFmpeg' : process.platform === 'darwin' ? '终端运行 brew install ffmpeg' : 'sudo apt install ffmpeg') + '，装完重开终端');

// 4. 浏览器
async function findBrowser() {
  let chromium; try { ({ chromium } = await import(pathToFileURL(path.join(ROOT, 'node_modules', 'playwright', 'index.mjs')).href)); } catch { return null; }
  const tries = [['Playwright Chromium', {}], ...['/opt/pw-browsers/chromium', process.env.CHROMIUM_PATH].filter(p => p && fs.existsSync(p)).map(p => ['Chromium', { executablePath: p }]),
    ['本机 Chrome', { channel: 'chrome' }], ['本机 Edge', { channel: 'msedge' }]];
  for (const [label, o] of tries) { try { const b = await chromium.launch(o); await b.close(); return label; } catch { /* 下一个 */ } }
  return '';
}
if (!missing().length) {
  let br = await findBrowser();
  if (br === '') {
    console.log('\n→ 没找到可用浏览器，下载 Chromium（约 150MB）…');
    let r = run('npx', ['playwright', 'install', 'chromium']);
    if (r.status !== 0) {
      console.log('\n→ 改用国内镜像重试…');
      r = run('npx', ['playwright', 'install', 'chromium'], { env: { ...process.env, PLAYWRIGHT_DOWNLOAD_HOST: 'https://npmmirror.com/mirrors/playwright' } });
    }
    br = await findBrowser();
  }
  br ? ok('浏览器', br) : bad('浏览器', '没有可用的浏览器。请安装 Chrome 或 Edge，或运行 npx playwright install chromium');
}

// 5. 试跑
if (results.every(r => r[0] === '✓')) {
  const r = spawnSync(process.execPath, [path.join(ROOT, 'tools', 'render.mjs'), 'examples/brachistochrone', '--timing'], { cwd: ROOT, encoding: 'utf8' });
  r.status === 0 ? ok('试跑', (r.stdout.split('\n')[0] || '').trim()) : bad('试跑', (r.stderr || r.stdout).slice(-600));
}

const fails = results.filter(r => r[0] === '✗');
console.log(fails.length ? `\n还有 ${fails.length} 项没就绪，按上面的提示处理后重新运行本脚本。` : '\n全部就绪，可以开始做视频了。');
process.exit(fails.length ? 1 : 0);
