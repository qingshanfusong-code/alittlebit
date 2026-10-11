#!/usr/bin/env python3
"""Detect tempo / beats / downbeats / onsets / drop of a music track (or a video's audio).

Usage:
  python beats.py music.mp3 -o beats.json
  python beats.py music.mp3 --start 42.5 --duration 20 -o beats.json   # only the section you will use
  python beats.py music.mp3 --bpm 128                                    # force tempo if detection is off by 2x

The JSON is consumed by render.py (spec "beats": "beats.json") so the edit spec can say
"b8" (9th beat), "d2" (3rd bar downbeat), "drop", or durations like "2b".
Beat times inside the JSON are relative to --start (i.e. relative to the music as it will play in the edit).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import audio  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("-o", "--out", default=None, help="output json (default: <path>.beats.json)")
    ap.add_argument("--start", type=float, default=None, help="music offset in seconds (section start)")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--bpm", type=float, default=None, help="force tempo")
    ap.add_argument("--meter", type=int, default=4)
    ap.add_argument("--librosa", action="store_true", help="use librosa beat tracker if installed")
    a = ap.parse_args()
    res = audio.analyze(a.path, start=a.start, duration=a.duration, bpm_hint=a.bpm, meter=a.meter,
                        use_librosa=a.librosa)
    out = a.out or (os.path.splitext(a.path)[0] + ".beats.json")
    audio.save(res, out)
    print(audio.summarize(res))
    print(f"first beats: {res['beats'][:8]}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
