"""Picasso '名画画框穿越' edit, 16:9, choreography copied from the two reference videos:
  0.00  La Muse full screen, slow push; a small framed 'Seated Nude' floats into the painting in 3D
  4.05  fast pull-back: La Muse is a framed painting on a Picasso-blue wall
  6.42  whip pan to the next frame: the 1907 self-portrait, his hair breaking out of the frame
  8.98  the portrait flies away; cubist shards + the painter rise from the bottom, title PABLO PICASSO
 14.43  cut back into La Muse close-up, zooming out to the opening frame (loops)
"""
import argparse
import math
import subprocess
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assets import framed, make_frame  # noqa: E402

S = os.environ.get('PICASSO_WORK', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work'))
A = S + '/assets'
FONTS = S + '/fonts'
W, H = 1920, 1080
FPS = 30
DUR = 14.9
WALL = np.array([30, 60, 146], np.float32) / 255.0          # Picasso blue

T_IN0, T_IN1 = 0.55, 1.05
T_PULL0, T_PULL1 = 4.05, 6.42
T_PAN0, T_PAN1 = 6.42, 7.45
T_FLY0, T_FLY1 = 8.98, 9.62
T_COL = 9.18
T_TITLE = 10.42
T_LOOP = 14.43


# ------------------------------------------------------------------ easing
def clamp01(u):
    return max(0.0, min(1.0, u))


def ease_io(u):
    u = clamp01(u)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_out(u, p=3):
    return 1 - (1 - clamp01(u)) ** p


def ease_in(u, p=3):
    return clamp01(u) ** p


def ease_back(u, s=1.5):
    u = clamp01(u) - 1
    return u * u * ((s + 1) * u + s) + 1


def lerp(a, b, u):
    return a + (b - a) * u


def seg(t, t0, t1):
    return clamp01((t - t0) / (t1 - t0))


# ------------------------------------------------------------------ textures
class Tex:
    """Premultiplied float32 RGBA with a mip chain."""

    def __init__(self, img, pad=2):
        a = np.asarray(img.convert('RGBA'), np.float32) / 255.0
        if pad:
            a = np.pad(a, ((pad, pad), (pad, pad), (0, 0)))
        a[..., :3] *= a[..., 3:4]
        self.pad = pad
        self.levels = [a]
        while min(self.levels[-1].shape[:2]) > 64:
            self.levels.append(cv2.resize(self.levels[-1], None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA))
        self.h, self.w = a.shape[:2]


def draw(canvas, tex, quad, opacity=1.0):
    """Warp tex onto the screen quad (tl, tr, br, bl), compositing premultiplied."""
    if opacity <= 0.002:
        return
    q = np.asarray(quad, np.float32)
    # the texture's padding lies outside the quad: expand the quad accordingly
    p = tex.pad
    if p:
        iw, ih = tex.w - 2 * p, tex.h - 2 * p
        src_inner = np.float32([[0, 0], [iw, 0], [iw, ih], [0, ih]])
        Mi = cv2.getPerspectiveTransform(src_inner, q)
        outer = np.float32([[-p, -p], [iw + p, -p], [iw + p, ih + p], [-p, ih + p]])
        q = cv2.perspectiveTransform(outer[None], Mi)[0]
    x0 = int(math.floor(max(0, q[:, 0].min()))); x1 = int(math.ceil(min(canvas.shape[1], q[:, 0].max())))
    y0 = int(math.floor(max(0, q[:, 1].min()))); y1 = int(math.ceil(min(canvas.shape[0], q[:, 1].max())))
    if x1 - x0 < 1 or y1 - y0 < 1:
        return
    dst_w = max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3]))
    dst_h = max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1]))
    ratio = min(dst_w / tex.w, dst_h / tex.h)
    lvl = 0
    while lvl + 1 < len(tex.levels) and ratio < 0.5 ** (lvl + 1) * 1.15:
        lvl += 1
    src = tex.levels[lvl]
    sh, sw = src.shape[:2]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]]), q - np.float32([x0, y0]))
    out = cv2.warpPerspective(src, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    reg = canvas[y0:y1, x0:x1]
    a = out[..., 3:4] * opacity
    reg *= (1 - a)
    reg += out[..., :3] * opacity


def rect_quad(cx, cy, w, h, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def shadow_tex(img, blur, strength=0.55, pad=None):
    a = np.asarray(img.convert('RGBA'))[..., 3].astype(np.float32) / 255
    pad = pad or int(blur * 3)
    a = np.pad(a, pad)
    a = cv2.GaussianBlur(a, (0, 0), blur) * strength
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Tex(Image.fromarray(rgba, 'RGBA'), pad=0), pad


def font(weight, size, family='oswald'):
    return ImageFont.truetype(f'{FONTS}/{family}/package/files/{family}-latin-{weight}-normal.woff', size)


def text_img(text, fnt, color, tracking=0.0):
    """Text with manual letter spacing (tracking in em). Tight RGBA."""
    size = fnt.size
    widths = [fnt.getlength(ch) for ch in text]
    total = sum(widths) + tracking * size * (len(text) - 1)
    asc, desc = fnt.getmetrics()
    im = Image.new('RGBA', (int(total) + 8, asc + desc + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 4
    for ch, w in zip(text, widths):
        d.text((x, 4), ch, font=fnt, fill=color)
        x += w + tracking * size
    return im.crop(im.getbbox())


# ------------------------------------------------------------------ scene assets
class Assets:
    def __init__(self):
        muse = Image.open(A + '/muse_x2.png')
        nude = Image.open(S + '/dl/seated_nude_hr.jpg')
        nude = Image.fromarray(np.clip(np.asarray(nude).astype(np.float32) * 1.22 + 6, 0, 255).astype(np.uint8))
        port = Image.open(A + '/selfport_adain_x2.png')
        cut = Image.open(A + '/selfport_cut.png')
        self.muse_img = muse

        # A: La Muse in a carved gold frame. world: interior 780 x 626, frame 74; texture scale 2.8
        self.A_in = (780, 626); self.A_fw = 74; ks = 2.8
        fa = framed(muse, int(780 * ks), int(626 * ks), int(74 * ks), style='gold', ornate=1.0)
        self.A = Tex(fa)
        self.A_out = (780 + 2 * 74, 626 + 2 * 74)
        self.A_sh, p = shadow_tex(fa.resize((fa.width // 4, fa.height // 4)), 9, 0.6)
        self.A_sh_pad = p * 4 / ks                                           # in world units

        # small frame inside A: Seated Nude in a light wood frame. world interior 130 x 169, frame 12
        self.N_in = (130, 169); self.N_fw = 12; ks = 3.2
        fn = framed(nude, int(130 * ks), int(169 * ks), int(12 * ks), style='wood', ornate=0.0)
        self.N = Tex(fn)
        self.N_out = (130 + 24, 169 + 24)
        self.N_sh, p = shadow_tex(fn.resize((fn.width // 2, fn.height // 2)), 7, 0.55)
        self.N_sh_pad = p * 2 / ks
        side = Image.new('RGBA', (64, 64), (140, 96, 54, 255))
        self.N_side = Tex(side)
        self.N_side_dark = Tex(Image.new('RGBA', (64, 64), (92, 60, 32, 255)))

        # B: 1907 self-portrait in a black frame with gold liner; hair breaks out over the top bar
        crop_top = int(0.2 * port.height)
        self.B_in = (440, 452); self.B_fw = 44; ks = 2.0
        fb = framed(port, int(440 * ks), int(452 * ks), int(44 * ks), crop=(0, crop_top, port.width, port.height),
                    style='black', ornate=0.25, liner=(214, 168, 84))
        self.B = Tex(fb)
        self.B_out = (440 + 88, 452 + 88)
        self.B_sh, p = shadow_tex(fb.resize((fb.width // 4, fb.height // 4)), 9, 0.6)
        self.B_sh_pad = p * 4 / ks
        k = 440 / port.width                                                  # world units per image px
        rows = crop_top + int(44 / k) + 40
        pop = cut.crop((0, 0, cut.width, rows))
        pa = np.asarray(pop).copy()
        fade = np.clip((rows - np.arange(rows)) / 30.0, 0, 1)                 # soften the bottom seam
        # the canvas edge slices the top of the hair flat: round it into a dome
        yy, xx = np.mgrid[0:rows, 0:pop.width].astype(np.float32)
        Wp, Hp = port.width, port.height
        ytop = 0.016 * Hp + 0.075 * Hp * ((xx - 0.45 * Wp) / (0.33 * Wp)) ** 2
        dome = np.clip((yy - ytop) / 10.0, 0, 1)
        pa[..., 3] = (pa[..., 3] * fade[:, None] * dome).astype(np.uint8)
        pop = Image.fromarray(pa, 'RGBA')
        self.pop = Tex(pop)
        self.pop_rect = (-220, -226 - crop_top * k, 440, rows * k)          # x, y, w, h in B-local world
        ps = pop.resize((pop.width // 2, pop.height // 2))
        self.pop_sh, p = shadow_tex(ps, 5, 0.5)
        self.pop_sh_pad = p * 2 * k

        # collage: the painter cut out, cubist shards, title
        cut_arr = np.asarray(cut).copy()
        cut_arr[:int(0.012 * cut.height), :, 3] = 0
        self.cut = Tex(Image.fromarray(cut_arr, 'RGBA'))
        self.cut_size = cut.size
        self.cut_sh, p = shadow_tex(cut.resize((cut.width // 4, cut.height // 4)), 8, 0.5)
        self.cut_sh_pad = p * 4
        self.shards = make_shards(muse, nude, port)

        # text
        cream = (236, 226, 204, 255)
        self.lbl_A = Tex(text_img('LA MUSE  ·  1935', font(400, 64), cream, 0.32))
        self.lbl_B = Tex(text_img('AUTOPORTRAIT  ·  1907', font(400, 64), cream, 0.32))
        self.lbl_B2 = Tex(text_img('PABLO PICASSO', font(500, 64), (226, 186, 104, 255), 0.4))
        gold = (243, 201, 105, 255)
        self.t_pablo = [Tex(text_img(ch, font(300, 150), cream)) for ch in 'PABLO']
        self.t_pic = [Tex(text_img(ch, font(600, 330), gold)) for ch in 'PICASSO']
        self.t_years = Tex(text_img('1881 — 1973', font(400, 64), cream, 0.45))
        self.t_sub = Tex(text_img('CUBISM  ·  THE MUSE  ·  THE SELF', font(300, 54), cream, 0.38))
        self.line = Tex(Image.new('RGBA', (16, 4), (236, 226, 204, 255)), pad=1)
        f330 = font(600, 330)
        self.pic_adv = [f330.getlength(ch) for ch in 'PICASSO']
        f150 = font(300, 150)
        self.pablo_adv = [f150.getlength(ch) for ch in 'PABLO']

        # wall light (precomputed low-res maps)
        self.vig = vignette()


def vignette():
    y, x = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
    x = (x - W / 8) / (W / 8); y = (y - H / 8) / (H / 8)
    v = 1 - 0.32 * np.clip((x * x * 0.8 + y * y) - 0.25, 0, 2) ** 1.2
    return cv2.resize(v, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]


def collage_textures(rng, R=512):
    """Papier-collé materials Picasso actually used: newspaper (LE JOURNAL), faux-bois, chair caning."""
    out = {}
    # newspaper
    paper = np.full((R, R, 3), (232, 222, 196), np.float32)
    paper += cv2.GaussianBlur(rng.standard_normal((R, R)).astype(np.float32), (0, 0), 2)[..., None] * 6
    im = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    fh = ImageFont.truetype(f'{FONTS}/playfair-display/package/files/playfair-display-latin-900-normal.woff', 150)
    d.text((26, 40), 'JOU', font=fh, fill=(28, 24, 22))
    fs = ImageFont.truetype(f'{FONTS}/playfair-display/package/files/playfair-display-latin-400-normal.woff', 30)
    d.text((30, 210), 'LE JOURNAL  ·  PARIS', font=fs, fill=(40, 36, 32))
    for col in range(3):
        for row in range(14):
            y = 262 + row * 17
            x0 = 30 + col * 160
            d.line([(x0, y), (x0 + rng.integers(90, 140), y)], fill=(90, 84, 76), width=5)
    out['journal'] = np.asarray(im)
    # faux bois
    y, x = np.mgrid[0:R, 0:R].astype(np.float32)
    n = cv2.GaussianBlur(rng.standard_normal((R, R)).astype(np.float32), (0, 0), 18) * 40
    rings = 0.5 + 0.5 * np.sin((x * 0.9 + y * 0.25 + n) / 7.0)
    rings = rings ** 3
    wood = np.array([170, 112, 58], np.float32) * (0.75 + 0.35 * rings[..., None])
    out['bois'] = np.clip(wood, 0, 255).astype(np.uint8)
    # chair caning (oilcloth print)
    cane = np.full((R, R, 3), (214, 190, 140), np.float32)
    im = Image.fromarray(cane.astype(np.uint8)); d = ImageDraw.Draw(im)
    s = 46
    for k in range(-R, 2 * R, s):
        d.line([(k, 0), (k + R, R)], fill=(150, 116, 66), width=7)
        d.line([(k, R), (k + R, 0)], fill=(150, 116, 66), width=7)
        d.line([(k, 0), (k, R)], fill=(170, 136, 86), width=5)
    for yy in range(0, R, s):
        d.line([(0, yy), (R, yy)], fill=(170, 136, 86), width=5)
    out['cane'] = np.asarray(im)
    return out


def make_shards(muse, nude, port):
    """Cubist fragments cut from the three paintings + papier-collé materials, black contour lines."""
    rng = np.random.default_rng(11)
    nude_b = np.clip(np.asarray(nude.convert('RGB')).astype(np.float32) * 1.25, 0, 255).astype(np.uint8)
    srcs = {'muse': np.asarray(muse.convert('RGB')), 'nude': nude_b, 'port': np.asarray(port.convert('RGB'))}
    mats = collage_textures(rng)
    # recognisable pieces: (source, fx, fy, crop fraction)
    features = [('muse', 0.37, 0.15, 0.30),   # vase & flowers
                ('muse', 0.83, 0.18, 0.26),   # the muse's face
                ('port', 0.62, 0.40, 0.42),   # the painter's eyes
                ('muse', 0.55, 0.35, 0.30),   # sleeping woman
                ('mat', 'journal'),
                ('muse', 0.12, 0.50, 0.32),   # mirror with the red figure
                ('nude', 0.38, 0.26, 0.30),   # seated nude head
                ('mat', 'bois'),
                ('muse', 0.62, 0.62, 0.30),   # drawing pad
                ('mat', 'cane'),
                ('muse', 0.85, 0.92, 0.24),   # blue cushion
                ('muse', 0.30, 0.90, 0.30),   # feet
                ('mat', 'journal'),
                ('port', 0.45, 0.85, 0.40)]   # shirt collar

    def dune(x):  # top of the pile (screen y)
        if x < 760:
            return 700 + 80 * clamp01((x - 450) / 300)
        if x < 1180:
            return 815
        return 815 - 395 * ease_io(clamp01((x - 1180) / 700))

    slots = []
    # three layers: back (tall, defines the silhouette), mid, front base strip
    for layer, n, smin, smax in [(0, 20, 280, 420), (1, 22, 230, 360), (2, 18, 220, 330)]:
        xs = np.linspace(-80, W + 80, n) + rng.uniform(-45, 45, n)
        for x in xs:
            size = rng.uniform(smin, smax)
            top = dune(x)
            if layer == 0:
                y = top + size * rng.uniform(0.32, 0.45)
            elif layer == 1:
                y = rng.uniform(top + size * 0.45, max(top + size * 0.5, 1000))
            else:
                if 200 < x < 700:          # keep the painter's face clear
                    continue
                y = rng.uniform(1010, 1110)
            slots.append((layer, float(x), float(y), size))
    order = rng.permutation(len(slots))
    shards = []
    fi = 0
    for j, idx in enumerate(order):
        layer, x, y, size = slots[idx]
        R = 512
        # keep the painter area (x 130..730) mostly behind him: front layer there uses small pieces
        if fi < len(features) and (layer == 1 or (layer == 0 and fi % 2 == 0)) and not (200 < x < 700):
            feat = features[fi]; fi += 1
        else:
            feat = None
        if feat and feat[0] == 'mat':
            crop = mats[feat[1]]
        else:
            if feat:
                src, fx, fy, fs = feat
            else:
                src = ['muse'] * 6 + ['nude'] * 2 + ['port'] * 2
                src = src[rng.integers(len(src))]
                fx, fy, fs = rng.uniform(0.08, 0.92), rng.uniform(0.08, 0.92), rng.uniform(0.2, 0.34)
            img = srcs[src]
            ih, iw = img.shape[:2]
            cs = int(fs * min(iw, ih))
            cx = int(np.clip(fx * iw, cs / 2, iw - cs / 2)); cy = int(np.clip(fy * ih, cs / 2, ih - cs / 2))
            crop = cv2.resize(img[cy - cs // 2: cy - cs // 2 + cs, cx - cs // 2: cx - cs // 2 + cs], (R, R),
                              interpolation=cv2.INTER_AREA)
        k = int(rng.integers(3, 6))
        ang = np.sort(rng.uniform(0, 2 * np.pi, k))
        while np.max(np.diff(np.concatenate([ang, [ang[0] + 2 * np.pi]]))) > 2.2:
            ang = np.sort(rng.uniform(0, 2 * np.pi, k))
        rad = rng.uniform(0.78, 1.0, k) * R * 0.48
        pts = np.stack([R / 2 + rad * np.cos(ang), R / 2 + rad * np.sin(ang)], 1)
        mask = np.zeros((R * 2, R * 2), np.uint8)
        cv2.fillPoly(mask, [(pts * 2).astype(np.int32)], 255, lineType=cv2.LINE_AA)
        mask = cv2.resize(mask, (R, R), interpolation=cv2.INTER_AREA)
        line = np.zeros((R * 2, R * 2), np.uint8)
        cv2.polylines(line, [(pts * 2).astype(np.int32)], True, 255, thickness=int(rng.uniform(10, 15)),
                      lineType=cv2.LINE_AA)
        line = cv2.resize(line, (R, R), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        ink = np.array([24, 20, 18], np.float32)
        rgb = crop.astype(np.float32) * (1 - line[..., None]) + ink * line[..., None]
        alpha = np.maximum(mask.astype(np.float32) / 255, line)
        if feat is None and rng.random() < 0.16:          # flat Picasso colour planes
            pal = [(226, 186, 68), (196, 58, 40), (244, 236, 216), (36, 84, 168), (64, 136, 78)]
            flat = np.array(pal[rng.integers(len(pal))], np.float32)
            lum = rgb.mean(-1, keepdims=True) / 255
            rgb = np.where(line[..., None] > 0.5, rgb, flat * (0.8 + 0.4 * lum))
        rgba = np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8)
        im = Image.fromarray(rgba, 'RGBA')
        sh, pad = shadow_tex(im.resize((R // 4, R // 4)), 4, 0.6)
        depth = layer + (y / 1200)
        xr = clamp01((x + 80) / (W + 160))
        shards.append(dict(tex=Tex(im), sh=sh, shpad=pad * 4 * size / R, x=x, y=y, size=size,
                           rot=float(rng.uniform(-0.6, 0.6)), rot0=float(rng.uniform(-0.9, 0.9)), depth=depth,
                           layer=layer, t0=T_COL + 0.02 + 0.62 * xr + 0.10 * layer + float(rng.uniform(-0.05, 0.07)),
                           bob=float(rng.uniform(0, 2 * np.pi))))
    shards.sort(key=lambda s: s['depth'])
    return shards


# ------------------------------------------------------------------ camera / choreography
OPEN_C = (-8.0, -78.0)        # world center at t=0 (A interior is centred on the origin)
OPEN_Z = 2.60


def camera(t):
    if t < T_PULL0:
        u = t / T_PULL0
        z = OPEN_Z * (2.84 / OPEN_Z) ** (u * (0.6 + 0.4 * u))
        return lerp(OPEN_C[0], 10.0, u), lerp(OPEN_C[1], -70.0, u), z
    if t < T_PAN0:
        u = ease_out(seg(t, T_PULL0, T_PULL1), 4)
        z = math.exp(lerp(math.log(2.84), math.log(1.20), u))
        return lerp(10.0, 0.0, u), lerp(-70.0, -12.0, u), z
    if t < T_FLY0:
        u = seg(t, T_PAN0, T_PAN1)
        e = ease_io(u ** 0.7)
        x = lerp(0.0, 1110.0, e) + 20 * seg(t, T_PAN1, T_FLY0)
        return x, lerp(-12.0, -4.0, e), lerp(1.20, 1.22, e) + 0.035 * ease_io(seg(t, T_PAN1, T_FLY0))
    u = seg(t, T_FLY0, T_FLY0 + 0.5)
    return 1130.0 + 420 * ease_in(u, 2), -4.0, 1.255 + 0.05 * ease_in(u, 2)


def to_screen(cam, pts):
    cx, cy, z = cam
    return [((x - cx) * z + W / 2, (y - cy) * z + H / 2) for x, y in pts]


def wall_world(canvas, cam):
    cx, cy, z = cam
    ys, xs = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32) * 8
    X = (xs - W / 2) / z + cx; Y = (ys - H / 2) / z + cy
    L = 0.78 + 0.30 * np.exp(-((X - 0) ** 2 + (Y + 160) ** 2) / (2 * 720 ** 2)) \
             + 0.30 * np.exp(-((X - 1180) ** 2 + (Y + 160) ** 2) / (2 * 640 ** 2)) \
             + 0.28 * np.exp(-((X - 1800) ** 2 + (Y + 120) ** 2) / (2 * 620 ** 2))
    L = cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    canvas[:] = WALL * L


def wall_screen(canvas, push):
    ys, xs = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32) * 8
    L = 0.80 + 0.32 * np.exp(-((xs - 1180) ** 2 + (ys - 330) ** 2) / (2 * 760 ** 2))
    L = cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    canvas[:] = WALL * L


def project_box(center, w, h, d, rx, ry, rz, F):
    """3D box (w x h x d) rotated, perspective projected. Returns dict face -> 2D quad (local units) and normal z."""
    hw, hh, hd = w / 2, h / 2, d / 2
    P = np.array([[-hw, -hh, -hd], [hw, -hh, -hd], [hw, hh, -hd], [-hw, hh, -hd],
                  [-hw, -hh, hd], [hw, -hh, hd], [hw, hh, hd], [-hw, hh, hd]], np.float64)
    cx_, sx_ = math.cos(rx), math.sin(rx); cy_, sy_ = math.cos(ry), math.sin(ry); cz_, sz_ = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx_, -sx_], [0, sx_, cx_]])
    Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    Rz = np.array([[cz_, -sz_, 0], [sz_, cz_, 0], [0, 0, 1]])
    P = P @ (Rz @ Ry @ Rx).T
    Z = P[:, 2] + F
    pts = np.stack([P[:, 0] * F / Z + center[0], P[:, 1] * F / Z + center[1]], 1)
    faces = {'front': [0, 1, 2, 3], 'right': [1, 5, 6, 2], 'left': [4, 0, 3, 7], 'top': [4, 5, 1, 0], 'bottom': [3, 2, 6, 7]}
    out = {}
    for name, idx in faces.items():
        q = pts[idx]
        # visibility from 2D winding (front faces are clockwise in screen space, y down)
        area = 0.0
        for i in range(4):
            x1, y1 = q[i]; x2, y2 = q[(i + 1) % 4]
            area += x1 * y2 - x2 * y1
        out[name] = (q, area > 0)
    return out


# ------------------------------------------------------------------ frame renderer
def render(t, AS):
    canvas = np.zeros((H, W, 3), np.float32)
    in_loop = t >= T_LOOP
    if in_loop:
        u = ease_out(seg(t, T_LOOP, DUR), 3)
        cam = (lerp(-40.0, OPEN_C[0], u), lerp(-110.0, OPEN_C[1], u), math.exp(lerp(math.log(4.1), math.log(OPEN_Z), u)))
    else:
        cam = camera(t)
    wall_world(canvas, cam)
    if in_loop or t < T_FLY1:
        aw, ah = AS.A_out
        sp = AS.A_sh_pad
        draw(canvas, AS.A_sh, to_screen(cam, rect_quad(10, 16, aw + 2 * sp, ah + 2 * sp)), 1.0)
        draw(canvas, AS.A, to_screen(cam, rect_quad(0, 0, aw, ah)))
    if not in_loop and t < T_FLY1:
        if t >= T_IN0:
            draw_small_frame(canvas, cam, t, AS)
        la = seg(t, 4.75, 5.35)
        if la > 0:
            lw = 190; lh = lw * AS.lbl_A.h / AS.lbl_A.w
            aw, ah = AS.A_out
            draw(canvas, AS.lbl_A, to_screen(cam, rect_quad(-aw / 2 + lw / 2, -ah / 2 - 18 - lh / 2, lw, lh)), 0.85 * la)
        if t > 5.5:
            draw_B(canvas, cam, t, AS)
    if not in_loop and t >= T_COL:
        draw_collage(canvas, t, AS)
    canvas *= AS.vig
    return canvas


def draw_small_frame(canvas, cam, t, AS):
    u = seg(t, T_IN0, T_IN1)
    e = ease_back(u, 1.3)
    # painting-local anchor (A interior spans x -390..390, y -313..313)
    base = (-390 + 0.215 * 780, -313 + 0.30 * 626)
    tt = t - T_IN0
    cx = base[0] - 70 * (1 - e) + 6 * math.sin(tt * 1.1)
    cy = base[1] + 150 * (1 - e) + 5 * math.sin(tt * 1.6 + 1.0)
    ry = math.radians(-30 - 22 * ease_io(seg(t, T_IN0, T_PULL0 + 0.6)) + 3 * math.sin(tt * 0.9))
    rx = math.radians(9 + 3 * math.sin(tt * 1.3))
    rz = math.radians(-5 + 8 * (1 - e) + 1.5 * math.sin(tt * 0.7))
    sc = lerp(0.8, 1.0, e)
    op = clamp01(u * 2.2)
    nw, nh = AS.N_out
    faces = project_box((cx, cy), nw * sc, nh * sc, 20 * sc, rx, ry, rz, 520)
    # soft shadow cast on the painting
    fq = faces['front'][0]
    shq = [(x + 16, y + 24) for x, y in fq]
    pad = AS.N_sh_pad * sc
    cxq, cyq = np.mean(shq, 0)
    shq = [(cxq + (x - cxq) * (1 + 2 * pad / nw), cyq + (y - cyq) * (1 + 2 * pad / nh)) for x, y in shq]
    draw(canvas, AS.N_sh, to_screen(cam, shq), op * 0.9)
    for name in ['top', 'bottom', 'left', 'right']:
        q, vis = faces[name]
        if vis:
            draw(canvas, AS.N_side if name in ('left', 'top') else AS.N_side_dark, to_screen(cam, q), op)
    q, vis = faces['front']
    draw(canvas, AS.N, to_screen(cam, q), op)


def draw_B(canvas, cam, t, AS):
    bx, by = 1180.0, 6.0
    rot = 0.0; dx = dy = 0.0
    if t > T_FLY0:
        u = seg(t, T_FLY0, T_FLY1)
        dx, dy = 760 * ease_in(u, 2.2), -1150 * ease_in(u, 2.2)
        rot = math.radians(24) * ease_in(u, 1.6)
        if u >= 1:
            return
    c, s = math.cos(rot), math.sin(rot)

    def L2W(pts):  # B-local -> world
        return [(bx + dx + x * c - y * s, by + dy + x * s + y * c) for x, y in pts]

    def rq(x, y, w, h):
        return L2W([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])

    bw, bh = AS.B_out
    sp = AS.B_sh_pad
    draw(canvas, AS.B_sh, to_screen(cam, rq(-bw / 2 - sp + 10, -bh / 2 - sp + 16, bw + 2 * sp, bh + 2 * sp)))
    draw(canvas, AS.B, to_screen(cam, rq(-bw / 2, -bh / 2, bw, bh)))
    x, y, w, h = AS.pop_rect
    p = AS.pop_sh_pad
    draw(canvas, AS.pop_sh, to_screen(cam, rq(x - p + 5, y - p + 9, w + 2 * p, h + 2 * p)), 0.85)
    draw(canvas, AS.pop, to_screen(cam, rq(x, y, w, h)))
    la = seg(t, 7.25, 7.8)
    if la > 0:
        lw = 205; lh = lw * AS.lbl_B.h / AS.lbl_B.w
        draw(canvas, AS.lbl_B, to_screen(cam, rq(bw / 2 - lw, bh / 2 + 22, lw, lh)), 0.8 * la)
        lw2 = 170; lh2 = lw2 * AS.lbl_B2.h / AS.lbl_B2.w
        x0 = -bw / 2 - 20 - lh2; y1 = bh / 2
        # rotated 90° ccw: reads bottom-to-top along the frame's left edge
        draw(canvas, AS.lbl_B2, to_screen(cam, L2W([(x0, y1), (x0, y1 - lw2), (x0 + lh2, y1 - lw2), (x0 + lh2, y1)])), 0.9 * la)


def draw_collage(canvas, t, AS):
    push = 1 + 0.05 * ease_io(seg(t, 9.9, T_LOOP))
    ox, oy = 960, 620

    def P(pts):
        return [(ox + (x - ox) * push, oy + (y - oy) * push) for x, y in pts]

    shards = AS.shards
    back = [s for s in shards if s['layer'] < 2]
    front = [s for s in shards if s['layer'] == 2]
    for s in back:
        draw_shard(canvas, s, t, P)
    # the painter rises bottom-left
    u = seg(t, 9.36, 9.98)
    if u > 0:
        e = ease_back(u, 1.25)
        cw, ch = AS.cut_size
        hgt = 800.0; wid = hgt * cw / ch
        cx, cy = 430.0, 1080 - hgt / 2 + 70 + 900 * (1 - e)
        cy += 4 * math.sin((t - 9.4) * 1.3)
        sp = AS.cut_sh_pad * hgt / ch
        draw(canvas, AS.cut_sh, P(rect_quad(cx + 14, cy + 12, wid + 2 * sp, hgt + 2 * sp)), 0.9)
        draw(canvas, AS.cut, P(rect_quad(cx, cy, wid, hgt)))
    for s in front:
        draw_shard(canvas, s, t, P)
    draw_title(canvas, t, AS, P)


def draw_shard(canvas, s, t, P):
    u = seg(t, s['t0'], s['t0'] + 0.5)
    if u <= 0:
        return
    e = ease_back(u, 1.6)
    y = s['y'] + 760 * (1 - e) + 3 * math.sin(t * 1.2 + s['bob'])
    rot = s['rot'] + s['rot0'] * (1 - e)
    sz = s['size']
    p = s['shpad']
    draw(canvas, s['sh'], P(rect_quad(s['x'] + 8, y + 12, sz + 2 * p, sz + 2 * p, rot)), 0.9)
    draw(canvas, s['tex'], P(rect_quad(s['x'], y, sz, sz, rot)))


def draw_title(canvas, t, AS, P):
    if t < T_TITLE:
        return
    cxT = 1235
    # PICASSO letters rise in one by one
    k = 0.62                                            # px per font px (330 -> ~205 px tall caps)
    total = sum(AS.pic_adv) * k + 6 * 14
    x = cxT - total / 2
    base_y = 440
    for i, (tex, adv) in enumerate(zip(AS.t_pic, AS.pic_adv)):
        u = seg(t, T_TITLE + 0.05 * i, T_TITLE + 0.05 * i + 0.45)
        e = ease_out(u, 3)
        w = tex.w * k; h = tex.h * k
        lx = x + (adv * k - w) / 2
        draw(canvas, tex, P([(lx, base_y - h + 50 * (1 - e)), (lx + w, base_y - h + 50 * (1 - e)),
                             (lx + w, base_y + 50 * (1 - e)), (lx, base_y + 50 * (1 - e))]), e)
        x += adv * k + 14
    # PABLO above, tracking opens up
    u = seg(t, T_TITLE + 0.2, T_TITLE + 0.8)
    e = ease_out(u, 3)
    k2 = 0.36; track = lerp(10, 34, e)
    tot = sum(AS.pablo_adv) * k2 + 4 * track
    x = cxT - tot / 2
    for tex, adv in zip(AS.t_pablo, AS.pablo_adv):
        w = tex.w * k2; h = tex.h * k2
        lx = x + (adv * k2 - w) / 2
        draw(canvas, tex, P([(lx, 213), (lx + w, 213), (lx + w, 213 + h), (lx, 213 + h)]), e * 0.95)
        x += adv * k2 + track
    # years with rules drawing outwards
    u = seg(t, T_TITLE + 0.45, T_TITLE + 1.05)
    e = ease_out(u, 3)
    yw = 230; yh = yw * AS.t_years.h / AS.t_years.w
    draw(canvas, AS.t_years, P(rect_quad(cxT, 497, yw, yh)), e * 0.9)
    ll = 150 * e
    draw(canvas, AS.line, P([(cxT - yw / 2 - 26 - ll, 496), (cxT - yw / 2 - 26, 496), (cxT - yw / 2 - 26, 498), (cxT - yw / 2 - 26 - ll, 498)]), 0.7 * e)
    draw(canvas, AS.line, P([(cxT + yw / 2 + 26, 496), (cxT + yw / 2 + 26 + ll, 496), (cxT + yw / 2 + 26 + ll, 498), (cxT + yw / 2 + 26, 498)]), 0.7 * e)


# ------------------------------------------------------------------ main
def mb_samples(t):
    for a, b, n in [(T_IN0, T_IN0 + 0.4, 5), (T_PULL0, T_PULL0 + 0.75, 9), (T_PAN0, T_PAN1 - 0.1, 14),
                    (T_FLY0 + 0.02, T_FLY1, 12), (T_COL, 10.35, 6), (T_LOOP, T_LOOP + 0.4, 9)]:
        if a <= t < b:
            return n
    return 1


def frame_at(t, AS, rng, mb=True):
    n = mb_samples(t) if mb else 1
    if n == 1:
        img = render(t, AS)
    else:
        sh = 0.6 / FPS
        img = sum(render(t - sh / 2 + sh * (i + 0.5) / n, AS) for i in range(n)) / n
    g = rng.standard_normal((H // 2, W // 2)).astype(np.float32) * 0.010
    img = img + cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--audio')
    ap.add_argument('--sheet')
    ap.add_argument('--at', default='')
    ap.add_argument('--from', dest='t0', type=float, default=0.0)
    ap.add_argument('--to', dest='t1', type=float, default=DUR)
    ap.add_argument('--crf', default='16')
    a = ap.parse_args()
    AS = Assets()
    rng = np.random.default_rng(3)
    if a.sheet:
        ts = [float(x) for x in a.at.split(',')]
        thumbs = []
        for t in ts:
            im = Image.fromarray(frame_at(t, AS, rng)).resize((640, 360))
            ImageDraw.Draw(im).text((8, 6), f'{t:.2f}s', fill='white')
            thumbs.append(im)
        cols = 3
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new('RGB', (640 * cols, 360 * rows))
        for i, im in enumerate(thumbs):
            sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
        sheet.save(a.sheet, quality=90)
        return
    n0 = int(round(a.t0 * FPS)); n1 = int(round(a.t1 * FPS))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    if a.audio:
        cmd += ['-ss', f'{a.t0}', '-t', f'{a.t1 - a.t0}', '-i', a.audio, '-c:a', 'aac', '-b:a', '256k', '-shortest']
    cmd += ['-c:v', 'libx264', '-preset', 'slow', '-crf', a.crf, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n0, n1):
        p.stdin.write(frame_at(i / FPS, AS, rng).tobytes())
        if i % 30 == 0:
            print(f'frame {i}/{n1}', flush=True)
    p.stdin.close(); p.wait()


if __name__ == '__main__':
    main()
