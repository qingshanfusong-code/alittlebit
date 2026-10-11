#!/usr/bin/env python3
"""Render an edit spec (JSON) to mp4, or to preview stills / a contact sheet.

  python render.py edit.json -o out.mp4                 # final render
  python render.py edit.json -o draft.mp4 --preview 0.5 # half resolution, much faster
  python render.py edit.json --sheet sheet.png          # 12 evenly spaced frames in one image (check layout!)
  python render.py edit.json --sheet sheet.png --at b0,b4,b8,drop   # frames at specific beats/times
  python render.py edit.json --still 2.5,4 --prefix shot           # full-size PNG stills
  python render.py edit.json --plan                     # print the expanded timeline (debug macros/timing)
  python render.py edit.json -o part.mp4 --from 4 --to 8  # render a time range

Spec format: see references/spec.md. Relative paths in the spec resolve against the spec's folder.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import compositor  # noqa: E402
from engine.util import parse_time  # noqa: E402


def describe(L, depth=0):
    src = L["source"]
    kind = next((k for k in compositor.SOURCE_KEYS if k in src), "?")
    what = src.get(kind)
    if kind in ("video", "image"):
        what = os.path.basename(str(what))
        if kind == "video" and src.get("in"):
            what += f" @{src['in']}s"
    elif kind == "group":
        what = f"{len(src.get('_layers', []))} layers"
    elif kind == "text":
        what = repr(str(what)[:30])
    extras = []
    for k in ("enter", "exit"):
        if L.get(k):
            v = L[k]
            extras.append(f"{k}:{v['type'] if isinstance(v, dict) else v}")
    if L.get("anim"):
        a = L["anim"] if isinstance(L["anim"], list) else [L["anim"]]
        extras.append("anim:" + ",".join(x if isinstance(x, str) else x.get("name", "?") for x in a))
    if L.get("effects"):
        extras.append("fx:" + ",".join(e if isinstance(e, str) else e.get("type", "?") for e in L["effects"]))
    if L.get("mask"):
        m = L["mask"]
        extras.append("mask:" + (m.get("type", "?") if isinstance(m, dict) else "multi"))
    if L.get("blend"):
        extras.append("blend:" + L["blend"])
    line = f"{'  ' * depth}{L['id']:>10s} {L['start']:7.2f}-{L['end']:7.2f}s  {kind:6s} {what}  {' '.join(extras)}"
    out = [line]
    if kind == "group":
        for c in src.get("_layers", []):
            out += describe(c, depth + 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--out")
    ap.add_argument("--preview", type=float, default=1.0, help="resolution scale, e.g. 0.5")
    ap.add_argument("--sheet", help="write a contact sheet PNG instead of a video")
    ap.add_argument("--n", type=int, default=12, help="frames in the contact sheet")
    ap.add_argument("--at", help="comma list of times / beat refs for --sheet or --still")
    ap.add_argument("--still", help="comma list of times / beat refs -> full-size PNGs")
    ap.add_argument("--prefix", default="still")
    ap.add_argument("--plan", action="store_true", help="print expanded layers and exit")
    ap.add_argument("--from", dest="t0", default=None)
    ap.add_argument("--to", dest="t1", default=None)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--speed", default="medium", help="x264 preset (ultrafast..slow)")
    ap.add_argument("--base", default=None, help="folder that relative media paths resolve against "
                                                 "(default: the spec's folder)")
    a = ap.parse_args()

    ctx = compositor.load_spec(a.spec, base_dir=os.path.abspath(a.base) if a.base else None, preview=a.preview)
    for w in ctx.warnings:
        print("WARNING:", w, file=sys.stderr)
    bm = ctx.bm
    print(f"canvas {ctx.W}x{ctx.H} @{ctx.fps:g}fps  duration {ctx.duration:.2f}s  layers {len(ctx.layers)}"
          + (f"  beat {bm.interval:.3f}s" if bm.has_music else "  (no beats loaded: 1b = 0.5s)"))
    if a.plan:
        for L in ctx.layers:
            print("\n".join(describe(L)))
        return
    if a.sheet or a.still:
        if a.at or a.still:
            refs = (a.still or a.at).split(",")
            times = [min(max(0.0, parse_time(r.strip(), bm)), ctx.duration - 1e-3) for r in refs if r.strip()]
        else:
            n = max(1, a.n)
            times = [(i + 0.5) * ctx.duration / n for i in range(n)]
        t = time.time()
        if a.sheet:
            compositor.render_sheet(ctx, times, a.sheet)
            print(f"sheet -> {a.sheet}  ({time.time() - t:.1f}s)")
        else:
            for p in compositor.render_stills(ctx, times, a.prefix):
                print("still ->", p)
        return
    if not a.out:
        ap.error("-o/--out is required for video output")
    t0 = parse_time(a.t0, bm) if a.t0 is not None else 0.0
    t1 = parse_time(a.t1, bm) if a.t1 is not None else None
    t = time.time()
    compositor.render_video(ctx, a.out, t0, t1, crf=a.crf, preset=a.speed)
    print(f"video -> {a.out}  ({time.time() - t:.1f}s)")


if __name__ == "__main__":
    main()
