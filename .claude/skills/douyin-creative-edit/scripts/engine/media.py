"""Media probing and frame access (ffmpeg pipes, sequential readers, image cache)."""
import collections
import json
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageFilter, ImageOps

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".flv", ".ts", ".mts", ".3gp", ".mpg"}

_probe_cache = {}


def is_image(path):
    return os.path.splitext(str(path))[1].lower() in IMAGE_EXT


def probe(path):
    """-> dict(width,height (display, rotation applied), duration, fps, has_audio, has_alpha, rotation)"""
    path = str(path)
    if path in _probe_cache:
        return _probe_cache[path]
    if is_image(path):
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            info = {"width": im.width, "height": im.height, "duration": None, "fps": None, "has_audio": False,
                    "has_alpha": im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info, "rotation": 0,
                    "kind": "image"}
        _probe_cache[path] = info
        return info
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {out.stderr[-300:]}")
    d = json.loads(out.stdout)
    vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
    aus = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs:
        info = {"width": 0, "height": 0, "duration": float(d.get("format", {}).get("duration", 0) or 0),
                "fps": None, "has_audio": bool(aus), "has_alpha": False, "rotation": 0, "kind": "audio"}
        _probe_cache[path] = info
        return info
    v = vs[0]
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    rot = 0
    tags = v.get("tags", {}) or {}
    if "rotate" in tags:
        rot = int(float(tags["rotate"]))
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if abs(rot) % 180 == 90:
        w, h = h, w
    fr = v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1"
    try:
        n, dd = fr.split("/")
        fps = float(n) / float(dd) if float(dd) else 30.0
    except Exception:
        fps = 30.0
    if not fps or fps > 240:
        fps = 30.0
    dur = v.get("duration") or d.get("format", {}).get("duration") or 0
    pix = v.get("pix_fmt", "") or ""
    alpha = any(k in pix for k in ("yuva", "rgba", "argb", "bgra", "gbrap", "ya")) or (
        v.get("codec_name") in ("prores", "qtrle", "png") and "a" in pix)
    if v.get("codec_name") == "vp9" and (tags.get("alpha_mode") == "1" or tags.get("ALPHA_MODE") == "1"):
        alpha = True
    info = {"width": w, "height": h, "duration": float(dur), "fps": fps, "has_audio": bool(aus),
            "has_alpha": alpha, "rotation": rot, "kind": "video", "codec": v.get("codec_name")}
    _probe_cache[path] = info
    return info


# ---------------------------------------------------------------- geometry


def fit_size(sw, sh, bw, bh, mode):
    """Size of the source after fitting into a bw x bh box."""
    if mode in ("stretch", "fill"):
        return bw, bh
    if mode == "none":
        return sw, sh
    if mode == "width":
        return bw, max(1, round(sh * bw / sw))
    if mode == "height":
        return max(1, round(sw * bh / sh)), bh
    r_cover = max(bw / sw, bh / sh)
    r_contain = min(bw / sw, bh / sh)
    r = r_cover if mode == "cover" else r_contain
    return max(1, round(sw * r)), max(1, round(sh * r))


def crop_box_for(sw, sh, crop):
    if not crop:
        return 0, 0, sw, sh
    x, y, w, h = crop
    return int(round(x * sw)), int(round(y * sh)), max(2, int(round(w * sw))), max(2, int(round(h * sh)))


def even(n):
    n = int(round(n))
    return n + (n % 2)


# ---------------------------------------------------------------- images

_img_cache = collections.OrderedDict()


def load_image(path, box_w, box_h, fit="cover", focus=(0.5, 0.5), crop=None, oversample=1.0):
    key = (str(path), box_w, box_h, fit, tuple(focus), tuple(crop) if crop else None, oversample)
    if key in _img_cache:
        _img_cache.move_to_end(key)
        return _img_cache[key]
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGBA")
    if crop:
        im = im.crop(_xywh_to_box(crop_box_for(im.width, im.height, crop)))
    out = fit_image(im, box_w, box_h, fit, focus, oversample)
    _img_cache[key] = out
    if len(_img_cache) > 64:
        _img_cache.popitem(last=False)
    return out


