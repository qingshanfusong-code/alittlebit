# 画框穿越 template (templates/frame_dive)

Built for Picasso (《缪斯》1935, 《坐着的裸女》1909–10, 《自画像》1907) — swap paintings/titles for any artist.

Files:
- `render.py` – the whole choreography. Edit `Assets.__init__` (which images, frame styles, crop for the
  out-of-frame pop), the wall colour `WALL`, the title strings, and the T_* constants (cut points).
  Work dir: env `PICASSO_WORK` or `templates/frame_dive/work/` containing `dl/`, `assets/`, `fonts/`.
- `assets.py` – `make_frame()` procedural carved frames (`gold`, `black`, `wood`, `silver`), `framed()`,
  `selfportrait_cutout()` = GrabCut from a hand-drawn polygon (write a new polygon for a new subject).
- `music.py` – original 96 BPM score aligned to the reference song's grid. Re-run after timing changes.

Commands:
```bash
python3 templates/frame_dive/assets.py cutout
python3 templates/frame_dive/music.py work/music.wav
python3 templates/frame_dive/render.py --sheet check.jpg --at 0.8,4.4,7.9,12
python3 templates/frame_dive/render.py --out out.mp4 --audio work/music.wav
```
Wall colour: pick the complement of painting 2 (blue wall for ochre portraits, red wall for blue night skies,
olive-yellow for pink/blue figures). Motion blur samples are set in `mb_samples()` – raise them if fast moves
show comb-like ghosting.

Using living paintings inside: render the loop with livepaint first, then in `Assets` load its frames and,
in `render()`, rebuild painting A's `Tex` from frame `int(t * 30) % n` (cost ~30 ms per frame).
