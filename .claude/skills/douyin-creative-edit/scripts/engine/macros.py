"""High-level building blocks ("macros") that expand into plain layers.

Every macro receives (item, ctx, off) where off is the absolute start of the parent (0 at top level)
and returns a list of raw layer dicts whose numeric times are parent-local.
"""
import colorsys
import glob
import math
import os
import random

import numpy as np

from . import media
from . import text as textmod
from .util import is_beat_ref, ltime, parse_dur

MACRO_KEYS = {"macro", "shots", "clips", "cut", "pattern", "transition", "td", "first_transition", "repeat", "count",
              "pick", "order", "seed", "backgrounds", "foreground", "between", "bg_effects", "style", "items",
              "lines", "accent", "ghost", "fonts", "cycle", "layout", "size", "border", "border_color", "rotate",
              "pop", "at", "panels", "stagger", "gap", "gap_color", "frame_color", "inset", "window", "shape",
              "intro", "intro_dur", "decor", "title", "sub", "note", "bg", "palette", "line", "line_color",
              "step", "subtitle", "x", "y", "font", "color", "end", "start", "type_dur", "cols", "rows",
              "shadow", "aspect", "speed_jitter", "keep_audio", "radius", "anim_in", "hold", "group_anim"}
SHARED_LAYER_KEYS = {"fit", "box", "focus", "effects", "anim", "mask", "blend", "crop", "oversample", "opacity",
                     "scale", "rotation", "anchor", "speed", "shutter", "loop", "audio", "volume"}
OVERLAP_TR = ("fade", "dissolve", "zoom", "zoom_out", "iris", "strip", "strip_h", "blinds", "grid", "brush",
              "brush_blob", "blur", "spin", "pop")


def expand_all(items, ctx, offset=0.0):
    out = []
    for it in items or []:
        if isinstance(it, dict) and "macro" in it:
            fn = MACROS.get(it["macro"])
            if fn is None:
                raise ValueError(f"unknown macro {it['macro']!r}; known: {sorted(MACROS)}")
            out += expand_all(fn(it, ctx, offset), ctx, offset)
        else:
            out.append(it)
    return out


# ---------------------------------------------------------------- helpers


def _T(v, ctx, off, default=0.0):
    return ltime(v, ctx.bm, off, default)


def _D(v, ctx, off, at_local):
    return parse_dur(v, ctx.bm, at_local + off)


def _is_portrait(ctx):
    return ctx.H > ctx.W


def _expand_paths(paths, ctx):
    out = []
    for p in paths if isinstance(paths, list) else [paths]:
        if isinstance(p, dict):
            out.append(p)
            continue
        pp = os.path.expanduser(str(p))
        if not os.path.isabs(pp):
            pp = os.path.join(ctx.base, pp)
        hits = sorted(glob.glob(pp))
        if any(ch in str(p) for ch in "*?[") and not hits:
            ctx.warnings.append(f"glob matched nothing: {p}")
        out += hits if hits else [pp]
    return out


def _as_shot(x):
    """'path' | {'video':..} | {'image':..} -> layer-ish dict"""
    if isinstance(x, dict):
        return dict(x)
    return {"image": x} if media.is_image(x) else {"video": x}


def _shared(item):
    return {k: v for k, v in item.items() if k in SHARED_LAYER_KEYS}


def _text_w(ctx, spec):
    img = textmod.render_text(ctx.fb, spec, ctx.S)
    return img.width / ctx.W, img.height / ctx.H


# ---------------------------------------------------------------- sequence


