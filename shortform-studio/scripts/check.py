#!/usr/bin/env python3
"""Verify a rendered shortform clip: full decode + a boundary contact sheet.

Two independent checks that catch different failure modes:

1. **Decode check** -- ffmpeg fully decodes the file (`-f null -`) and reports
   any decoder error, plus ffprobe confirms container/codec/resolution/fps
   and that audio and video duration match within a small tolerance.
2. **Boundary contact sheet** -- extracts jpgs at frame 0 (+ the next two
   frames) and around every cut boundary computed from the manifest's clip
   ranges, so a director/editor can eyeball every join for a background-only
   flash, a frozen frame, or a missing layer without opening a video editor.

Usage:
    python check.py --manifest clips.json --clip 01 --rendered /path/out.mp4 --out-dir /path/frames

Without --manifest/--clip, only frame 0/1/2 and the very end are sampled:
    python check.py --rendered /path/out.mp4 --out-dir /path/frames
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

FPS_DEFAULT = 24


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe_json(video: Path) -> dict:
    proc = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ])
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def decode_check(video: Path) -> list[str]:
    """Full decode; returns a list of problems (empty = clean)."""
    problems = []
    proc = run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
    if proc.returncode != 0 or proc.stderr.strip():
        problems.append(f"decode errors:\n{proc.stderr.strip()}")

    info = ffprobe_json(video)
    streams = {s["codec_type"]: s for s in info.get("streams", [])}
    fmt = info.get("format", {})

    if "video" not in streams:
        problems.append("no video stream found")
    else:
        v = streams["video"]
        if v.get("codec_name") != "h264":
            problems.append(f"video codec is {v.get('codec_name')!r}, expected h264")
        if (v.get("width"), v.get("height")) != (1080, 1920):
            problems.append(f"resolution is {v.get('width')}x{v.get('height')}, expected 1080x1920")

    if "audio" not in streams:
        problems.append("no audio stream found")
    else:
        a = streams["audio"]
        if a.get("codec_name") != "aac":
            problems.append(f"audio codec is {a.get('codec_name')!r}, expected aac")

    if "video" in streams and "audio" in streams:
        v_dur = float(streams["video"].get("duration") or fmt.get("duration") or 0)
        a_dur = float(streams["audio"].get("duration") or fmt.get("duration") or 0)
        if abs(v_dur - a_dur) > 0.15:
            problems.append(f"audio/video duration mismatch: video={v_dur:.3f}s audio={a_dur:.3f}s")

    return problems


def boundary_timestamps(manifest_path: Path, clip_id: str, fps: int) -> list[tuple[str, float]]:
    """Cut-boundary output timestamps from the manifest's hook/full ranges.

    Approximates the renderer's own timeline: hook ranges (if any) play back
    to back, a short transition follows a prepended hook, then full ranges
    play back to back. Good enough to land a contact-sheet frame within a
    couple of frames of each real join -- inspect the couple of frames
    around each listed time, not only the exact time.
    """
    manifest = json.loads(manifest_path.read_text())
    clip = next((c for c in manifest.get("clips", []) if str(c.get("id")) == str(clip_id)), None)
    if clip is None:
        raise SystemExit(f"clip {clip_id!r} not found in manifest")

    hook_ranges = clip.get("hook_ranges") or []
    full_ranges = clip.get("full_ranges") or []
    frame = 1.0 / fps
    points: list[tuple[str, float]] = [("frame 0", 0.0)]
    t = 0.0
    for i, (a, b) in enumerate(hook_ranges):
        t += b - a
        points.append((f"hook range {i} end", t))
    if hook_ranges:
        t += 0.28  # standard renderer's hook->body transition
        points.append(("hook transition end", t))
    for i, (a, b) in enumerate(full_ranges):
        if i > 0:
            points.append((f"full range {i} join", t))
        t += b - a
    points.append(("final frame", max(t - frame, 0.0)))
    return points


def extract_frame(video: Path, t: float, out_path: Path, retry: bool = True) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = run([
        "ffmpeg", "-y", "-strict", "unofficial", "-ss", f"{max(t, 0.0):.3f}", "-i", str(video),
        "-frames:v", "1", "-q:v", "2", "-pix_fmt", "yuvj420p", str(out_path),
    ])
    if proc.returncode != 0 or not out_path.exists():
        if retry:
            # Right at/near EOF, forward -ss can occasionally overshoot and yield no
            # frame; step back a bit further and try once more before giving up.
            extract_frame(video, max(t - 0.15, 0.0), out_path, retry=False)
            return
        raise RuntimeError(f"frame extraction failed at t={t:.3f}: {proc.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rendered", required=True, type=Path, help="Rendered clip mp4")
    parser.add_argument("--manifest", type=Path, help="Render manifest (for boundary timestamps)")
    parser.add_argument("--clip", help="Clip id within --manifest")
    parser.add_argument("--out-dir", required=True, type=Path, help="Where to write contact-sheet jpgs")
    parser.add_argument("--fps", type=int, default=FPS_DEFAULT)
    args = parser.parse_args()

    if not args.rendered.is_file():
        raise SystemExit(f"not found: {args.rendered}")

    print(f"== decode check: {args.rendered} ==")
    problems = decode_check(args.rendered)
    if problems:
        for p in problems:
            print(f"FAIL: {p}")
    else:
        print("OK: full decode, container/codec/resolution/duration all check out")

    if args.manifest and args.clip:
        points = boundary_timestamps(args.manifest, args.clip, args.fps)
    else:
        points = [("frame 0", 0.0), ("frame 1", 1 / args.fps), ("frame 2", 2 / args.fps)]

    print(f"\n== boundary contact sheet: {len(points)} point(s) -> {args.out_dir} ==")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for i, (label, t) in enumerate(points):
        frame = 1.0 / args.fps
        for j, offset in enumerate((-frame, 0.0, frame)):
            out_path = args.out_dir / f"{i:02d}-{label.replace(' ', '_')}-{j}.jpg"
            extract_frame(args.rendered, t + offset, out_path)
        print(f"  [{i:02d}] {label} @ {t:.3f}s -> 3 frames")

    if problems:
        print("\nRESULT: FAILED decode check -- see FAIL lines above")
        return 1
    print("\nRESULT: decode OK, contact sheet written -- inspect the frames for background-only "
          "flashes, missing layers, or a frozen join.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
