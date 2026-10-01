#!/usr/bin/env python3
"""Render approved shortform clips as captioned 9:16 videos.

The JSON manifest is the editorial source of truth. Each clip supplies optional
absolute hook ranges followed by absolute full-cut ranges. An empty hook list is
a cold open. The renderer remaps transcript captions across every reordered
range, optional semantic screen motion, and one chosen standard layout profile.

Examples:
    python render.py --manifest clips.json --check
    python render.py --manifest clips.json --clip 01 --preview-seconds 30
    python render.py --manifest clips.json --clip 01 --layout-profile immersive-speaker
    python render.py --manifest clips.json --clip 01 --overwrite
    python render.py --manifest clips.json --all
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: pip install Pillow") from exc


OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
TOP_SAFE_HEIGHT = 280
SCREEN_HEIGHT = 810
TITLE_GAP_HEIGHT = 170
SCREEN_Y = TOP_SAFE_HEIGHT
TITLE_Y = SCREEN_Y + SCREEN_HEIGHT
SPEAKER_Y = TITLE_Y + TITLE_GAP_HEIGHT
BACKGROUND = "#FBFAF4"
FFMPEG_BACKGROUND = "0xFBFAF4"
BOTTOM_BACKGROUND = "#000000"
FPS = 24
TITLE_SECONDS = 5
TRANSITION_SECONDS = 0.28
MAX_HOOK_SECONDS = 8.0
DUPLICATE_OPENING_WINDOW_SECONDS = 1.0
CAPTION_FONT_SIZE = 52
CAPTION_MAX_WORDS = 5
CAPTION_MAX_CHARACTERS = 34
CAPTION_WHITE = "#FFFFFF"
LAYOUT_PROFILES = {
    "full-width-speaker",
    "floating-card",
    "immersive-speaker",
}
DEFAULT_LAYOUT_PROFILE = "floating-card"
FLOATING_SPEAKER_WIDTH = 720
FLOATING_BOTTOM_SAFE = 250
FLOATING_SCREEN_LAYER_HEIGHT = 1090
FLOATING_SCREEN_FADE_START = 760
FLOATING_BACKGROUND_FADE_START = 760
FLOATING_BACKGROUND_FADE_END = 1760
FLOATING_TITLE_Y = 980
FLOATING_CAPTION_Y = 1090
IMMERSIVE_SPEAKER_Y = 1000
IMMERSIVE_SPEAKER_HEIGHT = OUTPUT_HEIGHT - IMMERSIVE_SPEAKER_Y
IMMERSIVE_SCREEN_LAYER_HEIGHT = 1090
IMMERSIVE_SCREEN_FADE_START = 880
IMMERSIVE_TEXT_Y = 980


@dataclass(frozen=True)
class SourceProfile:
    key: str
    video: Path
    transcript: Path
    screen_region: tuple[int, int, int, int]
    speaker_region: tuple[int, int, int, int]
    caption_replacements: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ClipSpec:
    clip_id: str
    source_key: str
    title: str
    hook_ranges: tuple[tuple[float, float], ...]
    full_ranges: tuple[tuple[float, float], ...]
    layout_profile: str
    motion_plan: Path | None


@dataclass(frozen=True)
class CaptionWord:
    text: str
    start: float
    end: float
    piece: int = 0


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def parse_region(value: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{label} must be [x, y, width, height]")
    region = tuple(int(item) for item in value)
    if min(region[:2]) < 0 or min(region[2:]) <= 0:
        raise ValueError(f"{label} contains invalid coordinates: {region}")
    return region  # type: ignore[return-value]


def parse_ranges(
    value: object, label: str, *, allow_empty: bool = False
) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of [start, end] ranges")
    if not value:
        if allow_empty:
            return ()
        raise ValueError(f"{label} must contain at least one [start, end] range")
    ranges: list[tuple[float, float]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError(f"{label} range must be [start, end]: {item!r}")
        start, end = float(item[0]), float(item[1])
        if start < 0 or end <= start:
            raise ValueError(f"{label} contains invalid range: {start}-{end}")
        ranges.append((start, end))
    return tuple(ranges)


def load_manifest(
    manifest_path: Path,
) -> tuple[dict[str, SourceProfile], list[ClipSpec], Path]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent.resolve()
    default_layout = str(payload.get("layout_profile", DEFAULT_LAYOUT_PROFILE))
    if default_layout not in LAYOUT_PROFILES:
        raise ValueError(
            f"Unknown layout_profile {default_layout!r}; choose one of "
            f"{', '.join(sorted(LAYOUT_PROFILES))}"
        )

    source_payload = payload.get("sources")
    if not isinstance(source_payload, dict) or not source_payload:
        raise ValueError("Manifest must contain a non-empty sources object")
    sources: dict[str, SourceProfile] = {}
    for key, value in source_payload.items():
        if not isinstance(value, dict):
            raise ValueError(f"Source {key!r} must be an object")
        replacements = value.get("caption_replacements", {})
        if not isinstance(replacements, dict):
            raise ValueError(f"{key}.caption_replacements must be an object")
        sources[str(key)] = SourceProfile(
            key=str(key),
            video=resolve_path(str(value["video"]), base),
            transcript=resolve_path(str(value["transcript"]), base),
            screen_region=parse_region(value.get("screen_region"), f"{key}.screen_region"),
            speaker_region=parse_region(value.get("speaker_region"), f"{key}.speaker_region"),
            caption_replacements=tuple(
                (str(source_text), str(display_text))
                for source_text, display_text in replacements.items()
            ),
        )

    clip_payload = payload.get("clips")
    if not isinstance(clip_payload, list) or not clip_payload:
        raise ValueError("Manifest must contain a non-empty clips array")
    clips: list[ClipSpec] = []
    seen_ids: set[str] = set()
    for value in clip_payload:
        if not isinstance(value, dict):
            raise ValueError("Every clip must be an object")
        clip_id = str(value["id"])
        if clip_id in seen_ids:
            raise ValueError(f"Duplicate clip id: {clip_id}")
        seen_ids.add(clip_id)
        source_key = str(value["source"])
        if source_key not in sources:
            raise ValueError(f"Clip {clip_id} references unknown source {source_key!r}")
        title = re.sub(r"\s+", " ", str(value["title"])).strip()
        if not 4 <= len(title.split()) <= 10:
            raise ValueError(f"Clip {clip_id} title must contain 4-10 words: {title!r}")
        layout_profile = str(value.get("layout_profile", default_layout))
        if layout_profile not in LAYOUT_PROFILES:
            raise ValueError(
                f"Clip {clip_id} has unknown layout_profile {layout_profile!r}; "
                f"choose one of {', '.join(sorted(LAYOUT_PROFILES))}"
            )
        clips.append(
            ClipSpec(
                clip_id=clip_id,
                source_key=source_key,
                title=title,
                hook_ranges=parse_ranges(
                    value.get("hook_ranges"),
                    f"clip {clip_id}.hook_ranges",
                    allow_empty=True,
                ),
                full_ranges=parse_ranges(value.get("full_ranges"), f"clip {clip_id}.full_ranges"),
                layout_profile=layout_profile,
                motion_plan=(
                    resolve_path(str(value["motion_plan"]), base)
                    if value.get("motion_plan")
                    else None
                ),
            )
        )

    output_value = str(payload.get("output_dir", "shortform-videos"))
    output_dir = resolve_path(output_value, base)
    return sources, clips, output_dir


def ffprobe(video: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(video),
    ]
    return json.loads(subprocess.check_output(command, text=True))


def source_dimensions(probe: dict) -> tuple[int, int]:
    stream = next(item for item in probe["streams"] if item.get("codec_type") == "video")
    return int(stream["width"]), int(stream["height"])


def source_duration(probe: dict) -> float:
    return float(probe["format"]["duration"])


def validate_region(region: tuple[int, int, int, int], size: tuple[int, int], label: str) -> None:
    x, y, width, height = region
    if x + width > size[0] or y + height > size[1]:
        raise ValueError(f"{label} {region} exceeds source dimensions {size}")


def load_segments(transcript: Path) -> list[dict]:
    payload = json.loads(transcript.read_text(encoding="utf-8"))
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(f"Transcript has no timestamped segments: {transcript}")
    for segment in segments:
        if not all(key in segment for key in ("start", "end", "text")):
            raise ValueError(f"Transcript segment is missing start/end/text: {segment!r}")
    return segments


def load_word_segments(transcript: Path) -> list[dict] | None:
    payload = json.loads(transcript.read_text(encoding="utf-8"))
    words = payload.get("word_segments")
    if words is None or words == []:
        return None
    if not isinstance(words, list):
        raise ValueError(f"Transcript word_segments must be a list: {transcript}")
    for word in words:
        text = word.get("word", word.get("text")) if isinstance(word, dict) else None
        if not isinstance(word, dict) or not all(key in word for key in ("start", "end")):
            raise ValueError(f"Transcript word segment is missing start/end: {word!r}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Transcript word segment is missing word/text: {word!r}")
        if float(word["end"]) <= float(word["start"]):
            raise ValueError(f"Transcript word segment has invalid timing: {word!r}")
    return words


def centered_aspect_crop(
    region: tuple[int, int, int, int], target_ratio: float = 4 / 3
) -> tuple[int, int, int, int]:
    x, y, width, height = region
    if width / height > target_ratio:
        crop_width = max(2, int(height * target_ratio) // 2 * 2)
        return x + (width - crop_width) // 2, y, crop_width, height
    crop_height = max(2, int(width / target_ratio) // 2 * 2)
    return x, y + (height - crop_height) // 2, width, crop_height


def even(value: float) -> int:
    rounded = max(2, int(round(value)))
    return rounded if rounded % 2 == 0 else rounded + 1


def speaker_height(region: tuple[int, int, int, int]) -> int:
    return even(OUTPUT_WIDTH * region[3] / region[2])


def validate_manifest(sources: dict[str, SourceProfile], clips: list[ClipSpec]) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed")
    probes: dict[str, dict] = {}
    for key, source in sources.items():
        if not source.video.exists():
            raise FileNotFoundError(f"Source video not found: {source.video}")
        if not source.transcript.exists():
            raise FileNotFoundError(f"Transcript not found: {source.transcript}")
        load_segments(source.transcript)
        load_word_segments(source.transcript)
        probe = ffprobe(source.video)
        probes[key] = probe
        size = source_dimensions(probe)
        validate_region(source.screen_region, size, f"{key}.screen_region")
        validate_region(source.speaker_region, size, f"{key}.speaker_region")

    for clip in clips:
        source = sources[clip.source_key]
        if clip.motion_plan is not None and not clip.motion_plan.is_file():
            raise FileNotFoundError(
                f"Clip {clip.clip_id} motion plan not found: {clip.motion_plan}"
            )
        if (
            clip.layout_profile == "full-width-speaker"
            and SPEAKER_Y + speaker_height(source.speaker_region) > OUTPUT_HEIGHT
        ):
            raise ValueError(
                f"{source.key}.speaker_region is too tall for full-width-speaker; "
                "measure the complete landscape speaker tile or choose another profile"
            )
        duration = source_duration(probes[clip.source_key])
        for label, ranges in (("hook", clip.hook_ranges), ("full", clip.full_ranges)):
            for start, end in ranges:
                if end > duration + 0.01:
                    raise ValueError(
                        f"Clip {clip.clip_id} {label} range {start}-{end} exceeds "
                        f"source duration {duration:.3f}"
                    )
        hook_duration = sum(end - start for start, end in clip.hook_ranges)
        if hook_duration > MAX_HOOK_SECONDS + 0.001:
            raise ValueError(
                f"Clip {clip.clip_id} prepended hook is {hook_duration:.3f} seconds; "
                f"hooks must be {MAX_HOOK_SECONDS:g} seconds or shorter"
            )

        full_envelope = (
            min(start for start, _ in clip.full_ranges),
            max(end for _, end in clip.full_ranges),
        )
        for hook_start, hook_end in clip.hook_ranges:
            if not full_envelope[0] <= hook_start < hook_end <= full_envelope[1] + 0.001:
                raise ValueError(
                    f"Clip {clip.clip_id} hook {hook_start}-{hook_end} is outside its "
                    "full cut envelope"
                )

        if clip.hook_ranges:
            first_full_start = clip.full_ranges[0][0]
            hook_starts_at_opening = any(
                hook_start <= first_full_start + DUPLICATE_OPENING_WINDOW_SECONDS
                and hook_end > first_full_start
                for hook_start, hook_end in clip.hook_ranges
            )
            if hook_starts_at_opening:
                raise ValueError(
                    f"Clip {clip.clip_id} prepended hook begins within the first "
                    f"{DUPLICATE_OPENING_WINDOW_SECONDS:g} second of the full cut, which "
                    "would repeat it. Use hook_ranges: [] for a cold open."
                )
        pieces = list(clip.hook_ranges) + list(clip.full_ranges)
        load_motion_events(
            clip.motion_plan,
            sum(end - start for start, end in pieces),
            pieces,
        )


def format_time(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    total, milliseconds = divmod(total_milliseconds, 1000)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower() or "clip"


def font_path() -> Path:
    # Set SHORTFORM_FONT to pin an exact font file; otherwise fall back to the
    # first supported bold system font found below.
    configured = os.environ.get("SHORTFORM_FONT")
    if configured:
        selected = Path(configured).expanduser().resolve()
        if not selected.is_file():
            raise FileNotFoundError("Configured shortform font is unavailable")
        return selected
    choices = [
        Path("/System/Library/Fonts/SFNS.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for choice in choices:
        if choice.exists():
            return choice
    raise FileNotFoundError("No supported bold font found")


def load_font(size: int, variation: str = "Bold") -> ImageFont.FreeTypeFont:
    selected = font_path()
    loaded = ImageFont.truetype(str(selected), size=size)
    if selected.name == "SFNS.ttf":
        try:
            loaded.set_variation_by_name(variation)
        except OSError:
            pass
    return loaded


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def make_gradient_background(destination: Path) -> None:
    """Create the floating-card profile's long off-white-to-black bridge."""
    image = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (251, 250, 244))
    draw = ImageDraw.Draw(image)
    span = FLOATING_BACKGROUND_FADE_END - FLOATING_BACKGROUND_FADE_START
    for y in range(FLOATING_BACKGROUND_FADE_START, OUTPUT_HEIGHT):
        progress = (y - FLOATING_BACKGROUND_FADE_START) / max(1, span)
        blend = smoothstep(progress)
        colour = tuple(
            round(light * (1.0 - blend) + 10 * blend)
            for light in (251, 250, 244)
        )
        draw.line((0, y, OUTPUT_WIDTH, y), fill=colour)
    image.save(destination)


