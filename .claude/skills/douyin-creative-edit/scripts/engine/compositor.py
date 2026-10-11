"""Layer compositor: spec -> frames -> mp4 (+ music / original audio)."""
import bisect
import copy
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time as _time

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from . import fx, masks, media
from . import text as textmod
from .fonts import FontBook
from .util import (BeatMap, ease, eval_kf, hash_noise, is_beat_ref, is_keyframes, load_json, ltime, parse_color,
                   parse_dur, parse_time)

SOURCE_KEYS = ("video", "image", "text", "shape", "group", "gradient", "color")  # "color" last: it is also a property
TEXT_KEYS = {"font", "size", "size_px", "color", "stroke", "stroke_color", "outline", "scale_x", "skew", "tracking",
             "line_spacing", "align", "vertical", "case", "shadow", "glow", "box", "fonts", "cycle"}
VIDEO_KEYS = {"in", "speed", "shutter", "loop", "reverse", "audio", "volume", "freeze"}
SHAPE_KEYS = {"points", "width", "color", "radius", "fill", "outline_width", "draw", "smooth", "rx", "ry", "r",
              "rect", "dash"}
LAYER_KEYS = {"id", "source", "start", "end", "dur", "box", "fit", "focus", "crop", "x", "y", "scale", "scale_x",
              "scale_y", "rotation", "opacity", "anchor", "anim", "enter", "exit", "mask", "effects", "blend",
              "oversample", "note", "comment"}
CANVAS_PRESETS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "4:3": (1440, 1080), "3:4": (1080, 1440),
                  "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (2520, 1080), "2.35:1": (2538, 1080)}


class Ctx:
    pass


# ====================================================================== spec loading


def load_spec(path_or_dict, base_dir=None, preview=1.0):
    if isinstance(path_or_dict, dict):
        spec = copy.deepcopy(path_or_dict)
        base = base_dir or os.getcwd()
    else:
        spec = load_json(path_or_dict)
        base = base_dir or os.path.dirname(os.path.abspath(path_or_dict))
    ctx = Ctx()
    ctx.base = base
    cv = spec.get("canvas", {})
    if isinstance(cv, str):
        cv = {"preset": cv}
    W, H = CANVAS_PRESETS.get(cv.get("preset", "9:16"), (1080, 1920))
    W, H = int(cv.get("width", W)), int(cv.get("height", H))
    ctx.full_W, ctx.full_H = W, H
    ctx.W, ctx.H = media.even(W * preview), media.even(H * preview)
    ctx.S = min(ctx.W, ctx.H)
    ctx.fps = float(cv.get("fps", 30))
    ctx.bg = parse_color(cv.get("bg", "#000000"))
    skill_fonts = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                               "assets", "fonts")
    ctx.fb = FontBook([os.path.join(base, "fonts"), skill_fonts], overrides=spec.get("fonts"))
    # ---- music + beat map
    auds = spec.get("audio") or []
    if isinstance(auds, dict):
        auds = [auds]
    ctx.audio = [dict(a) for a in auds]
    music = ctx.audio[0] if ctx.audio else None
    bsrc = spec.get("beats")
    if isinstance(bsrc, str):
        bsrc = load_json(resolve(ctx, bsrc))
    if bsrc:
        m_start = float(music.get("start", 0.0)) if music else 0.0
        m_at = float(music.get("at", 0.0)) if music else 0.0
        shift = m_start - float(bsrc.get("offset", 0.0)) - m_at
        ctx.bm = BeatMap(bsrc, shift=shift)
    elif spec.get("bpm"):
        ctx.bm = BeatMap(None, bpm=float(spec["bpm"]), first=float(spec.get("first_beat", 0.0)))
    else:
        ctx.bm = BeatMap(None)
    ctx.spec = spec
    ctx.warnings = []
    from .macros import expand_all
    raw = expand_all(spec.get("layers", []), ctx)
    ctx.layers = [normalize_layer(L, ctx, i) for i, L in enumerate(raw)]
    ctx.layers = [L for L in ctx.layers if L is not None]
    dur = spec.get("duration")
    if dur is not None:
        ctx.duration = parse_time(dur, ctx.bm)
    else:
        ctx.duration = max([L["end"] for L in ctx.layers if L["end"] < 1e8] + [1.0])
    for L in ctx.layers:
        if L["end"] > 1e8:
            L["end"] = ctx.duration
    ctx.post = spec.get("post", [])
    ctx.beat_fx = spec.get("beat_fx", [])
    ctx.beat_times = [sorted(ctx.bm.times_for(it.get("at", "beats"), 0, ctx.duration + 1)) for it in ctx.beat_fx]
    ctx.state = {}
    return ctx


def resolve(ctx, p):
    if p is None:
        return None
    p = os.path.expanduser(str(p))
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(ctx.base, p))