def m_sequence(item, ctx, off):
    """Shots back-to-back with beat-aware lengths and transitions."""
    t = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off) if item.get("end") is not None else None
    shots = [_as_shot(s) for s in item.get("shots", [])]
    if not shots:
        return []
    default_cut = item.get("cut", "1b" if ctx.bm.has_music else 1.5)
    pattern = item.get("pattern")
    tr_default = item.get("transition", "cut")
    td_default = item.get("td", 0.3)
    shared = _shared(item)
    layers, overlays = [], []
    prev = None
    i = 0
    guard = 0
    while guard < 4000:
        guard += 1
        if i >= len(shots):
            if item.get("repeat") and end is not None:
                i = 0
            else:
                break
        shot = shots[i]
        if "dur" in shot:
            d = _D(shot["dur"], ctx, off, t)
        elif pattern:
            pv = pattern[(guard - 1) % len(pattern)]
            d = _D(f"{pv}b" if isinstance(pv, (int, float)) else pv, ctx, off, t)
        else:
            d = _D(default_cut, ctx, off, t)
        t_end = t + d
        if end is not None:
            t_end = min(t_end, end)
        if t_end - t < 1e-3:
            break
        L = dict(shared)
        L.update({k: v for k, v in shot.items() if k not in ("dur", "transition", "td", "point")})
        L["start"], L["end"] = t, t_end
        tr = shot.get("transition", item.get("first_transition", "cut") if prev is None else tr_default)
        td = _D(shot.get("td", td_default), ctx, off, t)
        if prev is not None and tr not in ("cut", None):
            if tr in OVERLAP_TR or tr.startswith(("wipe_", "slide_")):
                L["start"] = t - td
                L["enter"] = {"type": tr, "dur": td}
            elif tr.startswith(("whip_", "push_")):
                direction = tr.split("_", 1)[1]
                L["start"] = t - td
                L["enter"] = {"type": f"{'whip' if tr.startswith('whip') else 'slide'}_{direction}", "dur": td}
                prev["exit"] = {"type": f"{'whip' if tr.startswith('whip') else 'slide'}_{direction}", "dur": td}
                prev["end"] = t
            elif tr in ("glitch", "invert"):
                L["enter"] = {"type": tr, "dur": td}
            elif tr == "flash":
                overlays.append({"color": item.get("flash_color", "#ffffff"), "start": t, "end": t + td,
                                 "anim": [{"name": "fade_out", "dur": td}], "id": f"flash{len(overlays)}"})
            elif tr in ("dip_black", "dip_white"):
                col = "#000000" if tr == "dip_black" else "#ffffff"
                overlays.append({"color": col, "start": t - td / 2, "end": t + td / 2,
                                 "opacity": [[0, 0], [td / 2, 1, "in"], [td, 0, "out"]]})
            elif tr == "zoom_into":
                pt = shot.get("point") or prev.get("point") or [0.5, 0.5]
                prev["exit"] = {"type": "zoom_into", "dur": td, "x": pt[0], "y": pt[1]}
            elif tr == "flash_in":
                L["anim"] = (L.get("anim") or []) if isinstance(L.get("anim"), list) else [L["anim"]] if L.get(
                    "anim") else []
                L["anim"] = L["anim"] + [{"name": "flash_in", "dur": td}]
            else:
                raise ValueError(f"unknown sequence transition {tr!r}")
        layers.append(L)
        prev = L
        t = t_end
        i += 1
        if end is not None and t >= end - 1e-6:
            break
        if item.get("count") and len(layers) >= int(item["count"]):
            break
    return layers + overlays


# ---------------------------------------------------------------- montage


def _clip_feature(path, mode):
    try:
        th = media.thumb(path).astype(np.float32) / 255
    except Exception:
        return 0.0
    if mode == "brightness":
        return float(th.mean())
    r, g, b = th[..., 0].mean(), th[..., 1].mean(), th[..., 2].mean()
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h if s > 0.08 else 1.5 + v  # greys go last, ordered by value


def m_montage(item, ctx, off):
    """Many clips/photos cut on the grid. Picks in-points automatically."""
    clips = _expand_paths(item.get("clips", []), ctx)
    if not clips:
        raise ValueError("montage needs clips")
    rng = random.Random(item.get("seed", 1))
    order = item.get("order", "given")
    if order == "shuffle":
        rng.shuffle(clips)
    elif order in ("hue", "brightness"):
        clips = sorted(clips, key=lambda c: _clip_feature(c if isinstance(c, str) else (c.get("video") or c.get(
            "image")), order))
    # dry run to get slot lengths
    t = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off) if item.get("end") is not None else None
    count = int(item.get("count", 0)) or None
    pattern = item.get("pattern")
    cut = item.get("cut", "1b" if ctx.bm.has_music else 0.8)
    slots = []
    k = 0
    while (end is None or t < end - 1e-3) and (count is None or len(slots) < count) and k < 4000:
        if pattern:
            pv = pattern[k % len(pattern)]
            d = _D(f"{pv}b" if isinstance(pv, (int, float)) else pv, ctx, off, t)
        else:
            d = _D(cut, ctx, off, t)
        if end is not None:
            d = min(d, end - t)
        slots.append(d)
        t += d
        k += 1
        if end is None and count is None and k >= len(clips):
            break
    pick = item.get("pick", "random")
    cursor = {}
    shots = []
    for i, d in enumerate(slots):
        c = clips[i % len(clips)]
        shot = _as_shot(c)
        if "video" in shot and "in" not in shot:
            p = shot["video"]
            info = media.probe(p if os.path.isabs(p) else os.path.join(ctx.base, p))
            dur = info.get("duration") or 0
            need = d * float(shot.get("speed", item.get("speed", 1.0)))
            room = max(0.0, dur - need - 0.05)
            if pick == "middle":
                shot["in"] = round(room / 2, 3)
            elif pick == "start":
                shot["in"] = 0.0
            elif pick == "sequential":
                cur = cursor.get(p, 0.0)
                if cur > room:
                    cur = 0.0
                shot["in"] = round(cur, 3)
                cursor[p] = cur + need
            else:
                shot["in"] = round(rng.uniform(min(0.15 * dur, room), room) if room > 0 else 0.0, 3)
        shot["dur"] = d
        shots.append(shot)
    seq = {k: v for k, v in item.items() if k not in ("clips", "macro", "count", "end", "pattern", "cut")}
    seq["shots"] = shots
    seq["start"] = _T(item.get("start", 0), ctx, off)
    return m_sequence(seq, ctx, off)


