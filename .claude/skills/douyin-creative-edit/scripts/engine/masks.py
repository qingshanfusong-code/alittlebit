"""Canvas-space masks (PIL 'L'). Coordinates are fractions of the canvas; sizes as noted."""
import collections
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import text as textmod
from .media import load_image

_cache = collections.OrderedDict()


def _cached(key, fn):
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    v = fn()
    _cache[key] = v
    if len(_cache) > 96:
        _cache.popitem(last=False)
    return v


def make_mask(m, W, H, fb=None):
    """m: dict with evaluated (non-keyframe) params. Returns PIL 'L' W x H."""
    t = m.get("type", "rect")
    key = (W, H, repr(sorted((k, round(v, 4) if isinstance(v, float) else repr(v)) for k, v in m.items())))
    return _cached(key, lambda: _make(m, t, W, H, fb))


def _make(m, t, W, H, fb):
    S = min(W, H)
    feather = float(m.get("feather", 0.0)) * S
    if t in ("rect", "box"):
        img = Image.new("L", (W, H), 0)
        cx, cy = m.get("x", 0.5) * W, m.get("y", 0.5) * H
        w, h = m.get("w", 1.0) * W, m.get("h", 1.0) * H
        r = float(m.get("radius", 0.0)) * S
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        d = ImageDraw.Draw(img)
        if r > 0:
            d.rounded_rectangle(box, radius=r, fill=255)
        else:
            d.rectangle(box, fill=255)
    elif t in ("circle", "ellipse", "iris"):
        img = Image.new("L", (W, H), 0)
        cx, cy = m.get("x", 0.5) * W, m.get("y", 0.5) * H
        if t == "iris":
            maxr = math.hypot(max(cx, W - cx), max(cy, H - cy))
            rx = ry = float(m.get("progress", 1.0)) * maxr
        else:
            r = float(m.get("r", 0.3)) * S
            rx, ry = float(m.get("rx", r / S)) * S, float(m.get("ry", r / S)) * S
        ImageDraw.Draw(img).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    elif t == "polygon":
        img = Image.new("L", (W, H), 0)
        pts = [(p[0] * W, p[1] * H) for p in m.get("points", [])]
        if len(pts) >= 3:
            ImageDraw.Draw(img).polygon(pts, fill=255)
    elif t == "strip":
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        if m.get("horizontal"):
            cy, h = m.get("y", 0.5) * H, m.get("w", 0.2) * H
            d.rectangle((0, cy - h / 2, W, cy + h / 2), fill=255)
        else:
            cx, w = m.get("x", 0.5) * W, m.get("w", 0.2) * W
            d.rectangle((cx - w / 2, 0, cx + w / 2, H), fill=255)
    elif t == "wipe":
        img = _wipe(W, H, float(m.get("progress", 1.0)), m.get("dir", "right"), max(feather, 1.0))
        feather = 0
    elif t == "blinds":
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        n = int(m.get("n", 8))
        p = float(m.get("progress", 1.0))
        if m.get("dir", "v") == "v":
            bw = W / n
            for i in range(n):
                d.rectangle((i * bw, 0, i * bw + bw * p, H), fill=255)
        else:
            bh = H / n
            for i in range(n):
                d.rectangle((0, i * bh, W, i * bh + bh * p), fill=255)
    elif t == "grid":
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        cols, rows = int(m.get("cols", 4)), int(m.get("rows", 4))
        order = np.random.RandomState(int(m.get("seed", 3))).permutation(cols * rows)
        k = int(math.ceil(float(m.get("progress", 1.0)) * cols * rows))
        tw, th = W / cols, H / rows
        for idx in order[:k]:
            c, r = idx % cols, idx // cols
            d.rectangle((c * tw, r * th, (c + 1) * tw + 1, (r + 1) * th + 1), fill=255)
    elif t == "brush":
        img = _brush(W, H, float(m.get("progress", 1.0)), int(m.get("seed", 7)), m.get("style", "sweep"),
                     m.get("x", 0.5), m.get("y", 0.5), float(m.get("r", 0.42)), float(m.get("width", 0.16)))
    elif t == "text":
        img = Image.new("L", (W, H), 0)
        spec = {k: v for k, v in m.items() if k not in ("type", "x", "y", "invert", "feather")}
        timg = textmod.render_text(fb, spec, S)
        a = timg.getchannel("A")
        img.paste(a, (int(m.get("x", 0.5) * W - timg.width / 2), int(m.get("y", 0.5) * H - timg.height / 2)))
    elif t == "image":
        im = load_image(m["path"], W, H, m.get("fit", "cover"))
        if im.getchannel("A").getextrema() != (255, 255):
            img = im.getchannel("A")
        else:
            img = im.convert("L")
        if img.size != (W, H):
            canvas = Image.new("L", (W, H), 0)
            canvas.paste(img, ((W - img.width) // 2, (H - img.height) // 2))
            img = canvas
    else:
        raise ValueError(f"unknown mask type {t}")
    if feather > 0.5:
        img = img.filter(ImageFilter.GaussianBlur(feather))
    if m.get("invert"):
        img = ImageOps.invert(img)
    return img


def _wipe(W, H, p, direction, feather):
    if isinstance(direction, (int, float)):
        ang = math.radians(direction)
    else:
        ang = math.radians({"right": 0, "down": 90, "left": 180, "up": 270}.get(direction, 0))
    dx, dy = math.cos(ang), math.sin(ang)
    # projection of canvas corners onto direction
    proj = [x * dx + y * dy for x in (0, W) for y in (0, H)]
    lo, hi = min(proj), max(proj)
    edge = lo + (hi - lo + 2 * feather) * p - feather
    ys, xs = np.mgrid[0:H:4, 0:W:4]
    v = (xs * dx + ys * dy)
    a = np.clip((edge - v) / max(feather, 1) * 0.5 + 0.5, 0, 1)
    img = Image.fromarray((a * 255).astype(np.uint8), "L").resize((W, H), Image.BILINEAR)
    return img


def _brush(W, H, p, seed, style, cx, cy, r, width):
    """Hand-painted reveal. sweep = zig-zag strokes covering the frame; blob = rough-edged iris;
    ring = a single circular paint stroke (use on a colour layer)."""
    sw, sh = max(32, W // 4), max(32, H // 4)
    img = Image.new("L", (sw, sh), 0)
    d = ImageDraw.Draw(img)
    rng = np.random.RandomState(seed)
    if style == "blob":
        maxr = math.hypot(sw, sh) * 0.55
        rad = p * maxr
        n = 90
        jitter = rng.rand(n) * 0.18 + 0.91
        # smooth jitter
        jitter = np.convolve(np.r_[jitter[-3:], jitter, jitter[:3]], np.ones(7) / 7, mode="valid")[: n]
        pts = [(cx * sw + math.cos(2 * math.pi * i / n) * rad * jitter[i],
                cy * sh + math.sin(2 * math.pi * i / n) * rad * jitter[i]) for i in range(n)]
        if rad > 1:
            d.polygon(pts, fill=255)
        # bristle flecks on the edge
        for _ in range(60):
            a = rng.rand() * 2 * math.pi
            rr = rad * (0.95 + rng.rand() * 0.12)
            x, y = cx * sw + math.cos(a) * rr, cy * sh + math.sin(a) * rr
            s = 1 + rng.rand() * sw * 0.01
            d.ellipse((x - s, y - s, x + s, y + s), fill=255)
    elif style == "ring":
        R = r * min(sw, sh)
        th = width * min(sw, sh)
        a0 = rng.rand() * 2 * math.pi
        steps = int(240 * p)
        for i in range(steps):
            a = a0 + 2 * math.pi * 1.08 * i / 240
            wob = 1 + 0.06 * math.sin(i * 0.11 + seed)
            x, y = cx * sw + math.cos(a) * R * wob, cy * sh + math.sin(a) * R * wob
            taper = min(1.0, i / 12.0, (steps - i) / 6.0 + 0.3)
            s = th / 2 * (0.75 + 0.25 * rng.rand()) * taper
            d.ellipse((x - s, y - s, x + s, y + s), fill=255)
        # dry-brush streak gaps
        for _ in range(int(40 * p)):
            a = a0 + rng.rand() * 2 * math.pi * 1.08 * p
            x, y = cx * sw + math.cos(a) * (R + (rng.rand() - 0.5) * th), cy * sh + math.sin(a) * (
                R + (rng.rand() - 0.5) * th)
            s = 0.6 + rng.rand()
            d.ellipse((x - s, y - s, x + s, y + s), fill=0)
    else:  # sweep
        n = 4
        band = sh / n
        total = n * sw
        reach = p * total * 1.08
        for k in range(n):
            y0 = band * (k + 0.5)
            start = k * sw
            seg = max(0.0, min(sw * 1.1, reach - start))
            if seg <= 0:
                break
            ltr = k % 2 == 0
            steps = max(2, int(seg / 2))
            for i in range(steps):
                x = (i * 2) if ltr else (sw - i * 2)
                y = y0 + math.sin(i * 0.05 + k) * band * 0.08
                s = band * 0.85 * (0.85 + 0.3 * rng.rand())
                d.ellipse((x - s, y - s * 0.75, x + s, y + s * 0.75), fill=255)
    img = img.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(max(1, min(W, H) // 400)))
    return img.point(lambda v: 0 if v < 70 else 255 if v > 185 else int((v - 70) * 255 / 115))


def apply_mask(layer_img, mask):
    """Multiply the alpha of a full-canvas RGBA image by an 'L' mask."""
    a = ImageChops.multiply(layer_img.getchannel("A"), mask)
    layer_img.putalpha(a)
    return layer_img
