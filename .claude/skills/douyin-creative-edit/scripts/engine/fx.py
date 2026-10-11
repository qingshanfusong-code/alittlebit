"""Pixel effects, colour grades, finishing passes and beat-synced global effects.

Every effect: fn(img RGBA, params(dict, already time-evaluated), ctx) -> RGBA
ctx: {"W","H","S","t","lt","state"(dict, per layer+effect), "fb"}
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .util import parse_color

# ---------------------------------------------------------------- helpers


def _rgb_a(img):
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img.convert("RGB"), img.getchannel("A")


def _merge(rgb, a):
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def _px(v, ctx, default=0.0):
    return float(v if v is not None else default) * ctx["S"]


# ---------------------------------------------------------------- grading

GRADES = {
    "none": {},
    "film": {"contrast": 0.08, "saturation": 0.92, "temperature": 0.08, "lift": 0.04,
             "shadows": ["#1f5f6b", 0.08], "highlights": ["#ffd09a", 0.06]},
    "teal_orange": {"contrast": 0.12, "saturation": 1.1, "shadows": ["#16707c", 0.2],
                    "highlights": ["#ffae66", 0.16]},
    "wes_pastel": {"contrast": -0.06, "saturation": 1.18, "temperature": 0.12, "lift": 0.07,
                   "highlights": ["#ffd9a8", 0.1], "shadows": ["#7d5c86", 0.06]},
    "bw_contrast": {"saturation": 0.0, "contrast": 0.38, "gamma": 0.95},
    "bw_soft": {"saturation": 0.0, "contrast": 0.04, "lift": 0.06},
    "night_neon": {"contrast": 0.16, "saturation": 1.3, "temperature": -0.14, "shadows": ["#1b2a70", 0.25],
                   "highlights": ["#ff4fa8", 0.1]},
    "moody_blue": {"contrast": 0.1, "saturation": 0.72, "temperature": -0.22, "shadows": ["#0c2a4c", 0.22],
                   "lift": 0.02},
    "warm_gold": {"temperature": 0.25, "saturation": 1.06, "contrast": 0.06, "highlights": ["#ffc870", 0.16]},
    "vivid": {"saturation": 1.38, "contrast": 0.1},
    "faded": {"contrast": -0.12, "lift": 0.1, "saturation": 0.82},
    "sunset": {"temperature": 0.3, "saturation": 1.2, "highlights": ["#ff8a4c", 0.14], "shadows": ["#5a2a7a", 0.1]},
    "cold_clean": {"temperature": -0.12, "saturation": 0.9, "contrast": 0.05, "lift": 0.03,
                   "highlights": ["#e8f4ff", 0.08]},
}


def grade(img, p, ctx=None):
    if isinstance(p, str):
        p = {"preset": p}
    q = dict(GRADES.get(p.get("preset", "none"), {}))
    q.update({k: v for k, v in p.items() if k not in ("preset", "type")})
    amt = float(q.pop("mix", 1.0))
    rgb, a = _rgb_a(img)
    src = rgb
    exp = 2 ** float(q.get("exposure", 0.0))
    con = 1 + float(q.get("contrast", 0.0))
    lift = float(q.get("lift", 0.0))
    gam = float(q.get("gamma", 1.0))
    temp = float(q.get("temperature", 0.0))
    tint = float(q.get("tint", 0.0))
    gains = [exp * (1 + 0.12 * temp), exp * (1 - 0.08 * tint), exp * (1 - 0.12 * temp)]
    luts = []
    x = np.arange(256) / 255.0
    for g in gains:
        v = x * g
        v = (v - 0.5) * con + 0.5
        v = v * (1 - lift) + lift
        v = np.clip(v, 0, 1) ** (1 / gam)
        luts.append(np.clip(v * 255, 0, 255).astype(np.uint8).tolist())
    rgb = rgb.point(luts[0] + luts[1] + luts[2])
    sat = float(q.get("saturation", 1.0))
    if abs(sat - 1) > 1e-3:
        rgb = ImageEnhance.Color(rgb).enhance(sat)
    sh, hl = q.get("shadows"), q.get("highlights")
    if sh or hl:
        arr = np.asarray(rgb).astype(np.int16)
        L = np.asarray(rgb.convert("L")).astype(np.float32) / 255.0
        if sh:
            c = np.array(parse_color(sh[0])[:3], np.float32)
            w = ((1 - L) ** 2 * float(sh[1]))[..., None]
            arr = arr + (w * (c - 128)).astype(np.int16)
        if hl:
            c = np.array(parse_color(hl[0])[:3], np.float32)
            w = (L ** 2 * float(hl[1]))[..., None]
            arr = arr + (w * (c - 128)).astype(np.int16)
        rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    if amt < 1:
        rgb = Image.blend(src, rgb, amt)
    return _merge(rgb, a)


def adjust(img, p, ctx=None):
    rgb, a = _rgb_a(img)
    if "brightness" in p:
        rgb = ImageEnhance.Brightness(rgb).enhance(float(p["brightness"]))
    if "contrast" in p:
        rgb = ImageEnhance.Contrast(rgb).enhance(float(p["contrast"]))
    if "saturation" in p:
        rgb = ImageEnhance.Color(rgb).enhance(float(p["saturation"]))
    return _merge(rgb, a)


# ---------------------------------------------------------------- per-layer effects


def blur(img, p, ctx):
    r = _px(p.get("radius", 0.01), ctx)
    return img.filter(ImageFilter.GaussianBlur(r)) if r >= 0.5 else img


def motion_blur(img, p, ctx):
    length = _px(p.get("length", 0.05), ctx)
    if length < 1:
        return img
    ang = math.radians(float(p.get("angle", 0)))
    n = int(min(12, max(3, length / 6)))
    acc = None
    for i in range(n):
        f = (i / (n - 1) - 0.5) * length
        sh = ImageChops.offset(img, int(round(math.cos(ang) * f)), int(round(math.sin(ang) * f)))
        arr = np.asarray(sh, np.float32)
        acc = arr if acc is None else acc + arr
    return Image.fromarray((acc / n).astype(np.uint8), "RGBA")


def zoom_blur(img, p, ctx):
    amt = float(p.get("amount", 0.15))
    if amt <= 0.005:
        return img
    n = 6
    W, H = img.size
    cx, cy = float(p.get("x", 0.5)) * W, float(p.get("y", 0.5)) * H
    acc = np.asarray(img, np.float32).copy()
    for i in range(1, n):
        s = 1 + amt * i / (n - 1)
        w, h = int(W * s), int(H * s)
        big = img.resize((w, h), Image.BILINEAR)
        x0, y0 = int(cx * s - cx), int(cy * s - cy)
        acc += np.asarray(big.crop((x0, y0, x0 + W, y0 + H)), np.float32)
    return Image.fromarray((acc / n).astype(np.uint8), "RGBA")


def rgb_split(img, p, ctx):
    amt = _px(p.get("amount", 0.006), ctx)
    if amt < 0.5:
        return img
    ang = math.radians(float(p.get("angle", 0)))
    dx, dy = int(round(math.cos(ang) * amt)), int(round(math.sin(ang) * amt))
    r, g, b, a = img.split()
    r = ImageChops.offset(r, dx, dy)
    b = ImageChops.offset(b, -dx, -dy)
    ar = ImageChops.offset(a, dx, dy)
    ab = ImageChops.offset(a, -dx, -dy)
    a = ImageChops.lighter(ImageChops.lighter(a, ar), ab)
    return Image.merge("RGBA", (r, g, b, a))


def invert(img, p, ctx):
    rgb, a = _rgb_a(img)
    return _merge(ImageOps.invert(rgb), a)


def bw(img, p, ctx):
    rgb, a = _rgb_a(img)
    g = rgb.convert("L")
    c = float(p.get("contrast", 1.0))
    if c != 1.0:
        g = ImageEnhance.Contrast(g).enhance(c)
    return _merge(g.convert("RGB"), a)


def threshold(img, p, ctx):
    """Graphic two-tone (high-contrast poster / 剪影)."""
    rgb, a = _rgb_a(img)
    lvl = int(float(p.get("level", 0.5)) * 255)
    soft = max(1, int(float(p.get("soft", 0.06)) * 255))
    g = rgb.convert("L").point(lambda v: 0 if v < lvl - soft else 255 if v > lvl + soft else int(
        (v - lvl + soft) * 255 / (2 * soft)))
    dark = Image.new("RGB", img.size, parse_color(p.get("dark", "#000000"))[:3])
    light = Image.new("RGB", img.size, parse_color(p.get("light", "#ffffff"))[:3])
    return _merge(Image.composite(light, dark, g), a)


def silhouette(img, p, ctx):
    """Fill the subject with a flat colour. Uses alpha if the source has it, else a luma key
    (dark subject on bright sky -> mode 'dark'; bright subject on dark -> mode 'light')."""
    col = parse_color(p.get("color", "#ffffff"))
    a = img.getchannel("A")
    if a.getextrema() == (255, 255):
        g = img.convert("L")
        lvl = int(float(p.get("level", 0.45)) * 255)
        if p.get("mode", "dark") == "dark":
            a = g.point(lambda v: 255 if v < lvl - 12 else 0 if v > lvl + 12 else int((lvl + 12 - v) * 255 / 24))
        else:
            a = g.point(lambda v: 255 if v > lvl + 12 else 0 if v < lvl - 12 else int((v - lvl + 12) * 255 / 24))
    out = Image.new("RGBA", img.size, col[:3] + (255,))
    out.putalpha(a)
    return out


def duotone(img, p, ctx):
    rgb, a = _rgb_a(img)
    g = rgb.convert("L")
    d = parse_color(p.get("dark", "#14213d"))
    li = parse_color(p.get("light", "#fca311"))
    return _merge(ImageOps.colorize(g, d[:3], li[:3]), a)


def tint(img, p, ctx):
    rgb, a = _rgb_a(img)
    c = Image.new("RGB", img.size, parse_color(p.get("color", "#ff0000"))[:3])
    return _merge(Image.blend(rgb, c, float(p.get("amount", 0.3))), a)


def posterize(img, p, ctx):
    rgb, a = _rgb_a(img)
    bits = max(1, min(8, int(round(math.log2(max(2, int(p.get("levels", 4))))))))
    return _merge(ImageOps.posterize(rgb, bits), a)


def glow(img, p, ctx):
    rgb, a = _rgb_a(img)
    r = _px(p.get("radius", 0.02), ctx)
    th = int(float(p.get("threshold", 0.6)) * 255)
    bright = rgb.point(lambda v: 0 if v < th else v)
    bl = bright.filter(ImageFilter.GaussianBlur(max(1, r)))
    s = float(p.get("strength", 0.8))
    bl = bl.point(lambda v: min(255, int(v * s)))
    return _merge(ImageChops.screen(rgb, bl), a)


def grain(img, p, ctx):
    amt = float(p.get("amount", 0.06))
    rgb, a = _rgb_a(img)
    W, H = img.size
    seed = int(ctx.get("t", 0) * 1000) % (2 ** 31)
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amt * 255, (H // 2 + 1, W // 2 + 1)).astype(np.float32)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)[:H, :W, None]
    arr = np.asarray(rgb, np.float32) + n
    return _merge(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"), a)


_vig_cache = {}


def vignette(img, p, ctx):
    W, H = img.size
    amt = float(p.get("amount", 0.35))
    key = (W, H, round(amt, 3), round(float(p.get("softness", 0.6)), 3))
    if key not in _vig_cache:
        ys, xs = np.mgrid[0:H:4, 0:W:4].astype(np.float32)
        d = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        soft = float(p.get("softness", 0.6))
        v = 1 - amt * np.clip((d - (1 - soft)) / soft, 0, 1) ** 1.6
        m = Image.fromarray((v * 255).astype(np.uint8), "L").resize((W, H), Image.BILINEAR)
        _vig_cache[key] = Image.merge("RGB", (m, m, m))
    rgb, a = _rgb_a(img)
    return _merge(ImageChops.multiply(rgb, _vig_cache[key]), a)


def pixelate(img, p, ctx):
    s = max(2, int(_px(p.get("size", 0.02), ctx)))
    W, H = img.size
    return img.resize((max(1, W // s), max(1, H // s)), Image.NEAREST).resize((W, H), Image.NEAREST)


def mirror(img, p, ctx):
    W, H = img.size
    out = img.copy()
    if p.get("axis", "x") == "x":
        half = img.crop((0, 0, W // 2, H)) if p.get("keep", "left") == "left" else img.crop((W - W // 2, 0, W, H))
        if p.get("keep", "left") == "left":
            out.paste(ImageOps.mirror(half), (W - W // 2, 0))
        else:
            out.paste(ImageOps.mirror(half), (0, 0))
    else:
        half = img.crop((0, 0, W, H // 2))
        out.paste(ImageOps.flip(half), (0, H - H // 2))
    return out


def flip(img, p, ctx):
    return ImageOps.mirror(img) if p.get("dir", "h") == "h" else ImageOps.flip(img)


def edges(img, p, ctx):
    """Line-art / sketch look."""
    rgb, a = _rgb_a(img)
    e = rgb.convert("L").filter(ImageFilter.FIND_EDGES)
    e = ImageEnhance.Contrast(e).enhance(float(p.get("strength", 3.0)))
    if p.get("invert", True):
        e = ImageOps.invert(e)
    ink = parse_color(p.get("ink", "#111111"))[:3]
    paper = parse_color(p.get("paper", "#f4efe6"))[:3]
    return _merge(ImageOps.colorize(e, ink, paper), a)


def halftone(img, p, ctx):
    W, H = img.size
    cell = max(4, int(_px(p.get("cell", 0.012), ctx)))
    rgb, a = _rgb_a(img)
    small = np.asarray(rgb.convert("L").resize((max(1, W // cell), max(1, H // cell)), Image.BILINEAR),
                       np.float32) / 255
    out = Image.new("RGB", (W, H), parse_color(p.get("paper", "#f2ece0"))[:3])
    d = ImageDraw.Draw(out)
    ink = parse_color(p.get("ink", "#1a1a1a"))[:3]
    for j in range(small.shape[0]):
        for i in range(small.shape[1]):
            r = (1 - small[j, i]) * cell * 0.62
            if r > 0.4:
                cx, cy = i * cell + cell / 2, j * cell + cell / 2
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)
    return _merge(out, a)


def trails(img, p, ctx):
    """Light trails: out = max(current, previous*decay) (like ffmpeg lagfun)."""
    st = ctx["state"]
    decay = float(p.get("decay", 0.9))
    cur = np.asarray(img, np.float32)
    prev = st.get("trails")
    if prev is not None and prev.shape == cur.shape:
        cur = np.maximum(cur, prev * decay)
    st["trails"] = cur
    return Image.fromarray(cur.astype(np.uint8), "RGBA")


def echo(img, p, ctx):
    """Ghosting: exponential average with previous output (dreamy / drunk)."""
    st = ctx["state"]
    k = float(p.get("decay", 0.6))
    cur = np.asarray(img, np.float32)
    prev = st.get("echo")
    if prev is not None and prev.shape == cur.shape:
        cur = cur * (1 - k) + prev * k
    st["echo"] = cur
    return Image.fromarray(cur.astype(np.uint8), "RGBA")


def chroma_key(img, p, ctx):
    arr = np.asarray(img, np.float32)
    c = np.array(parse_color(p.get("color", "#00ff00"))[:3], np.float32)
    dist = np.sqrt(((arr[..., :3] - c) ** 2).sum(-1)) / 441.0
    tol, soft = float(p.get("tolerance", 0.3)), float(p.get("softness", 0.1))
    alpha = np.clip((dist - tol) / max(soft, 1e-3), 0, 1) * arr[..., 3]
    out = arr.copy()
    out[..., 3] = alpha
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def luma_key(img, p, ctx):
    """Make dark (default) or bright areas transparent: drop black-background elements over footage."""
    g = img.convert("L")
    lo, hi = int(float(p.get("low", 0.08)) * 255), int(float(p.get("high", 0.35)) * 255)
    if p.get("invert"):
        m = g.point(lambda v: 255 if v < lo else 0 if v > hi else int((hi - v) * 255 / max(1, hi - lo)))
    else:
        m = g.point(lambda v: 0 if v < lo else 255 if v > hi else int((v - lo) * 255 / max(1, hi - lo)))
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), m))
    return out


def stroke(img, p, ctx):
    """Sticker outline around an alpha cutout (white-border cut-out look)."""
    w = max(1, int(_px(p.get("width", 0.008), ctx)))
    col = parse_color(p.get("color", "#ffffff"))
    pad = w + 2
    W, H = img.size
    big = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    big.paste(img, (pad, pad))
    a = big.getchannel("A")
    k = 2 * w + 1
    grown = a.filter(ImageFilter.MaxFilter(min(k, 31) | 1))
    if k > 31:
        for _ in range(k // 31):
            grown = grown.filter(ImageFilter.MaxFilter(31))
    base = Image.new("RGBA", big.size, col[:3] + (255,))
    base.putalpha(grown.point(lambda v: v * col[3] // 255))
    base.alpha_composite(big)
    return base


def shadow(img, p, ctx):
    from .text import drop_shadow
    return drop_shadow(img, dx=int(_px(p.get("dx", 0.0), ctx)), dy=int(_px(p.get("dy", 0.012), ctx)),
                       blur=max(1, int(_px(p.get("blur", 0.02), ctx))),
                       color=parse_color(p.get("color", "#00000090")))


def border(img, p, ctx):
    """Card / polaroid border. width & bottom are fractions of canvas short side."""
    w = int(_px(p.get("width", 0.012), ctx))
    b = int(_px(p.get("bottom", p.get("width", 0.012)), ctx))
    col = parse_color(p.get("color", "#ffffff"))
    out = Image.new("RGBA", (img.width + 2 * w, img.height + w + b), col)
    out.alpha_composite(img, (w, w))
    return out


def opacity_fx(img, p, ctx):
    o = float(p.get("value", 1.0))
    a = img.getchannel("A").point(lambda v: int(v * o))
    img = img.copy()
    img.putalpha(a)
    return img


EFFECTS = {
    "grade": grade, "adjust": adjust, "blur": blur, "motion_blur": motion_blur, "zoom_blur": zoom_blur,
    "rgb_split": rgb_split, "invert": invert, "bw": bw, "threshold": threshold, "silhouette": silhouette,
    "duotone": duotone, "tint": tint, "posterize": posterize, "glow": glow, "grain": grain, "vignette": vignette,
    "pixelate": pixelate, "mirror": mirror, "flip": flip, "edges": edges, "halftone": halftone, "trails": trails,
    "echo": echo, "chroma_key": chroma_key, "luma_key": luma_key, "stroke": stroke, "shadow": shadow,
    "border": border, "opacity": opacity_fx,
}

# effects that change the image size (must run before placement, never on full-canvas post)
SIZE_CHANGING = {"stroke", "shadow", "border"}


def apply_effects(img, effects, ctx, state_prefix=""):
    for i, e in enumerate(effects or []):
        if isinstance(e, str):
            e = {"type": e}
        fn = EFFECTS.get(e.get("type"))
        if fn is None:
            raise ValueError(f"unknown effect {e.get('type')!r}; known: {sorted(EFFECTS)}")
        sub = dict(ctx)
        sub["state"] = ctx["state"].setdefault(f"{state_prefix}{i}", {})
        img = fn(img, e, sub)
    return img


# ---------------------------------------------------------------- finishing


def letterbox(img, p, ctx):
    W, H = img.size
    ratio = float(p.get("ratio", 2.35))
    col = parse_color(p.get("color", "#000000"))
    out = img.copy()
    d = ImageDraw.Draw(out)
    if W / H < ratio:
        bh = int((H - W / ratio) / 2)
        if bh > 0:
            d.rectangle((0, 0, W, bh), fill=col)
            d.rectangle((0, H - bh, W, H), fill=col)
    else:
        bw_ = int((W - H * ratio) / 2)
        if bw_ > 0:
            d.rectangle((0, 0, bw_, H), fill=col)
            d.rectangle((W - bw_, 0, W, H), fill=col)
    return out


_film_cache = {}


def film_frame(img, p, ctx):
    """35mm film border with sprocket holes ('35mm') or a photo-print white border ('print')."""
    W, H = img.size
    style = p.get("style", "35mm")
    key = (W, H, style, p.get("label", ""))
    if key not in _film_cache:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        S = min(W, H)
        if style == "print":
            m = int(S * 0.035)
            d.rectangle((0, 0, W, m), fill=(245, 243, 238, 255))
            d.rectangle((0, H - m, W, H), fill=(245, 243, 238, 255))
            d.rectangle((0, 0, m, H), fill=(245, 243, 238, 255))
            d.rectangle((W - m, 0, W, H), fill=(245, 243, 238, 255))
            d.rectangle((m - 2, m - 2, W - m + 1, H - m + 1), outline=(20, 20, 20, 255), width=2)
        else:
            horizontal = W >= H
            band = int(S * 0.075)
            hole_w, hole_h = int(band * 0.42), int(band * 0.3)
            gap = int(band * 0.7)
            if horizontal:
                d.rectangle((0, 0, W, band), fill=(12, 12, 12, 255))
                d.rectangle((0, H - band, W, H), fill=(12, 12, 12, 255))
                for x in range(gap // 2, W, gap):
                    for y0 in ((band - hole_h) // 2, H - band + (band - hole_h) // 2):
                        d.rounded_rectangle((x, y0, x + hole_w, y0 + hole_h), radius=3, fill=(235, 230, 220, 255))
            else:
                d.rectangle((0, 0, band, H), fill=(12, 12, 12, 255))
                d.rectangle((W - band, 0, W, H), fill=(12, 12, 12, 255))
                for y in range(gap // 2, H, gap):
                    for x0 in ((band - hole_h) // 2, W - band + (band - hole_h) // 2):
                        d.rounded_rectangle((x0, y, x0 + hole_h, y + hole_w), radius=3, fill=(235, 230, 220, 255))
            if p.get("label"):
                fb = ctx.get("fb")
                if fb:
                    f, _ = fb.font("mono", max(8, int(band * 0.22)))
                    if horizontal:
                        d.text((int(W * 0.06), int(band * 0.04)), str(p["label"]), font=f, fill=(230, 160, 60, 255))
                    else:
                        d.text((int(band * 0.1), int(H * 0.03)), str(p["label"]), font=f, fill=(230, 160, 60, 255))
        _film_cache[key] = ov
    out = img.copy()
    out.alpha_composite(_film_cache[key])
    return out


POST = dict(EFFECTS)
POST.update({"letterbox": letterbox, "film_frame": film_frame})


def apply_post(img, post, ctx):
    for i, e in enumerate(post or []):
        if isinstance(e, str):
            e = {"type": e}
        fn = POST.get(e.get("type"))
        if fn is None:
            raise ValueError(f"unknown post effect {e.get('type')!r}")
        if e.get("type") in SIZE_CHANGING:
            raise ValueError(f"{e['type']} changes image size; use it on a layer, not in post")
        sub = dict(ctx)
        sub["state"] = ctx["state"].setdefault(f"post{i}", {})
        img = fn(img, e, sub)
    return img


# ---------------------------------------------------------------- beat-synced global effects


def beat_fx(img, items, t, ctx, times_cache):
    """items: [{"type": punch|shake|flash|invert|rgb|blur|dark, "at": ..., "amount": .., "decay": ..}]"""
    W, H = img.size
    for i, it in enumerate(items or []):
        times = times_cache[i]
        decay = float(it.get("decay", 0.18))
        # most recent trigger time <= t
        k = np_last_le(times, t)
        if k is None:
            continue
        dt = t - k
        if dt > decay * 3:
            continue
        typ = it.get("type", "punch")
        env = math.exp(-dt / max(decay, 1e-3) * 2.2)
        amt = float(it.get("amount", {"punch": 0.08, "shake": 0.02, "flash": 0.85, "rgb": 0.012, "blur": 0.02,
                                      "dark": 0.6, "invert": 1}.get(typ, 0.1)))
        if typ == "punch":
            s = 1 + amt * env
            w, h = int(W * s), int(H * s)
            img = img.resize((w, h), Image.BICUBIC).crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W,
                                                          (h - H) // 2 + H))
        elif typ == "shake":
            rng = np.random.default_rng(int(t * 997) + i)
            dx, dy = (rng.random(2) - 0.5) * 2 * amt * min(W, H) * env
            s = 1 + 2 * amt
            w, h = int(W * s), int(H * s)
            big = img.resize((w, h), Image.BILINEAR)
            x0, y0 = (w - W) // 2 + int(dx), (h - H) // 2 + int(dy)
            img = big.crop((x0, y0, x0 + W, y0 + H))
        elif typ == "flash":
            col = parse_color(it.get("color", "#ffffff"))
            img = Image.blend(img, Image.new("RGBA", img.size, col), min(1.0, amt * env))
        elif typ == "dark":
            img = Image.blend(img, Image.new("RGBA", img.size, (0, 0, 0, 255)), min(1.0, amt * env))
        elif typ == "invert":
            if dt < float(it.get("hold", 0.07)):
                img = invert(img, {}, ctx)
        elif typ == "rgb":
            img = rgb_split(img, {"amount": amt * env, "angle": it.get("angle", 0)}, ctx)
        elif typ == "blur":
            img = blur(img, {"radius": amt * env}, ctx)
    return img


def np_last_le(times, t):
    lo, hi = 0, len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] <= t + 1e-6:
            lo = mid + 1
        else:
            hi = mid
    return times[lo - 1] if lo > 0 else None
