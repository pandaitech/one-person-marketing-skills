#!/usr/bin/env python3
"""Apply verified Screen Studio-style zooms to the screen region of a 9:16 render."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


OUTPUT_SIZE = (1080, 1920)
DEFAULT_SCREEN_REGION = (0, 280, 1080, 810)
DEFAULT_FPS = 24


def probe(path: Path) -> dict:
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,nb_frames",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def parse_region(value: object) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("screen_region must be [x, y, width, height]")
    region = tuple(int(item) for item in value)
    if min(region[:2]) < 0 or min(region[2:]) <= 0:
        raise ValueError(f"Invalid screen_region: {region}")
    return region  # type: ignore[return-value]


def resolve_event_geometry(
    event: dict, region: tuple[int, int, int, int]
) -> None:
    """Resolve a semantic focus box into the center and zoom used by zoompan."""
    _, _, width, height = region
    if "focus_box" not in event:
        return
    box = [float(value) for value in event["focus_box"]]
    if len(box) != 4:
        raise ValueError(f"focus_box must be [x, y, width, height]: {event}")
    box_x, box_y, box_width, box_height = box
    if (
        box_x < 0
        or box_y < 0
        or box_width <= 0
        or box_height <= 0
        or box_x + box_width > width
        or box_y + box_height > height
    ):
        raise ValueError(f"focus_box lies outside the screen region: {event}")
    padding = float(event.get("padding", 60))
    maximum = float(event.get("max_zoom", 1.5))
    if padding < 0 or not 1.05 <= maximum <= 1.8:
        raise ValueError(f"Invalid focus-box padding or max_zoom: {event}")
    fitted_zoom = min(
        maximum,
        width / min(width, box_width + 2 * padding),
        height / min(height, box_height + 2 * padding),
    )
    if fitted_zoom < 1.05:
        raise ValueError(f"focus_box is too large to produce a useful zoom: {event}")
    event["center"] = [box_x + box_width / 2, box_y + box_height / 2]
    event["zoom"] = round(fitted_zoom, 4)


def validate_samples(event: dict) -> None:
    samples = [float(value) for value in event.get("verified_samples", [])]
    if not samples:
        raise ValueError(f"Every motion event needs verified_samples: {event}")
    start, end = float(event["start"]), float(event["end"])
    if samples != sorted(samples) or samples[0] < start or samples[-1] > end:
        raise ValueError(f"verified_samples must be sorted inside the event: {event}")
    maximum_gap = float(event.get("maximum_verification_gap", 2.1))
    checkpoints = [start, *samples, end]
    if max(right - left for left, right in zip(checkpoints, checkpoints[1:])) > maximum_gap:
        raise ValueError(f"Motion event contains an unverified visual gap: {event}")


def validate(
    plan: dict,
    plan_path: Path,
    input_override: Path | None,
    output_override: Path | None,
) -> tuple[Path, Path, int, tuple[int, int, int, int], list[dict]]:
    base = plan_path.parent.resolve()
    source = (
        input_override.expanduser().resolve()
        if input_override
        else resolve_path(str(plan["input"]), base)
    )
    output = (
        output_override.expanduser().resolve()
        if output_override
        else resolve_path(str(plan["output"]), base)
    )
    fps = int(plan.get("fps", DEFAULT_FPS))
    region = parse_region(plan.get("screen_region", list(DEFAULT_SCREEN_REGION)))
    events = [dict(event) for event in plan.get("events", [])]
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == output:
        raise ValueError("Motion output must not replace its input")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")

    metadata = probe(source)
    video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    size = int(video["width"]), int(video["height"])
    if size != OUTPUT_SIZE:
        raise ValueError(f"Expected {OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}, found {size}")
    if region[0] + region[2] > size[0] or region[1] + region[3] > size[1]:
        raise ValueError(f"screen_region {region} exceeds video size {size}")
    duration = float(metadata["format"]["duration"])

    previous_end = 0.0
    for event in events:
        resolve_event_geometry(event, region)
        start, end = float(event["start"]), float(event["end"])
        zoom = float(event.get("zoom", 0))
        transition = float(event.get("transition", 0.6))
        center = event.get("center")
        if start < previous_end or end <= start or end > duration + 0.01:
            raise ValueError(f"Invalid or overlapping motion event: {event}")
        if not 1.05 <= zoom <= 1.8:
            raise ValueError(f"zoom must be between 1.05 and 1.8: {event}")
        if transition <= 0 or transition * 2 >= end - start:
            raise ValueError(f"Invalid transition duration: {event}")
        if (
            not isinstance(center, list)
            or len(center) != 2
            or not (0 <= float(center[0]) <= region[2])
            or not (0 <= float(center[1]) <= region[3])
        ):
            raise ValueError(f"Focus center lies outside the screen region: {event}")
        if not str(event.get("reason", "")).strip():
            raise ValueError(f"Every motion event needs a semantic reason: {event}")
        validate_samples(event)
        previous_end = end
    return source, output, fps, region, events


def event_zoom(event: dict, fps: int) -> str:
    start = round(float(event["start"]) * fps)
    end = round(float(event["end"]) * fps)
    ramp = max(1, round(float(event.get("transition", 0.6)) * fps))
    maximum = float(event["zoom"])
    ramp_out = end - ramp
    ease_in = f"(0.5-0.5*cos(PI*(on-{start})/{ramp}))"
    ease_out = f"(0.5+0.5*cos(PI*(on-{ramp_out})/{ramp}))"
    return (
        f"if(lt(on,{start + ramp}),1+({maximum - 1:.6f})*{ease_in},"
        f"if(lt(on,{ramp_out}),{maximum:.6f},"
        f"1+({maximum - 1:.6f})*{ease_out}))"
    )


def nested_expression(events: list[dict], fps: int, builder, default: str) -> str:
    expression = default
    for event in reversed(events):
        start = round(float(event["start"]) * fps)
        end = round(float(event["end"]) * fps)
        expression = f"if(between(on,{start},{end}),{builder(event)},{expression})"
    return expression


def build_filter(
    fps: int, region: tuple[int, int, int, int], events: list[dict]
) -> str:
    x, y, width, height = region
    zooms = {id(event): event_zoom(event, fps) for event in events}
    zoom_expr = nested_expression(events, fps, lambda event: zooms[id(event)], "1")
    focus_x = nested_expression(
        events,
        fps,
        lambda event: (
            f"max(0,min(iw-iw/zoom,{float(event['center'][0]):.3f}-iw/(2*zoom)))"
        ),
        "0",
    )
    focus_y = nested_expression(
        events,
        fps,
        lambda event: (
            f"max(0,min(ih-ih/zoom,{float(event['center'][1]):.3f}-ih/(2*zoom)))"
        ),
        "0",
    )
    return ";".join(
        [
            "[0:v]split=2[base][screen_source]",
            (
                f"[screen_source]crop={width}:{height}:{x}:{y},"
                f"zoompan=z='{zoom_expr}':x='{focus_x}':y='{focus_y}':"
                f"d=1:s={width}x{height}:fps={fps},format=yuv420p[screen_motion]"
            ),
            f"[base][screen_motion]overlay=x={x}:y={y}:shortest=1[vout]",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    plan_path = args.plan.expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    source, output, fps, region, events = validate(
        plan, plan_path, args.input, args.output
    )
    source_probe = probe(source)
    video_stream = next(
        stream
        for stream in source_probe["streams"]
        if stream["codec_type"] == "video"
    )
    frame_count = int(video_stream["nb_frames"])
    print(
        f"Validated {len(events)} motion events for {source.name}; "
        f"screen region={region}."
    )
    if args.check:
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"Output exists; pass --overwrite: {output}")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stats",
        "-i",
        str(source),
        "-filter_complex",
        build_filter(fps, region, events),
        "-map",
        "[vout]",
        "-map",
        "0:a?",
        "-frames:v",
        str(frame_count),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "-y" if args.overwrite else "-n",
        str(output),
    ]
    subprocess.run(command, check=True)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