def make_vertical_alpha_mask(
    destination: Path, height: int, fade_start: int
) -> None:
    """Keep a layer opaque above fade_start and feather it to zero at height."""
    image = Image.new("L", (OUTPUT_WIDTH, height), 255)
    draw = ImageDraw.Draw(image)
    span = height - fade_start
    for y in range(fade_start, height):
        progress = (y - fade_start) / max(1, span - 1)
        alpha = round(255 * (1.0 - smoothstep(progress)))
        draw.line((0, y, OUTPUT_WIDTH, y), fill=alpha)
    image.save(destination)


def make_rounded_mask(destination: Path, width: int, height: int) -> None:
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=38,
        fill=255,
    )
    image.save(destination)


def balanced_title_lines(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> list[str]:
    max_width = OUTPUT_WIDTH - 96
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text]
    words = text.split()
    candidates: list[tuple[int, list[str]]] = []
    for split_at in range(1, len(words)):
        lines = [" ".join(words[:split_at]), " ".join(words[split_at:])]
        widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
        if max(widths) <= max_width:
            candidates.append((abs(widths[0] - widths[1]), lines))
    return min(candidates, key=lambda item: item[0])[1] if candidates else [text]


def make_title_card(text: str, destination: Path) -> None:
    image = Image.new("RGBA", (OUTPUT_WIDTH, TITLE_GAP_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    size = 54
    font = load_font(size, "Bold")
    lines = balanced_title_lines(text, draw, font)
    while any(draw.textbbox((0, 0), line, font=font)[2] > OUTPUT_WIDTH - 96 for line in lines):
        size -= 2
        if size < 38:
            raise ValueError(f"Title cannot fit in two lines: {text!r}")
        font = load_font(size, "Bold")
        lines = balanced_title_lines(text, draw, font)

    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [bottom - top for _, top, _, bottom in boxes]
    spacing = 7
    text_height = sum(heights) + spacing * (len(lines) - 1)
    text_width = max(right - left for left, _, right, _ in boxes)
    box_width = min(OUTPUT_WIDTH - 64, text_width + 72)
    box_height = min(TITLE_GAP_HEIGHT - 24, text_height + 38)
    left = (OUTPUT_WIDTH - box_width) / 2
    top = (TITLE_GAP_HEIGHT - box_height) / 2
    draw.rounded_rectangle(
        (left, top, left + box_width, top + box_height),
        radius=24,
        fill=(17, 17, 17, 238),
    )
    y = (TITLE_GAP_HEIGHT - text_height) / 2
    for line, (box_left, box_top, box_right, _), height in zip(lines, boxes, heights):
        width = box_right - box_left
        draw.text(((OUTPUT_WIDTH - width) / 2, y - box_top), line, font=font, fill="#FFFFFF")
        y += height + spacing
    image.save(destination)


# Common tech/brand proper-noun casing fixes for auto-generated captions.
# Course- or speaker-specific corrections (names, products, local terms) belong
# in the manifest's per-source `caption_replacements` instead of here.
PROPER_CASE = (
    (r"\bnano banana\b", "Nano Banana"),
    (r"\bchatgpt\b", "ChatGPT"),
    (r"\bopenai\b", "OpenAI"),
    (r"\bclaude\b", "Claude"),
    (r"\bgemini\b", "Gemini"),
    (r"\bgoogle\b", "Google"),
    (r"\bcanva\b", "Canva"),
    (r"\bmeta\b", "Meta"),
    (r"\btiktok\b", "TikTok"),
    (r"\bwhatsapp\b", "WhatsApp"),
    (r"\btelegram\b", "Telegram"),
    (r"\bcopilot\b", "Copilot"),
    (r"\bcodex\b", "Codex"),
    (r"\bmalaysia\b", "Malaysia"),
    (r"\baugust\b", "August"),
    (r"\bcustomer relationship management\b", "Customer Relationship Management"),
    (r"\bcrm\b", "CRM"),
    (r"\bmcp\b", "MCP"),
    (r"\bapi\b", "API"),
    (r"\bgpt\b", "GPT"),
    (r"\bpdf\b", "PDF"),
    (r"\bhtml\b", "HTML"),
    (r"\bjson\b", "JSON"),
    (r"\bsql\b", "SQL"),
    (r"\bai\b", "AI"),
)


def clean_caption_text(
    text: str, extra_replacements: tuple[tuple[str, str], ...] = ()
) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    for pattern, replacement in PROPER_CASE:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    for source_text, display_text in extra_replacements:
        cleaned = re.sub(
            re.escape(source_text), display_text, cleaned, flags=re.IGNORECASE
        )
    return cleaned


def detect_silences(video: Path, start: float, end: float) -> list[tuple[float, float]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "info",
        "-ss",
        format_time(start),
        "-t",
        f"{end - start:.3f}",
        "-i",
        str(video),
        "-vn",
        "-af",
        "silencedetect=noise=-35dB:d=0.28",
        "-f",
        "null",
        "-",
    ]
    result = run(command, capture_output=True, text=True)
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)]
    return [(start + a, start + b) for a, b in zip(starts, ends) if b > a]


