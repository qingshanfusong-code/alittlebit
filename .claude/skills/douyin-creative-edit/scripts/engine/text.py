"""Text rendering to RGBA images (typography is half of these edits, so it gets care)."""
import collections

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .util import parse_color

_cache = collections.OrderedDict()
_layout_cache = {}


def _skey(spec, short_side):
    return (short_side, repr(sorted((k, repr(v)) for k, v in spec.items())))


def _layout(fb, spec, short_side):
    key = _skey(spec, short_side)
    if key in _layout_cache:
        return _layout_cache[key]
    text = str(spec.get("text", ""))
    case = spec.get("case")
    if case == "upper":
        text = text.upper()
    elif case == "lower":
        text = text.lower()
    size_px = int(spec.get("size_px") or max(6, int(round(float(spec.get("size", 0.08)) * short_side))))
    font, tweaks = fb.font(spec.get("font", "sans"), size_px, text)
    tracking = float(spec.get("tracking", 0.0)) * size_px
    line_sp = float(spec.get("line_spacing", 1.15))
    stroke_w = int(round(float(spec.get("stroke", 0.0)) * size_px))
    outline = bool(spec.get("outline", False))
    if outline and stroke_w == 0:
        stroke_w = max(1, int(round(0.025 * size_px)))
    lines = text.split("\n")
    ascent, descent = font.getmetrics()
    line_h = int(round((ascent + descent) * line_sp))
    pad = stroke_w + int(size_px * 0.2)
    glyphs = []
    if spec.get("vertical"):
        col_w = int(size_px * line_sp)
        step = size_px + tracking
        maxn = max((len(ln) for ln in lines), default=0)
        W, H = col_w * len(lines) + 2 * pad, int(step * maxn) + 2 * pad
        for li, ln in enumerate(lines):
            x = W - pad - (li + 1) * col_w + (col_w - size_px) / 2
            for ci, ch in enumerate(ln):
                glyphs.append((x + (size_px - font.getlength(ch)) / 2, pad + ci * step, ch))
    else:
        widths = [sum(font.getlength(c) for c in ln) + tracking * max(0, len(ln) - 1) for ln in lines]
        maxw = max(widths) if widths else 0
        W, H = int(maxw) + 2 * pad, line_h * len(lines) + 2 * pad
        align = spec.get("align", "center")
        for li, ln in enumerate(lines):
            if align == "left":
                x = pad
            elif align == "right":
                x = pad + (maxw - widths[li])
            else:
                x = pad + (maxw - widths[li]) / 2
            y = pad + li * line_h
            for ch in ln:
                glyphs.append((x, y, ch))
                x += font.getlength(ch) + tracking
    lay = {
        "font": font, "tweaks": tweaks, "size_px": size_px, "glyphs": [g for g in glyphs if not g[2].isspace()],
        "W": max(1, int(W)), "H": max(1, int(H)), "stroke_w": stroke_w, "outline": outline,
        "color": parse_color(spec.get("color", "#ffffff")),
        "stroke_c": parse_color(spec.get("stroke_color", spec.get("color", "#ffffff"))),
    }
    full = _draw(lay, None)
    bb = full.getbbox() or (0, 0, 1, 1)
    m = max(2, stroke_w + 2)
    lay["bbox"] = (max(0, bb[0] - m), max(0, bb[1] - m), min(lay["W"], bb[2] + m), min(lay["H"], bb[3] + m))
    lay["n"] = len(lay["glyphs"])
    _layout_cache[key] = lay
    return lay


