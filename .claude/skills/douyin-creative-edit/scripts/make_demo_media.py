#!/usr/bin/env python3
"""Generate synthetic demo media (clips, photos, cut-outs, a 120 BPM track with a drop) so the engine and the
examples can be tested anywhere without real footage.

  python make_demo_media.py demo/
  python render.py ../examples/poster_typography.json --base demo/ --sheet check.png --preview 0.5
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import audio  # noqa: E402

CLIPS = [  # name, lavfi source, size
    ("c1", "gradients=s={s}:c0=0xff6b35:c1=0x1d3f6e:x0=0:y0=0:x1={w}:y1={h}:speed=0.03:d=4", "1280x720"),
    ("c2", "gradients=s={s}:c0=0x2ec4b6:c1=0xf7f7f2:c2=0x011627:n=3:speed=0.05:d=4", "1280x720"),
    ("c3", "mandelbrot=s={s}:rate=30:end_scale=0.02,trim=duration=4", "1280x720"),
    ("c4", "life=s={s}:mold=10:r=30:ratio=0.12:death_color=#1a1a2e:life_color=#e94560,"
           "scale=1280:720:flags=neighbor,trim=duration=4", "320x180"),
    ("c5", "gradients=s={s}:c0=0xf4c430:c1=0xb5222b:speed=0.08:d=4", "1280x720"),
    ("c6", "cellauto=s={s}:rule=110:rate=30,scale=1280:720:flags=neighbor,trim=duration=4", "320x180"),
    ("c7", "gradients=s={s}:c0=0x8338ec:c1=0x3a86ff:c2=0xff006e:n=3:speed=0.06:d=4", "720x1280"),
    ("c8", "testsrc2=s={s}:r=30,hue=s=0.4,trim=duration=4", "1280x720"),
]


def make_clips(out):
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)
    for name, src, size in CLIPS:
        w, h = size.split("x")
        lav = src.format(s=size, w=w, h=h)
        # add a moving bright bar so every clip has motion + a 'subject'
        vf = "format=yuv420p"
        if "gradients" in src:
            vf = ("drawbox=x='mod(t*420,iw)':y=ih*0.35:w=iw*0.08:h=ih*0.3:color=white@0.85:t=fill,"
                  "format=yuv420p")
        p = os.path.join(out, "clips", f"{name}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", lav, "-t", "4", "-r", "30", "-vf", vf,
                        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast", p], check=True)


def make_photos(out):
    os.makedirs(os.path.join(out, "photos"), exist_ok=True)
    palettes = [("#ffb36b", "#6a2c70", "#2b1b3d"), ("#a8dadc", "#457b9d", "#1d3557"), ("#ffd6a5", "#f08080", "#3d405b"),
                ("#d8f3dc", "#52b788", "#081c15"), ("#fde2e4", "#e5989b", "#6d6875"), ("#e9c46a", "#e76f51", "#264653")]
    for i, (sky, mid, ground) in enumerate(palettes):
        W, H = 1600, 1066 if i % 3 else 2000
        im = Image.new("RGB", (W, H), sky)
        d = ImageDraw.Draw(im)
        for y in range(H):
            f = y / H
            c1 = tuple(int(sky[k:k + 2], 16) for k in (1, 3, 5))
            c2 = tuple(int(mid[k:k + 2], 16) for k in (1, 3, 5))
            d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * f) for a, b in zip(c1, c2)))
        d.ellipse((W * 0.62, H * 0.18, W * 0.78, H * 0.18 + W * 0.16), fill="#fff4d6")
        rng = np.random.default_rng(i)
        pts = [(0, H)] + [(x, H * 0.62 - rng.random() * H * 0.25) for x in np.linspace(0, W, 9)] + [(W, H)]
        d.polygon(pts, fill=ground)
        d.rectangle((0, H * 0.82, W, H), fill=ground)
        im.save(os.path.join(out, "photos", f"p{i + 1}.jpg"), quality=90)


def make_cutouts(out):
    os.makedirs(os.path.join(out, "cutouts"), exist_ok=True)
    W, H = 1200, 1200
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(80, 1200), (150, 980), (330, 900), (620, 880), (900, 930), (1080, 1010), (1150, 1200)],
              fill=(92, 78, 66, 255))
    d.ellipse((560, 560, 660, 670), fill=(25, 22, 24, 255))
    d.rounded_rectangle((520, 660, 700, 900), radius=50, fill=(30, 28, 32, 255))
    d.rounded_rectangle((470, 860, 740, 920), radius=25, fill=(35, 33, 38, 255))
    im.filter(ImageFilter.GaussianBlur(1.2)).save(os.path.join(out, "cutouts", "person_on_rock.png"))
    # a standing figure (for silhouettes)
    im = Image.new("RGBA", (500, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((190, 40, 310, 170), fill=(40, 40, 40, 255))
    d.rounded_rectangle((160, 170, 340, 640), radius=60, fill=(40, 40, 40, 255))
    d.rounded_rectangle((170, 600, 245, 1160), radius=35, fill=(40, 40, 40, 255))
    d.rounded_rectangle((255, 600, 330, 1160), radius=35, fill=(40, 40, 40, 255))
    d.rounded_rectangle((110, 190, 165, 600), radius=28, fill=(40, 40, 40, 255))
    d.rounded_rectangle((335, 190, 390, 600), radius=28, fill=(40, 40, 40, 255))
    im.save(os.path.join(out, "cutouts", "figure.png"))
    # a product-like object (bottle)
    im = Image.new("RGBA", (600, 1100), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((90, 300, 510, 1080), radius=70, fill=(236, 222, 196, 255))
    d.rectangle((230, 120, 370, 310), fill=(200, 170, 110, 255))
    d.rounded_rectangle((200, 40, 400, 140), radius=20, fill=(30, 30, 30, 255))
    d.rectangle((150, 560, 450, 760), fill=(120, 30, 40, 255))
    im.save(os.path.join(out, "cutouts", "bottle.png"))


def make_music(out, bpm=120.0, dur=24.0, drop=8.0):
    sr = 44100
    n = int(sr * dur)
    t = np.arange(n) / sr
    y = np.zeros(n)
    bi = 60 / bpm
    first = 0.25

    def add(at, sig):
        s = int(at * sr)
        e = min(n, s + len(sig))
        if s < n:
            y[s:e] += sig[: e - s]

    k = 0
    while first + k * bi < dur:
        at = first + k * bi
        loud = 1.0 if at >= drop else 0.45
        L = int(0.18 * sr)
        tt = np.arange(L) / sr
        kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 18) * loud
        add(at, kick)
        if k % 2 == 1:
            Ls = int(0.12 * sr)
            add(at, np.random.default_rng(k).normal(0, 0.35, Ls) * np.exp(-np.arange(Ls) / sr * 30) * loud)
        Lh = int(0.03 * sr)
        add(at + bi / 2, np.random.default_rng(1000 + k).normal(0, 0.12, Lh) * np.exp(-np.arange(Lh) / sr * 120))
        k += 1
    chords = [220.0, 174.6, 261.6, 196.0]
    for i, f in enumerate(chords * int(dur / (4 * bi * len(chords)) + 2)):
        at = first + i * 4 * bi
        if at >= dur:
            break
        L = int(4 * bi * sr)
        tt = np.arange(L) / sr
        amp = 0.16 if at >= drop else 0.08
        pad = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.5 * tt)) * amp * np.minimum(1, tt * 8)
        add(at, pad)
    y = y / (np.abs(y).max() + 1e-9) * 0.85
    p = os.path.join(out, "music.wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    res = audio.analyze(p)
    audio.save(res, os.path.join(out, "music.beats.json"))
    print(audio.summarize(res))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "demo"
    os.makedirs(out, exist_ok=True)
    make_clips(out)
    make_photos(out)
    make_cutouts(out)
    make_music(out)
    print(f"demo media -> {os.path.abspath(out)}")


if __name__ == "__main__":
    main()
