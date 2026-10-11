"""Original 96 BPM track that mirrors the reference BGM's structure (not its melody):
pickup hook -> hit + 1 s stop -> 808 glide pre-drop -> 4 bar drop (F#m D A E) -> loop hit.
Grid: downbeats at 1.75 + 2.5 k seconds (identical to the reference, so the original
BGM can be swapped in by hand and every cut still lands)."""
import sys
import numpy as np
from scipy.signal import lfilter, fftconvolve

SR = 44100
DUR = 14.9
BEAT = 60 / 96
T0 = 1.75                      # beat 0 = first downbeat (the hit before the stop)
N = int(SR * DUR)
rng = np.random.default_rng(7)


def bt(b):                     # beat index -> seconds
    return T0 + b * BEAT


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


NOTE = {n: i for i, n in enumerate(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}


def m(name):                   # 'F#5' -> midi
    return NOTE[name[:-1]] + 12 * (int(name[-1]) + 1)


# ---------------------------------------------------------------- filters
def biquad(kind, f0, q, gain_db=0.0):
    w = 2 * np.pi * f0 / SR
    a = np.sin(w) / (2 * q)
    c = np.cos(w)
    A = 10 ** (gain_db / 40)
    if kind == 'lp':
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]; aa = [1 + a, -2 * c, 1 - a]
    elif kind == 'hp':
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]; aa = [1 + a, -2 * c, 1 - a]
    elif kind == 'bp':
        b = [a, 0, -a]; aa = [1 + a, -2 * c, 1 - a]
    elif kind == 'peak':
        b = [1 + a * A, -2 * c, 1 - a * A]; aa = [1 + a / A, -2 * c, 1 - a / A]
    elif kind == 'lowshelf':
        sq = 2 * np.sqrt(A) * a
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        aa = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    b = np.array(b) / aa[0]; aa = np.array(aa) / aa[0]
    return b, aa


def filt(x, kind, f0, q=0.707, gain_db=0.0):
    b, a = biquad(kind, f0, q, gain_db)
    return lfilter(b, a, x)


def sweep_filter(x, kind, f_start, f_end, q=0.9, block=256):
    """Time-varying biquad, coefficients updated per block (exponential sweep)."""
    out = np.zeros_like(x)
    zi = np.zeros(2)
    nb = int(np.ceil(len(x) / block))
    for i in range(nb):
        f = f_start * (f_end / f_start) ** (i / max(1, nb - 1))
        b, a = biquad(kind, f, q)
        seg = x[i * block:(i + 1) * block]
        y, zi = lfilter(b, a, seg, zi=zi)
        out[i * block:i * block + len(seg)] = y
    return out


# ---------------------------------------------------------------- buses
bus = {k: np.zeros((N, 2)) for k in ['drums', 'bass', 'keys', 'pad', 'vox', 'fx']}
send = np.zeros((N, 2))         # reverb send


def place(name, sig, t, pan=0.0, gain=1.0, rev=0.0):
    i = int(round(t * SR))
    if i >= N:
        return
    if sig.ndim == 1:
        l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l, sig * r], 1) * np.sqrt(2)
    j = min(N, i + len(sig))
    s = sig[:j - i] * gain
    if i < 0:
        s = s[-i:]; i = 0
    bus[name][i:j] += s
    if rev:
        send[i:j] += s * rev


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.1, hold=None):
    t = np.arange(n) / SR
    hold = (n / SR - r) if hold is None else hold
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = np.clip((t - hold) / max(r, 1e-4), 0, 1)
    return e * (1 - rel)


# ---------------------------------------------------------------- instruments
def kick(vel=1.0):
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.22)
    click = filt(rng.standard_normal(n), 'hp', 2500) * np.exp(-t / 0.004) * 0.35
    return np.tanh(1.6 * (body + click)) * vel


