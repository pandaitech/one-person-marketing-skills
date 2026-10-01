#!/usr/bin/env python3
"""Build a renderer-compatible absolute word timeline with local Whisper.cpp."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_time(value: str) -> float:
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError(f"Invalid timestamp: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid timestamp: {value}") from exc
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def media_duration(media: Path) -> float:
    value = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        text=True,
    ).strip()
    return float(value)


def merge_tokens(payload: dict, source_offset: float) -> list[dict]:
    transcription = payload.get("transcription")
    if not isinstance(transcription, list) or not transcription:
        raise ValueError("Whisper.cpp JSON contains no transcription entries")

    words: list[dict] = []
    for segment in transcription:
        tokens = segment.get("tokens") if isinstance(segment, dict) else None
        if not isinstance(tokens, list):
            continue
        current: dict | None = None
        for token in tokens:
            if not isinstance(token, dict):
                continue
            raw = str(token.get("text", ""))
            offsets = token.get("offsets")
            if not raw or raw.startswith("[_") or not isinstance(offsets, dict):
                continue
            if "from" not in offsets or "to" not in offsets:
                continue
            start = source_offset + float(offsets["from"]) / 1000
            end = source_offset + float(offsets["to"]) / 1000
            if raw[:1].isspace() or current is None:
                if current:
                    words.append(current)
                current = {
                    "word": raw.strip(),
                    "start": start,
                    "end": end,
                    "scores": [float(token.get("p", 0.0))],
                }
            else:
                current["word"] += raw
                current["end"] = max(float(current["end"]), end)
                current["scores"].append(float(token.get("p", 0.0)))
        if current:
            words.append(current)

    return [word for word in words if str(word["word"]).strip()]


def repair_invalid_durations(words: list[dict]) -> int:
    repaired = 0
    for index, word in enumerate(words):
        if float(word["end"]) > float(word["start"]):
            continue
        center = float(word["start"])
        previous_end = float(words[index - 1]["end"]) if index else center - 0.12
        next_start = (
            float(words[index + 1]["start"])
            if index + 1 < len(words)
            else center + 0.12
        )
        word["start"] = max(previous_end, center - 0.12)
        word["end"] = max(float(word["start"]) + 0.04, min(next_start, center + 0.12))
        repaired += 1
    return repaired


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path, help="Original recording or audio file")
    parser.add_argument("--model", type=Path, required=True, help="Multilingual GGML model")
    parser.add_argument("--output", type=Path, required=True, help="Destination JSON")
    parser.add_argument("--language", default="ms")
    parser.add_argument("--start", type=parse_time, default=0.0)
    parser.add_argument("--duration", type=parse_time)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--whisper-cli", default="whisper-cli")
    parser.add_argument("--prompt")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    media = args.media.expanduser().resolve()
    model = args.model.expanduser().resolve()
    output = args.output.expanduser().resolve()
    whisper_cli = shutil.which(args.whisper_cli) or args.whisper_cli

    if not media.exists():
        raise FileNotFoundError(media)
    if not model.exists():
        raise FileNotFoundError(model)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    if not Path(whisper_cli).exists() and shutil.which(str(whisper_cli)) is None:
        raise FileNotFoundError(f"Whisper.cpp CLI not found: {args.whisper_cli}")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"Output already exists; pass --overwrite to replace it: {output}")
    if args.start < 0 or (args.duration is not None and args.duration <= 0):
        raise ValueError("--start must be non-negative and --duration must be positive")
    if args.threads <= 0:
        raise ValueError("--threads must be positive")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="class-word-timeline-") as temp_dir:
        temp_root = Path(temp_dir)
        audio = temp_root / "source.wav"
        raw_prefix = temp_root / "whispercpp"

        ffmpeg_command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        if args.start:
            ffmpeg_command.extend(["-ss", f"{args.start:.3f}"])
        ffmpeg_command.extend(["-i", str(media)])
        if args.duration is not None:
            ffmpeg_command.extend(["-t", f"{args.duration:.3f}"])
        ffmpeg_command.extend(
            ["-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)]
        )
        run(ffmpeg_command)
        source_window_end = args.start + media_duration(audio)

        whisper_command = [
            str(whisper_cli),
            "-m",
            str(model),
            "-f",
            str(audio),
            "-l",
            args.language,
            "-t",
            str(args.threads),
            "-p",
            "1",
            "-ml",
            "1",
            "-sow",
            "-ojf",
            "-of",
            str(raw_prefix),
            "-np",
        ]
        if args.prompt:
            whisper_command.extend(["--prompt", args.prompt])
        run(whisper_command)

        raw_json = raw_prefix.with_suffix(".json")
        payload = json.loads(raw_json.read_text(encoding="utf-8"))
        words = merge_tokens(payload, args.start)
        words = [word for word in words if float(word["start"]) < source_window_end]
        for word in words:
            word["end"] = min(float(word["end"]), source_window_end)
        if not words:
            raise ValueError("Whisper.cpp produced no timed words")
        repaired = repair_invalid_durations(words)

    word_segments: list[dict] = []
    for word in words:
        scores = word.pop("scores")
        word_segments.append(
            {
                "word": str(word["word"]).strip(),
                "start": round(float(word["start"]), 3),
                "end": round(float(word["end"]), 3),
                "score": round(sum(scores) / len(scores), 4),
            }
        )

    result = {
        "source": str(media),
        "language": args.language,
        "segments": [
            {"start": word["start"], "end": word["end"], "text": word["word"]}
            for word in word_segments
        ],
        "word_segments": word_segments,
        "strategy": {
            "type": "full_recording_alignment" if args.start == 0 and args.duration is None else "focused_alignment",
            "engine": "local_whispercpp_token_timestamps",
            "model": str(model),
            "source_offset_seconds": args.start,
            "duration_seconds": args.duration,
            "processors": 1,
            "repaired_invalid_durations": repaired,
        },
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"output={output}")
    print(f"words={len(word_segments)}")
    print(f"repaired_invalid_durations={repaired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
