#!/usr/bin/env python3
"""Scan the user's footage so you can *see* it before planning the edit.

  python probe_media.py footage/ music/ -o media.json --sheet media_sheet.png
  python probe_media.py long_vlog.mp4 --shots          # also split long videos into shots

For every file: duration, resolution, orientation, fps, audio/alpha, brightness, saturation,
dominant colour, motion score, and (with --shots) internal shot boundaries + the most active moments.
The contact sheet(s) show 4 thumbnails per clip with its stats - open them with your image viewer/Read tool.
"""
import argparse
import colorsys
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import media  # noqa: E402

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus"}


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    out.append(os.path.join(root, f))
        else:
            out.append(p)
    keep = []
    for f in out:
        ext = os.path.splitext(f)[1].lower()
        if ext in media.IMAGE_EXT or ext in media.VIDEO_EXT or ext in AUDIO_EXT:
            keep.append(f)
    return keep


def sample_frames(path, dur, w=160):
    fps = 4.0 if dur <= 120 else max(0.2, 480.0 / dur)
    info = media.probe(path)
    h = max(2, int(round(w * info["height"] / max(1, info["width"]) / 2)) * 2)
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    n = len(r.stdout) // (w * h * 3)
    if n == 0:
        return np.zeros((0, h, w, 3), np.uint8), fps
    return np.frombuffer(r.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3), fps