def normalize_layer(L, ctx, idx, parent_dur=None, off=0.0):
    L = dict(L)
    L["_off"] = off
    L.setdefault("id", f"L{idx}")
    src = L.get("source")
    if src is None:
        for k in SOURCE_KEYS:
            if k in L:
                src = {k: L.pop(k)}
                extra = {"text": TEXT_KEYS, "video": VIDEO_KEYS, "image": set(), "color": set(),
                         "gradient": set(), "shape": SHAPE_KEYS, "group": set()}[k]
                for kk in list(L.keys()):
                    if kk in extra and kk not in ("x", "y"):
                        if kk == "in" and not isinstance(L[kk], (int, float)):
                            raise ValueError(f"layer {L['id']}: 'in' is the video in-point (seconds); "
                                             "use 'enter'/'exit' for transitions")
                        src[kk] = L.pop(kk)
                break
    if src is None:
        ctx.warnings.append(f"layer {L['id']} has no source; skipped")
        return None
    if "_kind" not in src:
        src["_kind"] = next((k for k in SOURCE_KEYS if k in src), None)
    L["source"] = src
    unknown = [k for k in L if k not in LAYER_KEYS and not k.startswith("_")]
    if unknown:
        ctx.warnings.append(f"layer {L['id']}: unknown keys {unknown} ignored (typo? see references/spec.md)")
    bm = ctx.bm
    start = ltime(L.get("start", 0), bm, off)
    if "end" in L:
        end = ltime(L["end"], bm, off)
    elif "dur" in L:
        end = start + parse_dur(L["dur"], bm, start + off)
    elif src["_kind"] == "video" and not src.get("loop", False):
        p = resolve(ctx, src["video"])
        info = media.probe(p) if os.path.exists(p) else {"duration": 0}
        remain = max(0.1, (info.get("duration") or 0) - float(src.get("in", 0)))
        sp = src.get("speed", 1.0)
        sp = 1.0 if isinstance(sp, (list, dict)) or src.get("freeze") else sp
        end = start + remain / max(1e-3, abs(float(sp)))
    else:
        end = 1e9 if parent_dur is None else parent_dur
    L["start"], L["end"] = start, end
    for k in ("video", "image"):
        if k in src:
            src[k] = resolve(ctx, src[k])
            if not os.path.exists(src[k]):
                raise FileNotFoundError(f"layer {L['id']}: {k} not found: {src[k]}")
    if src["_kind"] == "group":
        gdur = end - start if end < 1e8 else None
        from .macros import expand_all
        src["_layers"] = [x for x in (normalize_layer(c, ctx, f"{L['id']}.{j}", gdur, off + start)
                                      for j, c in enumerate(expand_all(src["group"], ctx, offset=off + start)))
                          if x is not None]
        # children are authored in group-local time
        for c in src["_layers"]:
            if c["end"] > 1e8:
                c["end"] = gdur if gdur else 1e9
    if src["_kind"] == "video":
        if src.pop("freeze", False):
            src["speed"], src["loop"] = 1e-6, False
        sp = src.get("speed", 1.0)
        if isinstance(sp, (list, dict)):
            # speed ramp: integrate speed(t) -> source time
            Ltmp = {"start": start, "end": end, "_off": off, "_kf_cache": {}}
            n = max(2, int((end - start) * 240))
            ts = np.linspace(0, end - start, n)
            v = np.array([max(0.02, float(ev(sp, t, Ltmp, ctx, True))) for t in ts])
            cum = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(ts))])
            L["_ramp"] = (ts, cum)
            src["speed"] = 1.0
    if src["_kind"] == "text" and src.get("fonts"):
        every = src.get("cycle", "1b")
        src["_switch"] = ctx.bm.times_for({"every": every, "from": start + off, "to": end + off}) \
            if end < 1e8 else [start + off]
    mk = L.get("mask")
    if isinstance(mk, dict) and mk.get("type") == "image":
        mk["path"] = resolve(ctx, mk["path"])
    L["_kf_cache"] = {}
    return L


# ====================================================================== value evaluation


def kf_time(v, L, ctx):
    dur = L["end"] - L["start"]
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0 * dur
    if s.startswith("end"):
        rest = s[3:]
        return dur + (parse_dur(rest[1:], ctx.bm) * (1 if rest[0] == "+" else -1) if rest else 0.0)
    if is_beat_ref(s):
        return parse_time(s, ctx.bm) - L["start"] - L["_off"]
    return parse_dur(s, ctx.bm, L["start"] + L["_off"])  # "0.4", "0.4s", "2b", "1bar", "12f"


def _kfs(raw, L, ctx):
    key = id(raw)
    c = L["_kf_cache"].get(key)
    if c is None:
        out = []
        for k in raw:
            if isinstance(k, dict):
                out.append((kf_time(k.get("t", 0), L, ctx), k.get("v"), k.get("ease", "inout")))
            else:
                out.append((kf_time(k[0], L, ctx), k[1], k[2] if len(k) > 2 else "inout"))
        out.sort(key=lambda x: x[0])
        c = L["_kf_cache"][key] = out
    return c


def ev(v, lt, L, ctx, transform_key=False):
    """Evaluate a possibly-animated value. Animated forms:
    {"kf": [[t, v, ease?], ...]}  |  {"from": a, "to": b, "dur": d?, "delay": s?, "ease": e?}
    and, for transform keys only, a bare [[t, v], ...] list."""
    if isinstance(v, dict):
        if "kf" in v:
            return eval_kf(_kfs(v["kf"], L, ctx), lt)
        if "from" in v and "to" in v and "every" not in v:
            dur = L["end"] - L["start"]
            delay = kf_time(v.get("delay", 0), L, ctx)
            d = kf_time(v.get("dur", dur - delay), L, ctx)
            p = 0 if d <= 0 else (lt - delay) / d
            p = ease(v.get("ease", "inout"), min(1, max(0, p)))
            a, b = v["from"], v["to"]
            if isinstance(a, list):
                return [x + (y - x) * p for x, y in zip(a, b)]
            return a + (b - a) * p
        return {k: ev(x, lt, L, ctx) for k, x in v.items()}
    if transform_key and is_keyframes(v):
        return eval_kf(_kfs(v, L, ctx), lt)
    if isinstance(v, list):
        return [ev(x, lt, L, ctx) for x in v]
    return v