# ---------------------------------------------------------------- bg_swap


def m_bg_swap(item, ctx, off):
    """Fixed subject (cut-out PNG / alpha video / text) while the world behind it changes on the beat."""
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    mont = {k: v for k, v in item.items() if k not in ("backgrounds", "foreground", "between", "macro",
                                                         "bg_effects")}
    mont["clips"] = item.get("backgrounds") or item.get("clips")
    mont["start"], mont["end"] = start, end
    if item.get("bg_effects"):
        mont["effects"] = item["bg_effects"]
    out = m_montage(mont, ctx, off)
    for grp in ("between", "foreground"):
        g = item.get(grp) or []
        if isinstance(g, dict):
            g = [g]
        for L in g:
            L = dict(L)
            if "macro" not in L:
                L.setdefault("start", start)
                L.setdefault("end", end)
            out.append(L)
    return out


# ---------------------------------------------------------------- lyrics / kinetic type


def _items(item, ctx, off):
    raw = item.get("items") or item.get("lines") or []
    end_all = _T(item["end"], ctx, off) if item.get("end") is not None else None
    res = []
    for i, it in enumerate(raw):
        if isinstance(it, str):
            it = {"text": it}
        it = dict(it)
        res.append(it)
    # fill timings: at / to
    t = _T(item.get("start", 0), ctx, off)
    every = item.get("cut", "1b" if ctx.bm.has_music else 0.8)
    for i, it in enumerate(res):
        if "at" in it:
            it["_at"] = _T(it["at"], ctx, off)
        else:
            it["_at"] = t
        t = it["_at"] + _D(it.get("dur", every), ctx, off, it["_at"])
        it["_auto_to"] = t
    for i, it in enumerate(res):
        if "to" in it:
            it["_to"] = _T(it["to"], ctx, off)
        elif "dur" in it:
            it["_to"] = it["_at"] + _D(it["dur"], ctx, off, it["_at"])
        elif i + 1 < len(res):
            it["_to"] = res[i + 1]["_at"]
        else:
            it["_to"] = end_all if end_all is not None else it["_auto_to"]
    return res


