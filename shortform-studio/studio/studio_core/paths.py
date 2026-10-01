"""Path resolution for Shortform Studio.

studio dir   = folder containing studio.py (parent of this package)
skill root   = studio dir's parent (the shortform-studio skill folder: SKILL.md,
               references/, scripts/, studio/)
DATA_DIR     = $STUDIO_DATA_DIR, or ./shortform-studio-data relative to the
               current working directory when the server (or CLI) was started.

All directories are created lazily by callers, not by this module.
"""
from __future__ import annotations

import os

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def studio_dir() -> str:
    return os.path.dirname(_PKG_DIR)


def skill_root() -> str:
    return os.path.dirname(studio_dir())


def data_dir() -> str:
    env = os.environ.get("STUDIO_DATA_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.abspath(os.path.join(os.getcwd(), "shortform-studio-data"))


def clips_dir() -> str:
    return os.path.join(data_dir(), "clips")


def recordings_dir() -> str:
    return os.path.join(data_dir(), "recordings")


def batches_file() -> str:
    return os.path.join(data_dir(), "batches.json")


def taste_file() -> str:
    return os.path.join(data_dir(), "taste.json")


def taste_seed_file() -> str:
    return os.path.join(skill_root(), "references", "taste-seed.json")


def settings_file() -> str:
    return os.path.join(data_dir(), "settings.json")


def events_file() -> str:
    return os.path.join(data_dir(), "events.jsonl")


def cache_dir() -> str:
    return os.path.join(data_dir(), "cache")


def logs_dir() -> str:
    return os.path.join(data_dir(), "logs")


def renders_root() -> str:
    return os.path.join(data_dir(), "renders")


def web_dir() -> str:
    return os.path.join(studio_dir(), "web")


def clip_file(clip_id: str) -> str:
    return os.path.join(clips_dir(), "%s.json" % clip_id)


def clip_lock_file(clip_id: str) -> str:
    return os.path.join(clips_dir(), "%s.lock" % clip_id)


def recording_file(rec_id: str) -> str:
    return os.path.join(recordings_dir(), "%s.json" % rec_id)


def recording_lock_file(rec_id: str) -> str:
    return os.path.join(recordings_dir(), "%s.lock" % rec_id)


def default_media_roots():
    return [data_dir(), os.path.expanduser("~/Downloads")]


# ---------------------------------------------------------------------------
# v2: recipes ("the edit spec") + snapshots
# ---------------------------------------------------------------------------

def edits_dir() -> str:
    return os.path.join(data_dir(), "edits")


def edit_file(clip_id: str) -> str:
    return os.path.join(edits_dir(), "%s.json" % clip_id)


def edit_lock_file(clip_id: str) -> str:
    return os.path.join(edits_dir(), "%s.lock" % clip_id)


def edit_snapshot_dir(clip_id: str) -> str:
    return os.path.join(edits_dir(), clip_id)


def edit_snapshot_file(clip_id: str, n) -> str:
    return os.path.join(edit_snapshot_dir(clip_id), "v%s.json" % n)