def b808(freq, length, glide_to=None, glide_time=0.0, vel=1.0):
    n = int((length + 0.08) * SR); t = np.arange(n) / SR
    f = freq * (1 + 1.0 * np.exp(-t / 0.018))
    if glide_to:
        k = np.clip(t / glide_time, 0, 1)
        f = f * (glide_to / freq) ** (k * k * (3 - 2 * k))
    ph = 2 * np.pi * np.cumsum(f) / SR
    amp = np.exp(-t / (length * 0.9 + 0.15)) * np.clip((length + 0.08 - t) / 0.06, 0, 1)
    x = np.sin(ph) * amp
    return np.tanh(2.2 * x) * 0.8 * vel


def clap(vel=1.0):
    n = int(0.6 * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    e = np.zeros(n)
    for k, d in enumerate([0.0, 0.011, 0.022, 0.031]):
        tt = t - d
        e += np.where(tt >= 0, np.exp(-np.maximum(tt, 0) / (0.006 if k < 3 else 0.16)), 0)
    x = filt(noise * e, 'bp', 1400, 0.9) * 2.2
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.4
    return (x + body) * vel


def hat(open_=False, vel=1.0):
    n = int((0.35 if open_ else 0.08) * SR); t = np.arange(n) / SR
    x = filt(filt(rng.standard_normal(n), 'hp', 7500, 0.8), 'peak', 10000, 1.0, 6)
    return x * np.exp(-t / (0.11 if open_ else 0.022)) * 0.35 * vel


def rhodes(notes, length, vel=1.0):
    n = int((length + 0.6) * SR); t = np.arange(n) / SR
    out = np.zeros(n)
    for k, nt in enumerate(notes):
        f = midi(nt)
        idx = 1.8 * np.exp(-t / 0.25) + 0.25
        mod = np.sin(2 * np.pi * f * t) * idx
        car = np.sin(2 * np.pi * f * t + mod)
        tine = np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t / 0.03) * 0.25
        amp = np.exp(-t / 1.6) * np.clip((length + 0.6 - t) / 0.5, 0, 1)
        trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t + k)
        out += (car + tine) * amp * trem * (0.9 ** k)
    out = filt(out, 'lp', 3800)
    return out / max(1, len(notes)) * 1.6 * vel


def pad(notes, length):
    n = int((length + 0.8) * SR); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for nt in notes:
        for det, side in [(-0.11, 0), (0.0, None), (0.12, 1)]:
            f = midi(nt) * 2 ** (det / 12)
            ph = (f * t + rng.random()) % 1.0
            saw = 2 * ph - 1
            if side is None:
                out += np.stack([saw, saw], 1) * 0.5
            else:
                out[:, side] += saw
    amp = np.clip(t / 0.35, 0, 1) * np.clip((length + 0.8 - t) / 0.8, 0, 1)
    out = np.stack([filt(out[:, 0], 'lp', 1100, 0.6), filt(out[:, 1], 'lp', 1100, 0.6)], 1)
    return out * amp[:, None] / (len(notes) * 3) * 0.9


VOWELS = {'a': [(730, 1.0, 10), (1090, 0.5, 12), (2440, 0.18, 14)],
          'o': [(500, 1.0, 10), (850, 0.45, 12), (2400, 0.12, 14)],
          'u': [(330, 1.0, 9), (900, 0.25, 12), (2300, 0.08, 14)]}