def m_lyrics(item, ctx, off):
    style = item.get("style", "word_pop")
    portrait = _is_portrait(ctx)
    items = _items(item, ctx, off)
    accent = item.get("accent", "#e3262e")
    color = item.get("color", "#ffffff")
    x0, y0 = item.get("x", 0.5), item.get("y", 0.5)
    out = []
    if style == "poster_stack":
        # v1 "Take me to the moon": giant ghost word behind, solid accent word in front, small side words.
        for it in items:
            word = it["text"]
            base = {"start": it["_at"], "end": it["_to"]}
            if item.get("ghost", True):
                g = {"text": it.get("ghost", word).upper(), "font": item.get("ghost_font", "condensed"),
                     "size": item.get("ghost_size", 0.95 if not portrait else 0.6), "color": "#ffffff",
                     "x": x0, "y": y0, "opacity": item.get("ghost_opacity", 0.38),
                     "scale_x": item.get("ghost_scale_x", 0.42)}
                g.update(base)
                out.append(g)
            main = {"text": word.upper() if item.get("upper", True) else word, "font": item.get("font", "serif_bold"),
                    "size": item.get("size", 0.26 if not portrait else 0.2), "color": accent,
                    "scale_x": item.get("scale_x", 0.5), "x": x0, "y": y0}
            if it.get("fonts") or item.get("fonts"):
                main["fonts"] = it.get("fonts") or item.get("fonts")
                main["cycle"] = it.get("cycle") or item.get("cycle", "0.5b")
            if item.get("anim"):
                main["anim"] = item["anim"]
            main.update(base)
            out.append(main)
            mw, _ = _text_w(ctx, {k: main[k] for k in ("text", "font", "size", "scale_x")})
            side = {"font": item.get("side_font", "serif"), "size": item.get("side_size", 0.055),
                    "color": item.get("side_color", color)}
            if it.get("left"):
                s = dict(side, text=it["left"], align="right")
                sw, _ = _text_w(ctx, s)
                s.update({"x": x0 - mw / 2 - sw / 2 - 0.01, "y": y0}, **base)
                out.append(s)
            if it.get("right"):
                s = dict(side, text=it["right"], align="left")
                sw, _ = _text_w(ctx, s)
                s.update({"x": x0 + mw / 2 + sw / 2 + 0.01, "y": y0}, **base)
                out.append(s)
        return out
    if style == "font_cycle":
        # v1 "LOVE" burst: same word, font swaps every half/quarter beat, ghost stays
        for it in items:
            base = {"start": it["_at"], "end": it["_to"]}
            if item.get("ghost", True):
                out.append(dict(base, text=it["text"].upper(), font="condensed", size=0.95 if not portrait else 0.6,
                                color="#ffffff", opacity=0.35, scale_x=0.42, x=x0, y=y0))
            fonts = item.get("fonts") or [{"font": "serif_bold", "scale_x": 0.6}, {"font": "script", "size": 0.16},
                                          {"font": "condensed"}, {"font": "serif", "skew": 0.25},
                                          {"font": "sans_bold", "scale_x": 0.5}, {"font": "serif_bold", "outline": True}]
            out.append(dict(base, text=it["text"].upper() if item.get("upper", True) else it["text"],
                            font="serif_bold", size=item.get("size", 0.17 if not portrait else 0.14),
                            color=accent, x=x0, y=y0, fonts=fonts, cycle=item.get("cycle", "0.5b")))
        return out
    if style == "staircase":
        # v2 angel poster: words step diagonally, thin elegant face, gold, a red line threads through.
        step = item.get("step", [0.12, 0.16] if not portrait else [0.1, 0.1])
        sx, sy = item.get("x", 0.22), item.get("y", 0.2)
        end_all = max(it["_to"] for it in items)
        pts = []
        for i, it in enumerate(items):
            x, y = sx + step[0] * i, sy + step[1] * i
            pts.append([x - 0.05, y + 0.02])
            L = {"text": it["text"], "font": item.get("font", "light"), "size": item.get("size", 0.085),
                 "color": item.get("color", "#d8b46a"), "x": x, "y": y, "start": it["_at"],
                 "end": end_all if item.get("hold", True) else it["_to"],
                 "anim": item.get("anim", [{"name": "blur_in", "dur": 0.35}])}
            out.append(L)
            if i == 0 and item.get("subtitle"):
                out.append({"text": item["subtitle"], "font": item.get("subtitle_font", "cjk_sans"), "size": 0.022,
                            "tracking": 0.9, "color": item.get("color", "#d8b46a"), "x": x, "y": y + 0.075,
                            "start": it["_at"], "end": end_all, "anim": [{"name": "fade_in", "dur": 0.5}]})
        if item.get("line", True) and len(pts) >= 2:
            pts = [[pts[0][0] - 0.12, pts[0][1] - 0.1]] + pts + [[pts[-1][0] + 0.25, pts[-1][1] + 0.12]]
            t0 = items[0]["_at"]
            out.insert(0, {"shape": "path", "points": pts, "color": item.get("line_color", "#a3252a"),
                           "width": 0.004, "start": t0, "end": end_all,
                           "draw": {"from": 0, "to": 1, "dur": (end_all - t0) * 0.8, "ease": "inout"}})
        return out
    if style in ("word_pop", "swap", "typewriter", "subtitle", "stack", "vertical"):
        defaults = {
            "word_pop": dict(font="sans_bold", size=0.16 if not portrait else 0.12, anim=["pop_in"]),
            "swap": dict(font="mono", size=0.12),
            "typewriter": dict(font="mono", size=0.05, anim=[{"name": "typewriter", "dur": 0.6}]),
            "subtitle": dict(font="sans", size=0.045 if portrait else 0.04, anim=[{"name": "rise", "dur": 0.25}],
                             shadow={"dy": 0.05, "blur": 0.15}),
            "stack": dict(font="serif", size=0.035, anim=[{"name": "fade_in", "dur": 0.2}]),
            "vertical": dict(font="cjk_serif", size=0.06, vertical=True,
                             anim=[{"name": "typewriter", "dur": "2b"}]),
        }[style]
        if style == "subtitle" and "y" not in item:
            y0 = 0.74 if portrait else 0.86
        if style == "vertical" and "x" not in item:
            x0 = 0.82
        for i, it in enumerate(items):
            L = dict(defaults)
            for k in ("font", "size", "color", "anim", "stroke", "stroke_color", "shadow", "glow", "tracking",
                      "scale_x", "skew", "case", "box", "outline", "line_spacing"):
                if k in item:
                    L[k] = item[k]
            L.setdefault("color", color)
            L.update({"text": it["text"], "x": it.get("x", x0), "y": it.get("y", y0), "start": it["_at"],
                      "end": it["_to"]})
            if style == "stack":
                L["y"] = it.get("y", y0 + i * float(item.get("line_gap", 0.045)))
                L["end"] = max(x["_to"] for x in items)
            if style == "vertical":
                L["x"] = it.get("x", x0 - i * float(item.get("col_gap", 0.09)))
                L["end"] = max(x["_to"] for x in items)
            if "type_dur" in item and style == "typewriter":
                L["anim"] = [{"name": "typewriter", "dur": item["type_dur"]}]
            out.append(L)
        return out
    if style == "letters":
        # v4 'SLOW SHUTTER' title: letters land one by one in random order
        it = items[0]
        font = item.get("font", "sans_bold")
        size = item.get("size", 0.12)
        txt = it["text"]
        fnt, tw = ctx.fb.font(font, int(size * ctx.S), txt)
        widths = [fnt.getlength(ch) * float(tw.get("scale_x", 1.0)) for ch in txt]
        tracking = float(item.get("tracking", 0.05)) * size * ctx.S
        total = sum(widths) + tracking * (len(txt) - 1)
        x = x0 * ctx.W - total / 2
        order = list(range(len(txt)))
        random.Random(item.get("seed", 5)).shuffle(order)
        span = it["_to"] - it["_at"]
        reveal = min(span * 0.7, _D(item.get("reveal", "2b"), ctx, off, it["_at"]))
        for i, ch in enumerate(txt):
            cx = x + widths[i] / 2
            x += widths[i] + tracking
            if ch.isspace():
                continue
            k = order.index(i)
            st = it["_at"] + reveal * k / max(1, len(txt) - 1)
            out.append({"text": ch, "font": font, "size": size, "color": item.get("color", color),
                        "x": cx / ctx.W, "y": y0, "start": st, "end": it["_to"],
                        "anim": item.get("anim", [{"name": "flash_in", "dur": 0.15}, "pop_in"])})
        return out
    raise ValueError(f"unknown lyrics style {style!r}")


