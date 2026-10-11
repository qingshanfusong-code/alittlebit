"""Shared helpers: colours, easing, keyframes, beat-aware time parsing."""
import json
import math
import re

import numpy as np

# ---------------------------------------------------------------- colours


def parse_color(c, default=(255, 255, 255, 255)):
    """'#rgb' '#rrggbb' '#rrggbbaa' [r,g,b] [r,g,b,a] 'white' -> (r,g,b,a) ints."""
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        if all(isinstance(x, float) and x <= 1.0 for x in c):
            v = [int(round(x * 255)) for x in c]
        else:
            v = [int(x) for x in c]
        if len(v) == 3:
            v.append(255)
        return tuple(v[:4])
    s = str(c).strip().lower()
    named = {
        "white": "#ffffff", "black": "#000000", "red": "#e3262e", "gold": "#c9a45c", "cream": "#f3ead8",
        "navy": "#1c3a63", "mint": "#a9d6c2", "pink": "#f2b8c6", "yellow": "#f4c430", "blue": "#2147d1",
        "transparent": "#00000000", "grey": "#808080", "gray": "#808080", "cyan": "#22c7d6",
    }
    s = named.get(s, s)
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) if len(h) == 8 else 255
        return (r, g, b, a)
    raise ValueError(f"bad colour {c!r}")


# ---------------------------------------------------------------- easing


def _back_out(p, s=1.70158):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


EASE = {
    "linear": lambda p: p,
    "in": lambda p: p ** 3,
    "out": lambda p: 1 - (1 - p) ** 3,
    "inout": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2,
    "sine": lambda p: -(math.cos(math.pi * p) - 1) / 2,
    "expo_out": lambda p: 1 if p >= 1 else 1 - 2 ** (-10 * p),
    "expo_in": lambda p: 0 if p <= 0 else 2 ** (10 * p - 10),
    "expo_inout": lambda p: 0 if p <= 0 else 1 if p >= 1 else (
        2 ** (20 * p - 10) / 2 if p < 0.5 else (2 - 2 ** (-20 * p + 10)) / 2),
    "back_out": _back_out,
    "elastic_out": lambda p: 0 if p <= 0 else 1 if p >= 1 else
    2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi) / 3) + 1,
    "step": lambda p: 0.0 if p < 1 else 1.0,
}


def ease(name, p):
    p = 0.0 if p < 0 else 1.0 if p > 1 else p
    return EASE.get(name or "linear", EASE["linear"])(p)


# ---------------------------------------------------------------- beat map


class BeatMap:
    """Maps beat references to timeline seconds.

    Beat indices count from the first beat at/after the start of the music used in the edit.
    """

    def __init__(self, data=None, shift=0.0, bpm=None, first=0.0):
        self.beats = np.array([])
        self.downbeats = np.array([])
        self.onsets = np.array([])
        self.strong = np.array([])
        self.drop = None
        if data:
            sh = shift
            self.beats = np.array(data.get("beats", [])) - sh
            self.downbeats = np.array(data.get("downbeats", [])) - sh
            self.onsets = np.array(data.get("onsets", [])) - sh
            self.strong = np.array(data.get("strong_onsets", [])) - sh
            self.beats = self.beats[self.beats >= -0.02]
            self.downbeats = self.downbeats[self.downbeats >= -0.02]
            self.onsets = self.onsets[self.onsets >= -0.02]
            self.strong = self.strong[self.strong >= -0.02]
            if data.get("drop") is not None:
                self.drop = data["drop"] - sh
            self.interval = float(data.get("beat_interval") or (np.median(np.diff(self.beats)) if len(
                self.beats) > 2 else 0.5))
        elif bpm:
            self.interval = 60.0 / bpm
            self.beats = first + self.interval * np.arange(2000)
            self.downbeats = self.beats[::4]
        else:
            self.interval = 0.5  # 120 bpm fallback so "1b" still means something
            self.beats = self.interval * np.arange(2000)
            self.downbeats = self.beats[::4]
        self.has_music = data is not None or bpm is not None

    def time(self, idx, kind="b"):
        arr = self.downbeats if kind == "d" else self.beats
        step = self.interval * (4 if kind == "d" else 1)
        if len(arr) == 0:
            return idx * step
        i = math.floor(idx)
        f = idx - i
        if i < 0:
            return float(arr[0] + idx * step)
        if i >= len(arr) - 1:
            return float(arr[-1] + (idx - (len(arr) - 1)) * step)
        return float(arr[i] + f * (arr[i + 1] - arr[i]))

    def index(self, t):
        b = self.beats
        if len(b) == 0:
            return t / self.interval
        if t <= b[0]:
            return (t - b[0]) / self.interval
        if t >= b[-1]:
            return len(b) - 1 + (t - b[-1]) / self.interval
        i = int(np.searchsorted(b, t) - 1)
        return i + (t - b[i]) / (b[i + 1] - b[i])

    def times_for(self, spec, start=0.0, end=1e9):
        """'beats' | 'downbeats' | 'onsets' | 'strong_onsets' | {'every':'2b','from':..,'to':..} | [refs]"""
        if isinstance(spec, str):
            src = {"beats": self.beats, "downbeats": self.downbeats, "bars": self.downbeats,
                   "onsets": self.onsets, "strong_onsets": self.strong}.get(spec)
            if src is None:
                return [parse_time(spec, self)]
            return [float(x) for x in src if start - 1e-6 <= x < end]
        if isinstance(spec, dict):
            a = parse_time(spec.get("from", start), self)
            b = parse_time(spec.get("to", end), self) if spec.get("to") is not None else end
            out, t = [], a
            while t < b - 1e-6 and len(out) < 5000:
                out.append(t)
                t = t + parse_dur(spec.get("every", "1b"), self, t)
            return out
        return [parse_time(x, self) for x in spec]