# ====================================================================== motion presets


def anim_mods(L, lt, ctx):
    """Built-in motion presets -> additive/multiplicative modifiers."""
    dur = L["end"] - L["start"]
    m = {"dx": 0.0, "dy": 0.0, "scale": 1.0, "sx": 1.0, "sy": 1.0, "rot": 0.0, "opacity": 1.0, "blur": 0.0,
         "rgb": 0.0, "mblur": 0.0, "mblur_angle": 0.0, "visible": None, "flash": 0.0, "invert": False}
    anims = L.get("anim") or []
    if isinstance(anims, (str, dict)):
        anims = [anims]
    for a in anims:
        if isinstance(a, str):
            a = {"name": a}
        name = a.get("name")
        d = parse_dur(a.get("dur", 0.3 if name not in ("ken_burns", "zoom_out", "drift", "shake", "float", "spin",
                                                          "typewriter", "pulse", "flicker", "wiggle") else dur),
                      ctx.bm, L["start"] + L["_off"])
        delay = parse_dur(a.get("delay", 0), ctx.bm, L["start"] + L["_off"])
        amt = a.get("amount")
        p = 1.0 if d <= 0 else max(0.0, min(1.0, (lt - delay) / d))
        q = 1.0 if d <= 0 else max(0.0, min(1.0, (dur - lt) / d))  # for *_out (1 -> 0 at end)
        direction = a.get("dir", "left")
        vec = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}.get(direction, (-1, 0))
        if name == "pop_in":
            m["scale"] *= 0.4 + 0.6 * ease("back_out", p)
            m["opacity"] *= min(1, p * 2.5)
        elif name == "pop_out":
            m["scale"] *= 0.4 + 0.6 * ease("out", q)
            m["opacity"] *= min(1, q * 2.5)
        elif name == "punch_in":
            m["scale"] *= 1 + float(amt or 0.18) * (1 - ease("out", p))
        elif name == "scale_in":
            m["scale"] *= ease("expo_out", p)
        elif name == "stretch_in":
            m["sy"] *= max(0.001, ease("expo_out", p))
        elif name == "ken_burns":
            k = float(amt or 0.12)
            pp = ease("sine", lt / max(dur, 1e-3))
            m["scale"] *= 1 + k * pp
            m["dx"] += float(a.get("pan_x", 0)) * pp
            m["dy"] += float(a.get("pan_y", 0)) * pp
        elif name == "zoom_out":
            k = float(amt or 0.12)
            m["scale"] *= 1 + k * (1 - ease("sine", lt / max(dur, 1e-3)))
        elif name == "drift":
            k = float(amt or 0.03)
            pp = lt / max(dur, 1e-3)
            m["dx"] += vec[0] * k * pp
            m["dy"] += vec[1] * k * pp
        elif name in ("slide_in", "whip_in"):
            dist = float(amt or 1.0)
            e = 1 - ease("expo_out", p)
            m["dx"] -= vec[0] * dist * e
            m["dy"] -= vec[1] * dist * e
            if name == "whip_in":
                m["mblur"] += 0.12 * e
                m["mblur_angle"] = 0 if vec[1] == 0 else 90
        elif name in ("slide_out", "whip_out"):
            dist = float(amt or 1.0)
            e = 1 - ease("expo_out", q) if q < 1 else 0
            e = ease("expo_in", 1 - q)
            m["dx"] += vec[0] * dist * e
            m["dy"] += vec[1] * dist * e
            if name == "whip_out":
                m["mblur"] += 0.12 * e
                m["mblur_angle"] = 0 if vec[1] == 0 else 90
        elif name == "fade_in":
            m["opacity"] *= ease("inout", p)
        elif name == "fade_out":
            m["opacity"] *= ease("inout", q)
        elif name == "blur_in":
            m["blur"] += float(amt or 0.03) * (1 - ease("out", p))
            m["opacity"] *= min(1, p * 1.5)
        elif name == "blur_out":
            m["blur"] += float(amt or 0.03) * (1 - ease("in", q))
            m["opacity"] *= min(1, q * 1.5)
        elif name == "rise":
            m["dy"] += float(amt or 0.04) * (1 - ease("expo_out", p))
            m["opacity"] *= ease("out", p)
        elif name == "shake":
            k = float(amt or 0.008)
            f = float(a.get("freq", 14))
            i = int(lt * f)
            m["dx"] += (hash_noise(i, 1) - 0.5) * 2 * k
            m["dy"] += (hash_noise(i, 2) - 0.5) * 2 * k
            m["rot"] += (hash_noise(i, 3) - 0.5) * 2 * k * 60
        elif name == "wiggle":
            k = float(amt or 2.0)
            m["rot"] += math.sin(lt * 2 * math.pi * float(a.get("freq", 1.5))) * k
        elif name == "float":
            k = float(amt or 0.012)
            m["dy"] += math.sin(lt * 2 * math.pi / float(a.get("period", 3.0))) * k
        elif name == "spin":
            m["rot"] += float(amt or 20.0) * lt
        elif name == "pulse":
            a0 = L["start"] + L["_off"]
            bt = ctx.bm.times_for(a.get("at", "beats"), a0, L["end"] + L["_off"])
            last = fx.np_last_le(bt, a0 + lt)
            if last is not None:
                m["scale"] *= 1 + float(amt or 0.06) * math.exp(-(a0 + lt - last) / 0.09)
        elif name == "flicker":
            i = int(lt * float(a.get("freq", 18)))
            if hash_noise(i, 7) < float(amt or 0.3):
                m["opacity"] *= 0.15
        elif name == "typewriter":
            m["visible"] = p
        elif name == "flash_in":
            m["flash"] = max(m["flash"], 1 - ease("out", p))
        else:
            raise ValueError(f"unknown anim preset {name!r}")
    return m


