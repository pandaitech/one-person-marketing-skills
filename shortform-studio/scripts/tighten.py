#!/usr/bin/env python3
"""Suggest retained source ranges by measuring long internal silences.

This is an editorial aid. Review every proposed removal against the transcript.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path


def parse_time(value: str) -> float:
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError(f"Invalid timestamp: {value}")
    numbers = [float(part) for part in parts]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]


def format_time(seconds: float) -> str:
    total = int(math.floor(max(0, seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int(round((seconds - math.floor(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def detect(
    video: Path, start: float, end: float, noise: str, minimum: float
) -> list[tuple[float, float]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{end - start:.3f}",
        "-i",
        str(video),
        "-vn",
        "-af",
        f"silencedetect=noise={noise}:d={minimum:.3f}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)]
    return [(start + a, start + b) for a, b in zip(starts, ends) if b > a]


def retained_ranges(
    start: float,
    end: float,
    silences: list[tuple[float, float]],
    room_tone: float,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    retained: list[tuple[float, float]] = []
    removed: list[tuple[float, float]] = []
    cursor = start
    for silence_start, silence_end in silences:
        remove_start = min(silence_end, silence_start + room_tone)
        remove_end = max(silence_start, silence_end - room_tone)
        if remove_end <= remove_start:
            continue
        if remove_start > cursor:
            retained.append((cursor, remove_start))
        removed.append((remove_start, remove_end))
        cursor = remove_end
    if cursor < end:
        retained.append((cursor, end))
    return retained, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--start", type=parse_time, required=True)
    parser.add_argument("--end", type=parse_time, required=True)
    parser.add_argument("--minimum", type=float, default=1.1)
    parser.add_argument("--room-tone", type=float, default=0.12)
    parser.add_argument("--noise", default="-35dB")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video = args.video.expanduser().resolve()
    if not video.exists():
        raise FileNotFoundError(video)
    if args.end <= args.start:
        raise ValueError("--end must be greater than --start")
    if args.minimum <= 0 or args.room_tone < 0:
        raise ValueError("Silence and room-tone values must be non-negative")

    silences = detect(video, args.start, args.end, args.noise, args.minimum)
    retained, removed = retained_ranges(args.start, args.end, silences, args.room_tone)
    payload = {
        "source": str(video),
        "input_range": [args.start, args.end],
        "minimum_silence": args.minimum,
        "room_tone": args.room_tone,
        "removed_silences": [[round(a, 3), round(b, 3)] for a, b in removed],
        "retained_ranges": [[round(a, 3), round(b, 3)] for a, b in retained],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Review these silence removals against the transcript:\n")
        for start, end in removed:
            print(f"remove {format_time(start)}-{format_time(end)} ({end - start:.2f}s)")
        print("\nSuggested retained ranges for the manifest:\n")
        for start, end in retained:
            print(f"[{start:.3f}, {end:.3f}],  # {format_time(start)}-{format_time(end)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