# ---------------------------------------------------------------- collage


def m_collage(item, ctx, off):
    """Photo cards popping in on the beat (scatter / grid / row / column / stack)."""
    paths = _expand_paths(item.get("items", []), ctx)
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    n = len(paths)
    at = item.get("at", "0.5b" if ctx.bm.has_music else 0.3)
    if isinstance(at, list):
        times = [_T(a, ctx, off) for a in at]
    else:
        times, t = [], start
        for _ in range(n):
            times.append(t)
            t += _D(at, ctx, off, t)
    portrait = _is_portrait(ctx)
    layout = item.get("layout", "scatter")
    size = float(item.get("size", 0.55 if portrait else 0.3))
    rng = random.Random(item.get("seed", 4))
    rot = float(item.get("rotate", 7))
    out = []
    if item.get("bg"):
        out += [dict(_as_shot(item["bg"]) if not isinstance(item["bg"], dict) else item["bg"], start=start, end=end)]
    cols = int(item.get("cols", 2 if portrait else 3))
    rows = int(item.get("rows", math.ceil(n / cols)))
    for i, p in enumerate(paths):
        shot = _as_shot(p)
        src = shot.get("video") or shot.get("image")
        asp = item.get("aspect")
        if asp is None and src:
            try:
                info = media.probe(src if os.path.isabs(src) else os.path.join(ctx.base, src))
                asp = info["width"] / max(1, info["height"])
            except Exception:
                asp = 4 / 3
        asp = asp or 4 / 3
        w = size
        h = w * ctx.W / ctx.H / asp
        if layout == "grid":
            cw, ch = 1 / cols, 1 / rows
            c, r = i % cols, i // cols
            w, h = cw * 0.92, ch * 0.92
            x, y = c * cw + cw * 0.04, r * ch + ch * 0.04
            angle = 0
        elif layout == "row":
            w = 0.92 / n
            h = w * ctx.W / ctx.H / asp
            x, y = 0.04 + i * w, 0.5 - h / 2
            angle = 0
        elif layout == "column":
            h = 0.92 / n
            w = h * ctx.H / ctx.W * asp
            x, y = 0.5 - w / 2, 0.04 + i * h
            angle = 0
        elif layout == "stack":
            x, y = 0.5 - w / 2 + rng.uniform(-0.04, 0.04), 0.5 - h / 2 + rng.uniform(-0.04, 0.04)
            angle = rng.uniform(-rot, rot)
        else:  # scatter on a jittered grid so cards spread out
            gc = max(1, round(math.sqrt(n * (ctx.W / ctx.H))))
            gr = max(1, math.ceil(n / gc))
            c, r = i % gc, i // gc
            cx = (c + 0.5) / gc + rng.uniform(-0.08, 0.08)
            cy = (r + 0.5) / gr + rng.uniform(-0.06, 0.06)
            x, y = min(max(0.0, cx - w / 2), 1 - w), min(max(0.0, cy - h / 2), 1 - h)
            angle = rng.uniform(-rot, rot)
        L = dict(shot)
        L.update({"box": [x, y, w, h], "fit": "cover", "rotation": angle, "start": times[i], "end": end,
                  "anim": item.get("pop", ["pop_in"])})
        eff = list(item.get("effects", []))
        b = item.get("border", 0.012)
        if b:
            eff.append({"type": "border", "width": b, "color": item.get("border_color", "#ffffff"),
                        "bottom": item.get("border_bottom", b)})
        if item.get("shadow", True):
            eff.append({"type": "shadow", "dy": 0.01, "blur": 0.015})
        L["effects"] = eff
        out.append(L)
    return out


