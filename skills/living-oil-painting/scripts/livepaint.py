"""Living oil painting toolkit.

  enhance: an old/low-res oil painting -> '细腻' version (super-resolution, stroke-coherent repaint,
           impasto lighting, palette grade)
  animate: the enhanced painting + a motion spec -> seamless loop where strokes flow along their own
           direction, swirls spin, plants sway, water shimmers, lights twinkle, camera drifts in 2.5D

The stroke direction comes from the structure tensor of the painting itself, so motion follows the
artist's brush - which is what makes the reference 'Starry Night' feel alive rather than warped.
"""
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ io / colour helpers
def imread(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f'cannot read {path}')
    return im.astype(np.float32) / 255.0


def imwrite(path, im):
    cv2.imwrite(path, (np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8))


def luminance(im):
    return im[..., 0] * 0.114 + im[..., 1] * 0.587 + im[..., 2] * 0.299


def poly_mask(shape, polys, feather=0.01):
    """Polygons in normalised (x, y) coordinates -> soft float mask."""
    h, w = shape[:2]
    m = np.zeros((h, w), np.float32)
    for poly in polys:
        pts = (np.asarray(poly, np.float32) * [w, h]).astype(np.int32)
        cv2.fillPoly(m, [pts], 1.0, lineType=cv2.LINE_AA)
    if feather > 0:
        s = feather * max(h, w)
        m = cv2.GaussianBlur(m, (0, 0), s)
    return np.clip(m, 0, 1)


def region_mask(shape, region, default_feather=0.012):
    """region: {'polys': [...]} | {'all': true} | {'circle': [cx, cy, r]} | {'luma': [lo, hi]} (combined by product)."""
    h, w = shape[:2]
    if region is None or region.get('all'):
        m = np.ones((h, w), np.float32)
    elif 'circle' in region:
        cx, cy, r = region['circle']
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.hypot(xx / w - cx, (yy / w) - cy * h / w)
        f = region.get('feather', default_feather)
        m = np.clip((r - d) / max(f, 1e-4) + 0.5, 0, 1)
    else:
        m = poly_mask(shape, region['polys'], region.get('feather', default_feather))
    if 'not_polys' in region:
        m *= 1 - poly_mask(shape, region['not_polys'], region.get('feather', default_feather))
    return m


# ------------------------------------------------------------------ orientation field
def structure_tensor(im, sigma_d=1.0, sigma_t=5.0):
    g = cv2.GaussianBlur(luminance(im), (0, 0), sigma_d)
    # colour-aware gradient: sum over channels
    jxx = jxy = jyy = 0
    for c in range(3):
        ch = cv2.GaussianBlur(im[..., c], (0, 0), sigma_d)
        gx = cv2.Sobel(ch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(ch, cv2.CV_32F, 0, 1, ksize=3)
        jxx = jxx + gx * gx; jxy = jxy + gx * gy; jyy = jyy + gy * gy
    jxx = cv2.GaussianBlur(jxx, (0, 0), sigma_t)
    jxy = cv2.GaussianBlur(jxy, (0, 0), sigma_t)
    jyy = cv2.GaussianBlur(jyy, (0, 0), sigma_t)
    tr = jxx + jyy
    det = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2)
    l1 = (tr + det) / 2; l2 = (tr - det) / 2
    coh = ((l1 - l2) / (l1 + l2 + 1e-8)) ** 2
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2      # along the stroke
    return np.cos(theta).astype(np.float32), np.sin(theta).astype(np.float32), coh.astype(np.float32)


