"""Asset prep: carved picture frames (procedural), the self-portrait cut-out, cubist shards."""
import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageFilter

S = os.environ.get('PICASSO_WORK', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work'))
A = S + '/assets'


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


PALETTES = {
    # dark, mid, light, highlight
    'gold':   [(52, 30, 10), (150, 98, 38), (214, 168, 84), (255, 238, 178)],
    'black':  [(8, 8, 10), (28, 27, 30), (60, 58, 62), (190, 188, 196)],
    'wood':   [(70, 44, 22), (150, 104, 60), (196, 150, 98), (246, 214, 160)],
    'silver': [(40, 38, 52), (118, 112, 140), (182, 176, 204), (244, 240, 255)],
}


def make_frame(iw, ih, fw, style='gold', ornate=1.0, seed=1, liner=None):
    """RGBA frame image of size (iw+2fw, ih+2fw) with a transparent opening of iw x ih.
    Height-field profile (bead, cove, carved band, flat, sight bead) lit from the top-left."""
    rng = np.random.default_rng(seed)
    W, H = iw + 2 * fw, ih + 2 * fw
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    dl, dr, dt, db = x, W - 1 - x, y, H - 1 - y
    d = np.minimum(np.minimum(dl, dr), np.minimum(dt, db))          # distance from outer edge (mitred)
    side_h = np.minimum(dt, db) <= np.minimum(dl, dr)                # top/bottom bars
    s = np.where(side_h, x, y)                                       # position along the bar
    u = d / fw                                                       # 0 outer .. 1 sight edge
    h = np.zeros_like(u)
    h += 0.55 * np.sin(np.pi * np.clip(u / 0.13, 0, 1)) * (u < 0.13)                 # outer bead
    cove = (u >= 0.13) & (u < 0.36)
    h += np.where(cove, 0.15 + 0.35 * ((u - 0.245) / 0.115) ** 2, 0)                  # concave cove
    band = (u >= 0.36) & (u < 0.74)
    bu = (u - 0.36) / 0.38
    period = fw * 0.42
    carve = (0.5 + 0.5 * np.cos(2 * np.pi * s / period)) * np.sin(np.pi * bu)
    leaf = 0.5 + 0.5 * np.cos(2 * np.pi * s / period * 2 + np.pi * bu * 2)
    h += np.where(band, 0.45 + ornate * (0.35 * carve + 0.12 * leaf * np.sin(np.pi * bu)), 0)
    flat = (u >= 0.74) & (u < 0.9)
    h += np.where(flat, 0.38 - 0.25 * (u - 0.74) / 0.16, 0)
    sight = u >= 0.9
    h += np.where(sight, 0.25 * np.sin(np.pi * np.clip((u - 0.9) / 0.1, 0, 1)), 0)
    # wear / gesso texture
    noise = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 1.2)
    h += noise * 0.02 * (1 + ornate)
    hh = cv2.GaussianBlur(h.astype(np.float32), (0, 0), 0.8) * fw * 0.35
    gx = cv2.Sobel(hh, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(hh, cv2.CV_32F, 0, 1, ksize=3) / 8
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.55, -0.65, 0.52]); L /= np.linalg.norm(L)
    diff = np.clip((n * L).sum(-1), 0, 1)
    Hv = L + np.array([0, 0, 1.0]); Hv /= np.linalg.norm(Hv)
    spec = np.clip((n * Hv).sum(-1), 0, 1) ** 28
    ao = 0.55 + 0.45 * smoothstep(0.0, 0.5, h)
    pal = np.array(PALETTES[style], np.float32)
    k = np.clip(diff * ao, 0, 1)
    col = np.where(k[..., None] < 0.5,
                   pal[0] + (pal[1] - pal[0]) * (k[..., None] / 0.5),
                   pal[1] + (pal[2] - pal[1]) * ((k[..., None] - 0.5) / 0.5))
    col = col + (pal[3] - col) * (spec[..., None] * 0.85)
    # inner shadow cast by the frame onto the sight edge
    col *= (1 - 0.35 * smoothstep(0.86, 1.0, u))[..., None]
    if liner is not None:                                            # thin coloured liner (e.g. gold in black)
        lm = (u > 0.9)
        col = np.where(lm[..., None], np.array(liner, np.float32) * (0.6 + 0.6 * diff[..., None]), col)
    alpha = (d < fw).astype(np.float32)
    rgba = np.concatenate([np.clip(col, 0, 255), alpha[..., None] * 255], -1).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')


