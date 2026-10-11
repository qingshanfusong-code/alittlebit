#!/usr/bin/env node
/* ============================================================
   舒缓配乐生成器（纯 Node，无依赖，无版权问题）
   毛毡钢琴分解和弦 + 弦乐铺底 + 低音 + 稀疏旋律 + 混响，
   时长与视频完全对齐：开头淡入、标题处“绽放”、结尾落在主和弦上淡出。
   单独使用：node tools/music.mjs --dur 53 --out music.wav [--seed 3] [--style piano|ambient] [--bpm 72] [--accents 13.7,40]
   渲染器会自动调用（script.json 里 meta.music 控制，默认 "piano"）。
   ============================================================ */
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const SR = 44100;
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);
function rng(seed = 1) {
  let a = (seed * 2654435761) >>> 0;
  return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// 和弦（a 小调 / C 大调，带 7、9 音，沉思而不悲伤）
const CHORDS = {
  Am9:   { bass: 45, pad: [57, 60, 64, 67, 71], arp: [57, 64, 67, 71, 72] },
  Fmaj7: { bass: 41, pad: [53, 57, 60, 64], arp: [53, 60, 64, 65, 69] },
  Cadd9: { bass: 48, pad: [55, 60, 62, 64], arp: [55, 60, 62, 64, 67] },
  G6:    { bass: 43, pad: [55, 59, 62, 64], arp: [55, 62, 64, 67, 71] },
  Em7:   { bass: 40, pad: [55, 59, 62, 64], arp: [52, 59, 62, 64, 67] },
};
const PROGRESSIONS = [
  ['Am9', 'Fmaj7', 'Cadd9', 'G6'],
  ['Fmaj7', 'G6', 'Em7', 'Am9'],
  ['Am9', 'Em7', 'Fmaj7', 'Cadd9'],
];
const MELODY = [69, 72, 74, 76, 79, 81];   // 五声音阶，高音区

/* ---------- 音色 ---------- */
function addPiano(L, R, t0, midi, vel, pan = 0, len = 5) {
  const f = mtof(midi), n0 = Math.round(t0 * SR), N = Math.min(Math.round(len * SR), L.length - n0);
  if (N <= 0 || n0 < 0) return;
  const B = 0.00035, base = 4.2 * Math.pow(220 / f, 0.35);
  const parts = [];
  for (let k = 1; k <= 8; k++) {
    const fk = k * f * Math.sqrt(1 + B * k * k); if (fk > 9000) break;
    parts.push({ w: 2 * Math.PI * fk / SR, a: vel * Math.pow(vel, (k - 1) * 0.35) / Math.pow(k, 1.7), tau: Math.max(.25, base - .3 * k) / 6.9, ph: k * 1.3 });
  }
  const gl = Math.cos((pan + 1) * Math.PI / 4), gr = Math.sin((pan + 1) * Math.PI / 4);
  let lp = 0; const lpa = Math.exp(-2 * Math.PI * 3200 / SR);    // 毛毡感：低通
  for (let i = 0; i < N; i++) {
    const t = i / SR, att = 1 - Math.exp(-t / 0.005);
    let s = 0;
    for (const p of parts) s += p.a * Math.sin(p.w * i + p.ph) * (0.6 * Math.exp(-t / 0.3) + 0.4 * Math.exp(-t / p.tau));
    s *= att; if (i > N - 2205) s *= (N - i) / 2205;
    lp = (1 - lpa) * s + lpa * lp;
    L[n0 + i] += lp * gl; R[n0 + i] += lp * gr;
  }
}
function addPad(L, R, t0, t1, notes, gain, gainFn) {
  const n0 = Math.max(0, Math.round(t0 * SR)), n1 = Math.min(L.length, Math.round((t1 + 2.4) * SR));
  const voices = [];
  notes.forEach((m, j) => [-1, 0, 1].forEach(d => voices.push({ w: 2 * Math.PI * mtof(m) * (1 + d * 0.0011) / SR, pan: d * 0.6, ph: j * 2.1 + d })));
  let lpL = 0, lpR = 0; const a = Math.exp(-2 * Math.PI * 1300 / SR);
  for (let i = n0; i < n1; i++) {
    const t = i / SR, rel = t < t1 ? 1 : Math.max(0, 1 - (t - t1) / 2.4);
    const env = Math.min(1, (t - t0) / 1.8) * rel * gain * (1 + 0.08 * Math.sin(2 * Math.PI * 0.21 * t)) * (gainFn ? gainFn(t) : 1);
    if (env <= 0) continue;
    let sl = 0, sr = 0;
    for (const v of voices) { const s = Math.sin(v.w * i + v.ph) + 0.25 * Math.sin(2 * v.w * i + v.ph); sl += s * (0.5 - v.pan * .3); sr += s * (0.5 + v.pan * .3); }
    lpL = (1 - a) * sl * env + a * lpL; lpR = (1 - a) * sr * env + a * lpR;
    L[i] += lpL; R[i] += lpR;
  }
}
function addBass(L, R, t0, t1, midi, gain) {
  const w = 2 * Math.PI * mtof(midi) / SR, n0 = Math.round(t0 * SR), n1 = Math.min(L.length, Math.round((t1 + 1.2) * SR));
  for (let i = n0; i < n1; i++) {
    const t = i / SR - t0, rel = i / SR < t1 ? 1 : Math.max(0, 1 - (i / SR - t1) / 1.2);
    const env = Math.min(1, t / .08) * (0.55 + 0.45 * Math.exp(-t / 1.2)) * rel * gain;
    const s = (Math.sin(w * (i - n0)) + 0.22 * Math.sin(2 * w * (i - n0))) * env;
    L[i] += s; R[i] += s;
  }
}

/* ---------- 混响（Freeverb） ---------- */
function freeverb(inp, spread = 0, room = 0.86, damp = 0.35) {
  const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map(d => ({ buf: new Float32Array(d + spread), i: 0, f: 0 }));
  const alls = [556, 441, 341, 225].map(d => ({ buf: new Float32Array(d + spread), i: 0 }));
  const fb = room * 0.28 + 0.7, d1 = damp * 0.4, d2 = 1 - d1, out = new Float32Array(inp.length);
  for (let n = 0; n < inp.length; n++) {
    const x = inp[n] * 0.015; let y = 0;
    for (const c of combs) { const o = c.buf[c.i]; c.f = o * d2 + c.f * d1; c.buf[c.i] = x + c.f * fb; if (++c.i >= c.buf.length) c.i = 0; y += o; }
    for (const a of alls) { const b = a.buf[a.i]; const o = -y + b; a.buf[a.i] = y + b * 0.5; if (++a.i >= a.buf.length) a.i = 0; y = o; }
    out[n] = y;
  }
  return out;
}

/* ---------- 编曲 ---------- */
export function makeMusic({ dur, seed = 1, style = 'piano', bpm = 72, accents = [] }) {
  const R0 = rng(seed), N = Math.round((dur + 0.2) * SR);
  const L = new Float32Array(N), Rr = new Float32Array(N);
  const beat = 60 / bpm, bar = beat * 4, chordLen = bar * 2;
  const prog = PROGRESSIONS[seed % PROGRESSIONS.length];
  const endAt = Math.max(chordLen, Math.floor((dur - 4.5) / bar) * bar);   // 尾和弦开始
  const swell = t => 1 + accents.reduce((s, a) => s + 0.7 * Math.exp(-Math.pow((t - a - 1.2) / 1.6, 2)), 0);

  // 主体：每 2 小节一个和弦
  let ci = 0;
  for (let t = 0; t < endAt - 1e-6; t += chordLen, ci++) {
    const ch = CHORDS[prog[ci % prog.length]], t1 = Math.min(t + chordLen, endAt);
    addPad(L, Rr, t, t1, ch.pad, style === 'ambient' ? .05 : .032, swell);
    if (t >= bar * 2 || style === 'ambient') addBass(L, Rr, t, t1, ch.bass, style === 'ambient' ? .07 : .09);
    if (style === 'piano') {
      for (let b = 0; b < 2 && t + b * bar < t1 - .01; b++) {
        const pat = b === 0 ? [[0, 0], [3, 2], [4, 1], [6, 3]] : [[0, 0], [2, 1], [4, 2], [7, 4]];
        for (const [e, k] of pat) {
          const tt = t + b * bar + e * beat / 2 + (R0() - .5) * .016;
          if (tt >= t1) continue;
          const m = ch.arp[k], intro = t < bar * 2 ? .8 : 1;
          addPiano(L, Rr, tt, m, (.42 + R0() * .14) * intro, (m - 62) / 24);
        }
      }
    }
    // 稀疏旋律（第 3 小节起）
    if (t >= bar * 2) {
      const nn = style === 'ambient' ? 1 : 1 + (R0() < .5 ? 1 : 0);
      for (let k = 0; k < nn; k++) {
        const tt = t + (Math.floor(R0() * 4) * 2 + (k ? 8 : 0)) * beat / 2;
        if (tt < t1 - .3) addPiano(L, Rr, tt, MELODY[Math.floor(R0() * MELODY.length)], .3 + R0() * .1, .3, 6);
      }
    }
  }
  // 标题处的点缀：一串轻柔的高音
  for (const a of accents) [76, 79, 83, 86].forEach((m, i) => addPiano(L, Rr, a + .15 + i * .11, m, .22 - i * .03, .4, 5));
  // 尾声：Fmaj7 → C(add9) 的变格终止，琶音滚奏后长音淡出
  const fin = CHORDS.Cadd9;
  addPad(L, Rr, endAt, dur, fin.pad, .03);
  addBass(L, Rr, endAt, dur, fin.bass, .08);
  [48, 55, 64, 67, 74].forEach((m, i) => addPiano(L, Rr, endAt + i * .07, m, .45 - i * .04, (m - 62) / 24, 7));

  // 混响 + 母带
  const wl = freeverb(L, 0), wr = freeverb(Rr, 23);
  let peak = 0;
  for (let i = 0; i < N; i++) {
    const t = i / SR, fade = Math.min(1, t / 1.5) * Math.min(1, Math.max(0, (dur - t) / 3.5));
    L[i] = (L[i] * .85 + wl[i] * .5) * fade; Rr[i] = (Rr[i] * .85 + wr[i] * .5) * fade;
    peak = Math.max(peak, Math.abs(L[i]), Math.abs(Rr[i]));
  }
  let ss = 0; for (let i = 0; i < N; i++) ss += L[i] * L[i] + Rr[i] * Rr[i];
  const rms = Math.sqrt(ss / (2 * N)), g = Math.min(0.1 / (rms + 1e-9), 0.89 / (peak + 1e-9));   // RMS≈-20dBFS，峰值≤-1dBFS
  for (let i = 0; i < N; i++) { L[i] *= g; Rr[i] *= g; }
  return [L, Rr];
}

export function writeWav(file, [L, R]) {
  const N = L.length, buf = Buffer.alloc(44 + N * 4);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24);
  buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(N * 4, 40);
  for (let i = 0; i < N; i++) {
    buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i])) * 32767), 44 + i * 4);
    buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i])) * 32767), 46 + i * 4);
  }
  fs.writeFileSync(file, buf);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const a = process.argv.slice(2), opt = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
  const t0 = Date.now(), out = opt('out', 'music.wav');
  writeWav(out, makeMusic({ dur: +opt('dur', 60), seed: +opt('seed', 1), style: opt('style', 'piano'), bpm: +opt('bpm', 72),
    accents: (opt('accents', '') || '').split(',').filter(Boolean).map(Number) }));
  console.log(`配乐：${out}（${opt('dur', 60)}s，用时 ${((Date.now() - t0) / 1000).toFixed(1)}s）`);
}