# ---------------------------------------------------------------- split screen


def m_split(item, ctx, off):
    panels = [_as_shot(p) for p in item.get("panels", [])]
    n = len(panels)
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    layout = item.get("layout", "auto")
    if layout == "auto":
        layout = "rows" if _is_portrait(ctx) else "cols"
    gap = float(item.get("gap", 0.006))
    out = [{"color": item.get("gap_color", "#000000"), "start": start, "end": end}]
    if layout == "grid":
        cols = int(item.get("cols", 2))
        rows = math.ceil(n / cols)
    elif layout == "cols":
        cols, rows = n, 1
    else:
        cols, rows = 1, n
    anim = item.get("anim", "slide")
    stag = item.get("stagger", "0.5b" if ctx.bm.has_music else 0.25)
    t = start
    for i, p in enumerate(panels):
        c, r = i % cols, i // cols
        cw, ch = 1 / cols, 1 / rows
        box = [c * cw + gap / 2, r * ch + gap / 2, cw - gap, ch - gap]
        L = dict(_shared(item))
        L.update(p)
        L.update({"box": box, "start": t, "end": end, "fit": p.get("fit", "cover")})
        if anim == "slide":
            if layout == "cols":
                L["enter"] = {"type": "slide_down" if i % 2 == 0 else "slide_up", "dur": 0.35}
            else:
                L["enter"] = {"type": "slide_right" if i % 2 == 0 else "slide_left", "dur": 0.35}
        elif anim == "stretch":
            L["anim"] = [{"name": "stretch_in", "dur": 0.3}]
        elif anim == "pop":
            L["anim"] = ["pop_in"]
        elif anim == "fade":
            L["enter"] = {"type": "fade", "dur": 0.25}
        L["mask"] = {"type": "rect", "box": box}
        out.append(L)
        t += _D(stag, ctx, off, t)
    return out


# ---------------------------------------------------------------- window / frame-in-frame