def _draw(lay, visible):
    W, H, font = lay["W"], lay["H"], lay["font"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gl = lay["glyphs"] if visible is None else lay["glyphs"][: max(0, int(visible))]
    sw = lay["stroke_w"]
    if lay["outline"]:
        for x, y, ch in gl:
            d.text((x, y), ch, font=font, fill=lay["stroke_c"], stroke_width=sw, stroke_fill=lay["stroke_c"])
        inner = Image.new("L", (W, H), 0)
        di = ImageDraw.Draw(inner)
        for x, y, ch in gl:
            di.text((x, y), ch, font=font, fill=255)
        img.putalpha(ImageChops.subtract(img.getchannel("A"), inner))
    else:
        for x, y, ch in gl:
            d.text((x, y), ch, font=font, fill=lay["color"], stroke_width=sw,
                   stroke_fill=lay["stroke_c"] if sw else None)
    return img


def glyph_count(fb, spec, short_side):
    return _layout(fb, spec, short_side)["n"]


def render_text(fb, spec, short_side, visible=None):
    """spec: text, font, size (fraction of canvas short side) | size_px, color, stroke (frac of size),
    stroke_color, outline, scale_x, skew, tracking (frac of size), line_spacing, align, vertical,
    case, shadow, glow, box.  visible: draw only the first N glyphs (layout stays fixed)."""
    key = (_skey(spec, short_side), visible)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    lay = _layout(fb, spec, short_side)
    img = _draw(lay, visible).crop(lay["bbox"])
    size_px = lay["size_px"]
    scale_x = float(spec.get("scale_x", lay["tweaks"].get("scale_x", 1.0)))
    skew = float(spec.get("skew", lay["tweaks"].get("skew", 0.0)))
    if abs(scale_x - 1.0) > 1e-3:
        img = img.resize((max(1, int(img.width * scale_x)), img.height), Image.LANCZOS)
    if abs(skew) > 1e-3:
        extra = int(abs(skew) * img.height)
        img = img.transform((img.width + extra, img.height), Image.AFFINE,
                            (1, skew, -extra if skew > 0 else 0, 0, 1, 0), resample=Image.BICUBIC)
    box = spec.get("box")
    if box:
        b = box if isinstance(box, dict) else {"color": box}
        bc = parse_color(b.get("color", "#000000b0"))
        bp = int(float(b.get("pad", 0.3)) * size_px)
        bg = Image.new("RGBA", (img.width + 2 * bp, img.height + bp), bc)
        bg.alpha_composite(img, (bp, bp // 2))
        img = bg
    glow = spec.get("glow")
    if glow:
        g = glow if isinstance(glow, dict) else {}
        img = with_glow(img, max(1, int(float(g.get("radius", 0.25)) * size_px)),
                        parse_color(g.get("color", spec.get("color", "#ffffff"))), float(g.get("strength", 1.0)))
    shadow = spec.get("shadow")
    if shadow:
        s = shadow if isinstance(shadow, dict) else {}
        img = drop_shadow(img, dx=int(float(s.get("dx", 0.0)) * size_px), dy=int(float(s.get("dy", 0.05)) * size_px),
                          blur=max(1, int(float(s.get("blur", 0.1)) * size_px)),
                          color=parse_color(s.get("color", "#000000a0")))
    _cache[key] = img
    if len(_cache) > 400:
        _cache.popitem(last=False)
    return img


def drop_shadow(img, dx=0, dy=8, blur=10, color=(0, 0, 0, 160)):
    m = blur * 2 + max(abs(dx), abs(dy))
    sh = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    solid = Image.new("RGBA", img.size, color[:3] + (255,))
    solid.putalpha(img.getchannel("A").point(lambda v: v * color[3] // 255))
    sh.alpha_composite(solid, (m + dx, m + dy))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(img, (m, m))
    return sh


def with_glow(img, r, color, strength=1.0):
    m = r * 2
    base = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    solid = Image.new("RGBA", img.size, color[:3] + (255,))
    solid.putalpha(img.getchannel("A"))
    base.alpha_composite(solid, (m, m))
    g = base.filter(ImageFilter.GaussianBlur(r))
    if strength != 1.0:
        g.putalpha(g.getchannel("A").point(lambda v: min(255, int(v * strength))))
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.alpha_composite(g)
    out.alpha_composite(g)
    out.alpha_composite(img, (m, m))
    return out
