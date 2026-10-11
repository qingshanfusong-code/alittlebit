#!/usr/bin/env python3
"""生成基础音效库（纯 numpy 合成，无版权问题）→ studio/sfx/*.wav

这些是“够用”的占位音效。想要更精致的质感，可以把同名文件替换成
自己下载的素材（如 Pixabay / 爱给网的免版权音效），引擎按文件名调用：
  tick 字符滚动/计数   whoosh 转场/飞散   shimmer 标题出现   boom 重音/反转
  stamp 盖章           shatter 玻璃碎裂   crack 裂纹         riser 悬念上升
  heart 心跳（低频双击）
项目里也可以放 videos/<名>/sfx/<同名>.wav 覆盖全局音效。
"""
import os, wave
import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx")
rng = np.random.default_rng(7)


def t_axis(sec):
    return np.arange(int(SR * sec)) / SR


def env_exp(sec, decay):
    return np.exp(-t_axis(sec) / decay)


def biquad_bp(x, f0, q):
    """时变带通（f0 可为数组）。"""
    f0 = np.broadcast_to(np.asarray(f0, dtype=float), x.shape)
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        w = 2 * np.pi * f0[i] / SR
        alpha = np.sin(w) / (2 * q)
        b0, b2, a0, a1, a2 = alpha, -alpha, 1 + alpha, -2 * np.cos(w), 1 - alpha
        yi = (b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x[i], y1, yi
        y[i] = yi
    return y


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def reverb(x, sec=1.4, decay=0.45, mix=0.25):
    ir = rng.standard_normal(int(SR * sec)) * env_exp(sec, decay)
    ir = lowpass(ir, 5000)
    n = len(x) + len(ir)
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    wet /= np.max(np.abs(wet)) + 1e-9
    out = np.zeros(n)
    out[: len(x)] += x / (np.max(np.abs(x)) + 1e-9)
    return out * (1 - mix) + wet * mix


def fade(x, ms_in=2, ms_out=30):
    n_in, n_out = int(SR * ms_in / 1000), int(SR * ms_out / 1000)
    x = x.copy()
    if n_in:
        x[:n_in] *= np.linspace(0, 1, n_in)
    if n_out:
        x[-n_out:] *= np.linspace(1, 0, n_out)
    return x


def save(name, x, peak=0.7):
    x = x / (np.max(np.abs(x)) + 1e-9)
    loud = np.nonzero(np.abs(x) > 0.004)[0]          # 去掉混响尾巴里听不见的部分
    x = x[: loud[-1] + int(SR * 0.05)] if len(loud) else x
    x = fade(x)
    x = x / (np.max(np.abs(x)) + 1e-9) * peak
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    print(f"  sfx/{name}.wav  {len(x) / SR:.2f}s")


def tick():
    t = t_axis(0.06)
    click = rng.standard_normal(len(t)) * env_exp(0.06, 0.004)
    tone = np.sin(2 * np.pi * 2300 * t) * env_exp(0.06, 0.012) * 0.6
    return biquad_bp(click, 3200, 1.2) + tone


def whoosh():
    sec = 1.1
    t = t_axis(sec)
    n = rng.standard_normal(len(t))
    sweep = 350 + 2600 * np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 2
    env = np.sin(np.pi * np.clip(t / sec, 0, 1)) ** 1.6
    return biquad_bp(n, sweep, 0.9) * env


def shimmer():
    sec = 3.2
    t = t_axis(sec)
    x = np.zeros_like(t)
    notes = [1318.5, 1568.0, 1975.5, 2637.0, 3136.0, 3951.1, 2093.0, 2637.0]
    for k, f in enumerate(notes):
        on = 0.05 + k * 0.07 + rng.uniform(0, 0.03)
        tt = np.clip(t - on, 0, None)
        e = (t >= on) * np.exp(-tt / 1.1) * (1 - np.exp(-tt / 0.004))
        x += np.sin(2 * np.pi * f * (1 + 0.0015 * np.sin(2 * np.pi * 5 * tt)) * tt) * e * (0.5 + 0.5 * rng.random())
    air = biquad_bp(rng.standard_normal(len(t)), 7000, 0.7) * np.exp(-t / 0.9) * 0.15
    return reverb(x + air, 2.2, 0.8, 0.35)


def boom():
    sec = 2.4
    t = t_axis(sec)
    f = 38 + 50 * np.exp(-t / 0.25)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(sec, 0.7)
    hit = lowpass(rng.standard_normal(len(t)) * env_exp(sec, 0.03), 900) * 3
    return reverb(body + hit, 2.0, 0.7, 0.3)


def stamp():
    sec = 0.5
    t = t_axis(sec)
    thump = np.sin(2 * np.pi * (95 + 60 * np.exp(-t / 0.03)) * t) * env_exp(sec, 0.07)
    slap = biquad_bp(rng.standard_normal(len(t)), 1800, 0.8) * env_exp(sec, 0.012) * 1.4
    return reverb(thump + slap, 0.6, 0.15, 0.15)


def crack():
    sec = 0.35
    t = t_axis(sec)
    x = rng.standard_normal(len(t)) * env_exp(sec, 0.006) * 1.5
    for _ in range(6):
        on = rng.uniform(0.01, 0.2)
        tt = np.clip(t - on, 0, None)
        x += (t >= on) * rng.standard_normal(len(t)) * np.exp(-tt / 0.003) * 0.6
    return biquad_bp(x, 4200, 0.7)


def shatter():
    sec = 2.0
    t = t_axis(sec)
    x = lowpass(rng.standard_normal(len(t)), 3000) * env_exp(sec, 0.05) * 1.2
    for _ in range(70):
        on = 0.005 + rng.exponential(0.18)
        if on > 1.2:
            continue
        tt = np.clip(t - on, 0, None)
        f = rng.uniform(2500, 9000)
        x += (t >= on) * np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.02, 0.15)) * rng.uniform(0.15, 0.6)
    x += biquad_bp(rng.standard_normal(len(t)), 6000, 0.6) * env_exp(sec, 0.25) * 0.5
    return reverb(x, 1.2, 0.35, 0.2)


def riser():
    sec = 2.2
    t = t_axis(sec)
    p = t / sec
    f = 180 * 2 ** (p * 2.5)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * p ** 2 * 0.5
    air = biquad_bp(rng.standard_normal(len(t)), 500 + 5000 * p ** 2, 1.0) * p ** 2.2
    return tone + air


def heart():
    sec = 1.0
    t = t_axis(sec)
    x = np.zeros_like(t)
    for on, a in ((0.0, 1.0), (0.22, 0.7)):
        tt = np.clip(t - on, 0, None)
        x += (t >= on) * np.sin(2 * np.pi * 52 * tt) * np.exp(-tt / 0.09) * a
    return lowpass(x, 300)


if __name__ == "__main__":
    print("生成音效 →", os.path.normpath(OUT))
    for name, fn in [("tick", tick), ("whoosh", whoosh), ("shimmer", shimmer), ("boom", boom), ("stamp", stamp),
                     ("crack", crack), ("shatter", shatter), ("riser", riser), ("heart", heart)]:
        save(name, fn())