def vox_phrase(notes, vowel='a'):
    """Formant 'vocal' lead. notes: list of (start_s, dur_s, midi). Gliding legato line."""
    start = notes[0][0]; end = notes[-1][0] + notes[-1][1]
    n = int((end - start + 0.5) * SR); t = np.arange(n) / SR
    f = np.zeros(n); gate = np.zeros(n)
    for (s, d, nt) in notes:
        i0 = int((s - start) * SR); i1 = int((s - start + d) * SR)
        f[i0:] = midi(nt)
        gate[i0:i1] = 1
    # portamento
    f = lfilter([1 - np.exp(-1 / (0.045 * SR))], [1, -np.exp(-1 / (0.045 * SR))], f, zi=[f[0]])[0]
    # delayed vibrato
    vib_depth = np.zeros(n)
    for (s, d, nt) in notes:
        i0 = int((s - start) * SR); i1 = int((s - start + d) * SR)
        local = np.arange(i1 - i0) / SR
        vib_depth[i0:i1] = np.clip((local - 0.18) / 0.3, 0, 1) * 0.35
    f = f * 2 ** (vib_depth * np.sin(2 * np.pi * 5.4 * t) / 12)
    ph = np.cumsum(f) / SR
    # band-limited-ish saw via a few harmonics weighted 1/k
    src = np.zeros(n)
    for k in range(1, 18):
        src += np.sin(2 * np.pi * k * ph) / k * (f * k < 9000)
    src += rng.standard_normal(n) * 0.04
    out = np.zeros(n)
    for (fc, g, q) in VOWELS[vowel]:
        out += filt(src, 'bp', fc, q) * g
    g = lfilter([1 - np.exp(-1 / (0.025 * SR))], [1, -np.exp(-1 / (0.025 * SR))], gate)
    out = out * g
    out = filt(out, 'hp', 180)
    sub = np.sin(2 * np.pi * ph) * g * 0.18
    return (out * 2.4 + sub), start


def whoosh(length, f0, f1, vel=1.0):
    n = int(length * SR); t = np.arange(n) / SR
    x = rng.standard_normal(n)
    y = sweep_filter(x, 'bp', f0, f1, q=1.2)
    e = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 2
    e = e * np.where(t / length > 0.55, np.exp(-(t / length - 0.55) * 4), 1)
    return y * e * 1.4 * vel


def riser(length):
    n = int(length * SR); t = np.arange(n) / SR
    y = sweep_filter(rng.standard_normal(n), 'bp', 400, 6000, q=1.5)
    return y * (t / length) ** 2 * 0.5


def chime(freqs, vel=1.0):
    n = int(2.0 * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / 0.7) for f in freqs)
    return x * 0.18 * vel


def thump(vel=1.0):
    n = int(0.18 * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * (90 + 120 * np.exp(-t / 0.01)) * t) * np.exp(-t / 0.05)
    x += filt(rng.standard_normal(n), 'bp', 2400, 1.0) * np.exp(-t / 0.008) * 0.3
    return x * vel


# ---------------------------------------------------------------- arrangement
CH = {  # chord tones (midi) for keys/pad, 808 root (Hz)
    'Dmaj7': (['F#3', 'A3', 'C#4', 'E4'], midi(m('D2'))),
    'E': (['E3', 'G#3', 'B3', 'E4'], midi(m('E2'))),
    'F#m': (['F#3', 'A3', 'C#4', 'E4'], midi(m('F#1'))),
    'D': (['F#3', 'A3', 'D4', 'E4'], midi(m('D2'))),
    'A': (['E3', 'A3', 'C#4', 'E4'], midi(m('A1'))),
    'Esus': (['E3', 'A3', 'B3', 'E4'], midi(m('E2'))),
}


def keys_chord(name, b, beats, vel=1.0, padv=True):
    tones = [m(x) for x in CH[name][0]]
    place('keys', rhodes(tones, beats * BEAT, vel), bt(b), pan=-0.15, gain=0.55, rev=0.25)
    if padv:
        place('pad', pad([x + 12 for x in tones[1:3]], beats * BEAT), bt(b), gain=0.35, rev=0.3)


# --- intro (pickup b -2.5 .. 0)
keys_chord('Dmaj7', -2.5, 1.5, 0.8)
keys_chord('E', -1.0, 1.0, 0.85)
for b in np.arange(-2.5, 0, 0.5):
    place('drums', hat(vel=0.55 + 0.2 * (b % 1 == 0.5)), bt(b), pan=0.25, gain=0.6)
place('bass', b808(midi(m('D2')), 0.5, vel=0.6), bt(-2.0), gain=0.7)
v, s0 = vox_phrase([(bt(-2.5), 0.28, m('C#5')), (bt(-2.0), 0.42, m('E5')), (bt(-1.5), 0.25, m('F#5')),
                    (bt(-1.0), 0.28, m('G#5')), (bt(-0.5), 0.3, m('E5')), (bt(0.0), 0.16, m('F#5'))], 'a')