def speech_intervals(
    start: float, end: float, silences: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    cursor = start
    intervals: list[tuple[float, float]] = []
    for silence_start, silence_end in silences:
        if silence_end <= start or silence_start >= end:
            continue
        clipped_start = max(start, silence_start)
        clipped_end = min(end, silence_end)
        if clipped_start > cursor:
            intervals.append((cursor, clipped_start))
        cursor = max(cursor, clipped_end)
    if cursor < end:
        intervals.append((cursor, end))
    return [(a, b) for a, b in intervals if b - a >= 0.02] or [(start, end)]


def active_position_to_time(intervals: list[tuple[float, float]], position: float) -> float:
    remaining = max(0.0, position)
    for start, end in intervals:
        duration = end - start
        if remaining <= duration:
            return start + remaining
        remaining -= duration
    return intervals[-1][1]


def apply_sentence_case(word: str, sentence_start: bool) -> tuple[str, bool]:
    if sentence_start:
        word = re.sub(
            r"^([^a-zA-Z]*)([a-z])",
            lambda match: match.group(1) + match.group(2).upper(),
            word,
            count=1,
        )
    return word, bool(re.search(r"[.!?][\"')\]]*$", word))


def native_transcript_words(
    transcript: Path,
    extra_replacements: tuple[tuple[str, str], ...],
) -> list[CaptionWord] | None:
    source_words = load_word_segments(transcript)
    if source_words is None:
        return None

    caption_words: list[CaptionWord] = []
    sentence_start = True
    for item in source_words:
        start, end = float(item["start"]), float(item["end"])
        raw_text = str(item.get("word", item.get("text", ""))).strip()
        tokens = clean_caption_text(raw_text, extra_replacements).split()
        if not tokens:
            continue
        for index, token in enumerate(tokens):
            token, sentence_start = apply_sentence_case(token, sentence_start)
            token_start = start + (end - start) * index / len(tokens)
            token_end = start + (end - start) * (index + 1) / len(tokens)
            caption_words.append(CaptionWord(token, token_start, token_end))
    if not caption_words:
        raise ValueError(f"Transcript has no usable timed words: {transcript}")
    return caption_words


def estimated_transcript_words(
    transcript: Path,
    silences: list[tuple[float, float]],
    extra_replacements: tuple[tuple[str, str], ...],
) -> list[CaptionWord]:
    caption_words: list[CaptionWord] = []
    sentence_start = True
    for segment in load_segments(transcript):
        start, end = float(segment["start"]), float(segment["end"])
        raw_text = str(segment.get("text", "")).strip()
        if raw_text[:1].isupper():
            sentence_start = True
        words = clean_caption_text(raw_text, extra_replacements).split()
        if not words or end <= start:
            continue
        cased_words: list[str] = []
        for word in words:
            word, sentence_start = apply_sentence_case(word, sentence_start)
            cased_words.append(word)
        intervals = speech_intervals(start, end, silences)
        active_duration = sum(b - a for a, b in intervals)
        for index, word in enumerate(cased_words):
            word_start = active_position_to_time(intervals, active_duration * index / len(words))
            word_end = active_position_to_time(intervals, active_duration * (index + 1) / len(words))
            caption_words.append(CaptionWord(word, word_start, max(word_end, word_start + 0.04)))
    return caption_words


def output_caption_words(
    source: SourceProfile, pieces: list[tuple[float, float]]
) -> list[CaptionWord]:
    source_words = native_transcript_words(source.transcript, source.caption_replacements)
    if source_words is None:
        silences = detect_silences(
            source.video,
            min(start for start, _ in pieces),
            max(end for _, end in pieces),
        )
        source_words = estimated_transcript_words(
            source.transcript, silences, source.caption_replacements
        )
    output_words: list[CaptionWord] = []
    output_cursor = 0.0
    for piece_index, (piece_start, piece_end) in enumerate(pieces):
        for word in source_words:
            midpoint = (word.start + word.end) / 2
            if not piece_start <= midpoint < piece_end:
                continue
            mapped_start = output_cursor + max(word.start, piece_start) - piece_start
            mapped_end = output_cursor + min(word.end, piece_end) - piece_start
            output_words.append(
                CaptionWord(word.text, mapped_start, max(mapped_end, mapped_start + 0.04), piece_index)
            )
        output_cursor += piece_end - piece_start
    return output_words


def caption_groups(words: list[CaptionWord]) -> list[list[CaptionWord]]:
    raw_groups: list[list[CaptionWord]] = []
    current: list[CaptionWord] = []
    for word in words:
        proposed = current + [word]
        text = " ".join(item.text for item in proposed)
        must_break = bool(
            current
            and (
                word.piece != current[-1].piece
                or word.start - current[-1].end > 0.65
                or len(proposed) > CAPTION_MAX_WORDS
                or len(text) > CAPTION_MAX_CHARACTERS
            )
        )
        if must_break:
            raw_groups.append(current)
            current = [word]
        else:
            current = proposed
    if current:
        raw_groups.append(current)

    groups: list[list[CaptionWord]] = []
    index = 0
    while index < len(raw_groups):
        group = raw_groups[index]
        if (
            len(group) == 1
            and index + 1 < len(raw_groups)
            and raw_groups[index + 1][0].piece == group[0].piece
        ):
            groups.append(group + raw_groups[index + 1])
            index += 2
            continue
        if len(group) == 1 and groups and groups[-1][-1].piece == group[0].piece:
            groups[-1].extend(group)
        else:
            groups.append(group)
        index += 1
    return groups


def caption_lines(
    group: list[CaptionWord], draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont
) -> list[list[CaptionWord]]:
    if len(group) < 2:
        return [group]
    max_width = OUTPUT_WIDTH - 70
    candidates: list[tuple[float, list[list[CaptionWord]]]] = []
    for split_at in range(1, len(group)):
        lines = [group[:split_at], group[split_at:]]
        widths = [draw.textlength(" ".join(word.text for word in line), font=font) for line in lines]
        if max(widths) <= max_width:
            candidates.append((abs(widths[0] - widths[1]), lines))
    if candidates:
        return min(candidates, key=lambda item: item[0])[1]
    split_at = max(1, len(group) // 2)
    return [group[:split_at], group[split_at:]]


def render_caption_image(
    group: list[CaptionWord], destination: Path, *, card_style: bool
) -> None:
    image = Image.new("RGBA", (OUTPUT_WIDTH, TITLE_GAP_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_size = CAPTION_FONT_SIZE
    font = load_font(font_size, "Semibold")
    lines = caption_lines(group, draw, font)
    max_width = OUTPUT_WIDTH - 70
    while (
        max(draw.textlength(" ".join(word.text for word in line), font=font) for line in lines)
        > max_width
        and font_size > 38
    ):
        font_size -= 2
        font = load_font(font_size, "Semibold")
        lines = caption_lines(group, draw, font)
    line_height = font_size + (8 if card_style else 20)
    y = (TITLE_GAP_HEIGHT - len(lines) * line_height) / 2
    if card_style:
        widest = max(
            draw.textlength(" ".join(word.text for word in line), font=font)
            for line in lines
        )
        card_width = min(OUTPUT_WIDTH - 150, round(widest + 76))
        card_height = min(TITLE_GAP_HEIGHT - 16, len(lines) * line_height + 28)
        left = (OUTPUT_WIDTH - card_width) / 2
        top = (TITLE_GAP_HEIGHT - card_height) / 2
        draw.rounded_rectangle(
            (left, top, left + card_width, top + card_height),
            radius=27,
            fill=(10, 10, 10, 218),
        )
    space_width = draw.textlength(" ", font=font)
    for line in lines:
        widths = [draw.textlength(word.text, font=font) for word in line]
        total_width = sum(widths) + space_width * max(0, len(line) - 1)
        x = (OUTPUT_WIDTH - total_width) / 2
        for word, width in zip(line, widths):
            draw.text(
                (x, y),
                word.text,
                font=font,
                fill=CAPTION_WHITE,
                stroke_width=0 if card_style else 6,
                stroke_fill="#111111",
            )
            x += width + space_width
        y += line_height
    image.save(destination)


def concat_entry(path: Path) -> str:
    return f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"


def render_caption_overlay(
    words: list[CaptionWord],
    duration: float,
    destination: Path,
    temp_root: Path,
    *,
    card_style: bool,
) -> None:
    image_dir = temp_root / "caption-frames"
    image_dir.mkdir(parents=True, exist_ok=True)
    blank = image_dir / "blank.png"
    Image.new("RGBA", (OUTPUT_WIDTH, TITLE_GAP_HEIGHT), (0, 0, 0, 0)).save(blank)

    entries: list[tuple[Path, float]] = []
    cursor = 0.0
    groups = caption_groups(words)
    if any(len(group) < 2 for group in groups):
        raise ValueError(
            "A source range produced a one-word caption. Extend or merge that range "
            "so every visible caption can use two lines."
        )
    for index, group in enumerate(groups):
        start, end = max(cursor, group[0].start), min(duration, group[-1].end)
        if start > cursor + 0.001:
            entries.append((blank, start - cursor))
        if end <= start:
            continue
        frame = image_dir / f"caption-{index:04d}.png"
        render_caption_image(group, frame, card_style=card_style)
        entries.append((frame, end - start))
        cursor = end
    if cursor < duration:
        entries.append((blank, duration - cursor))
    if not entries:
        entries.append((blank, duration))

    concat_path = temp_root / "captions.concat.txt"
    lines: list[str] = []
    for frame, frame_duration in entries:
        lines.extend((concat_entry(frame), f"duration {frame_duration:.6f}"))
    lines.append(concat_entry(entries[-1][0]))
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            f"fps={FPS},format=argb",
            "-c:v",
            "qtrle",
            "-pix_fmt",
            "argb",
            "-an",
            "-y",
            str(destination),
        ]
    )


def load_motion_events(
    plan_path: Path | None,
    total_duration: float,
    pieces: list[tuple[float, float]],
) -> list[dict]:
    if plan_path is None:
        return []
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    region = payload.get("screen_region", [0, SCREEN_Y, OUTPUT_WIDTH, SCREEN_HEIGHT])
    if (
        not isinstance(region, list)
        or len(region) != 4
        or tuple(int(value) for value in region[2:]) != (OUTPUT_WIDTH, SCREEN_HEIGHT)
    ):
        raise ValueError(
            f"{plan_path} must target the rendered 1080x810 screen region"
        )
    events = [dict(event) for event in payload.get("events", [])]
    previous_end = 0.0
    for event in events:
        start, end = float(event["start"]), float(event["end"])
        if start < previous_end or end <= start or end > total_duration + 0.01:
            raise ValueError(f"Invalid or overlapping motion event: {event}")
        if "focus_box" in event:
            box = [float(value) for value in event["focus_box"]]
            if len(box) != 4:
                raise ValueError(f"focus_box must be [x, y, width, height]: {event}")
            box_x, box_y, box_width, box_height = box
            if (
                box_x < 0
                or box_y < 0
                or box_width <= 0
                or box_height <= 0
                or box_x + box_width > OUTPUT_WIDTH
                or box_y + box_height > SCREEN_HEIGHT
            ):
                raise ValueError(f"focus_box lies outside the screen: {event}")
            padding = float(event.get("padding", 60))
            maximum = float(event.get("max_zoom", 1.5))
            fitted_zoom = min(
                maximum,
                OUTPUT_WIDTH / min(OUTPUT_WIDTH, box_width + 2 * padding),
                SCREEN_HEIGHT / min(SCREEN_HEIGHT, box_height + 2 * padding),
            )
            event["center"] = [
                box_x + box_width / 2,
                box_y + box_height / 2,
            ]
            event["zoom"] = round(fitted_zoom, 4)

        zoom = float(event.get("zoom", 0))
        transition = float(event.get("transition", 0.6))
        center = event.get("center")
        if not 1.05 <= zoom <= 1.8:
            raise ValueError(f"Motion zoom must be between 1.05 and 1.8: {event}")
        if transition <= 0 or transition * 2 >= end - start:
            raise ValueError(f"Invalid motion transition: {event}")
        if (
            not isinstance(center, list)
            or len(center) != 2
            or not 0 <= float(center[0]) <= OUTPUT_WIDTH
            or not 0 <= float(center[1]) <= SCREEN_HEIGHT
        ):
            raise ValueError(f"Motion center lies outside the screen: {event}")
        if not str(event.get("reason", "")).strip():
            raise ValueError(f"Every motion event needs a semantic reason: {event}")
        samples = [float(value) for value in event.get("verified_samples", [])]
        if not samples:
            raise ValueError(f"Every motion event needs verified_samples: {event}")
        if samples != sorted(samples) or samples[0] < start or samples[-1] > end:
            raise ValueError(f"verified_samples must be sorted inside the event: {event}")
        checkpoints = [start, *samples, end]
        maximum_gap = float(event.get("maximum_verification_gap", 2.1))
        if max(b - a for a, b in zip(checkpoints, checkpoints[1:])) > maximum_gap:
            raise ValueError(f"Motion event contains an unverified visual gap: {event}")
        previous_end = end
    return events


def overlapping_motion_events(
    events: list[dict], piece_start: float, piece_end: float
) -> list[dict]:
    return [
        event
        for event in events
        if float(event["end"]) > piece_start
        and float(event["start"]) < piece_end
    ]


def motion_event_zoom(event: dict, frame_offset: int) -> str:
    start = round(float(event["start"]) * FPS)
    end = round(float(event["end"]) * FPS)
    ramp = max(1, round(float(event.get("transition", 0.6)) * FPS))
    maximum = float(event["zoom"])
    ramp_out = end - ramp
    timeline_frame = f"(on+{frame_offset})"
    ease_in = f"(0.5-0.5*cos(PI*({timeline_frame}-{start})/{ramp}))"
    ease_out = f"(0.5+0.5*cos(PI*({timeline_frame}-{ramp_out})/{ramp}))"
    return (
        f"if(lt({timeline_frame},{start + ramp}),1+({maximum - 1:.6f})*{ease_in},"
        f"if(lt({timeline_frame},{ramp_out}),{maximum:.6f},"
        f"1+({maximum - 1:.6f})*{ease_out}))"
    )


def nested_motion_expression(
    events: list[dict], frame_offset: int, builder, default: str
) -> str:
    expression = default
    timeline_frame = f"(on+{frame_offset})"
    for event in reversed(events):
        start = round(float(event["start"]) * FPS)
        end = round(float(event["end"]) * FPS)
        expression = (
            f"if(between({timeline_frame},{start},{end}),"
            f"{builder(event)},{expression})"
        )
    return expression


def screen_motion_filter(events: list[dict], timeline_offset: float) -> str:
    if not events:
        return ""
    frame_offset = round(timeline_offset * FPS)
    zooms = {
        id(event): motion_event_zoom(event, frame_offset)
        for event in events
    }
    zoom = nested_motion_expression(
        events, frame_offset, lambda event: zooms[id(event)], "1"
    )
    x = nested_motion_expression(
        events,
        frame_offset,
        lambda event: (
            f"max(0,min(iw-iw/zoom,{float(event['center'][0]):.3f}-iw/(2*zoom)))"
        ),
        "0",
    )
    y = nested_motion_expression(
        events,
        frame_offset,
        lambda event: (
            f"max(0,min(ih-ih/zoom,{float(event['center'][1]):.3f}-ih/(2*zoom)))"
        ),
        "0",
    )
    return (
        f",zoompan=z='{zoom}':x='{x}':y='{y}':"
        f"d=1:s={OUTPUT_WIDTH}x{SCREEN_HEIGHT}:fps={FPS}"
    )


def render_clip(
    clip: ClipSpec,
    source: SourceProfile,
    output_dir: Path,
    preview_seconds: float | None,
    skip_hook: bool,
    overwrite: bool,
    layout_override: str | None = None,
) -> Path:
    layout_profile = layout_override or clip.layout_profile
    if layout_profile not in LAYOUT_PROFILES:
        raise ValueError(f"Unknown layout profile: {layout_profile}")
    hook_ranges = [] if skip_hook else list(clip.hook_ranges)
    pieces = hook_ranges + list(clip.full_ranges)
    hook_count = len(hook_ranges)
    total_duration = sum(end - start for start, end in pieces)
    motion_events = load_motion_events(clip.motion_plan, total_duration, pieces)
    screen_x, screen_y, screen_w, screen_h = centered_aspect_crop(source.screen_region)
    speaker_x, speaker_y, speaker_w, speaker_h = source.speaker_region
    rendered_speaker_height = speaker_height(source.speaker_region)
    floating_speaker_height = even(FLOATING_SPEAKER_WIDTH * speaker_h / speaker_w)
    floating_speaker_x = (OUTPUT_WIDTH - FLOATING_SPEAKER_WIDTH) // 2
    floating_speaker_y = OUTPUT_HEIGHT - FLOATING_BOTTOM_SAFE - floating_speaker_height
    if floating_speaker_y <= FLOATING_CAPTION_Y:
        raise ValueError(
            f"{source.key}.speaker_region is too tall for floating-card; "
            "measure a landscape speaker tile"
        )

    if layout_profile == "floating-card":
        title_y, caption_y = FLOATING_TITLE_Y, FLOATING_CAPTION_Y
    elif layout_profile == "immersive-speaker":
        title_y = caption_y = IMMERSIVE_TEXT_Y
    else:
        title_y = caption_y = TITLE_Y

    output_dir.mkdir(parents=True, exist_ok=True)
    preview_suffix = "-preview" if preview_seconds else ""
    output = output_dir / (
        f"{clip.clip_id}-{slugify(clip.title)}-{layout_profile}{preview_suffix}.mp4"
    )
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists; pass --overwrite to replace it: {output}")

    with tempfile.TemporaryDirectory(prefix=f"shortform-{clip.clip_id}-") as temp_dir:
        temp_root = Path(temp_dir)
        title_card = temp_root / "title.png"
        caption_video = temp_root / "captions.mov"
        make_title_card(clip.title, title_card)
        caption_words = output_caption_words(source, pieces)
        render_caption_overlay(
            caption_words,
            total_duration,
            caption_video,
            temp_root,
            card_style=layout_profile != "full-width-speaker",
        )

        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats"]
        for start, end in pieces:
            command.extend(
                ["-ss", format_time(start), "-t", f"{end - start:.3f}", "-i", str(source.video)]
            )
        title_input = len(pieces)
        command.extend(["-loop", "1", "-framerate", str(FPS), "-t", f"{total_duration:.3f}", "-i", str(title_card)])
        caption_input = title_input + 1
        command.extend(["-i", str(caption_video)])

        filters: list[str] = []
        concat_inputs: list[str] = []
        background_branches: list[str] = []
        screen_mask_branches: list[str] = []
        speaker_mask_branches: list[str] = []

        if layout_profile == "floating-card":
            background = temp_root / "floating-background.png"
            screen_mask = temp_root / "floating-screen-mask.png"
            speaker_mask = temp_root / "floating-speaker-mask.png"
            make_gradient_background(background)
            make_vertical_alpha_mask(
                screen_mask,
                FLOATING_SCREEN_LAYER_HEIGHT,
                FLOATING_SCREEN_FADE_START,
            )
            make_rounded_mask(
                speaker_mask,
                FLOATING_SPEAKER_WIDTH,
                floating_speaker_height,
            )
            background_input = caption_input + 1
            screen_mask_input = background_input + 1
            speaker_mask_input = screen_mask_input + 1
            command.extend(
                [
                    "-loop", "1", "-framerate", str(FPS), "-t", f"{total_duration:.3f}", "-i", str(background),
                    "-loop", "1", "-framerate", str(FPS), "-t", f"{total_duration:.3f}", "-i", str(screen_mask),
                    "-loop", "1", "-framerate", str(FPS), "-t", f"{total_duration:.3f}", "-i", str(speaker_mask),
                ]
            )
            background_branches = [f"floating_bg_{index}" for index in range(len(pieces))]
            screen_mask_branches = [f"floating_screen_mask_{index}" for index in range(len(pieces))]
            speaker_mask_branches = [f"floating_speaker_mask_{index}" for index in range(len(pieces))]
            if len(pieces) == 1:
                filters.extend(
                    [
                        f"[{background_input}:v]format=yuv420p[{background_branches[0]}]",
                        f"[{screen_mask_input}:v]format=gray[{screen_mask_branches[0]}]",
                        f"[{speaker_mask_input}:v]format=gray[{speaker_mask_branches[0]}]",
                    ]
                )
            else:
                filters.extend(
                    [
                        (
                            f"[{background_input}:v]format=yuv420p,"
                            f"split={len(pieces)}"
                            + "".join(f"[{name}]" for name in background_branches)
                        ),
                        (
                            f"[{screen_mask_input}:v]format=gray,"
                            f"split={len(pieces)}"
                            + "".join(f"[{name}]" for name in screen_mask_branches)
                        ),
                        (
                            f"[{speaker_mask_input}:v]format=gray,"
                            f"split={len(pieces)}"
                            + "".join(f"[{name}]" for name in speaker_mask_branches)
                        ),
                    ]
                )
        elif layout_profile == "immersive-speaker":
            screen_mask = temp_root / "immersive-screen-mask.png"
            make_vertical_alpha_mask(
                screen_mask,
                IMMERSIVE_SCREEN_LAYER_HEIGHT,
                IMMERSIVE_SCREEN_FADE_START,
            )
            screen_mask_input = caption_input + 1
            command.extend(
                ["-loop", "1", "-framerate", str(FPS), "-t", f"{total_duration:.3f}", "-i", str(screen_mask)]
            )
            screen_mask_branches = [f"immersive_screen_mask_{index}" for index in range(len(pieces))]
            if len(pieces) == 1:
                filters.append(
                    f"[{screen_mask_input}:v]format=gray[{screen_mask_branches[0]}]"
                )
            else:
                filters.append(
                    (
                        f"[{screen_mask_input}:v]format=gray,"
                        f"split={len(pieces)}"
                        + "".join(f"[{name}]" for name in screen_mask_branches)
                    )
                )

        piece_output_cursor = 0.0
        for index, (piece_start, piece_end) in enumerate(pieces):
            duration = piece_end - piece_start
            piece_motion = overlapping_motion_events(
                motion_events,
                piece_output_cursor,
                piece_output_cursor + duration,
            )
            motion_filter = screen_motion_filter(piece_motion, piece_output_cursor)
            video_transition = ""
            audio_transition = ""
            if hook_count and index == hook_count - 1:
                transition_start = max(0.0, duration - TRANSITION_SECONDS)
                video_transition = (
                    f",fade=t=out:st={transition_start:.3f}:d={TRANSITION_SECONDS:.3f}:"
                    f"color={FFMPEG_BACKGROUND}"
                )
                audio_transition = (
                    f",afade=t=out:st={transition_start:.3f}:d={TRANSITION_SECONDS:.3f}"
                )
            elif hook_count and index == hook_count:
                video_transition = (
                    f",fade=t=in:st=0:d={TRANSITION_SECONDS:.3f}:color={FFMPEG_BACKGROUND}"
                )
                audio_transition = f",afade=t=in:st=0:d={TRANSITION_SECONDS:.3f}"

            filters.extend(
                [
                    f"[{index}:v]split=2[screen_src_{index}][speaker_src_{index}]",
                    (
                        f"[screen_src_{index}]crop={screen_w}:{screen_h}:{screen_x}:{screen_y},"
                        f"scale={OUTPUT_WIDTH}:{SCREEN_HEIGHT}:flags=lanczos,"
                        f"fps={FPS}:start_time=0"
                        f"{motion_filter},setsar=1[screen_{index}]"
                    ),
                ]
            )

            if layout_profile == "floating-card":
                filters.extend(
                    [
                        (
                            f"[speaker_src_{index}]crop={speaker_w}:{speaker_h}:{speaker_x}:{speaker_y},"
                            f"scale={FLOATING_SPEAKER_WIDTH}:{floating_speaker_height}:"
                            f"flags=lanczos,fps={FPS}:start_time=0,setsar=1,"
                            f"format=rgba[floating_speaker_{index}]"
                        ),
                        (
                            f"[screen_{index}]pad={OUTPUT_WIDTH}:{FLOATING_SCREEN_LAYER_HEIGHT}:"
                            f"0:{SCREEN_Y}:color={FFMPEG_BACKGROUND},"
                            f"format=rgba[floating_screen_layer_{index}]"
                        ),
                        (
                            f"[floating_screen_layer_{index}]"
                            f"[{screen_mask_branches[index]}]"
                            f"alphamerge=shortest=1[floating_screen_{index}]"
                        ),
                        (
                            f"[{background_branches[index]}][floating_screen_{index}]"
                            f"overlay=0:0:shortest=1[floating_with_screen_{index}]"
                        ),
                        (
                            f"[floating_speaker_{index}]"
                            f"[{speaker_mask_branches[index]}]"
                            f"alphamerge=shortest=1[floating_speaker_rounded_{index}]"
                        ),
                        (
                            f"[floating_with_screen_{index}]"
                            f"[floating_speaker_rounded_{index}]"
                            f"overlay={floating_speaker_x}:{floating_speaker_y}:shortest=1"
                            f"{video_transition},fps={FPS},format=yuv420p,"
                            f"setpts=PTS-STARTPTS[v{index}]"
                        ),
                    ]
                )
            elif layout_profile == "immersive-speaker":
                filters.extend(
                    [
                        (
                            f"[speaker_src_{index}]crop={speaker_w}:{speaker_h}:{speaker_x}:{speaker_y},"
                            f"scale={OUTPUT_WIDTH}:{IMMERSIVE_SPEAKER_HEIGHT}:"
                            "force_original_aspect_ratio=increase:flags=lanczos,"
                            f"crop={OUTPUT_WIDTH}:{IMMERSIVE_SPEAKER_HEIGHT},"
                            f"fps={FPS}:start_time=0,setsar=1[immersive_speaker_{index}]"
                        ),
                        (
                            f"[immersive_speaker_{index}]pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:"
                            f"0:{IMMERSIVE_SPEAKER_Y}:color={BOTTOM_BACKGROUND}"
                            f"[immersive_canvas_{index}]"
                        ),
                        (
                            f"[screen_{index}]pad={OUTPUT_WIDTH}:{IMMERSIVE_SCREEN_LAYER_HEIGHT}:"
                            f"0:{SCREEN_Y}:color={FFMPEG_BACKGROUND},"
                            f"format=rgba[immersive_screen_layer_{index}]"
                        ),
                        (
                            f"[immersive_screen_layer_{index}]"
                            f"[{screen_mask_branches[index]}]"
                            f"alphamerge=shortest=1[immersive_screen_{index}]"
                        ),
                        (
                            f"[immersive_canvas_{index}][immersive_screen_{index}]"
                            f"overlay=0:0:shortest=1"
                            f"{video_transition},fps={FPS},format=yuv420p,"
                            f"setpts=PTS-STARTPTS[v{index}]"
                        ),
                    ]
                )
            else:
                filters.extend(
                    [
                        (
                            f"[speaker_src_{index}]crop={speaker_w}:{speaker_h}:{speaker_x}:{speaker_y},"
                            f"scale={OUTPUT_WIDTH}:{rendered_speaker_height}:flags=lanczos,"
                            f"fps={FPS}:start_time=0,setsar=1[speaker_{index}]"
                        ),
                        (
                            f"[screen_{index}]pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:0:{SCREEN_Y}:"
                            f"color={FFMPEG_BACKGROUND},"
                            f"drawbox=x=0:y={SPEAKER_Y}:w={OUTPUT_WIDTH}:"
                            f"h={OUTPUT_HEIGHT - SPEAKER_Y}:"
                            f"color={BOTTOM_BACKGROUND}:t=fill[canvas_{index}]"
                        ),
                        (
                            f"[canvas_{index}][speaker_{index}]overlay=x=0:y={SPEAKER_Y}:shortest=1"
                            f"{video_transition},fps={FPS},format=yuv420p,"
                            f"setpts=PTS-STARTPTS[v{index}]"
                        ),
                    ]
                )

            filters.append(
                (
                    f"[{index}:a]aresample=48000{audio_transition},"
                    f"asetpts=PTS-STARTPTS[a{index}]"
                )
            )
            concat_inputs.append(f"[v{index}][a{index}]")
            piece_output_cursor += duration

        filters.append(
            f"{''.join(concat_inputs)}concat=n={len(pieces)}:v=1:a=1[joined_v][out_a]"
        )
        filters.append(f"[{title_input}:v]format=rgba[title]")
        filters.append(
            f"[joined_v][title]overlay=x=0:y={title_y}:"
            f"enable='lt(t,{TITLE_SECONDS})':shortest=1[titled_v]"
        )
        filters.append(f"[{caption_input}:v]format=rgba[caption_overlay]")
        filters.append(
            f"[titled_v][caption_overlay]overlay=x=0:y={caption_y}:"
            f"enable='gte(t,{TITLE_SECONDS})':eof_action=pass:shortest=0[out_v]"
        )

        # Keep image-loop/framesync scheduling bounded and deterministic. With
        # several infinite mask inputs, automatic filter thread pools can stall
        # on newer FFmpeg versions. The manifest already fixes the output length.
        command.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters), "-map", "[out_v]", "-map", "[out_a]"])
        command.extend(["-t", f"{min(total_duration, preview_seconds) if preview_seconds else total_duration:.3f}"])
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                "-shortest",
                "-y" if overwrite else "-n",
                str(output),
            ]
        )

        print(
            f"Rendering clip {clip.clip_id}: {clip.title}\n"
            f"  Source: {source.key}\n"
            f"  Layout: {layout_profile}\n"
            f"  Motion events: {len(motion_events)}\n"
            f"  Background: {BACKGROUND}\n"
            f"  Caption words: {len(caption_words)}\n"
            f"  Pieces: {', '.join(f'{format_time(a)}-{format_time(b)}' for a, b in pieces)}\n"
            f"  Output: {output}"
        )
        run(command)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--clip", help="Render one manifest clip id")
    target.add_argument("--all", action="store_true", help="Render every manifest clip")
    target.add_argument("--check", action="store_true", help="Validate without rendering")
    parser.add_argument("--preview-seconds", type=float)
    parser.add_argument("--skip-hook", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--layout-profile",
        choices=sorted(LAYOUT_PROFILES),
        help="Override the manifest layout for this render or comparison proof",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if args.preview_seconds is not None and args.preview_seconds <= 0:
        raise ValueError("--preview-seconds must be greater than zero")

    sources, clips, manifest_output = load_manifest(manifest_path)
    validate_manifest(sources, clips)
    if args.check:
        cold_opens = sum(not clip.hook_ranges for clip in clips)
        prepended_hooks = len(clips) - cold_opens
        print(
            f"Validated {len(clips)} clips across {len(sources)} source profiles: "
            f"{cold_opens} cold opens, {prepended_hooks} prepended hooks; "
            f"layouts: {', '.join(sorted({clip.layout_profile for clip in clips}))}."
        )
        return 0

    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else manifest_output
    if args.all:
        selected = clips
    else:
        selected = [clip for clip in clips if clip.clip_id == str(args.clip)]
        if not selected:
            raise ValueError(f"Clip id not found in manifest: {args.clip}")

    for clip in selected:
        render_clip(
            clip,
            sources[clip.source_key],
            output_dir,
            args.preview_seconds,
            args.skip_hook,
            args.overwrite,
            args.layout_profile,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