def color_stats(arr):
    a = arr.reshape(-1, 3).astype(np.float32) / 255
    bright = float(a.mean())
    mx, mn = a.max(1), a.min(1)
    sat = float(np.mean((mx - mn) / np.maximum(mx, 1e-3)))
    # dominant colour via coarse histogram
    q = (a * 7.999).astype(int)
    keys = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    k = np.bincount(keys, minlength=512).argmax()
    dom = ((k // 64) + 0.5) / 8, ((k // 8 % 8) + 0.5) / 8, ((k % 8) + 0.5) / 8
    hexc = "#%02x%02x%02x" % tuple(int(x * 255) for x in dom)
    hue = float(colorsys.rgb_to_hsv(*[float(x) for x in a.mean(0)])[0])
    return float(bright), float(sat), hexc, hue


def analyze_video(path, info, want_shots):
    dur = info["duration"] or 0
    frames, fps = sample_frames(path, dur)
    res = {}
    if len(frames) == 0:
        return res, []
    b, s, hexc, hue = color_stats(frames[:: max(1, len(frames) // 12)])
    res.update({"brightness": round(b, 3), "saturation": round(s, 3), "dominant": hexc, "hue": round(hue, 3)})
    if len(frames) > 1:
        d = np.abs(np.diff(frames.astype(np.int16), axis=0)).mean(axis=(1, 2, 3))
        res["motion"] = round(float(np.median(d)), 2)
        if want_shots:
            thr = max(28.0, float(np.median(d) * 4))
            cuts = [0.0] + [round((i + 1) / fps, 2) for i, v in enumerate(d) if v > thr] + [round(dur, 2)]
            shots = []
            for a_, b_ in zip(cuts, cuts[1:]):
                if b_ - a_ < 0.3:
                    continue
                i0, i1 = int(a_ * fps), max(int(a_ * fps) + 1, int(b_ * fps))
                m = float(d[i0:max(i0 + 1, i1 - 1)].mean()) if i1 - 1 > i0 else 0.0
                shots.append({"start": a_, "end": b_, "motion": round(m, 2)})
            res["shots"] = shots
            # 1.5s windows with the most movement (good for fast cuts)
            win = max(1, int(1.5 * fps))
            if len(d) > win:
                cs = np.convolve(d, np.ones(win) / win, mode="valid")
                top = np.argsort(-cs)[:20]
                picks = []
                for i in top:
                    t = round(i / fps, 2)
                    if all(abs(t - p) > 2.0 for p in picks):
                        picks.append(t)
                    if len(picks) >= 5:
                        break
                res["active_moments"] = sorted(picks)
    idx = np.linspace(0, len(frames) - 1, 4).astype(int)
    thumbs = [Image.fromarray(frames[i]) for i in idx]
    return res, thumbs


def build_sheets(entries, out_path, rows_per_sheet=10):
    font = ImageFont.load_default()
    tw, th = 220, 124
    rows = []
    for e in entries:
        thumbs = e.pop("_thumbs", [])
        row = Image.new("RGB", (4 * (tw + 4) + 330, th + 8), (24, 24, 24))
        for i, im in enumerate(thumbs[:4]):
            im = im.copy()
            im.thumbnail((tw, th))
            row.paste(im, (330 + i * (tw + 4), 4 + (th - im.height) // 2))
        d = ImageDraw.Draw(row)
        lines = [os.path.basename(e["path"])[:44],
                 f"{e['kind']}  {e.get('width', '?')}x{e.get('height', '?')}  {e.get('orientation', '')}",
                 f"dur {e.get('duration') or '-'}s  fps {e.get('fps') or '-'}  audio {e.get('has_audio')}"
                 f"  alpha {e.get('has_alpha')}",
                 f"bright {e.get('brightness', '-')}  sat {e.get('saturation', '-')}  motion {e.get('motion', '-')}",
                 f"dominant {e.get('dominant', '-')}  shots {len(e.get('shots', [])) or '-'}"]
        for i, ln in enumerate(lines):
            d.text((8, 8 + i * 18), ln, fill=(235, 235, 235) if i else (255, 210, 0), font=font)
        if e.get("dominant"):
            d.rectangle((300, 8, 322, 30), fill=e["dominant"])
        rows.append(row)
    paths = []
    for k in range(0, len(rows), rows_per_sheet):
        chunk = rows[k:k + rows_per_sheet]
        sheet = Image.new("RGB", (chunk[0].width, sum(r.height + 2 for r in chunk)), (0, 0, 0))
        y = 0
        for r in chunk:
            sheet.paste(r, (0, y))
            y += r.height + 2
        p = out_path if len(rows) <= rows_per_sheet else out_path.replace(".png", f"_{k // rows_per_sheet + 1}.png")
        sheet.save(p)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out", default="media.json")
    ap.add_argument("--sheet", default="media_sheet.png")
    ap.add_argument("--shots", action="store_true", help="detect shots / active moments inside videos")
    a = ap.parse_args()
    files = collect(a.paths)
    if not files:
        sys.exit("no media files found")
    entries = []
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        try:
            info = media.probe(f)
        except Exception as ex:  # noqa
            print("skip", f, ex, file=sys.stderr)
            continue
        e = {"path": os.path.abspath(f), "kind": info["kind"] if ext not in AUDIO_EXT else "audio"}
        if e["kind"] == "audio":
            e["duration"] = round(info.get("duration") or 0, 2)
            entries.append(e)
            continue
        w, h = info["width"], info["height"]
        e.update({"width": w, "height": h, "orientation": "portrait" if h > w * 1.05 else "landscape" if w > h * 1.05
                  else "square", "has_alpha": info["has_alpha"], "has_audio": info["has_audio"]})
        if e["kind"] == "video":
            e.update({"duration": round(info["duration"], 2), "fps": round(info["fps"] or 0, 2)})
            res, thumbs = analyze_video(f, info, a.shots or (info["duration"] or 0) > 20)
            e.update(res)
            e["_thumbs"] = thumbs
        else:
            im = Image.open(f).convert("RGB")
            im.thumbnail((320, 320))
            b, s, hexc, hue = color_stats(np.asarray(im))
            e.update({"brightness": round(b, 3), "saturation": round(s, 3), "dominant": hexc, "hue": round(hue, 3)})
            e["_thumbs"] = [im]
        entries.append(e)
        print(f"{os.path.basename(f):40s} {e['kind']:5s} {e.get('orientation', ''):9s} "
              f"{e.get('duration', '')!s:>7s}s motion {e.get('motion', '-')!s:>6s} {e.get('dominant', '')}")
    visual = [e for e in entries if e["kind"] != "audio"]
    sheets = build_sheets(visual, a.sheet) if visual else []
    for e in entries:
        e.pop("_thumbs", None)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=1)
    n_land = sum(1 for e in visual if e.get("orientation") == "landscape")
    n_port = sum(1 for e in visual if e.get("orientation") == "portrait")
    total = sum(e.get("duration") or 0 for e in visual if e["kind"] == "video")
    print(f"\n{len(visual)} visual files ({n_land} landscape, {n_port} portrait), {total:.1f}s of video,"
          f" {sum(1 for e in entries if e['kind'] == 'audio')} audio files")
    print(f"json -> {a.out}")
    for s in sheets:
        print(f"sheet -> {s}")


if __name__ == "__main__":
    main()