place('vox', v, s0, gain=0.42, rev=0.35)

# --- the hit on beat 0, then STOP (hard gate applied at the end)
place('drums', kick(1.0), bt(0), gain=0.9)
place('bass', b808(CH['F#m'][1], 0.6, vel=1.0), bt(0), gain=0.9)
place('drums', clap(0.6), bt(0), gain=0.5, rev=0.2)
keys_chord('F#m', 0, 1.0, 1.0, padv=False)
STOP0, STOP1 = bt(0) + 0.16, bt(2) - 0.01        # silence 1.91 .. 2.99

# --- pre-drop (b2 .. b4): vocal pickup + 808 glide + riser
v, s0 = vox_phrase([(bt(2.0), 0.3, m('A4')), (bt(2.5), 0.3, m('B4')), (bt(3.0), 0.3, m('C#5')),
                    (bt(3.5), 0.45, m('E5'))], 'o')
place('vox', v, s0, gain=0.45, rev=0.35)
place('bass', b808(midi(m('E2')), 2 * BEAT - 0.05, glide_to=midi(m('E1')), glide_time=1.1, vel=1.0), bt(2), gain=0.95)
keys_chord('Esus', 2, 2, 0.7)
place('fx', riser(2 * BEAT), bt(2), gain=0.55, rev=0.2)
for b in [3.0, 3.25, 3.5, 3.625, 3.75, 3.875]:
    place('drums', clap(0.25 + 0.1 * (b - 3)), bt(b), gain=0.35, pan=0.1, rev=0.15)

# --- drop: 4 bars F#m D A E, then the loop hit (F#m) at b20
prog = ['F#m', 'D', 'A', 'E']
hook = [
    [(0, 1.5, 'F#5'), (1.5, 0.5, 'E5'), (2.0, 1.0, 'C#5'), (3.0, 0.5, 'A4'), (3.5, 0.5, 'B4')],
    [(0, 1.5, 'D5'), (1.5, 0.5, 'C#5'), (2.0, 1.5, 'A4'), (3.5, 0.5, 'C#5')],
    [(0, 1.5, 'C#5'), (1.5, 0.5, 'B4'), (2.0, 1.0, 'A4'), (3.0, 0.5, 'E5'), (3.5, 0.5, 'F#5')],
    [(0, 1.0, 'E5'), (1.0, 0.5, 'C#5'), (1.5, 1.5, 'B4'), (3.0, 0.5, 'G#4'), (3.5, 0.5, 'C#5')],
]
for bar, ch in enumerate(prog):
    b0 = 4 + bar * 4
    root = CH[ch][1]
    # 808 + kick
    for st, ln, kk in [(0, 6, True), (6, 3, False), (10, 5, True)]:
        place('bass', b808(root, ln * BEAT / 4 - 0.02, vel=1.0 if st == 0 else 0.8), bt(b0 + st / 4), gain=0.9)
        if kk:
            place('drums', kick(1.0 if st == 0 else 0.8), bt(b0 + st / 4), gain=0.85)
    # half-time clap on beat 3
    place('drums', clap(1.0), bt(b0 + 2), gain=0.75, pan=0.05, rev=0.22)
    # hats: 8ths, open on step 6, 16th roll at the end of bars 2 and 4
    for st in range(0, 16, 2):
        place('drums', hat(open_=(st == 6), vel=0.6 + 0.35 * (st % 4 == 2)), bt(b0 + st / 4), pan=0.3, gain=0.55)
    if bar in (1, 3):
        for st in (13, 14, 15):
            place('drums', hat(vel=0.45 + 0.1 * (st - 12)), bt(b0 + st / 4), pan=0.3, gain=0.5)
    # keys comping + pad
    keys_chord(ch, b0, 1.5, 0.95)
    keys_chord(ch, b0 + 1.5, 1.0, 0.6, padv=False)
    keys_chord(ch, b0 + 2.5, 1.5, 0.75, padv=False)
    place('pad', pad([m(x) + 12 for x in CH[ch][0][1:3]], 4 * BEAT), bt(b0), gain=0.3, rev=0.3)
    # vocal-like hook
    v, s0 = vox_phrase([(bt(b0 + s), d * BEAT * 0.92, m(nt)) for s, d, nt in hook[bar]], 'a' if bar % 2 == 0 else 'o')
    place('vox', v, s0, gain=0.45, rev=0.4)