def m_window(item, ctx, off):
    """v3 Wes Anderson: picture shrinks into a coloured frame / round porthole, shots swap inside."""
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    dur = end - start
    inset = item.get("inset", 0.09)
    if item.get("window"):
        win = item["window"]
    else:
        mx = inset
        my = inset * ctx.W / ctx.H if not _is_portrait(ctx) else inset * 0.8
        win = [mx, my, 1 - 2 * mx, 1 - 2 * my]
    shape = item.get("shape", "rect")
    if shape == "circle":
        r = min(win[2] * ctx.W, win[3] * ctx.H) / 2 / ctx.S
        cx, cy = win[0] + win[2] / 2, win[1] + win[3] / 2
        mask = {"type": "circle", "x": cx, "y": cy, "r": r}
        bw, bh = 2 * r * ctx.S / ctx.W, 2 * r * ctx.S / ctx.H
        box = [cx - bw / 2, cy - bh / 2, bw, bh]
    else:
        mask = {"type": "rect", "box": win, "radius": item.get("radius", 0.0)}
        box = win
    seq = {k: v for k, v in item.items() if k in SHARED_LAYER_KEYS or k in ("cut", "pattern", "transition", "td",
                                                                            "repeat")}
    seq.update({"macro": "sequence", "shots": item.get("shots", []), "start": 0, "end": dur, "box": box,
                "mask": mask})
    children = []
    fc = item.get("frame_color", "#a9d6c2")
    if isinstance(fc, dict):
        children.append(dict(fc, start=0, end=dur))
    else:
        children.append({"color": fc, "start": 0, "end": dur})
    if item.get("border"):
        b = item["border"]
        if shape == "circle":
            children.append({"shape": "circle", "x": mask["x"], "y": mask["y"], "r": mask["r"] + b.get("width", 0.01),
                             "color": b.get("color", "#ffffff"), "start": 0, "end": dur})
        else:
            w = b.get("width", 0.01)
            children.append({"shape": "rect", "rect": [win[0] - w, win[1] - w * ctx.W / ctx.H, win[2] + 2 * w,
                                                       win[3] + 2 * w * ctx.W / ctx.H],
                             "color": b.get("color", "#ffffff"), "start": 0, "end": dur})
    children.append(seq)
    for d in item.get("decor", []) or []:
        children.append(dict(d))
    G = {"group": children, "start": start, "end": end}
    if item.get("intro", "zoom_out") == "zoom_out" and shape != "circle":
        k = max(1 / win[2], 1 / win[3])
        idur = parse_dur(item.get("intro_dur", 0.5), ctx.bm, start + off)
        G["scale"] = [[0, k], [idur, 1.0, "expo_inout"]]
        G["anchor"] = [win[0] + win[2] / 2, win[1] + win[3] / 2]
        G["x"], G["y"] = win[0] + win[2] / 2, win[1] + win[3] / 2
    for k in ("enter", "exit", "effects"):
        if k in item:
            G[k] = item[k]
    if item.get("group_anim"):
        G["anim"] = item["group_anim"]
    return [G]


# ---------------------------------------------------------------- chapter / title cards