# ====================================================================== transitions


def transition_mods(L, lt, ctx, m):
    """Layer in/out transitions -> modifiers + optional mask dict."""
    dur = L["end"] - L["start"]
    mask = None
    for side in ("in", "out"):
        tr = L.get("enter" if side == "in" else "exit")
        if not tr:
            continue
        if isinstance(tr, str):
            tr = {"type": tr}
        typ = tr.get("type", "fade")
        if typ in ("cut", "none"):
            continue
        d = parse_dur(tr.get("dur", 0.3), ctx.bm, L["start"] + L["_off"])
        if d <= 0:
            continue
        p = lt / d if side == "in" else (dur - lt) / d
        if p >= 1:
            continue
        p = max(0.0, p)
        sgn = 1
        if typ == "fade" or typ == "dissolve":
            m["opacity"] *= ease("inout", p)
        elif typ == "zoom":
            m["scale"] *= 1 + float(tr.get("amount", 0.35)) * (1 - ease("expo_out", p))
            m["opacity"] *= min(1, p * 2.5)
            m["blur"] += 0.012 * (1 - p)
        elif typ == "zoom_out":
            m["scale"] *= 0.65 + 0.35 * ease("expo_out", p)
            m["opacity"] *= min(1, p * 2.5)
        elif typ.startswith("slide_") or typ.startswith("whip_") or typ.startswith("push_"):
            direction = typ.split("_", 1)[1]
            vec = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[direction]
            if side == "in":
                e = 1 - ease("expo_out" if not typ.startswith("whip") else "inout", p)
                m["dx"] -= vec[0] * e
                m["dy"] -= vec[1] * e
            else:
                e = 1 - ease("expo_in" if not typ.startswith("whip") else "inout", p)
                m["dx"] += vec[0] * e
                m["dy"] += vec[1] * e
            if typ.startswith("whip"):
                m["mblur"] += 0.18 * math.sin(math.pi * min(1, p))
                m["mblur_angle"] = 0 if vec[1] == 0 else 90
        elif typ.startswith("wipe_"):
            mask = {"type": "wipe", "progress": ease("inout", p), "dir": typ.split("_", 1)[1], "feather": 0.02}
        elif typ == "iris":
            mask = {"type": "iris", "progress": ease("inout", p), "x": tr.get("x", 0.5), "y": tr.get("y", 0.5)}
        elif typ == "strip":
            mask = {"type": "strip", "w": ease("expo_inout", p), "x": tr.get("x", 0.5)}
        elif typ == "strip_h":
            mask = {"type": "strip", "w": ease("expo_inout", p), "y": tr.get("y", 0.5), "horizontal": True}
        elif typ == "blinds":
            mask = {"type": "blinds", "progress": ease("inout", p), "n": tr.get("n", 8), "dir": tr.get("dir", "v")}
        elif typ == "grid":
            mask = {"type": "grid", "progress": p, "cols": tr.get("cols", 4), "rows": tr.get("rows", 4),
                    "seed": tr.get("seed", 3)}
        elif typ == "brush":
            mask = {"type": "brush", "progress": ease("inout", p), "style": "sweep", "seed": tr.get("seed", 7)}
        elif typ == "brush_blob":
            mask = {"type": "brush", "progress": ease("out", p), "style": "blob", "x": tr.get("x", 0.5),
                    "y": tr.get("y", 0.5), "seed": tr.get("seed", 7)}
        elif typ == "blur":
            m["blur"] += float(tr.get("amount", 0.04)) * (1 - ease("out", p))
            m["opacity"] *= ease("inout", p)
        elif typ == "glitch":
            k = 1 - p
            i = int(lt * 40)
            m["rgb"] += 0.02 * k
            m["dx"] += (hash_noise(i, 11) - 0.5) * 0.06 * k
            if hash_noise(i, 13) < 0.3 * k:
                m["opacity"] *= 0.3
        elif typ == "spin":
            sgn = 1 if side == "in" else -1
            m["rot"] += sgn * float(tr.get("amount", 120)) * (1 - ease("expo_out", p))
            m["scale"] *= 0.4 + 0.6 * ease("expo_out", p)
            m["mblur"] += 0.04 * (1 - p)
        elif typ == "pop":
            m["scale"] *= max(0.001, ease("back_out", p))
        elif typ == "flash":
            m["flash"] = max(m["flash"], 1 - ease("out", p))
        elif typ == "invert":
            if p < 0.5:
                m["invert"] = True
        elif typ == "zoom_into":
            k = 1 - p  # 0 -> 1 as the layer exits
            m["scale"] *= 1 + float(tr.get("amount", 7.0)) * ease("expo_in", k)
            m["zoom_point"] = (float(tr.get("x", 0.5)), float(tr.get("y", 0.5)))
            m["blur"] += 0.015 * ease("in", k)
        else:
            raise ValueError(f"unknown transition {typ!r}")
    return mask


# ====================================================================== sources