def framed(painting, iw, ih, fw, crop=None, **kw):
    """Painting (PIL) cover-fitted into iw x ih, wrapped by a frame. Returns RGBA."""
    p = painting.convert('RGB')
    if crop:
        p = p.crop(crop)
    pr = p.width / p.height
    if pr > iw / ih:
        nh = ih; nw = int(round(ih * pr))
    else:
        nw = iw; nh = int(round(iw / pr))
    p = p.resize((nw, nh), Image.LANCZOS)
    p = p.crop(((nw - iw) // 2, (nh - ih) // 2, (nw - iw) // 2 + iw, (nh - ih) // 2 + ih))
    fr = make_frame(iw, ih, fw, **kw)
    out = Image.new('RGBA', fr.size, (0, 0, 0, 0))
    out.paste(p, (fw, fw))
    out.alpha_composite(fr)
    return out


def selfportrait_cutout(src, dst):
    im = cv2.imread(src)
    H, W = im.shape[:2]
    sx, sy = W / 597, H / 766
    poly = np.array([(0, 766), (0, 615), (40, 588), (100, 522), (152, 470), (168, 420), (140, 382),
                     (118, 330), (126, 268), (98, 228), (84, 168), (100, 100), (150, 40), (222, 12),
                     (302, 10), (372, 40), (432, 88), (490, 140), (516, 212), (510, 300), (498, 380),
                     (470, 448), (462, 482), (520, 520), (597, 548), (597, 766)], np.float32)
    poly[:, 0] *= sx; poly[:, 1] *= sy
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [poly.astype(np.int32)], 1)
    k = int(28 * sx)
    fg = cv2.erode(m, np.ones((k, k), np.uint8))
    bgz = 1 - cv2.dilate(m, np.ones((k, k), np.uint8))
    gc = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    gc[m == 1] = cv2.GC_PR_FGD
    gc[fg == 1] = cv2.GC_FGD
    gc[bgz == 1] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(im, gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    a = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # keep the largest component, close small holes, soft edge
    n, lab, stats, _ = cv2.connectedComponentsWithStats(a)
    big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    a = np.where(lab == big, 255, 0).astype(np.uint8)
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    inv = 255 - a
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n):                                   # fill holes not touching the border
        x, y, w, h, area = stats[i]
        if x > 0 and y > 0 and x + w < W and y + h < H:
            a[lab == i] = 255
    a = cv2.GaussianBlur(a, (0, 0), 1.1)
    rgba = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    rgba[..., 3] = a
    cv2.imwrite(dst, rgba)


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'cutout':
        selfportrait_cutout(A + '/selfport_adain_x2.png', A + '/selfport_cut.png')
    elif what == 'frames':
        muse = Image.open(A + '/muse_x2.png') if len(sys.argv) < 3 else Image.open(sys.argv[2])
        f1 = framed(muse, 780, 626, 74, style='gold', ornate=1.0)
        f2 = framed(Image.open(A + '/selfport_adain_x2.png'), 440, 500, 44, style='black', ornate=0.25,
                    liner=(214, 168, 84))
        f3 = framed(Image.open(S + '/dl/seated_nude_hr.jpg'), 240, 312, 18, style='wood', ornate=0.0)
        bg = Image.new('RGBA', (1900, 900), (31, 59, 143, 255))
        bg.alpha_composite(f1, (40, 60)); bg.alpha_composite(f2, (1000, 80)); bg.alpha_composite(f3, (1580, 200))
        bg.convert('RGB').save(S + '/work/frames_test.jpg', quality=90)