def tangent_field(im, work=900, sigma_t=4.0):
    """Unsigned stroke tangent (tx, ty) and coherence at full resolution (computed at a working scale)."""
    h, w = im.shape[:2]
    s = work / max(h, w)
    small = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else im
    tx, ty, coh = structure_tensor(small, 1.0, sigma_t)
    # double-angle representation survives interpolation; convert back after resize
    c2 = tx * tx - ty * ty; s2 = 2 * tx * ty
    c2 = cv2.resize(c2, (w, h), interpolation=cv2.INTER_CUBIC)
    s2 = cv2.resize(s2, (w, h), interpolation=cv2.INTER_CUBIC)
    coh = cv2.resize(coh, (w, h), interpolation=cv2.INTER_CUBIC)
    th = 0.5 * np.arctan2(s2, c2)
    return np.cos(th).astype(np.float32), np.sin(th).astype(np.float32), np.clip(coh, 0, 1)


def guide_field(shape, guides):
    """Directional prior used to give the unsigned stroke field a consistent sign (and fill flat areas)."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    X = xx / w; Y = yy / w                                            # isotropic normalised coords
    gx = np.zeros((h, w), np.float32); gy = np.zeros((h, w), np.float32); wt = np.full((h, w), 1e-4, np.float32)
    for g in guides:
        k = g.get('weight', 1.0)
        if g['type'] == 'dir':
            a = math.radians(g['angle'])
            if 'region' in g:
                m = region_mask(shape, g['region'], 0.05)
            else:
                m = np.ones((h, w), np.float32)
            gx += k * m * math.cos(a); gy += k * m * math.sin(a); wt += k * m
        elif g['type'] == 'vortex':
            cx, cy = g['center']; cy = cy * h / w
            r = g['radius']
            dx, dy = X - cx, Y - cy
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            sgn = 1.0 if g.get('ccw', False) else -1.0                # screen y is down: -1 = clockwise on screen
            tx_, ty_ = -dy / d * -sgn, dx / d * -sgn
            infl = g.get('inflow', 0.0)                                # spiral in (+) / out (-)
            tx_ += -dx / d * infl; ty_ += -dy / d * infl
            m = np.exp(-(d / r) ** 2) * k * 3
            gx += m * tx_; gy += m * ty_; wt += m
    n = np.sqrt(gx * gx + gy * gy) + 1e-6
    return gx / n, gy / n, np.clip(n / wt, 0, 1)


def flow_field(im, guides, follow=0.85, smooth=0.004):
    """Signed unit flow following the strokes, sign chosen by the guides."""
    tx, ty, coh = tangent_field(im)
    gx, gy, gconf = guide_field(im.shape, guides)
    dot = tx * gx + ty * gy
    sgn = np.where(dot >= 0, 1.0, -1.0).astype(np.float32)
    a = follow * np.clip(coh * 1.6, 0, 1) * np.clip(np.abs(dot) * 2.5, 0, 1)   # trust strokes when coherent & unambiguous
    vx = a * sgn * tx + (1 - a) * gx
    vy = a * sgn * ty + (1 - a) * gy
    s = smooth * max(im.shape[:2])
    vx = cv2.GaussianBlur(vx, (0, 0), s); vy = cv2.GaussianBlur(vy, (0, 0), s)
    n = np.sqrt(vx * vx + vy * vy) + 1e-6
    return (vx / n).astype(np.float32), (vy / n).astype(np.float32)


# ------------------------------------------------------------------ enhancement ('细腻')
def super_resolve(im, scale, model_dir):
    """EDSR via OpenCV dnn_superres, tiled. Falls back to Lanczos if the model is missing."""
    path = os.path.join(model_dir, f'EDSR_x{scale}.pb')
    if not os.path.exists(path):
        print(f'  [sr] {path} missing, Lanczos x{scale}', flush=True)
        return cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(path); sr.setModel('edsr', scale)
    u8 = (np.clip(im, 0, 1) * 255 + 0.5).astype(np.uint8)
    h, w = u8.shape[:2]
    T, P = 384, 16
    out = np.zeros((h * scale, w * scale, 3), np.float32)
    for y0 in range(0, h, T):
        for x0 in range(0, w, T):
            ya, xa = max(0, y0 - P), max(0, x0 - P)
            yb, xb = min(h, y0 + T + P), min(w, x0 + T + P)
            up = sr.upsample(np.ascontiguousarray(u8[ya:yb, xa:xb])).astype(np.float32) / 255
            oy, ox = (y0 - ya) * scale, (x0 - xa) * scale
            th, tw = (min(h, y0 + T) - y0) * scale, (min(w, x0 + T) - x0) * scale
            out[y0 * scale:y0 * scale + th, x0 * scale:x0 * scale + tw] = up[oy:oy + th, ox:ox + tw]
    return out


def lic_smooth(im, tx, ty, length, steps=None):
    """Line-integral convolution along the (unsigned) stroke direction: strokes become clean ribbons."""
    h, w = im.shape[:2]
    steps = steps or max(3, int(length / 1.5))
    ds = length / steps
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    acc = im.copy(); wsum = 1.0
    for sign in (1.0, -1.0):
        px, py = xx.copy(), yy.copy()
        dx, dy = tx * sign, ty * sign
        for k in range(1, steps + 1):
            vx = cv2.remap(tx, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            vy = cv2.remap(ty, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            flip = np.where(vx * dx + vy * dy < 0, -1.0, 1.0).astype(np.float32)   # keep marching the same way
            dx, dy = vx * flip, vy * flip
            px = px + dx * ds; py = py + dy * ds
            wk = math.exp(-0.5 * (k / steps * 2.0) ** 2)
            acc += cv2.remap(im, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) * wk
            wsum += wk
    return acc / wsum


def shock_sharpen(im, amount=0.6, sigma=1.2):
    blur = cv2.GaussianBlur(im, (0, 0), sigma)
    return im + (im - blur) * amount


def impasto(im, tx, ty, coh, strength=0.22, spec=0.10, scale=1.0):
    """Fake thick paint: a height field built from luminance detail smoothed *along* the strokes (so noise
    does not become pits), lit from the top-left with a soft, broad highlight."""
    L = luminance(im)
    base = cv2.GaussianBlur(L, (0, 0), 7 * scale)
    detail = lic_smooth((L - base)[..., None].repeat(3, -1), tx, ty, length=10 * scale)[..., 0]
    hgt = cv2.GaussianBlur(detail, (0, 0), 1.6 * scale)
    gx = cv2.Sobel(hgt, cv2.CV_32F, 1, 0, ksize=5) / 16
    gy = cv2.Sobel(hgt, cv2.CV_32F, 0, 1, ksize=5) / 16
    k = 9.0 / scale
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(gx)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    l = np.array([-0.5, -0.6, 0.62], np.float32); l /= np.linalg.norm(l)
    diff = nx * l[0] + ny * l[1] + nz * l[2] - l[2]
    hv = l + np.array([0, 0, 1.0], np.float32); hv /= np.linalg.norm(hv)
    sp = np.clip(nx * hv[0] + ny * hv[1] + nz * hv[2], 0, 1) ** 18
    sp = cv2.GaussianBlur(sp, (0, 0), 0.8 * scale)
    shade = 1 + strength * diff * 2.0
    out = im * shade[..., None] + spec * sp[..., None] * (0.5 + 0.5 * L[..., None])
    return out.astype(np.float32)


def grade(im, preset='natural'):
    """Palette presets. 'natural': clean & vivid. 'luminous': the reference look - high-key, creamy whites,
    cooler shadows, slightly softened yellows."""
    lab = cv2.cvtColor(np.clip(im, 0, 1).astype(np.float32), cv2.COLOR_BGR2LAB)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    # local contrast on L
    l8 = np.clip(L / 100 * 255, 0, 255).astype(np.uint8)
    cl = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(l8).astype(np.float32) / 255 * 100
    L = L * 0.5 + cl * 0.5
    if preset == 'luminous':
        L = 100 * (1 - (1 - L / 100) ** 1.18)                              # lift mids / high-key
        L = 2 + L * 0.98
        chroma = np.sqrt(a * a + b * b) + 1e-6
        yellow = np.clip(b / chroma, 0, 1) * np.clip((L - 55) / 30, 0, 1)
        a *= 1 - 0.15 * yellow; b *= 1 - 0.35 * yellow                     # creamy rather than mustard highlights
        b -= 4 * np.clip((60 - L) / 60, 0, 1)                             # cool the shadows
        a *= 1.08; b *= 1.08
    else:
        L = 3 + L * 0.97
        a *= 1.12; b *= 1.12
    lab = np.stack([np.clip(L, 0, 100), a, b], -1)
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), 0, 1)


def enhance(im, out_long=2560, sr_scale=2, model_dir=None, preset='natural', lic=1.0, relief=1.0, denoise=4,
            cache=None):
    model_dir = model_dir or os.path.join(HERE, 'models')
    h, w = im.shape[:2]
    if cache and os.path.exists(cache):
        print(f'  [sr] using cached {cache}', flush=True)
        im = imread(cache)
    else:
        if denoise:
            u8 = (np.clip(im, 0, 1) * 255).astype(np.uint8)
            im = cv2.fastNlMeansDenoisingColored(u8, None, denoise, denoise, 5, 15).astype(np.float32) / 255
        need = out_long / max(h, w)
        if need > 1.15 and sr_scale > 1:
            sc = 4 if (need > 2.6 and os.path.exists(os.path.join(model_dir, 'EDSR_x4.pb'))) else sr_scale
            print(f'  [sr] EDSR x{sc} on {w}x{h}', flush=True)
            im = super_resolve(im, sc, model_dir)
        if cache:
            imwrite(cache, im)
    h, w = im.shape[:2]
    s = out_long / max(h, w)
    if abs(s - 1) > 0.01:
        im = cv2.resize(im, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA)
    unit = max(im.shape[:2]) / 2048
    tx, ty, coh = tangent_field(im, sigma_t=3.0)
    if lic > 0:
        sm = lic_smooth(im, tx, ty, length=12 * unit * lic)
        a = np.clip(coh * 2.2, 0, 1)[..., None] * 0.9
        im = im * (1 - a) + sm * a
        im = shock_sharpen(im, 0.55, 1.1 * unit)
    if relief > 0:
        im = impasto(im, tx, ty, coh, 0.16 * relief, 0.07 * relief, unit)
    im = grade(im, preset)
    return np.clip(im, 0, 1)


# ------------------------------------------------------------------ animation
def lowfreq_noise(shape, scale, seed=0):
    rng = np.random.default_rng(seed)
    h, w = shape[:2]
    n = rng.random((max(2, int(h / scale)) + 2, max(2, int(w / scale)) + 2)).astype(np.float32)
    n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    return (n - n.min()) / (n.max() - n.min() + 1e-6)


class Animator:
    """Sequential renderer. Flow layers keep per-pixel trace state (half resolution) and advance it a
    little every frame, so the cost per frame is a few remaps regardless of how far strokes travel.
    Output is periodic in spec['loop'] (every layer period divides the loop)."""

    def __init__(self, im, spec, fps=30):
        self.im = im
        self.spec = spec
        self.fps = fps
        h, w = im.shape[:2]
        self.h, self.w = h, w
        self.unit = w / 1920.0
        self.loop = spec.get('loop', 4.0)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.layers = []
        self.t_prev = None
        for i, L in enumerate(spec['layers']):
            kind = L['type']
            m = region_mask(im.shape, L.get('region'))
            lay = dict(L, mask=m)
            per = L.get('period', 2.0 if kind != 'ripple' else 1.5)
            lay['P'] = self.loop / max(1, round(self.loop / per))
            if kind == 'flow':
                vx, vy = flow_field(im, L.get('guides', [{'type': 'dir', 'angle': 0, 'weight': 0.3}]),
                                    L.get('follow', 0.85))
                ys, xs = np.where(m > 0.01)
                if len(xs) == 0:
                    continue
                Lpx = L.get('speed', 18) * self.unit * lay['P']
                pad = int(Lpx + 8)
                x0, x1 = int(max(0, xs.min() - pad)), int(min(w, xs.max() + pad + 1))
                y0, y1 = int(max(0, ys.min() - pad)), int(min(h, ys.max() + pad + 1))
                lay['bbox'] = (x0, y0, x1, y1)
                f = 2                                                   # state resolution divisor
                sw, sh = max(2, (x1 - x0) // f), max(2, (y1 - y0) // f)
                lay['ss'] = (sw, sh)
                gy, gx = np.mgrid[0:sh, 0:sw].astype(np.float32)
                lay['idx'] = tuple(a.astype(np.float32) for a in (gx * (x1 - x0) / sw + x0 + 0.5 * (x1 - x0) / sw - 0.5,
                              gy * (y1 - y0) / sh + y0 + 0.5 * (y1 - y0) / sh - 0.5))
                lay['vx'], lay['vy'] = vx, vy
                lay['L'] = Lpx
                off = lowfreq_noise(im.shape, w / 5, seed=i) * L.get('desync', 0.35)
                lay['off'] = cv2.resize(off[y0:y1, x0:x1], (sw, sh), interpolation=cv2.INTER_AREA)
                lay['state'] = None
            elif kind in ('sway', 'ripple'):
                lay['noise'] = lowfreq_noise(im.shape, w / 6, seed=10 + i)
            elif kind == 'twinkle':
                Lm = luminance(im)
                thr = L.get('threshold', 0.7)
                hl = np.clip((Lm - thr) / (1 - thr), 0, 1) * m
                lay['hl'] = hl
                lay['glow'] = cv2.GaussianBlur(hl, (0, 0), L.get('glow', 6) * self.unit)
                lay['tw_noise'] = lowfreq_noise(im.shape, w / 24, seed=99 + i) * 3
                lay['col'] = np.array(L.get('color', [0.85, 0.95, 1.0]), np.float32)
            self.layers.append(lay)

    # -- flow state ------------------------------------------------------------------------
    def _trace(self, lay, qx, qy, dist, n):
        for _ in range(n):
            vx = cv2.remap(lay['vx'], qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            vy = cv2.remap(lay['vy'], qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            qx = (qx - vx * dist / n).astype(np.float32); qy = (qy - vy * dist / n).astype(np.float32)
        return qx, qy

    def _flow_step(self, lay, t):
        P, L = lay['P'], lay['L']
        ph = ((t / P + lay['off']) % 1.0).astype(np.float32)
        ix, iy = lay['idx']
        streams = []
        if lay['state'] is None or self.t_prev is None or t <= self.t_prev or t - self.t_prev > 0.2:
            st = []
            for k in (0.0, 0.5):
                p = (ph + k) % 1.0
                qx, qy = self._trace(lay, ix.copy(), iy.copy(), p * L, 8)
                st.append([qx, qy])
            lay['state'] = st
        else:
            dp = (t - self.t_prev) / P
            for j, k in enumerate((0.0, 0.5)):
                p = (ph + k) % 1.0
                qx, qy = lay['state'][j]
                wrapped = p < dp
                qx = np.where(wrapped, ix, qx); qy = np.where(wrapped, iy, qy)
                step = np.where(wrapped, p, dp) * L
                vx = cv2.remap(lay['vx'], qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                vy = cv2.remap(lay['vy'], qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                qx = (qx - vx * step).astype(np.float32); qy = (qy - vy * step).astype(np.float32)
                lay['state'][j] = [qx, qy]
        x0, y0, x1, y1 = lay['bbox']
        bw, bh = x1 - x0, y1 - y0
        res = 0; wsum = 0
        for j, k in enumerate((0.0, 0.5)):
            p = (ph + k) % 1.0
            qx, qy = lay['state'][j]
            fx = cv2.resize(qx, (bw, bh), interpolation=cv2.INTER_LINEAR)
            fy = cv2.resize(qy, (bw, bh), interpolation=cv2.INTER_LINEAR)
            smp = cv2.remap(self.im, fx, fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            wgt = cv2.resize((1 - np.abs(2 * p - 1)).astype(np.float32), (bw, bh), interpolation=cv2.INTER_LINEAR)[..., None]
            res = res + smp * wgt; wsum = wsum + wgt
        return res / np.maximum(wsum, 1e-4)

    def displacement(self, t):
        dx = np.zeros((self.h, self.w), np.float32); dy = np.zeros_like(dx)
        for lay in self.layers:
            k = lay['type']; m = lay['mask']; P = lay['P']
            if k == 'sway':
                amp = lay.get('amp', 6) * self.unit
                ay = lay.get('anchor_y', 1.0) * self.h
                hgt = np.clip((ay - self.yy) / (self.h * lay.get('height', 0.5)), 0, 1.2)
                ph = 2 * np.pi * (t / P + lay['noise'] * lay.get('desync', 0.3))
                ang = math.radians(lay.get('angle', 0.0))
                d = amp * hgt ** 1.5 * np.sin(ph) * m
                dx += d * math.cos(ang); dy += d * math.sin(ang)
            elif k == 'ripple':
                amp = lay.get('amp', 2.5) * self.unit
                wl = lay.get('wavelength', 0.02) * self.w
                ph = 2 * np.pi * (t / P) - 2 * np.pi * self.yy / wl + lay['noise'] * 6
                dx += m * amp * np.sin(ph); dy += m * amp * 0.3 * np.cos(ph)
            elif k == 'breathe':
                cx, cy = lay.get('center', [0.5, 0.5])
                s = lay.get('amp', 0.006) * math.sin(2 * np.pi * t / P)
                dx += m * (self.xx - cx * self.w) * s; dy += m * (self.yy - cy * self.h) * s
        return dx, dy

    def frame(self, t):
        out = self.im.copy()
        for lay in self.layers:
            if lay['type'] == 'flow':
                x0, y0, x1, y1 = lay['bbox']
                flowed = self._flow_step(lay, t)
                m = lay['mask'][y0:y1, x0:x1, None]
                out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - m) + flowed * m
        self.t_prev = t
        dx, dy = self.displacement(t)
        if np.abs(dx).max() > 0.01 or np.abs(dy).max() > 0.01:
            out = cv2.remap(out, self.xx - dx, self.yy - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        for lay in self.layers:
            if lay['type'] == 'twinkle':
                pulse = 0.5 + 0.5 * np.sin(2 * np.pi * (t / lay['P']) + lay['tw_noise'] * 2 * np.pi)
                amt = lay.get('amp', 0.25)
                out = out + (lay['glow'] * pulse * amt)[..., None] * lay['col']
                out = out * (1 + (lay['hl'] * (pulse - 0.5) * amt * 0.6)[..., None])
        return np.clip(out, 0, 1)


def render_loop(im, spec, out_path, fps=30, seconds=None, size=None, crf=17):
    anim = Animator(im, spec, fps)
    seconds = seconds or spec.get('loop', 4.0)
    h, w = im.shape[:2]
    if size:
        W_, H_ = size
    else:
        W_, H_ = w - w % 2, h - h % 2
    cam = spec.get('camera')                      # optional slow push/pan for the clip itself
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W_}x{H_}', '-r', str(fps),
           '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', out_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(seconds * fps))
    for i in range(n):
        t = i / fps
        fr = anim.frame(t)
        if cam:
            u = t / seconds
            z0, z1 = cam.get('zoom', [1.0, 1.0])
            z = z0 + (z1 - z0) * (0.5 - 0.5 * math.cos(math.pi * u))
            cx0, cy0 = cam.get('from', [0.5, 0.5]); cx1, cy1 = cam.get('to', [0.5, 0.5])
            cx = (cx0 + (cx1 - cx0) * u) * w; cy = (cy0 + (cy1 - cy0) * u) * h
            vw, vh = W_ / z * (w / W_) if False else (w / z, w / z * H_ / W_)
            M = np.float32([[W_ / vw, 0, W_ / 2 - cx * W_ / vw], [0, W_ / vw, H_ / 2 - cy * W_ / vw]])
            fr = cv2.warpAffine(fr, M, (W_, H_), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        elif (W_, H_) != (w, h):
            fr = cv2.resize(fr, (W_, H_), interpolation=cv2.INTER_AREA)
        p.stdin.write((np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        if i % 30 == 0:
            print(f'  frame {i}/{n}', flush=True)
    p.stdin.close(); p.wait()


# ------------------------------------------------------------------ CLI
def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('enhance', help='painting -> 细腻 high-res painting')
    e.add_argument('src'); e.add_argument('dst')
    e.add_argument('--long', type=int, default=2560, help='output long side in px')
    e.add_argument('--preset', default='natural', choices=['natural', 'luminous'])
    e.add_argument('--lic', type=float, default=1.0, help='stroke smoothing strength (0 = off)')
    e.add_argument('--relief', type=float, default=1.0, help='impasto lighting strength (0 = off)')
    e.add_argument('--denoise', type=int, default=4)
    e.add_argument('--models', default=os.path.join(HERE, 'models'))
    a = sub.add_parser('animate', help='painting + motion spec -> seamless loop mp4')
    a.add_argument('src'); a.add_argument('spec'); a.add_argument('dst')
    a.add_argument('--seconds', type=float); a.add_argument('--fps', type=int, default=30)
    a.add_argument('--width', type=int, help='output width (keeps aspect)')
    f = sub.add_parser('field', help='debug: visualise the flow field of a spec layer')
    f.add_argument('src'); f.add_argument('spec'); f.add_argument('dst'); f.add_argument('--layer', type=int, default=0)
    args = ap.parse_args()
    if args.cmd == 'enhance':
        im = imread(args.src)
        out = enhance(im, args.long, 2, args.models, args.preset, args.lic, args.relief, args.denoise,
                      cache=os.path.splitext(args.dst)[0] + '_sr.png')
        imwrite(args.dst, out)
        print('wrote', args.dst, out.shape[1], 'x', out.shape[0])
    elif args.cmd == 'animate':
        im = imread(args.src)
        spec = json.load(open(args.spec))
        size = None
        if args.width:
            h, w = im.shape[:2]
            W_ = args.width - args.width % 2; H_ = int(round(h * W_ / w)); H_ -= H_ % 2
            im = cv2.resize(im, (W_, H_), interpolation=cv2.INTER_AREA)
        render_loop(im, spec, args.dst, args.fps, args.seconds, size)
        print('wrote', args.dst)
    elif args.cmd == 'field':
        im = imread(args.src)
        spec = json.load(open(args.spec))
        L = spec['layers'][args.layer]
        vx, vy = flow_field(im, L.get('guides', []), L.get('follow', 0.85))
        m = region_mask(im.shape, L.get('region'))
        vis = (im * 0.55 * 255).astype(np.uint8)
        h, w = im.shape[:2]
        st = max(12, w // 80)
        for y in range(st // 2, h, st):
            for x in range(st // 2, w, st):
                if m[y, x] < 0.3:
                    continue
                ex, ey = int(x + vx[y, x] * st * 0.9), int(y + vy[y, x] * st * 0.9)
                cv2.arrowedLine(vis, (x, y), (ex, ey), (255, 255, 255), max(1, w // 1200), tipLength=0.35)
        cv2.imwrite(args.dst, vis)


if __name__ == '__main__':
    main()
