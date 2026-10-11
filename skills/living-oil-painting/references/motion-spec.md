# Motion spec reference

```json
{
  "loop": 6.0,
  "layers": [ { "type": "...", "region": {...}, ...params } ]
}
```
Coordinates are normalised (0..1). Speeds/amplitudes are in px at 1920 px output width (scaled automatically).
Layers apply in order: all `flow` layers (each composited by its mask), then the geometric layers
(`sway`, `ripple`, `breathe`) as one displacement, then `twinkle`.

## Regions
- `{"polys": [[[x,y], ...], ...], "not_polys": [...], "feather": 0.01}`
- `{"circle": [cx, cy, r], "feather": 0.02}` (r relative to width)
- `{"all": true}`
Feather 0.006–0.02. Exclude rigid objects that sit inside a moving area with `not_polys`.

## flow
| param | default | notes |
|---|---|---|
| `speed` | 18 | px/s. sky/clouds 25–40, swirling stars/moon 35–45, water 15–25, smoke 10–20, hills 8–14 |
| `period` | 2.0 | flow-map cycle. 1.0–1.5 s; `speed*period` > ~60 px starts to look liquid |
| `follow` | 0.85 | how much to trust the painting's own strokes vs the guide (0.3 for forced rotation) |
| `desync` | 0.35 | phase variation so the cross-fade does not pulse in sync (0.5 for big areas) |
| `guides` | dir 0° | give the unsigned stroke field a direction |

Guides:
- `{"type": "dir", "angle": 0, "weight": 0.6}` — 0 = right, 90 = down, -90 = up. Optional `region`.
- `{"type": "vortex", "center": [x, y], "radius": 0.1, "ccw": false, "inflow": 0}` — clockwise by default
  (on screen); `inflow` > 0 spirals inward. Use one per swirl, moon, star, whirlpool.

Spinning disc (moon, sun, star): an extra flow layer with `region.circle`, a vortex guide at the same centre,
`follow` 0.3–0.4, speed 35–45.

## sway
`amp` (px, 3–10), `period` (2–4 s), `anchor_y` (0..1, where the stems are rooted; 1 = bottom),
`height` (fraction of image height over which bending reaches full amplitude), `angle` (0 = horizontal sway),
`desync` (0.15 for one tree, 0.4 for a field of flowers).

## ripple
`amp` (1.5–4 px), `wavelength` (0.01–0.03 of width), `period` (1–2 s). Use on water under a horizon.

## breathe
`amp` 0.003–0.008, `center`. Gentle life for still lifes or portraits' background — never on faces.

## twinkle
`threshold` (luma 0.55–0.8: only bright pixels glow), `amp` (0.15–0.35), `glow` (px blur), `period`,
`color` in **BGR** 0..1 (warm lamp light ≈ [0.55, 0.85, 1.0], cool starlight ≈ [1.0, 0.95, 0.85]).

## Recipes
- 星空/夜景: sky flow + vortex per swirl/star + moon disc + twinkle; trees sway 3–5 px; windows twinkle warm.
- 海景/湖景: water flow (dir along waves, 15–20) + ripple; clouds flow 20–30 dir 0°; boats/sails sway 2–4 px.
- 麦田/花田: field sway (desync 0.4, amp 4–8, anchor at bottom of each band); clouds flow; sky slight flow.
- 印象派花园/睡莲: water flow slow 10–15 + ripple 1.5; flowers sway 2–3; light twinkle on highlights 0.12.
- 肖像/静物: no flow on the subject; background breathe 0.004 or a slow flow on drapery/background 6–10;
  candles/jewels twinkle. Keep faces and hands static.
- 抽象/立体主义: flow in colour fields along strokes 10–20, twinkle off; or keep still and animate via the edit.