def source_image(L, lt, ctx, t_abs):
    src = L["source"]
    W, H, S = ctx.W, ctx.H, ctx.S
    box = L.get("box") or [0, 0, 1, 1]
    box = ev(box, lt, L, ctx)
    bw, bh = max(2, int(round(box[2] * W))), max(2, int(round(box[3] * H)))
    fit = L.get("fit", "cover")
    focus = tuple(L.get("focus", (0.5, 0.5)))
    kind = src["_kind"]
    if kind == "video":
        rd = L.get("_reader")
        if rd is None:
            over = float(L.get("oversample", 1.0))
            ramp = L.get("_ramp")
            rd = media.VideoReader(src["video"], bw, bh, fit=fit, focus=focus, crop=L.get("crop"),
                                   in_point=float(src.get("in", 0.0)),
                                   speed=float(src.get("speed", 1.0)) if not ramp else max(1.0, float(
                                       np.max(np.diff(ramp[1]) / np.maximum(np.diff(ramp[0]), 1e-9)))),
                                   fps=ctx.fps, max_src_dur=(float(ramp[1][-1]) if ramp else (L["end"] - L["start"])
                                                             * abs(float(src.get("speed", 1))))
                                   + float(src.get("shutter", 0)),
                                   shutter=float(src.get("shutter", 0.0)), loop=bool(src.get("loop", True)),
                                   reverse=bool(src.get("reverse", False)), oversample=over)
            L["_reader"] = rd
        if L.get("_ramp"):
            ts, cum = L["_ramp"]
            return rd.get_source(float(np.interp(lt, ts, cum))), "media"
        return rd.get(lt), "media"
    if kind == "image":
        over = float(L.get("oversample", 1.0))
        return media.load_image(src["image"], bw, bh, fit, focus, L.get("crop"), over), "media"
    if kind == "color":
        key = ("color", src["color"], bw, bh)
        img = _solid_cache.get(key)
        if img is None:
            img = _solid_cache[key] = Image.new("RGBA", (bw, bh), parse_color(ev(src["color"], lt, L, ctx)))
        return img, "media"
    if kind == "gradient":
        g = ev(src["gradient"], lt, L, ctx)
        return gradient_image(bw, bh, g), "media"
    if kind == "text":
        spec = {k: ev(v, lt, L, ctx) for k, v in src.items() if not k.startswith("_") and k not in ("fonts", "cycle")}
        if src.get("fonts"):
            idx = bisect.bisect_right(src["_switch"], t_abs + 1e-6) - 1
            fspec = src["fonts"][max(0, idx) % len(src["fonts"])]
            if isinstance(fspec, dict):
                spec.update(fspec)
            else:
                spec["font"] = fspec
        return spec, "text"
    if kind == "shape":
        return draw_shape(ev({k: v for k, v in src.items() if k != "_kind"}, lt, L, ctx), ctx), "canvas"
    if kind == "group":
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        compose(src["_layers"], lt, ctx, canvas, t_abs - lt)
        return canvas, "canvas"
    raise ValueError(f"unknown source {src}")


_solid_cache = {}


def gradient_image(w, h, g):
    cols = [parse_color(c) for c in g.get("colors", ["#000000", "#ffffff"])]
    ang = math.radians(float(g.get("angle", 90)))
    sw, sh = max(2, w // 8), max(2, h // 8)
    ys, xs = np.mgrid[0:sh, 0:sw].astype(np.float32)
    u = ((xs / sw - 0.5) * math.cos(ang) + (ys / sh - 0.5) * math.sin(ang)) + 0.5
    if g.get("radial"):
        u = np.sqrt((xs / sw - 0.5) ** 2 + (ys / sh - 0.5) ** 2) * 2
    u = np.clip(u, 0, 1) * (len(cols) - 1)
    i0 = np.floor(u).astype(int).clip(0, len(cols) - 2) if len(cols) > 1 else np.zeros_like(u, int)
    f = (u - i0)[..., None]
    c = np.array(cols, np.float32)
    arr = c[i0] * (1 - f) + c[np.minimum(i0 + 1, len(cols) - 1)] * f
    return Image.fromarray(arr.astype(np.uint8), "RGBA").resize((w, h), Image.BILINEAR)


def draw_shape(s, ctx):
    W, H, S = ctx.W, ctx.H, ctx.S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    kind = s["shape"]
    col = parse_color(s.get("color", "#ffffff"))
    ow = int(float(s.get("outline_width", 0)) * S)
    fill = col if s.get("fill", True) and not ow else None
    if kind == "rect":
        if "rect" in s:
            x, y, w, h = s["rect"]
            box = (x * W, y * H, (x + w) * W, (y + h) * H)
        else:
            cx, cy, w, h = s.get("x", 0.5) * W, s.get("y", 0.5) * H, s.get("w", 0.3) * W, s.get("h", 0.3) * H
            box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        r = float(s.get("radius", 0)) * S
        if r > 0:
            d.rounded_rectangle(box, r, fill=fill, outline=col if ow else None, width=ow or 1)
        else:
            d.rectangle(box, fill=fill, outline=col if ow else None, width=ow or 1)
    elif kind in ("ellipse", "circle"):
        cx, cy = s.get("x", 0.5) * W, s.get("y", 0.5) * H
        r = float(s.get("r", 0.1)) * S
        rx, ry = float(s.get("rx", r / S)) * S, float(s.get("ry", r / S)) * S
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=fill, outline=col if ow else None, width=ow or 1)
    elif kind in ("line", "path"):
        pts = [(p[0] * W, p[1] * H) for p in s.get("points", [])]
        if s.get("smooth", kind == "path") and len(pts) > 2:
            pts = catmull_rom(pts, 16)
        prog = float(s.get("draw", 1.0))
        pts = partial_path(pts, prog)
        width = max(1, int(float(s.get("width", 0.006)) * S))
        if len(pts) >= 2:
            d.line(pts, fill=col, width=width, joint="curve")
            r = width / 2
            for (x, y) in (pts[0], pts[-1]):
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    elif kind == "polygon":
        pts = [(p[0] * W, p[1] * H) for p in s.get("points", [])]
        if len(pts) >= 3:
            d.polygon(pts, fill=fill, outline=col if ow else None)
    else:
        raise ValueError(f"unknown shape {kind}")
    return img


