# What the reference edits do (measured)

Two Douyin edits by 墨尔温 MOERWEN (Van Gogh 《星月夜》/《向日葵》, and an AI sunflower-field painting),
both 16:9, ~14.5 s, same song (96 BPM, A major / F#m).

## The painting look ('细腻')
Compared with the museum photo of 《星月夜》:
- Strokes re-rendered as long, smooth, creamy ribbons; no canvas grain, no JPEG noise.
- Each stroke has volume: a soft highlight on one edge, slight shadow on the other (top-left light).
- Palette unified and high-key: yellows pushed to cream/pale lemon, whites creamy, shadows cooler but deep navy kept.
- Resolution: crisp at full 1080p even in close-ups (the edit zooms in to ~3x on the moon).

Our approximation: denoise → EDSR ×2/×4 → structure-tensor stroke direction → LIC smoothing along strokes
(+ mild shock sharpen) → impasto height from stroke-smoothed luminance detail → Blinn-Phong light → grade.

## The motion
Measured with dense optical flow after removing the global camera move (scripts/localmotion.py):
- 《星月夜》 sky: whole sky flows along the swirl directions, ~17 px per 0.25 s at 960 px width; the moon's
  rings rotate; the cypress and village move only with the camera (parallax), not by themselves.
- Collage (向日葵 + Van Gogh with violin): flower groups sway in opposite directions (left group →, right group ←),
  a few px per 0.25 s; the figure's bowing arm moves.
- Sunflower-field painting: field static; motion comes from elements entering (a figure dropping in,
  a small framed painting floating in 3D).

## The edit (画框穿越 template)
0–4 s painting full screen, slow push, small framed painting floats in 3D (visible frame thickness) →
4.05 s fast pull-back reveals the painting framed on a flat coloured wall (complementary colour) →
6.42 s whip pan to frame 2, subject pops out of the frame →
8.98 s frame 2 flies off rotating, cut-out elements rise from the bottom with overshoot, artist figure rises →
10.42 s title (condensed caps, small tracked subtitle) →
14.43 s cut back into a close-up of painting 1, zooming out to the opening framing (loop).
Audio grid: downbeats at 1.75 + 2.5k s; hit at 1.75, full silence 1.9–3.0, 808 glide, drop at 4.25.
Every big move starts ~0.2 s before a downbeat and lands on it.