def m_chapter(item, ctx, off):
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    portrait = _is_portrait(ctx)
    style = item.get("style", "wes")
    color = item.get("color", "#222222")
    out = []
    bg = item.get("bg")
    if bg is not None:
        if isinstance(bg, str) and bg.startswith("#"):
            out.append({"color": bg, "start": start, "end": end})
        else:
            b = _as_shot(bg) if not isinstance(bg, dict) else dict(bg)
            b.setdefault("start", start)
            b.setdefault("end", end)
            b.setdefault("anim", ["ken_burns"])
            out.append(b)
    y = item.get("y", 0.2 if not portrait else 0.3)
    x = item.get("x", 0.5)
    title, sub, note = item.get("title", ""), item.get("sub"), item.get("note")
    base = {"start": start, "end": end}
    if style == "wes":
        ts = float(item.get("size", 0.036))
        out.append(dict(base, text=title.upper(), font=item.get("font", "sans"), size=ts,
                        tracking=0.16, color=color, x=x, y=y))
        if sub:
            out.append(dict(base, text=sub.upper(), font="sans", size=ts * 0.4, tracking=0.35, color=color, x=x,
                            y=y + ts * 1.15 * ctx.S / ctx.H))
        if note:
            out.append(dict(base, text=note.upper(), font="sans", size=ts * 0.36, tracking=0.25,
                            color=item.get("note_color", "#c9a227"), x=x, y=y + ts * 3.2 * ctx.S / ctx.H))
    elif style == "bold":
        out.append(dict(base, text=title.upper(), font=item.get("font", "condensed"), size=item.get("size", 0.22),
                        color=item.get("color", "#e3262e"), x=x, y=item.get("y", 0.5), anim=["punch_in"]))
        if sub:
            out.append(dict(base, text=sub, font="serif", size=0.05, color="#ffffff", x=x,
                            y=item.get("y", 0.5) + 0.12 * ctx.S / ctx.H))
    elif style == "script":
        out.append(dict(base, text=title, font=item.get("font", "script"), size=item.get("size", 0.1),
                        color=item.get("color", "#2b2b2b"), x=x, y=y, anim=[{"name": "blur_in", "dur": 0.5}]))
        if sub:
            out.append(dict(base, text=sub, font="script", size=0.045, color=item.get("color", "#2b2b2b"), x=x + 0.03,
                            y=y + 0.07 * ctx.S / ctx.H * 1.6, anim=[{"name": "fade_in", "dur": 0.6}]))
    elif style == "brush":
        out.append(dict(base, text=title, font=item.get("font", "cjk_brush"), size=item.get("size", 0.09),
                        color=item.get("color", "#ffffff"), x=x, y=y, vertical=item.get("vertical", False),
                        shadow={"dy": 0.03, "blur": 0.08}, anim=[{"name": "blur_in", "dur": 0.4}]))
        if sub:
            out.append(dict(base, text=sub, font="cjk_brush", size=0.05, color=item.get("color", "#ffffff"),
                            x=x, y=y + 0.1 * ctx.S / ctx.H * 1.6))
    elif style == "minimal":
        out.append(dict(base, text=title, font=item.get("font", "thin"), size=item.get("size", 0.05), tracking=0.4,
                        color=item.get("color", "#ffffff"), x=x, y=item.get("y", 0.5),
                        anim=[{"name": "fade_in", "dur": 0.6}]))
        if sub:
            out.append(dict(base, text=sub, font="thin", size=0.016, tracking=0.6, color=item.get("color", "#ffffff"),
                            x=x, y=item.get("y", 0.5) + 0.05, opacity=0.7, anim=[{"name": "fade_in", "dur": 0.9}]))
    elif style == "bilingual":
        # v1 '失LOST了': a big grey Latin word sits behind a CJK phrase, both semi-transparent
        out.append(dict(base, text=item.get("latin", "LOST"), font="condensed", size=item.get("size", 0.3),
                        scale_x=0.55, color="#9a9a9a", opacity=0.55, x=x, y=item.get("y", 0.5)))
        out.append(dict(base, text=title, font="cjk_bold", size=item.get("size", 0.3) * 0.55, tracking=0.6,
                        color="#bdbdbd", opacity=0.65, x=x, y=item.get("y", 0.5)))
    else:
        raise ValueError(f"unknown chapter style {style!r}")
    return out


# ---------------------------------------------------------------- bauhaus colour blocks


def m_blocks(item, ctx, off):
    """v2: flat colour blocks sliding in on beats behind type (Bauhaus / Swiss poster motion)."""
    start = _T(item.get("start", 0), ctx, off)
    end = _T(item["end"], ctx, off)
    pal = item.get("palette", ["#c9a46a", "#a3252a", "#22436e"])
    n = int(item.get("count", 3))
    rng = random.Random(item.get("seed", 2))
    at = item.get("at", "1b" if ctx.bm.has_music else 0.5)
    out, t = [], start
    style = item.get("style", "bauhaus")
    for i in range(n):
        if style == "stripes":
            h = 0.06 + rng.random() * 0.08
            rect = [0, 0.15 + i * 0.7 / n, 1, h]
        elif style == "mondrian":
            rect = [rng.choice([0, 0.5]) + rng.random() * 0.1, rng.random() * 0.6, 0.3 + rng.random() * 0.2,
                    0.2 + rng.random() * 0.25]
        else:
            w, h = 0.3 + rng.random() * 0.35, 0.1 + rng.random() * 0.2
            rect = [rng.choice([0.0, 1 - w, 0.25 + rng.random() * 0.3]), 0.35 + rng.random() * 0.45, w, h]
        direction = "left" if rect[0] + rect[2] / 2 > 0.5 else "right"
        out.append({"shape": "rect", "rect": rect, "color": pal[i % len(pal)], "start": t, "end": end,
                    "opacity": item.get("opacity", 1.0),
                    "anim": [{"name": "slide_in", "dir": direction, "dur": item.get("slide_dur", 0.45),
                              "amount": 0.8}]})
        t += _D(at, ctx, off, t)
    return out


MACROS = {
    "sequence": m_sequence, "montage": m_montage, "bg_swap": m_bg_swap, "lyrics": m_lyrics, "type": m_lyrics,
    "collage": m_collage, "split": m_split, "window": m_window, "chapter": m_chapter, "title": m_chapter,
    "blocks": m_blocks,
}