def catmull_rom(pts, n=16):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (
                -p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (
                -p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def partial_path(pts, prog):
    if prog >= 1 or len(pts) < 2:
        return pts
    if prog <= 0:
        return []
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    target = total * prog
    out = [pts[0]]
    acc = 0
    for (a, b), s in zip(zip(pts, pts[1:]), seg):
        if acc + s >= target:
            f = (target - acc) / s if s else 0
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            break
        out.append(b)
        acc += s
    return out


# ====================================================================== compositing


def blend_into(canvas, layer_full, mode):
    """layer_full: canvas-size RGBA. mode: normal|screen|multiply|add|overlay|difference|lighten|darken|soft_light"""
    if mode in (None, "normal"):
        canvas.alpha_composite(layer_full)
        return
    base = canvas.convert("RGB")
    top = layer_full.convert("RGB")
    fn = {"screen": ImageChops.screen, "multiply": ImageChops.multiply, "add": ImageChops.add,
          "overlay": ImageChops.overlay, "difference": ImageChops.difference, "lighten": ImageChops.lighter,
          "darken": ImageChops.darker, "soft_light": ImageChops.soft_light, "hard_light": ImageChops.hard_light}
    if mode not in fn:
        raise ValueError(f"unknown blend {mode}")
    mixed = fn[mode](base, top)
    out = Image.composite(mixed, base, layer_full.getchannel("A")).convert("RGBA")
    canvas.paste(out, (0, 0))


def place(canvas, img, px, py, blend, mask_img):
    W, H = canvas.size
    if mask_img is None and blend in (None, "normal"):
        x0, y0 = max(0, px), max(0, py)
        x1, y1 = min(W, px + img.width), min(H, py + img.height)
        if x1 <= x0 or y1 <= y0:
            return
        canvas.alpha_composite(img, (x0, y0), (x0 - px, y0 - py, x1 - px, y1 - py))
        return
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full.paste(img, (px, py))
    if mask_img is not None:
        masks.apply_mask(full, mask_img)
    blend_into(canvas, full, blend)


def render_layer(L, t_local, ctx, canvas, abs_off):
    lt = t_local - L["start"]
    t_abs = t_local + abs_off
    dur = L["end"] - L["start"]
    W, H, S = ctx.W, ctx.H, ctx.S
    img, kind = source_image(L, lt, ctx, t_abs)
    m = anim_mods(L, lt, ctx)
    tmask = transition_mods(L, lt, ctx, m)
    if kind == "text":
        n = textmod.glyph_count(ctx.fb, img, S)
        vis = None if m["visible"] is None else int(math.ceil(n * m["visible"]))
        img = textmod.render_text(ctx.fb, img, S, vis)
    fx_ctx = {"W": W, "H": H, "S": S, "t": t_abs, "lt": lt, "state": ctx.state.setdefault(L["id"], {}),
              "fb": ctx.fb}
    effects = [ev(e, lt, L, ctx) if isinstance(e, dict) else e for e in (L.get("effects") or [])]
    if effects:
        img = fx.apply_effects(img, effects, fx_ctx)
    if m["blur"] > 0:
        img = fx.blur(img, {"radius": m["blur"]}, fx_ctx)
    if m["mblur"] > 0:
        img = fx.motion_blur(img, {"length": m["mblur"], "angle": m["mblur_angle"]}, fx_ctx)
    if m["rgb"] > 0:
        img = fx.rgb_split(img, {"amount": m["rgb"]}, fx_ctx)
    if m["invert"]:
        img = fx.invert(img, {}, fx_ctx)
    if m["flash"] > 0.01:
        a = img.getchannel("A")
        white = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.blend(img, white, min(1.0, m["flash"]))
        img.putalpha(a)
    # ---------------- transform
    box = ev(L.get("box") or [0, 0, 1, 1], lt, L, ctx)
    if kind == "canvas":
        bx, by = 0.5, 0.5
    else:
        bx, by = box[0] + box[2] / 2, box[1] + box[3] / 2
    x = float(ev(L.get("x", bx), lt, L, ctx, True)) + m["dx"]
    y = float(ev(L.get("y", by), lt, L, ctx, True)) + m["dy"]
    sc = float(ev(L.get("scale", 1.0), lt, L, ctx, True)) * m["scale"]
    sx = sc * float(ev(L.get("scale_x", 1.0), lt, L, ctx, True)) * m["sx"]
    sy = sc * float(ev(L.get("scale_y", 1.0), lt, L, ctx, True)) * m["sy"]
    rot = float(ev(L.get("rotation", 0.0), lt, L, ctx, True)) + m["rot"]
    op = float(ev(L.get("opacity", 1.0), lt, L, ctx, True)) * m["opacity"]
    if op <= 0.003 or sx <= 0.001 or sy <= 0.001:
        return
    ax, ay = L.get("anchor", (0.5, 0.5))
    X, Y = x * W, y * H
    if "zoom_point" in m:
        zx, zy = m["zoom_point"][0] * W, m["zoom_point"][1] * H
        ax = (zx - (X - img.width * ax)) / img.width
        ay = (zy - (Y - img.height * ay)) / img.height
        X, Y = zx, zy
    iw, ih = img.size
    if abs(sx - 1) > 1e-3 or abs(sy - 1) > 1e-3:
        nw, nh = max(1, int(round(iw * sx))), max(1, int(round(ih * sy)))
        # crop before upscaling huge zooms (zoom_into) to keep it fast
        if nw > 3 * W or nh > 3 * H:
            img, ax, ay, iw, ih = _precrop(img, ax, ay, sx, sy, X, Y, W, H)
            nw, nh = max(1, int(round(iw * sx))), max(1, int(round(ih * sy)))
        img = img.resize((nw, nh), Image.BICUBIC if max(sx, sy) < 1.5 else Image.BILINEAR)
    if abs(rot) > 0.01:
        cxo, cyo = img.width / 2, img.height / 2
        vx, vy = ax * img.width - cxo, ay * img.height - cyo
        img = img.rotate(-rot, resample=Image.BICUBIC, expand=True)
        r = math.radians(rot)
        rvx, rvy = vx * math.cos(r) - vy * math.sin(r), vx * math.sin(r) + vy * math.cos(r)
        ax, ay = (img.width / 2 + rvx) / img.width, (img.height / 2 + rvy) / img.height
    if op < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * op)))
    px, py = int(round(X - ax * img.width)), int(round(Y - ay * img.height))
    mask_img = None
    mspecs = L.get("mask")
    if mspecs:
        if isinstance(mspecs, dict):
            mspecs = [mspecs]
        for ms in mspecs:
            mm = ev(ms, lt, L, ctx)
            if "box" in mm:
                bx_, by_, bw_, bh_ = mm["box"]
                mm.update({"x": bx_ + bw_ / 2, "y": by_ + bh_ / 2, "w": bw_, "h": bh_})
                mm.pop("box")
            mi = masks.make_mask(mm, W, H, ctx.fb)
            mask_img = mi if mask_img is None else ImageChops.multiply(mask_img, mi)
    if tmask:
        mi = masks.make_mask(tmask, W, H, ctx.fb)
        mask_img = mi if mask_img is None else ImageChops.multiply(mask_img, mi)
    place(canvas, img, px, py, L.get("blend"), mask_img)


