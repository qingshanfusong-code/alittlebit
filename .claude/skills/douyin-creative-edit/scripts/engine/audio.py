"""Audio analysis: onset envelope, tempo, beat tracking, downbeats, energy, drop.

Pure numpy (librosa is used only if installed and --librosa is passed).
"""
import json
import subprocess

import numpy as np

SR = 22050
HOP = 512
NFFT = 2048
LATENCY = 0.02


def load_audio(path, sr=SR, start=None, duration=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to decode audio from {path}: {out.stderr.decode()[-400:]}")
    y = np.frombuffer(out.stdout, dtype=np.float32).copy()
    if y.size == 0:
        raise RuntimeError(f"No audio stream decoded from {path}")
    return y


def stft_mag(y, nfft=NFFT, hop=HOP):
    # centre frames on their timestamps (frame i <-> time i*hop/sr)
    y = np.pad(y, (nfft // 2, nfft // 2))
    if len(y) < nfft:
        y = np.pad(y, (0, nfft - len(y)))
    n = 1 + (len(y) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    win = np.hanning(nfft).astype(np.float32)
    frames = y[idx] * win
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)  # (n, nfft/2+1)


def mel_filter(sr=SR, nfft=NFFT, n_mels=64, fmin=30, fmax=8000):
    def hz2mel(f):
        return 2595 * np.log10(1 + f / 700.0)

    def mel2hz(m):
        return 700 * (10 ** (m / 2595.0) - 1)

    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2)
    hz = mel2hz(mels)
    bins = np.floor((nfft + 1) * hz / sr).astype(int)
    fb = np.zeros((n_mels, nfft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        if b > a:
            fb[i, a:b] = (np.arange(a, b) - a) / (b - a)
        if c > b:
            fb[i, b:c] = (c - np.arange(b, c)) / (c - b)
    return fb


def onset_envelope(mag, sr=SR):
    fb = mel_filter(sr)
    mel = np.log1p(10 * (mag @ fb.T))  # (n, n_mels)
    d = np.maximum(0, np.diff(mel, axis=0))
    # broadband flux + extra weight on the low bands (kick / bass carry the beat; hats carry subdivisions)
    flux = d.mean(axis=1) + 1.5 * d[:, :10].mean(axis=1)
    flux = np.concatenate([[0], flux])
    # remove slow trend
    k = 16
    trend = np.convolve(flux, np.ones(k) / k, mode="same")
    env = np.maximum(0, flux - trend)
    if env.std() > 0:
        env = env / env.std()
    # low band flux (kick-ish) for downbeat estimation
    low = np.maximum(0, np.diff(mel[:, :12], axis=0)).mean(axis=1)
    low = np.concatenate([[0], low])
    return env.astype(np.float32), low.astype(np.float32)


def estimate_tempo(env, sr=SR, hop=HOP, bpm_min=55, bpm_max=210, prior_bpm=120):
    """Tempo from the autocorrelation of a smoothed onset curve, scoring each candidate on its
    first harmonics (period, 2x, 3x, 4x) so a single lucky lag cannot win."""
    fps = sr / hop
    k = np.exp(-0.5 * (np.arange(-6, 7) / 2.0) ** 2)
    e = np.convolve(env, k / k.sum(), mode="same")
    e = e - e.mean()
    n = len(e)
    ac = np.correlate(e, e, mode="full")[n - 1:]
    ac = ac / (ac[0] + 1e-9)
    lags = np.arange(len(ac))

    def at(lag):
        return np.interp(lag, lags, ac) if lag < len(ac) - 1 else 0.0

    best_bpm, best = prior_bpm, -1e9
    for bpm in np.arange(bpm_min, bpm_max, 0.25):
        p = 60.0 * fps / bpm
        sc = at(p) + 0.5 * at(2 * p) + 0.33 * at(3 * p) + 0.25 * at(4 * p)
        sc *= np.exp(-0.5 * (np.log2(bpm / prior_bpm) / 1.0) ** 2) ** 0.5
        if sc > best:
            best, best_bpm = sc, bpm
    return float(best_bpm)


def track_beats(env, bpm, sr=SR, hop=HOP, tightness=100.0):
    """Dynamic-programming beat tracker (Ellis 2007)."""
    fps = sr / hop
    period = 60.0 * fps / bpm
    n = len(env)
    # smooth envelope with gaussian of width period/32
    w = max(1, int(period / 8))
    g = np.exp(-0.5 * (np.arange(-w, w + 1) / (period / 32 + 1e-9)) ** 2)
    local = np.convolve(env, g / g.sum(), mode="same")
    score = local.copy()
    back = -np.ones(n, dtype=int)
    lo, hi = int(round(period / 2)), int(round(2 * period))
    offsets = np.arange(-hi, -lo + 1)
    penalty = -tightness * (np.log(-offsets / period)) ** 2
    for t in range(hi, n):
        cand = score[t + offsets] + penalty
        j = int(np.argmax(cand))
        score[t] = local[t] + cand[j]
        back[t] = t + offsets[j]
    # pick best end within last period
    tail = max(0, n - int(period))
    t = tail + int(np.argmax(score[tail:]))
    beats = []
    while t >= 0:
        beats.append(t)
        if back[t] < 0:
            break
        t = back[t]
    beats = np.array(beats[::-1])
    # extend backwards toward the start using the period (DP stops at hi)
    first = beats[0] if len(beats) else 0
    pre = []
    t = first - period
    while t > period * 0.25:
        pre.append(int(round(t)))
        t -= period
    beats = np.concatenate([np.array(pre[::-1], dtype=int), beats]) if pre else beats
    return beats / fps


def downbeat_phase(beat_times, low_env, sr=SR, hop=HOP, meter=4):
    fps = sr / hop
    idx = np.clip((np.asarray(beat_times) * fps).astype(int), 0, len(low_env) - 1)
    strength = low_env[idx]
    best, best_s = 0, -1
    for ph in range(meter):
        s = strength[ph::meter].mean() if len(strength[ph::meter]) else 0
        if s > best_s:
            best, best_s = ph, s
    return best


def pick_onsets(env, sr=SR, hop=HOP, delta=1.0, min_gap=0.08):
    fps = sr / hop
    w = int(0.1 * fps)
    n = len(env)
    peaks = []
    last = -1e9
    mean = np.convolve(env, np.ones(2 * w + 1) / (2 * w + 1), mode="same")
    for i in range(1, n - 1):
        if env[i] >= env[i - 1] and env[i] > env[i + 1] and env[i] > mean[i] + delta:
            t = i / fps
            if t - last >= min_gap:
                peaks.append((t, float(env[i])))
                last = t
    return peaks


def rms_curve(y, sr=SR, step=0.25):
    hop = int(sr * step)
    n = max(1, len(y) // hop)
    r = np.sqrt(np.array([np.mean(y[i * hop:(i + 1) * hop] ** 2) for i in range(n)]) + 1e-12)
    db = 20 * np.log10(r + 1e-9)
    db = np.clip(db, -60, 0)
    norm = (db + 60) / 60
    return norm, step


def find_drop(energy, step, downbeats, min_time=3.0):
    """Biggest sustained energy rise -> 'drop' (the moment the music hits)."""
    if len(energy) < 8:
        return None
    win = max(2, int(1.0 / step))
    best_t, best_v = None, 0.0
    for i in range(win, len(energy) - win):
        before = energy[i - win:i].mean()
        after = energy[i:i + win].mean()
        v = after - before
        t = i * step
        if t >= min_time and v > best_v:
            best_v, best_t = v, t
    if best_t is None or best_v < 0.06:
        return None
    if len(downbeats):
        db = np.asarray(downbeats)
        near = db[np.argmin(np.abs(db - best_t))]
        if abs(near - best_t) < 1.0:
            best_t = float(near)
    return round(float(best_t), 3)


def analyze(path, start=None, duration=None, bpm_hint=None, meter=4, use_librosa=False):
    y = load_audio(path, start=start, duration=duration)
    dur = len(y) / SR
    if use_librosa:
        try:
            import librosa  # noqa

            tempo, bt = librosa.beat.beat_track(y=y, sr=SR, units="time", start_bpm=bpm_hint or 120)
            bpm = float(np.atleast_1d(tempo)[0])
            beats = np.asarray(bt)
        except Exception:
            use_librosa = False
    mag = stft_mag(y)
    env, low = onset_envelope(mag)
    if not use_librosa:
        bpm = bpm_hint or estimate_tempo(env)
        beats = track_beats(env, bpm)
    if len(beats) > 3:
        # regression slope is robust to the 23ms frame quantisation of individual intervals
        slope = np.polyfit(np.arange(len(beats)), beats, 1)[0]
        bpm_eff = 60.0 / slope
    else:
        bpm_eff = bpm
    # spectral flux fires ~20 ms before the perceived attack (centred windows); compensate
    beats = np.asarray(beats) + LATENCY
    ph = downbeat_phase(beats - LATENCY, low, meter=meter)
    downbeats = beats[ph::meter]
    onsets = [(t + LATENCY, v) for t, v in pick_onsets(env)]
    energy, step = rms_curve(y)
    drop = find_drop(energy, step, downbeats)
    strong = sorted(onsets, key=lambda x: -x[1])[: max(8, int(dur * 1.5))]
    strong = sorted(strong)
    res = {
        "source": str(path),
        "offset": float(start or 0.0),
        "duration": round(dur, 3),
        "bpm": round(float(bpm_eff), 2),
        "beat_interval": round(60.0 / float(bpm_eff), 4),
        "meter": meter,
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": [round(float(b), 3) for b in downbeats],
        "onsets": [round(t, 3) for t, _ in onsets],
        "strong_onsets": [round(t, 3) for t, _ in strong],
        "drop": drop,
        "energy_step": step,
        "energy": [round(float(e), 3) for e in energy],
    }
    return res


def summarize(res):
    bi = res["beat_interval"]
    lines = [
        f"BPM ≈ {res['bpm']}  (1 beat = {bi:.3f}s, 1 bar = {bi * res['meter']:.2f}s)",
        f"duration {res['duration']}s, {len(res['beats'])} beats, {len(res['downbeats'])} bars, drop at {res['drop']}",
        "cut-length menu:  4 beats = {:.2f}s (slow / poster)  2 beats = {:.2f}s (narrative)  1 beat = {:.2f}s (卡点)  "
        "1/2 beat = {:.2f}s (fast)  1/4 beat = {:.3f}s (flash burst, keep ≤3s)".format(4 * bi, 2 * bi, bi, bi / 2, bi / 4),
    ]
    e = np.asarray(res["energy"])
    if len(e):
        step = res["energy_step"]
        q = np.quantile(e, [0.33, 0.66])
        segs = []
        cur, s0 = None, 0.0
        for i, v in enumerate(e):
            lvl = "low" if v < q[0] else ("mid" if v < q[1] else "high")
            if lvl != cur:
                if cur is not None and i * step - s0 >= 1.0:
                    segs.append(f"{s0:.1f}-{i * step:.1f}s {cur}")
                cur, s0 = lvl, i * step
        segs.append(f"{s0:.1f}-{len(e) * step:.1f}s {cur}")
        lines.append("energy: " + " | ".join(segs[:16]))
    return "\n".join(lines)


def save(res, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
