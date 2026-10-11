#!/usr/bin/env python3
"""Cut a subject out of its background -> PNG / MOV with alpha (for bg_swap, text-behind-subject, silhouettes).

  python make_cutout.py person.jpg -o person.png                 # AI matting (needs: pip install "rembg[cpu]")
  python make_cutout.py walk.mp4 -o walk_alpha.mov --fps 30      # per-frame, slow but works
  python make_cutout.py backlit.jpg -o sil.png --luma dark       # no AI: keep the dark subject on a bright sky
  python make_cutout.py greenscreen.mp4 -o key.mov --key "#00ff00"  # chroma key (e.g. 剪映 抠像 exported on green)

Without rembg, the two fallbacks (--luma / --key) need nothing extra. The render engine can also key on the
fly with the "chroma_key" / "luma_key" / "silhouette" effects, so a separate file is optional.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import fx, media  # noqa: E402


def get_remover():
    try:
        from rembg import new_session, remove  # noqa
    except Exception:
        return None
    sess = new_session("u2net_human_seg" if os.environ.get("CUTOUT_HUMAN") else "isnet-general-use")
    return lambda im: remove(im, session=sess)


def cut_image(im, args, remover):
    im = im.convert("RGBA")
    if args.key:
        return fx.chroma_key(im, {"color": args.key, "tolerance": args.tol, "softness": 0.08}, {})
    if args.luma:
        return _luma(im, args.luma, args.level)
    if remover is None:
        sys.exit("rembg is not installed. Options:\n"
                 "  pip install \"rembg[cpu]\"   (first run downloads a ~170MB model)\n"
                 "  or --luma dark|light for backlit silhouettes, or --key '#00ff00' for green screen\n"
                 "  or in 剪映/CapCut: 抠像 -> 智能抠像, put a pure green background, export, then use --key")
    return remover(im)


def _luma(im, mode, level):
    g = im.convert("L")
    lv = int(level * 255)
    if mode == "dark":
        a = g.point(lambda v: 255 if v < lv - 12 else 0 if v > lv + 12 else int((lv + 12 - v) * 255 / 24))
    else:
        a = g.point(lambda v: 255 if v > lv + 12 else 0 if v < lv - 12 else int((v - lv + 12) * 255 / 24))
    out = im.copy()
    out.putalpha(a)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--fps", type=float, default=None)
    ap.add_argument("--luma", choices=["dark", "light"], default=None)
    ap.add_argument("--level", type=float, default=0.45)
    ap.add_argument("--key", default=None, help="chroma key colour, e.g. '#00ff00'")
    ap.add_argument("--tol", type=float, default=0.3)
    ap.add_argument("--crop", action="store_true", help="crop image output to the subject bbox")
    a = ap.parse_args()
    remover = None if (a.luma or a.key) else get_remover()
    if media.is_image(a.input):
        out = cut_image(Image.open(a.input), a, remover)
        if a.crop:
            bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
            if bb:
                out = out.crop(bb)
        out.save(a.out)
        print("cutout ->", a.out, out.size)
        return
    info = media.probe(a.input)
    fps = a.fps or info["fps"] or 30
    tmp = tempfile.mkdtemp(prefix="cut_")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-i", a.input, "-vf", f"fps={fps}", os.path.join(tmp, "f%05d.png")],
                       check=True)
        frames = sorted(f for f in os.listdir(tmp) if f.startswith("f"))
        for i, f in enumerate(frames):
            p = os.path.join(tmp, f)
            cut_image(Image.open(p), a, remover).save(os.path.join(tmp, "c" + f[1:]))
            if i % 10 == 0:
                print(f"\r  {i + 1}/{len(frames)}", end="", file=sys.stderr, flush=True)
        print("", file=sys.stderr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", os.path.join(tmp, "c%05d.png"),
                        "-c:v", "png", "-pix_fmt", "rgba", a.out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("cutout video ->", a.out)


if __name__ == "__main__":
    main()