def _precrop(img, ax, ay, sx, sy, X, Y, W, H):
    """For extreme zooms keep only the source region that will land on screen."""
    iw, ih = img.size
    # canvas rect in source coords
    left = ax * iw - X / sx
    top = ay * ih - Y / sy
    right = left + W / sx
    bottom = top + H / sy
    l, t_ = max(0, int(left) - 2), max(0, int(top) - 2)
    r, b = min(iw, int(right) + 3), min(ih, int(bottom) + 3)
    if r - l < 2 or b - t_ < 2:
        return img, ax, ay, iw, ih
    crop = img.crop((l, t_, r, b))
    nax = (ax * iw - l) / crop.width
    nay = (ay * ih - t_) / crop.height
    return crop, nax, nay, crop.width, crop.height


def compose(layers, t, ctx, canvas, abs_off=0.0):
    for L in layers:
        if L["start"] - 1e-9 <= t < L["end"] - 1e-9:
            render_layer(L, t, ctx, canvas, abs_off)
        elif t >= L["end"] and L.get("_reader"):
            L["_reader"].close()
            L["_reader"] = None
    return canvas


def frame_at(ctx, t):
    canvas = Image.new("RGBA", (ctx.W, ctx.H), ctx.bg)
    compose(ctx.layers, t, ctx, canvas)
    fctx = {"W": ctx.W, "H": ctx.H, "S": ctx.S, "t": t, "lt": t, "state": ctx.state.setdefault("_post", {}),
            "fb": ctx.fb}
    if ctx.post:
        canvas = fx.apply_post(canvas, ctx.post, fctx)
    if ctx.beat_fx:
        canvas = fx.beat_fx(canvas, ctx.beat_fx, t, fctx, ctx.beat_times)
    return canvas


def close_all(layers):
    for L in layers:
        if L.get("_reader"):
            L["_reader"].close()
            L["_reader"] = None
        if L["source"].get("_kind") == "group":
            close_all(L["source"]["_layers"])


# ====================================================================== output


