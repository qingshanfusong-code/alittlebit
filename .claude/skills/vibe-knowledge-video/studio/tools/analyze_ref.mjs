#!/usr/bin/env node
/* ============================================================
   学习新的参考视频（风格学习用，一次性成本）：
     node <skill目录>/studio/tools/analyze_ref.mjs 参考视频.mp4 [输出目录]
   产出（默认在当前目录的 ref_<文件名>/ 下）：
     sheet_*.jpg  每秒 1 帧的联系表（每张 15 帧，约 1.5k token/张——给 Claude 看这个，不要看原视频）
     spec.png     音频频谱（看有没有人声、BGM 段落、音效位置）
     report.txt   时长/分辨率、响度、静音段、硬切点
   录屏素材会自动裁掉黑边。
   ============================================================ */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const [input, outArg] = process.argv.slice(2);
if (!input || !fs.existsSync(input)) { console.error('用法：node analyze_ref.mjs 参考视频.mp4 [输出目录]'); process.exit(1); }
const out = outArg || `ref_${path.parse(input).name}`;
fs.mkdirSync(out, { recursive: true });
const ff = args => spawnSync('ffmpeg', ['-hide_banner', ...args], { encoding: 'utf8', maxBuffer: 64 << 20 });
const errText = args => ff(args).stderr || '';

const crop = (errText(['-ss', '3', '-i', input, '-t', '3', '-vf', 'cropdetect=24:2:0', '-f', 'null', '-']).match(/crop=[0-9:]+/g) || []).pop();
const r1 = ff(['-v', 'error', '-y', '-i', input, '-vf', `${crop ? crop + ',' : ''}fps=1,scale=520:-2,tile=3x5:padding=4:color=red`, path.join(out, 'sheet_%d.jpg')]);
if (r1.status !== 0) { console.error('ffmpeg 失败：' + r1.stderr); process.exit(1); }
ff(['-v', 'error', '-y', '-i', input, '-lavfi', 'showspectrumpic=s=1400x300:legend=1:scale=log:fscale=log', path.join(out, 'spec.png')]);

const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=width,height,r_frame_rate', '-of', 'compact', input], { encoding: 'utf8' }).stdout;
const loud = (errText(['-i', input, '-af', 'ebur128', '-f', 'null', '-']).match(/^\s+(I|LRA):.*$/gm) || []).join('\n');
const sil = (errText(['-i', input, '-af', 'silencedetect=n=-40dB:d=0.3', '-f', 'null', '-']).match(/silence_(start|end): [0-9.]+/g) || []).join(' ');
const cuts = (errText(['-i', input, '-vf', `${crop ? crop + ',' : ''}select='gt(scene,0.3)',showinfo`, '-f', 'null', '-']).match(/pts_time:[0-9.]+/g) || []).map(s => s.slice(9)).join(' ');
fs.writeFileSync(path.join(out, 'report.txt'),
  `== 时长/分辨率\n${probe}\n== 响度\n${loud}\n== 静音段(<-40dB, >0.3s)\n${sil || '无'}\n== 硬切点(场景变化>0.3)\n${cuts || '无'}\n`);
console.log(`完成：${out}/  →  ${fs.readdirSync(out).join('  ')}`);