_TERM = re.compile(r"([+-]?)\s*([a-z_]*)\s*(-?[0-9]*\.?[0-9]+)?\s*([a-z%]*)")


def parse_time(v, bm, default=0.0):
    """Absolute timeline position.

    number | "12.5" | "b8" (beat 8) | "b8.5" | "d2" (downbeat/bar 2) | "drop" | "o3" (onset 3)
    optionally followed by offsets: "b8+0.1", "d2-0.5b", "drop+2b".
    """
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace(" ", "")
    if not s:
        return default
    parts = re.findall(r"[+-]?[^+-]+", s)
    if not parts:
        return default
    head = parts[0]
    base = _abs_term(head, bm)
    t = base
    for p in parts[1:]:
        sign = -1 if p.startswith("-") else 1
        t += sign * parse_dur(p.lstrip("+-"), bm, t)
    return t


def _abs_term(s, bm):
    if s == "drop":
        if bm.drop is None:
            raise ValueError("spec uses 'drop' but no drop was detected in beats.json; use a beat index instead")
        return float(bm.drop)
    m = re.fullmatch(r"([bdo])(-?[0-9]*\.?[0-9]+)", s)
    if m:
        kind, n = m.group(1), float(m.group(2))
        if kind == "o":
            arr = bm.onsets
            i = int(n)
            if not len(arr):
                raise ValueError("no onsets available")
            return float(arr[min(i, len(arr) - 1)])
        return bm.time(n, kind)
    if s.endswith("s"):
        s = s[:-1]
    return float(s)


def parse_dur(v, bm, at=0.0):
    """Duration: number (s) | "0.5" | "0.5s" | "2b" (beats, measured from `at`) | "1bar" | "1d"."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    m = re.fullmatch(r"(-?[0-9]*\.?[0-9]+)(b|beat|beats|bar|bars|d|s|f)?", s)
    if not m:
        raise ValueError(f"bad duration {v!r}")
    n, u = float(m.group(1)), m.group(2) or "s"
    if u in ("b", "beat", "beats"):
        i0 = bm.index(at)
        return bm.time(i0 + n) - bm.time(i0) if bm.has_music else n * bm.interval
    if u in ("bar", "bars", "d"):
        i0 = bm.index(at)
        return bm.time(i0 + 4 * n) - bm.time(i0)
    if u == "f":
        return n / 30.0
    return n


# ---------------------------------------------------------------- keyframes


def kf_time(t, dur):
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0 * dur
    if s.startswith("end"):
        rest = s[3:]
        return dur + (float(rest) if rest else 0.0)
    return float(s)


def is_keyframes(v):
    return isinstance(v, list) and v and isinstance(v[0], (list, dict))


def norm_keyframes(v, dur):
    out = []
    for k in v:
        if isinstance(k, dict):
            out.append((kf_time(k.get("t", 0), dur), k.get("v"), k.get("ease", "inout")))
        else:
            out.append((kf_time(k[0], dur), k[1], k[2] if len(k) > 2 else "inout"))
    out.sort(key=lambda x: x[0])
    return out


def lerp(a, b, p):
    if isinstance(a, (list, tuple)):
        return [lerp(x, y, p) for x, y in zip(a, b)]
    return a + (b - a) * p


def eval_kf(kfs, t):
    if not kfs:
        return None
    if t <= kfs[0][0]:
        return kfs[0][1]
    for (t0, v0, _), (t1, v1, e1) in zip(kfs, kfs[1:]):
        if t <= t1:
            p = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
            return lerp(v0, v1, ease(e1, p))
    return kfs[-1][1]


def value_at(v, t, dur, default=None):
    """Static value or keyframe list -> value at local time t."""
    if v is None:
        return default
    if is_keyframes(v):
        return eval_kf(norm_keyframes(v, dur), t)
    return v


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def hash_noise(i, seed=0):
    """Deterministic pseudo-random float in [0,1) for integer i."""
    x = math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453
    return x - math.floor(x)


def is_beat_ref(v):
    return isinstance(v, str) and bool(re.match(r"\s*(b|d|o)-?[0-9.]|\s*drop", v.strip().lower()))


def ltime(v, bm, off=0.0, default=0.0):
    """Time inside a parent whose absolute start is `off`: numbers are parent-local,
    beat references (b8, d2, drop...) are absolute music positions converted to local."""
    if v is None:
        return default
    t = parse_time(v, bm, default)
    return t - off if is_beat_ref(v) else t