def render_video(ctx, out_path, t0=0.0, t1=None, crf=18, preset="medium", progress=True):
    t1 = ctx.duration if t1 is None else min(t1, ctx.duration)
    n = int(round((t1 - t0) * ctx.fps))
    tmpdir = tempfile.mkdtemp(prefix="dce_")
    vtmp = os.path.join(tmpdir, "video.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ctx.W}x{ctx.H}",
           "-r", f"{ctx.fps}", "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", vtmp]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = _time.time()
    try:
        for i in range(n):
            t = t0 + i / ctx.fps
            fr = frame_at(ctx, t).convert("RGB")
            proc.stdin.write(fr.tobytes())
            if progress and (i % max(1, n // 20) == 0 or i == n - 1):
                el = _time.time() - t_start
                eta = el / (i + 1) * (n - i - 1)
                print(f"\r  frame {i + 1}/{n}  t={t:6.2f}s  elapsed {el:5.1f}s  eta {eta:5.1f}s", end="",
                      file=sys.stderr, flush=True)
    finally:
        proc.stdin.close()
        proc.wait()
        close_all(ctx.layers)
    if progress:
        print("", file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg video encode failed")
    mux_audio(ctx, vtmp, out_path, t0, t1)
    shutil.rmtree(tmpdir, ignore_errors=True)
    return out_path


def collect_audio_tracks(ctx, layers=None, offset=0.0):
    tracks = []
    for L in (ctx.layers if layers is None else layers):
        src = L["source"]
        if src.get("_kind") == "video" and src.get("audio") and not L.get("_ramp"):
            info = media.probe(src["video"])
            if info.get("has_audio"):
                tracks.append({"path": src["video"], "start": float(src.get("in", 0.0)),
                               "at": L["start"] + offset, "dur": L["end"] - L["start"],
                               "volume": float(src.get("volume", 1.0)), "speed": float(src.get("speed", 1.0)),
                               "fade_in": 0.03, "fade_out": 0.05})
        if src.get("_kind") == "group":
            tracks += collect_audio_tracks(ctx, src["_layers"], offset + L["start"])
    return tracks


def mux_audio(ctx, vtmp, out_path, t0, t1):
    inputs, filters, labels = [], [], []
    k = 0
    span = t1 - t0
    entries = []
    for a in ctx.audio:
        p = resolve(ctx, a["path"])
        at = parse_time(a.get("at", 0.0), ctx.bm)
        entries.append({"path": p, "start": float(a.get("start", 0.0)), "at": at,
                        "dur": parse_dur(a["dur"], ctx.bm) if a.get("dur") else None,
                        "volume": float(a.get("volume", 1.0)), "fade_in": float(a.get("fade_in", 0.0)),
                        "fade_out": float(a.get("fade_out", 0.6)), "speed": 1.0})
    for s in ctx.spec.get("sfx", []) or []:
        entries.append({"path": resolve(ctx, s["path"]), "start": float(s.get("start", 0.0)),
                        "at": parse_time(s.get("at", 0), ctx.bm), "dur": None,
                        "volume": float(s.get("volume", 1.0)), "fade_in": 0, "fade_out": 0, "speed": 1.0})
    entries += collect_audio_tracks(ctx)
    for e in entries:
        at = e["at"] - t0
        start = e["start"]
        if at < 0:
            start += -at * e.get("speed", 1.0)
            at = 0
        if at >= span:
            continue
        dur = min(span - at, e["dur"] if e["dur"] else span - at)
        inputs += ["-ss", f"{start:.3f}", "-t", f"{dur * e.get('speed', 1.0) + 0.05:.3f}", "-i", e["path"]]
        k += 1
        chain = f"[{k}:a]"
        ops = []
        sp = e.get("speed", 1.0)
        if abs(sp - 1.0) > 1e-3:
            sp_ = sp
            while sp_ > 2.0:
                ops.append("atempo=2.0")
                sp_ /= 2
            while sp_ < 0.5:
                ops.append("atempo=0.5")
                sp_ /= 0.5
            ops.append(f"atempo={sp_:.4f}")
        ops.append("aresample=44100")
        ops.append(f"volume={e['volume']:.3f}")
        if e["fade_in"] > 0:
            ops.append(f"afade=t=in:st=0:d={e['fade_in']:.3f}")
        if e["fade_out"] > 0 and dur > e["fade_out"]:
            ops.append(f"afade=t=out:st={dur - e['fade_out']:.3f}:d={e['fade_out']:.3f}")
        ms = int(at * 1000)
        ops.append(f"adelay={ms}|{ms}")
        filters.append(f"{chain}{','.join(ops)}[a{k}]")
        labels.append(f"[a{k}]")
    if not labels:
        shutil.move(vtmp, out_path)
        return
    fc = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0," \
                             f"apad,atrim=0:{span:.3f}[aout]"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", vtmp] + inputs + ["-filter_complex", fc, "-map", "0:v", "-map",
                                                                  "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a",
                                                                  "192k", "-shortest", "-movflags", "+faststart",
                                                                  out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("audio mux failed: " + r.stderr[-800:])


def render_stills(ctx, times, out_prefix):
    paths = []
    for t in times:
        im = frame_at(ctx, t).convert("RGB")
        p = f"{out_prefix}_{t:06.2f}.png"
        im.save(p)
        paths.append(p)
    close_all(ctx.layers)
    return paths


def render_sheet(ctx, times, out_path, cols=4, thumb_w=360):
    from PIL import ImageFont
    thumbs = []
    for t in times:
        im = frame_at(ctx, t).convert("RGB")
        tw = thumb_w
        th = int(im.height * tw / im.width)
        im = im.resize((tw, th), Image.BILINEAR)
        d = ImageDraw.Draw(im)
        label = f"{t:.2f}s  b{ctx.bm.index(t):.1f}" if ctx.bm.has_music else f"{t:.2f}s"
        d.rectangle((0, 0, 8 * len(label) + 8, 18), fill=(0, 0, 0))
        d.text((4, 3), label, fill=(255, 220, 0), font=ImageFont.load_default())
        thumbs.append(im)
    close_all(ctx.layers)
    rows = math.ceil(len(thumbs) / cols)
    tw, th = thumbs[0].size
    sheet = Image.new("RGB", (cols * (tw + 6), rows * (th + 6)), (30, 30, 30))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * (tw + 6), (i // cols) * (th + 6)))
    sheet.save(out_path)
    return out_path
