#!/usr/bin/env python3
"""Reverse-engineer a reference edit (a Douyin/TikTok download or screen recording).

  python analyze_reference.py ref.mp4 --out ref_report     # -> ref_report.json + ref_report_sheet.png

Reports: content area (strips phone UI bars / letterbox), shot boundaries, shot-length stats and how
the cutting rate changes over time, music tempo, how many cuts land on beats / half beats, per-shot
colour + motion, and a contact sheet with one frame per shot labelled with time and beat number.
Use it to learn a NEW style the user shows you, then map what you find onto the techniques in
references/techniques.md.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import audio, media  # noqa: E402


def decode(path, w=192, fps=None):
    info = media.probe(path)
    h = max(2, int(round(w * info["height"] / info["width"] / 2)) * 2)
    vf = f"scale={w}:{h}" if not fps else f"fps={fps},scale={w}:{h}"
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    n = len(r.stdout) // (w * h * 3)
    return np.frombuffer(r.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3), info


def content_box(frames):
    """Find the region that actually changes (ignores static UI overlays / bars)."""
    sd = frames[:: max(1, len(frames) // 60)].astype(np.float32).std(axis=0).mean(axis=2)
    act = sd > max(6.0, np.percentile(sd, 60) * 0.35)
    cols = np.where(act.mean(axis=0) > 0.25)[0]
    rows = np.where(act.mean(axis=1) > 0.25)[0]
    H, W = sd.shape
    if len(cols) < W * 0.2 or len(rows) < H * 0.2:
        return 0, 0, W, H
    return int(cols[0]), int(rows[0]), int(cols[-1] + 1), int(rows[-1] + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", default=None, help="output prefix")
    ap.add_argument("--threshold", type=float, default=None, help="cut threshold (mean abs diff, 0-255)")
    a = ap.parse_args()
    prefix = a.out or os.path.splitext(a.video)[0] + "_ref"
    frames, info = decode(a.video)
    fps = info["fps"] or 30
    n = len(frames)
    if n < 3:
        sys.exit("could not decode video")
    x0, y0, x1, y1 = content_box(frames)
    fr = frames[:, y0:y1, x0:x1].astype(np.int16)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))
    # histogram distance catches cuts between similar-brightness shots
    hists = np.stack([np.histogram(f[..., c], bins=16, range=(0, 255))[0] for f in fr[:, ::2, ::2]
                      for c in range(3)]).reshape(n, 48).astype(np.float32)
    hists /= hists.sum(1, keepdims=True) + 1e-9
    hd = np.abs(np.diff(hists, axis=0)).sum(1) * 100
    score = d + hd * 0.6
    thr = a.threshold or max(22.0, float(np.median(score) * 3.5))
    cut_idx = [i + 1 for i, v in enumerate(score) if v > thr]
    # merge cuts closer than 2 frames
    cuts = []
    for c in cut_idx:
        if not cuts or c - cuts[-1] > 1:
            cuts.append(c)
    times = [0.0] + [round(c / fps, 3) for c in cuts] + [round(n / fps, 3)]
    shots = []
    for s, e in zip(times, times[1:]):
        i0, i1 = int(s * fps), max(int(s * fps) + 1, int(e * fps))
        seg = fr[i0:i1]
        mot = float(np.abs(np.diff(seg, axis=0)).mean()) if len(seg) > 1 else 0.0
        mean = seg.reshape(-1, 3).mean(0)
        shots.append({"start": s, "end": e, "len": round(e - s, 3), "motion": round(mot, 2),
                      "brightness": round(float(mean.mean() / 255), 3),
                      "color": "#%02x%02x%02x" % tuple(int(v) for v in mean)})
    lens = np.array([s["len"] for s in shots])
    dur = n / fps
    # cutting rate per 2-second window
    rate = []
    for w0 in np.arange(0, dur, 2.0):
        k = sum(1 for c in times[1:-1] if w0 <= c < w0 + 2.0)
        rate.append(round(k / 2.0, 2))
    rep = {"video": a.video, "duration": round(dur, 2), "fps": round(fps, 2),
           "frame": [info["width"], info["height"]],
           "content_box_frac": [round(x0 / frames.shape[2], 3), round(y0 / frames.shape[1], 3),
                                round((x1 - x0) / frames.shape[2], 3), round((y1 - y0) / frames.shape[1], 3)],
           "n_shots": len(shots), "shot_len_median": round(float(np.median(lens)), 3),
           "shot_len_min": round(float(lens.min()), 3), "shot_len_max": round(float(lens.max()), 3),
           "cuts_per_sec_by_2s_window": rate, "shots": shots}
    if info.get("has_audio"):
        try:
            ar = audio.analyze(a.video)
            b = np.array(ar["beats"])
            bi = ar["beat_interval"]
            cut_t = np.array(times[1:-1])
            if len(b) and len(cut_t):
                dist = np.min(np.abs(cut_t[:, None] - b[None, :]), axis=1)
                half = np.concatenate([b, b[:-1] + np.diff(b) / 2])
                dist_h = np.min(np.abs(cut_t[:, None] - half[None, :]), axis=1)
                tol = max(0.06, 1.5 / fps)
                rep["music"] = {"bpm": ar["bpm"], "beat_interval": bi, "drop": ar["drop"],
                                "cuts_on_beat_pct": round(float(np.mean(dist < tol) * 100), 1),
                                "cuts_on_half_beat_pct": round(float(np.mean(dist_h < tol) * 100), 1),
                                "median_shot_in_beats": round(float(np.median(lens) / bi), 2)}
                for s in shots:
                    s["beat"] = round(float(np.interp(s["start"], b, np.arange(len(b)))), 2)
        except Exception as ex:  # noqa
            rep["music_error"] = str(ex)
    with open(prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    # contact sheet: middle frame of each shot (cap 48)
    full, _ = decode(a.video, w=320)
    fx0, fy0 = int(x0 * 320 / frames.shape[2]), int(y0 * full.shape[1] / frames.shape[1])
    fx1, fy1 = int(x1 * 320 / frames.shape[2]), int(y1 * full.shape[1] / frames.shape[1])
    pick = shots if len(shots) <= 48 else [shots[int(i)] for i in np.linspace(0, len(shots) - 1, 48)]
    thumbs = []
    font = ImageFont.load_default()
    for s in pick:
        i = min(len(full) - 1, int((s["start"] + s["end"]) / 2 * fps))
        im = Image.fromarray(full[i, fy0:fy1, fx0:fx1])
        im.thumbnail((240, 240))
        canvas = Image.new("RGB", (240, im.height + 16), (20, 20, 20))
        canvas.paste(im, ((240 - im.width) // 2, 16))
        lab = f"{s['start']:.2f}s +{s['len']:.2f}" + (f" b{s['beat']}" if "beat" in s else "")
        ImageDraw.Draw(canvas).text((3, 2), lab, fill=(255, 210, 0), font=font)
        thumbs.append(canvas)
    if thumbs:
        cols = 6
        th = max(t.height for t in thumbs)
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 244, rows * (th + 4)), (0, 0, 0))
        for k, t in enumerate(thumbs):
            sheet.paste(t, ((k % cols) * 244, (k // cols) * (th + 4)))
        sheet.save(prefix + "_sheet.png")
    print(f"duration {rep['duration']}s, {rep['n_shots']} shots, median shot {rep['shot_len_median']}s "
          f"(min {rep['shot_len_min']}, max {rep['shot_len_max']})")
    print("cuts/sec per 2s window:", rate)
    if "music" in rep:
        m = rep["music"]
        print(f"music ~{m['bpm']} BPM; {m['cuts_on_beat_pct']}% of cuts on a beat, {m['cuts_on_half_beat_pct']}% on "
              f"half-beats; median shot = {m['median_shot_in_beats']} beats; drop {m['drop']}")
    print(f"report -> {prefix}.json   sheet -> {prefix}_sheet.png")


if __name__ == "__main__":
    main()
