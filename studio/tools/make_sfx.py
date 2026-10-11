#!/usr/bin/env python3
"""生成柔和版基础音效库（纯 numpy 合成，无版权问题）→ studio/sfx/*.wav

设计原则（配合舒缓配乐）：低频、圆润、短；不用白噪声爆破，全部过 3.8kHz 双极低通，
所以不会“刺耳、吵”。想要更好的质感，可以把同名文件替换成自己的素材，引擎按文件名调用：
  tick 轻木质点击      whoosh 柔和气流     shimmer 标题钟片    boom 低频绽放（反转）
  stamp 闷声落章       shatter 玻璃轻响     crack 细微裂响      riser 轻微上升
  heart 心跳
项目里也可以放 videos/<名>/sfx/<同名>.wav 覆盖全局音效。
默认（meta.sfx = "soft"）只会自动用到 shimmer / stamp / shatter，其余要手动 c.sfx() 才会响。
"""
import os, wave
import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx")
rng = np.random.default_rng(7)


def t_axis(sec):
    return np.arange(int(SR * sec)) / SR


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def bandpass(x, f0, q):
    """时变带通（f0 可为数组）。"""
    f0 = np.broadcast_to(np.asarray(f0, dtype=float), x.shape)
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        w = 2 * np.pi * f0[i] / SR
        al = np.sin(w) / (2 * q)
        b0, b2, a0, a1, a2 = al, -al, 1 + al, -2 * np.cos(w), 1 - al
        yi = (b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x[i], y1, yi
        y[i] = yi
    return y


def reverb(x, sec=1.6, decay=0.5, mix=0.3):
    ir = lowpass(lowpass(rng.standard_normal(int(SR * sec)) * np.exp(-t_axis(sec) / decay), 2500), 2500)
    n = len(x) + len(ir)
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    wet /= np.max(np.abs(wet)) + 1e-9
    out = np.zeros(n)
    out[: len(x)] += x / (np.max(np.abs(x)) + 1e-9)
    return out * (1 - mix) + wet * mix


def tone(freq, sec, decay, attack=0.004, harm=(1.0,)):
    t = t_axis(sec)
    s = sum(a * np.sin(2 * np.pi * freq * (k + 1) * t) for k, a in enumerate(harm))
    return s * (1 - np.exp(-t / attack)) * np.exp(-t / decay)


def place(dst, src, at):
    i = int(at * SR)
    n = min(len(src), len(dst) - i)
    dst[i:i + n] += src[:n]


def save(name, x, peak=0.5):
    x = lowpass(lowpass(x, 3800), 3800)                 # 统一去掉刺耳的高频（12dB/oct）
    x = x / (np.max(np.abs(x)) + 1e-9)
    loud = np.nonzero(np.abs(x) > 0.004)[0]
    x = x[: loud[-1] + int(SR * 0.05)] if len(loud) else x
    n_in, n_out = int(SR * 0.003), int(SR * 0.04)
    x[:n_in] *= np.linspace(0, 1, n_in)
    x[-n_out:] *= np.linspace(1, 0, n_out)
    x *= peak
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    print(f"  sfx/{name}.wav  {len(x) / SR:.2f}s")


def tick():          # 轻木质“哒”
    return tone(620, 0.12, 0.022, 0.002, (1.0, 0.25, 0.08))


def whoosh():        # 柔和气流
    sec = 1.4
    t = t_axis(sec)
    p = np.clip(t / sec, 0, 1)
    air = bandpass(rng.standard_normal(len(t)), 260 + 700 * np.sin(np.pi * p) ** 2, 0.7)
    return lowpass(lowpass(air * np.sin(np.pi * p) ** 2, 1100), 1100)


def shimmer():       # 标题：几片柔和的钟片
    x = np.zeros(int(SR * 3.0))
    for k, f in enumerate([659.3, 784.0, 987.8, 1174.7]):
        place(x, tone(f, 2.6, 0.9, 0.015, (1.0, 0.18)) * (0.9 - 0.12 * k), 0.02 + k * 0.09)
    return reverb(x, 2.0, 0.7, 0.35)


def boom():          # 反转：低频绽放，不是爆炸
    sec = 3.0
    t = t_axis(sec)
    env = (1 - np.exp(-t / 0.25)) * np.exp(-t / 1.1)
    x = (np.sin(2 * np.pi * 55 * t) + 0.35 * np.sin(2 * np.pi * 110 * t) + 0.2 * np.sin(2 * np.pi * 164.8 * t)) * env
    return reverb(x, 2.0, 0.7, 0.3)


def stamp():         # 闷声落章
    sec = 0.6
    t = t_axis(sec)
    body = np.sin(2 * np.pi * (58 + 30 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    paper = lowpass(rng.standard_normal(len(t)), 700) * np.exp(-t / 0.012) * 1.5
    return lowpass(body + paper, 900)


def crack():         # 细微裂响
    x = np.zeros(int(SR * 0.3))
    for at in (0.0, 0.05, 0.11):
        place(x, tone(1400 + rng.uniform(-200, 200), 0.08, 0.012, 0.001), at)
    return x


def shatter():       # 玻璃轻响：稀疏的叮当，而不是爆裂
    x = np.zeros(int(SR * 2.2))
    place(x, lowpass(rng.standard_normal(int(SR * 0.4)), 1200) * np.exp(-t_axis(0.4) / 0.08) * 0.6, 0)
    for _ in range(14):
        at = rng.exponential(0.16)
        if at < 0.8:
            place(x, tone(rng.uniform(1200, 2600), 1.0, rng.uniform(0.15, 0.4), 0.003) * rng.uniform(0.2, 0.5), at)
    return reverb(x, 1.4, 0.4, 0.25)


def riser():         # 轻微上升
    sec = 2.4
    t = t_axis(sec)
    p = t / sec
    f = 220 * 2 ** (p * 1.0)
    x = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)) * p ** 2
    return lowpass(x, 1500)


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