def _xywh_to_box(b):
    x, y, w, h = b
    return (x, y, x + w, y + h)


def fit_image(im, box_w, box_h, fit="cover", focus=(0.5, 0.5), oversample=1.0):
    bw, bh = max(1, round(box_w * oversample)), max(1, round(box_h * oversample))
    if fit == "blur_fill":
        fw, fh = fit_size(im.width, im.height, bw, bh, "contain")
        fg = im.resize((fw, fh), Image.LANCZOS)
        cw, ch = fit_size(im.width, im.height, bw, bh, "cover")
        small = im.resize((max(1, cw // 8), max(1, ch // 8)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
        bg = small.resize((cw, ch), Image.BILINEAR)
        bg = _crop_focus(bg, bw, bh, (0.5, 0.5))
        bg = Image.blend(bg, Image.new("RGBA", bg.size, (0, 0, 0, 255)), 0.35)
        bg.alpha_composite(fg, ((bw - fw) // 2, (bh - fh) // 2))
        return bg
    fw, fh = fit_size(im.width, im.height, bw, bh, fit)
    im = im.resize((fw, fh), Image.LANCZOS) if (fw, fh) != im.size else im
    if fit == "cover":
        im = _crop_focus(im, bw, bh, focus)
    return im


def _crop_focus(im, bw, bh, focus):
    fx, fy = focus
    x0 = int(round((im.width - bw) * fx))
    y0 = int(round((im.height - bh) * fy))
    return im.crop((x0, y0, x0 + bw, y0 + bh))


# ---------------------------------------------------------------- video


class VideoReader:
    """Sequential frame reader for one layer.

    Source time for local time lt is in_point + speed*lt. Frames are sampled at `rate` frames per
    source-second. shutter>0 averages the frames covering the last `shutter` source-seconds
    (a real slow-shutter / long-exposure smear, not a fake blur).
    """

    def __init__(self, path, box_w, box_h, fit="cover", focus=(0.5, 0.5), crop=None, in_point=0.0,
                 speed=1.0, fps=30, max_src_dur=None, shutter=0.0, loop=True, reverse=False, oversample=1.0):
        self.path = str(path)
        self.info = probe(self.path)
        self.alpha = self.info["has_alpha"]
        self.fit = fit
        sw, sh = self.info["width"], self.info["height"]
        cx, cy, cw, ch = crop_box_for(sw, sh, crop)
        bw, bh = max(2, round(box_w * oversample)), max(2, round(box_h * oversample))
        mode = "contain" if fit == "blur_fill" else fit
        fw, fh = fit_size(cw, ch, bw, bh, mode)
        fw, fh = even(fw), even(fh)
        vf = []
        if crop:
            vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
        src_fps = self.info["fps"] or 30.0
        speed = abs(speed) or 1.0
        self.speed = speed
        self.shutter = shutter
        rate = min(fps / speed, max(src_fps, fps))
        if shutter > 0:
            rate = max(rate, min(src_fps, 60.0))
        self.rate = rate
        vf.append(f"fps={rate:.5f}")
        vf.append(f"scale={fw}:{fh}:flags=bicubic")
        if fit == "cover":
            ow, oh = min(even(bw), fw), min(even(bh), fh)
            x0 = int(round((fw - ow) * focus[0]))
            y0 = int(round((fh - oh) * focus[1]))
            vf.append(f"crop={ow}:{oh}:{max(0, x0)}:{max(0, y0)}")
            fw, fh = ow, oh
        self.w, self.h = fw, fh
        self.box = (bw, bh)
        self.channels = 4 if self.alpha else 3
        dur = self.info["duration"] or 0
        self.src_dur = dur
        self.in_point = min(max(0.0, in_point), max(0.0, dur - 0.1)) if dur else max(0.0, in_point)
        self.loop = loop
        self.reverse = reverse
        self.max_src_dur = max_src_dur
        self.vf = ",".join(vf)
        self.proc = None
        self.pos = -1
        self.n_loop = None
        n_hist = max(1, int(round(shutter * rate))) if shutter > 0 else 1
        self.hist = collections.deque(maxlen=n_hist)
        self.last = None
        self._start()

    def _start(self):
        self.close()
        cmd = ["ffmpeg", "-v", "error"]
        if self.in_point > 0:
            cmd += ["-ss", f"{self.in_point:.3f}"]
        if self.alpha and self.info.get("codec") == "vp9":
            cmd += ["-c:v", "libvpx-vp9"]
        cmd += ["-i", self.path]
        if self.max_src_dur and not self.loop:
            cmd += ["-t", f"{self.max_src_dur + 0.5:.3f}"]
        cmd += ["-an", "-vf", self.vf, "-f", "rawvideo", "-pix_fmt", "rgba" if self.alpha else "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
        self.pos = -1
        self.frame_bytes = self.w * self.h * self.channels

    def _read(self):
        buf = self.proc.stdout.read(self.frame_bytes) if self.proc else b""
        if len(buf) < self.frame_bytes:
            return None
        return np.frombuffer(buf, np.uint8).reshape(self.h, self.w, self.channels)

    def frame_index(self, lt):
        return int(math.floor(max(0.0, lt) * self.speed * self.rate + 1e-6))

    def _to_image(self, fr):
        im = Image.fromarray(fr, "RGBA" if self.channels == 4 else "RGB").convert("RGBA")
        if self.fit == "blur_fill":
            im = _blur_fill(im, *self.box)
        return im

    def get(self, lt):
        return self.get_source(max(0.0, lt) * self.speed)

    def get_source(self, src_t):
        """Frame at src_t seconds after the in-point (used directly by speed ramps)."""
        g = int(math.floor(max(0.0, src_t) * self.rate + 1e-6))
        if self.reverse:
            return self._get_reverse(g)
        target = g % self.n_loop if self.n_loop else g
        if target < self.pos:
            self._start()
            self.hist.clear()
        while self.pos < target:
            fr = self._read()
            if fr is None:
                if self.loop and self.n_loop is None and self.pos >= 1:
                    self.n_loop = self.pos + 1
                    target = g % self.n_loop
                    self._start()
                    continue
                break
            self.pos += 1
            self.last = fr
            if self.shutter > 0:
                self.hist.append(fr)
        if self.last is None:
            return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        if self.shutter > 0 and len(self.hist) > 1:
            fr = np.mean(np.stack(list(self.hist)).astype(np.float32), axis=0).clip(0, 255).astype(np.uint8)
        else:
            fr = self.last
        return self._to_image(fr)

    def _get_reverse(self, idx):
        if not hasattr(self, "_rev_frames"):
            frames = []
            limit = int((self.max_src_dur or 10.0) * self.rate) + 2
            while len(frames) < limit:
                fr = self._read()
                if fr is None:
                    break
                frames.append(fr)
            self._rev_frames = frames[::-1]
            self.close()
        fr = self._rev_frames
        if not fr:
            return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        return self._to_image(fr[min(idx, len(fr) - 1)])

    def close(self):
        if self.proc:
            try:
                self.proc.stdout.close()
            except Exception:
                pass
            self.proc.kill()
            self.proc.wait()
            self.proc = None


def _blur_fill(im, bw, bh):
    cw, ch = fit_size(im.width, im.height, bw, bh, "cover")
    small = im.resize((max(1, cw // 10), max(1, ch // 10)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    bg = small.resize((cw, ch), Image.BILINEAR)
    bg = _crop_focus(bg, bw, bh, (0.5, 0.5))
    bg = Image.blend(bg, Image.new("RGBA", bg.size, (0, 0, 0, 255)), 0.35)
    bg.alpha_composite(im, ((bw - im.width) // 2, (bh - im.height) // 2))
    return bg


def thumb(path, t=None, size=160):
    """Small RGB numpy thumbnail of an image/video at time t (default middle)."""
    if is_image(path):
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        im.thumbnail((size, size))
        return np.asarray(im)
    info = probe(path)
    if t is None:
        t = (info["duration"] or 0) / 2
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={size}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True)
    w = size
    n = len(out.stdout) // 3
    if n == 0:
        return np.zeros((size, size, 3), np.uint8)
    h = n // w
    return np.frombuffer(out.stdout[: w * h * 3], np.uint8).reshape(h, w, 3)