# loop hit at b20 (t = 14.25)
place('drums', kick(1.0), bt(20), gain=0.9)
place('bass', b808(CH['F#m'][1], 0.6), bt(20), gain=0.9)
keys_chord('F#m', 20, 1.0, 0.9)
v, s0 = vox_phrase([(bt(20), 0.5, m('F#5'))], 'a')
place('vox', v, s0, gain=0.45, rev=0.4)

# --- sound effects tied to the picture
place('fx', whoosh(0.45, 300, 2500, 0.45), 0.52, pan=-0.4, rev=0.2)      # small frame floats in
place('fx', whoosh(0.7, 3500, 250, 1.0), 3.95, rev=0.25)                  # pull back from the painting
place('fx', whoosh(0.75, 600, 4000, 0.9), 6.38, pan=0.5, rev=0.2)        # pan to the next frame
place('fx', whoosh(0.6, 500, 5000, 0.9), 8.98, pan=0.6, rev=0.2)         # painting flies away
for k, tt in enumerate([9.32, 9.45, 9.58, 9.7, 9.83, 9.95, 10.1, 10.22]):
    place('fx', thump(0.35 + 0.05 * (k % 3)), tt, pan=-0.6 + 0.17 * k, gain=0.6)
place('fx', chime([midi(m('C#7')), midi(m('F#7')), midi(m('A7'))], 0.8), 10.42, gain=0.6, rev=0.5)
place('fx', whoosh(0.4, 4000, 400, 0.6), 14.3, rev=0.2)                    # loop zoom

# ---------------------------------------------------------------- mix
def reverb_ir(length=1.7):
    n = int(length * SR); t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t / (length / 6.9))[:, None]
    ir[: int(0.018 * SR)] = 0
    ir = np.stack([filt(ir[:, 0], 'lp', 5000), filt(ir[:, 1], 'lp', 5000)], 1)
    return ir / np.sqrt((ir ** 2).sum(0))


ir = reverb_ir()
wet = np.stack([fftconvolve(send[:, c], ir[:, c])[:N] for c in range(2)], 1) * 0.55

gains = {'drums': 1.0, 'bass': 0.88, 'keys': 0.85, 'pad': 0.78, 'vox': 0.74, 'fx': 0.75}
for c in range(2):
    bus['vox'][:, c] = filt(bus['vox'][:, c], 'lp', 5200, 0.7)
mix = sum(bus[k] * g for k, g in gains.items()) + wet
# low-end tidy + presence
for c in range(2):
    mix[:, c] = filt(mix[:, c], 'hp', 28)
    mix[:, c] = filt(mix[:, c], 'peak', 3200, 0.8, 1.5)

# the stop: hard gate with short fades (reference goes to ~-65 dB)
t = np.arange(N) / SR
gate = np.ones(N)
f = 0.03
gate = np.where((t > STOP0) & (t < STOP1), 0.0, gate)
gate = np.where((t > STOP0 - f) & (t <= STOP0), (STOP0 - t) / f, gate)
mix *= gate[:, None]

# glue: soft compression-ish saturation then normalise
peak = np.abs(mix).max()
mix = np.tanh(mix / peak * 1.6) / np.tanh(1.6)
# fade in/out
fi = np.clip(t / 0.01, 0, 1); fo = np.clip((DUR - t) / 0.12, 0, 1)
mix *= (fi * fo)[:, None]
mix *= 0.89 / np.abs(mix).max()

out = sys.argv[1] if len(sys.argv) > 1 else 'music.wav'
import wave
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
print('wrote', out, f'{DUR}s', 'rms dB', 20 * np.log10(np.sqrt((mix ** 2).mean())))
