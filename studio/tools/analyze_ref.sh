#!/usr/bin/env bash
# 学习新的参考视频（风格学习用，一次性成本）：
#   bash tools/analyze_ref.sh 参考视频.mp4 [输出目录]
# 产出：
#   sheet_*.jpg  每秒 1 帧的联系表（每张 15 帧，约 1.5k token/张——给 Claude 看这个，不要看原视频）
#   spec.png     音频频谱（看有没有人声、BGM 段落、音效位置）
#   audio.txt    响度/静音段
# 录屏素材会自动裁掉黑边。
set -euo pipefail
in="$1"; out="${2:-ref_$(basename "${in%.*}")}"
mkdir -p "$out"
crop=$(ffmpeg -v info -ss 3 -i "$in" -t 3 -vf cropdetect=24:2:0 -f null - 2>&1 | grep -o 'crop=[0-9:]*' | tail -1 || true)
vf="${crop:+$crop,}fps=1,scale=520:-2,tile=3x5:padding=4:color=red"
ffmpeg -v error -y -i "$in" -vf "$vf" "$out/sheet_%d.jpg"
ffmpeg -v error -y -i "$in" -lavfi "showspectrumpic=s=1400x300:legend=1:scale=log:fscale=log" "$out/spec.png" || true
{
  echo "== 时长/分辨率"; ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of compact "$in"
  echo "== 响度"; ffmpeg -hide_banner -i "$in" -af ebur128 -f null - 2>&1 | grep -E "^\s+(I|LRA):" || true
  echo "== 静音段(<-40dB, >0.3s)"; ffmpeg -hide_banner -i "$in" -af silencedetect=n=-40dB:d=0.3 -f null - 2>&1 | grep -oE "silence_(start|end): [0-9.]+" | tr '\n' ' ' || true
  echo; echo "== 画面切换点(场景变化>0.3)"; ffmpeg -hide_banner -i "$in" -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep -oE "pts_time:[0-9.]+" | tr '\n' ' ' || true
  echo
} > "$out/audio.txt"
ls "$out"
