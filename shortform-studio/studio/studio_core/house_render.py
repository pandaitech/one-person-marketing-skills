"""House-style recipe renderer - numpy + Pillow frame compositor piped into
ffmpeg, driven by a generic recipe (house_plan.py) instead of hard-coded
scenes. Colours and font come from the "theme" in Studio settings (see
theme() below); the defaults are a neutral off-white/near-black/blue.

Not stdlib-only - run through uv so numpy/Pillow are available without a
project-wide dependency:

    uv run --with pillow --with numpy python -m studio_core.house_render \\
        render <spec.json> <out.mp4> [--progress <file.json>]
    uv run --with pillow --with numpy python -m studio_core.house_render \\
        still <spec.json> <t_out> <out.jpg> [--width 540]

(cwd = the studio dir, so `studio_core` is importable.)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studio_core import house_plan, paths  # noqa: E402

# ---------------------------------------------------------------------------
# theme: colours + font, overridable from Studio settings ("theme" dict).
# Defaults are a neutral, brand-agnostic palette. SKILL.md fills these in from
# a brand's marketing-brain.md (background/text/accent colours + font family)
# when one is supplied; otherwise these defaults are used as-is.
# ---------------------------------------------------------------------------

_DEFAULT_THEME = {
    "background": "#F4F3EF",
    "text": "#1C1C1C",
    "accent": "#3B6EA5",
    "accent2": "#2B4C6F",
    "font": "Inter",
}


def _hex_to_rgb(value, fallback):
    if not value or not isinstance(value, str):
        return fallback
    v = value.strip().lstrip("#")
    if len(v) != 6:
        return fallback
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def theme():
    """Read the active theme once per process: Studio settings.json "theme"
    patch merged over the neutral defaults above."""
    if not hasattr(theme, "_cache"):
        merged = dict(_DEFAULT_THEME)
        try:
            with open(paths.settings_file(), "r", encoding="utf-8") as f:
                saved = json.load(f).get("theme") or {}
            merged.update({k: v for k, v in saved.items() if v})
        except (OSError, ValueError):
            pass
        theme._cache = merged
    return theme._cache


# ---------------------------------------------------------------------------
# "house-v1" look constants
# ---------------------------------------------------------------------------

W, H, FPS, SR = 1080, 1920, 24, 48000

BG = np.array(_hex_to_rgb(theme().get("background"), (244, 243, 239)), np.float32)
TEXT = _hex_to_rgb(theme().get("text"), (28, 28, 28))
ACCENT2 = _hex_to_rgb(theme().get("accent2"), (43, 76, 111))
ACCENT = _hex_to_rgb(theme().get("accent"), (59, 110, 165))
FONT_FAMILY = theme().get("font") or "Inter"

VID_W, VID_H = 968, 542
VID_X, VID_Y = (W - VID_W) // 2, 760
BORDER = 14

HEAD_LEFT, HEAD_SIZE, HEAD_LINE, HEAD_TRACK = 84, 100, 112, -2.5
HEAD_BOTTOM = 672
CAP_SIZE, CAP_TOP, CAP_MAXW = 68, VID_Y + VID_H + BORDER + 40, 980

TITLE_LEAD = house_plan.TITLE_LEAD  # 0.8s - title is fully drawn by output frame 0

# "screen" moment: the class's live screen share fills a wide panel on the stage
# (leaving room for the title/headlines above and captions below), the speaker
# becomes a small corner cam. Geometry lives here (not house_plan.py, which is
# stdlib-only and output-time-only) since it's pixels, not timing.
SCREEN_X, SCREEN_Y, SCREEN_W, SCREEN_MAXH, SCREEN_R = 40, 706, 1000, 616, 30
SCREEN_TRANS = 0.4  # ease in/out, same order of magnitude as the fullscreen card slide
SCREEN_CAM_W, SCREEN_CAM_MARGIN, SCREEN_CAM_EDGE, SCREEN_CAM_R = 260, 24, 5, 22
# Consecutive screen moments within house_plan.SCREEN_ADJACENT_GAP hand over
# directly (see build_screen_chains/screen_chain_alpha): the speaker card
# never reappears between them, and the panel content cross-fades over this
# window instead, centred on the boundary between the two moments.
SCREEN_CROSSFADE = 0.3


def house_assets_dir():
    return os.path.join(paths.data_dir(), "assets", "house")


def _font(name):
    return os.path.join(house_assets_dir(), name)


# No font files ship in the skill. FONT_BOLD()/FONT_SEMI() download the theme
# font (default: Inter) from Google Fonts into the data dir the first time a
# render needs it, and cache it there. Offline, or if the family isn't found,
# they fall back to a system sans-serif so rendering still works.
_GOOGLE_FONTS_CSS = "https://fonts.googleapis.com/css2?family={family}:wght@{weight}&display=swap"
# Google Fonts serves woff2/woff to a modern desktop UA. An old mobile UA that
# predates woff support is the standard trick to get a plain, Pillow-loadable
# .ttf URL back instead.
_UA = "Mozilla/5.0 (Linux; U; Android 2.2) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1"

_SYSTEM_SANS_FALLBACKS = {
    700: [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    600: [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
}


def _download_font(weight, dest_path):
    family = FONT_FAMILY.replace(" ", "+")
    css_url = _GOOGLE_FONTS_CSS.format(family=family, weight=weight)
    req = urllib.request.Request(css_url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=6) as r:
        css = r.read().decode("utf-8", "ignore")
    m = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)", css)
    if not m:
        raise RuntimeError("no ttf source in Google Fonts response for %s" % FONT_FAMILY)
    with urllib.request.urlopen(m.group(1), timeout=8) as r:
        data = r.read()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp = dest_path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest_path)


def _ensure_weight_font(name, weight):
    path = _font(name)
    if os.path.exists(path):
        return path
    try:
        _download_font(weight, path)
        return path
    except Exception:
        pass  # offline, blocked, or family not on Google Fonts -- fall back below
    for cand in _SYSTEM_SANS_FALLBACKS.get(weight, []):
        if os.path.exists(cand):
            return cand
    raise RuntimeError(
        "no usable font found for weight %s: offline and no system fallback present" % weight)


def FONT_BOLD():
    return _ensure_weight_font("theme-700.ttf", 700)


def FONT_SEMI():
    return _ensure_weight_font("theme-600.ttf", 600)


# Decorative "manuscript page" moment only (see build_page below) -- not the
# theme font. Falls back to a system serif, then to FONT_SEMI(), so a render
# never fails just because this one macOS-only font isn't installed.
_TYPEWRITER_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


def _typewriter_font(size, index=0):
    ttc = _TYPEWRITER_CANDIDATES[0]
    if os.path.exists(ttc):
        try:
            return ImageFont.truetype(ttc, size, index=index)
        except Exception:
            pass
    for cand in _TYPEWRITER_CANDIDATES[1:]:
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.truetype(FONT_SEMI(), size)


# ---------------------------------------------------------------------------
# generic drawing helpers (verbatim port from the V02/V01 renderers)
# ---------------------------------------------------------------------------

def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back_out(x, s=1.9):
    x = min(max(x, 0.0), 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def rgba(im):
    return np.asarray(im.convert("RGBA")).astype(np.float32) / 255.0


def blend(frame, spr, x, y, alpha=1.0, cols=None):
    h, w = spr.shape[:2]
    if cols is not None:
        w = max(0, min(w, int(cols)))
        spr = spr[:, :w]
    x, y = int(round(x)), int(round(y))
    fh, fw = frame.shape[:2]
    fx0, fy0, fx1, fy1 = max(x, 0), max(y, 0), min(x + w, fw), min(y + h, fh)
    if fx0 >= fx1 or fy0 >= fy1 or alpha <= 0:
        return
    s = spr[fy0 - y:fy1 - y, fx0 - x:fx1 - x]
    a = s[..., 3:4] * alpha
    region = frame[fy0:fy1, fx0:fx1]
    frame[fy0:fy1, fx0:fx1] = region * (1 - a) + s[..., :3] * 255 * a


def tracked_text(text, font, color, track=0.0, pad=16):
    asc, desc = font.getmetrics()
    xs = [font.getlength(text[:i]) + i * track for i in range(len(text) + 1)]
    im = Image.new("RGBA", (int(xs[-1]) + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ch in enumerate(text):
        d.text((pad + xs[i], pad), ch, font=font, fill=color + (255,))
    return im, xs, asc, desc


def brush_marker(w, h, seed):
    rng = np.random.default_rng(seed)
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    step = 26
    top = [(x, 4 + rng.uniform(-3, 3)) for x in range(4, w + 5, step)] + [(w + 4, 4 + rng.uniform(-2, 2))]
    bot = [(x, h + 4 + rng.uniform(-3, 3)) for x in range(w + 4, 3, -step)] + [(4, h + 4)]
    ImageDraw.Draw(im).polygon(top + bot, fill=ACCENT + (255,))
    return rgba(im.filter(ImageFilter.GaussianBlur(0.6)))


def wrap(text, font, maxw):
    words = text.split()
    if font.getlength(text) <= maxw:
        return [text]
    best = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        mm = max(font.getlength(a), font.getlength(b))
        if best is None or mm < best[0]:
            best = (mm, [a, b])
    return best[1]


# ---------------------------------------------------------------------------
# rounded-corner + soft-shadow helpers, for the "screen" moment's panel and
# corner cam (no hand-drawn card shape there - just rounded rectangles, so it
# reads as a clean livestream overlay rather than another bordered card).
# ---------------------------------------------------------------------------

_ROUND_MASKS = {}


def round_mask(w, h, r):
    key = (w, h, r)
    if key not in _ROUND_MASKS:
        k = 3  # supersample so the corner curve stays smooth after downscale
        im = Image.new("L", (w * k, h * k), 0)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), r * k, fill=255)
        _ROUND_MASKS[key] = im.resize((w, h), Image.LANCZOS)
    return _ROUND_MASKS[key]


def rounded(img, r):
    im = img.convert("RGBA")
    im.putalpha(round_mask(im.width, im.height, r))
    return rgba(im)


_PANEL_SHADOWS = {}


def panel_shadow(w, h, r, strength=0.28):
    """Soft shadow sprite (and its margin) for a w x h rounded rect - same warm
    ink colour as build_item()'s/build_card()'s shadows, so it reads as part of
    the house look rather than the reference renderer's plain black shadow."""
    key = (w, h, r, strength)
    if key not in _PANEL_SHADOWS:
        mg = 46
        im = Image.new("L", (w + 2 * mg, h + 2 * mg), 0)
        ImageDraw.Draw(im).rounded_rectangle((mg, mg + 12, mg + w, mg + h + 12), r, fill=int(255 * strength))
        im = im.filter(ImageFilter.GaussianBlur(18))
        spr = np.zeros((im.height, im.width, 4), np.float32)
        spr[..., 3] = np.asarray(im, np.float32) / 255
        spr[..., :3] = np.array([40, 30, 10], np.float32) / 255
        _PANEL_SHADOWS[key] = (spr, mg)
    return _PANEL_SHADOWS[key]


# ---------------------------------------------------------------------------
# paper background + speaker card
# ---------------------------------------------------------------------------

def build_paper():
    """Solid theme background plus a very subtle fine-grain texture (~2-4%
    luminance noise, like real paper) - no image asset needed. Deliberately
    understated: this must read as a clean background, not visible static."""
    rng = np.random.default_rng(20260930)
    noise_img = np.clip(rng.standard_normal((H, W)) * 55 + 128, 0, 255).astype(np.uint8)
    tex = np.asarray(Image.fromarray(noise_img).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32)
    grain = (tex - 128.0)[..., None] * 0.13
    return np.clip(BG + grain, 0, 255)


def build_card():
    mg = 60
    cw, ch = VID_W + 2 * BORDER, VID_H + 2 * BORDER
    im = Image.new("RGBA", (cw + 2 * mg, ch + 2 * mg), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rectangle((mg + 6, mg + 18, mg + cw + 4, mg + ch + 18), fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(20))
    im.paste(Image.new("RGBA", im.size, (40, 30, 10, 255)), (0, 0), sh)
    x0, y0, x1, y1 = mg, mg, mg + cw, mg + ch
    pts = [(x0 - 2, y0 - 3), ((x0 + x1) // 2, y0 - 6), (x1 + 3, y0 + 1), (x1 + 1, (y0 + y1) // 2),
           (x1 - 2, y1 + 3), ((x0 + x1) // 2, y1 + 5), (x0 + 1, y1 + 1), (x0 - 3, (y0 + y1) // 2)]
    ImageDraw.Draw(im).polygon(pts, fill=ACCENT2 + (255,))
    return rgba(im), (VID_X - BORDER - mg, VID_Y - BORDER - mg)


# ---------------------------------------------------------------------------
# headlines (and the title, which is just a headline with a fixed reveal time)
# ---------------------------------------------------------------------------

def resolve_lines(lines_spec, spec):
    """spec's line list (each {"text","at","hl"} or {"dim":true,"at"}) into
    the (text_or_"__dim__", output_at, hl) tuples headline_rows() expects."""
    out = []
    for line in lines_spec or []:
        at = house_plan.src_to_out(spec, line.get("at", 0)) or 0.0
        if line.get("dim"):
            out.append(("__dim__", at, None))
        else:
            out.append((line.get("text", ""), at, line.get("hl")))
    return out


def headline_rows(lines, bottom, seed, top=None, shrink=True):
    """Rows for one headline. Font shrinks (per headline) so the widest real
    (non-dim) line fits. Ported verbatim from the V02 renderer.

    `shrink=False` reproduces the V01 v3 renderer's simpler headline_rows,
    which never shrinks and always draws at HEAD_SIZE - a real difference
    between the two approved renderers (V02 added the auto-fit later), not a
    "look" choice, so it is a `look.shrink_headlines` spec flag rather than a
    module constant."""
    real = [l for l in lines if l[0] != "__dim__"]
    if shrink:
        probe = ImageFont.truetype(FONT_BOLD(), HEAD_SIZE)
        widest = max(probe.getlength(t) + len(t) * HEAD_TRACK for t, _, _ in real)
        size = int(min(HEAD_SIZE, HEAD_SIZE * (W - 2 * HEAD_LEFT) / widest))
    else:
        size = HEAD_SIZE
    font = ImageFont.truetype(FONT_BOLD(), size)
    line_h = round(HEAD_LINE * size / HEAD_SIZE)
    if top is None:
        top = bottom - line_h * len(real)
    rows, i = [], 0
    for text, at, hl in lines:
        if text == "__dim__":
            for r in rows:
                r["dim_at"] = at
            continue
        im, xs, asc, desc = tracked_text(text, font, TEXT, HEAD_TRACK * size / HEAD_SIZE)
        row = {"spr": rgba(im), "at": at, "x": HEAD_LEFT - 16, "y": top + i * line_h - 16, "marker": None, "dim_at": None}
        if hl:
            k = text.index(hl)
            mx0, mx1 = 16 + xs[k] - 12, 16 + xs[k + len(hl)] + 10
            mh = int(asc * 0.86)
            row["marker"] = (brush_marker(int(mx1 - mx0), mh, seed + i), mx0 - 4, 16 + asc * 0.2 - 4)
        rows.append(row)
        i += 1
    return rows


def _shrink_headlines(spec):
    return bool((spec.get("look", {}) or {}).get("shrink_headlines", True))


def build_headlines(spec):
    """[{"end": out_t, "rows": [...]}] for the title (if any) then every
    headline, in spec order - the title behaves exactly like a headline whose
    lines are all revealed TITLE_LEAD seconds before output 0."""
    out = []
    n = 0
    shrink = _shrink_headlines(spec)
    title = spec.get("title")
    if title:
        end = house_plan.src_to_out(spec, title.get("until", 0)) or 0.0
        lines = [(l.get("text", ""), -TITLE_LEAD, l.get("hl")) for l in title.get("lines", [])]
        out.append({"end": end, "rows": headline_rows(lines, HEAD_BOTTOM, 10 * n, shrink=shrink)})
        n += 1
    for hl in spec.get("headlines", []) or []:
        end = house_plan.src_to_out(spec, hl.get("until", 0)) or 0.0
        lines = resolve_lines(hl.get("lines", []), spec)
        out.append({"end": end, "rows": headline_rows(lines, HEAD_BOTTOM, 10 * n, shrink=shrink)})
        n += 1
    return out


def draw_rows(f, head, t, start_fade_at):
    out_a = 1.0 - ease_out((t - start_fade_at) / 0.25) if t > start_fade_at else 1.0
    if out_a <= 0:
        return
    for r in head["rows"]:
        if t < r["at"]:
            continue
        k = ease_out((t - r["at"]) / 0.35)
        dy = 24 * (1 - k)
        dim = 1.0 - 0.62 * ease_out((t - r["dim_at"]) / 0.35) if r["dim_at"] is not None and t > r["dim_at"] else 1.0
        if r["marker"]:
            mk, mx, my = r["marker"]
            p = ease_out((t - r["at"] - 0.2) / 0.3)
            if p > 0:
                blend(f, mk, r["x"] + mx, r["y"] + my + dy, out_a * dim, cols=mk.shape[1] * p)
        blend(f, r["spr"], r["x"], r["y"] + dy, k * out_a * dim)


# ---------------------------------------------------------------------------
# fullscreen moments: items (photo/cutout/book frame styles) + year counter
# ---------------------------------------------------------------------------

def _find_image(path):
    if os.path.exists(path):
        return path
    # allow an extension-less reference (mirrors ROOT.glob(f"assets/img/{name}.*"))
    d, base = os.path.split(path)
    stem = os.path.splitext(base)[0]
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if os.path.splitext(name)[0] == stem:
                return os.path.join(d, name)
    raise FileNotFoundError(path)


def build_item(item_spec):
    path = _find_image(item_spec["image"])
    frame = item_spec.get("frame") or "cutout"
    scale, ang = float(item_spec.get("scale", 1.0)), float(item_spec.get("angle", 0.0))
    im = Image.open(path).convert("RGBA")
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)

    if frame == "book":  # spine shading on the left edge
        shade = Image.new("L", im.size, 0)
        d = ImageDraw.Draw(shade)
        for x in range(18):
            d.line([(x, 0), (x, im.height)], fill=int(90 * (1 - x / 18)))
        dark = Image.new("RGBA", im.size, (0, 0, 0, 255))
        dark.putalpha(shade)
        im.alpha_composite(dark)
    elif frame == "photo":  # off-white printed-photo card, thin navy keyline
        card = Image.new("RGBA", (im.width + 28, im.height + 28), (252, 249, 240, 255))
        card.paste(im, (14, 14))
        ImageDraw.Draw(card).rectangle((0, 0, card.width - 1, card.height - 1), outline=(214, 205, 180, 255), width=2)
        im = card
    # frame == "cutout": no extra border, just the shadow below.

    im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", (im.width + 60, im.height + 60), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * 0.22))
    blk = Image.new("RGBA", im.size, (40, 30, 10, 255))
    blk.putalpha(a)
    sh.paste(blk, (30 + 6, 30 + 12), blk)
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    sh.alpha_composite(im, (30, 30))

    tag = None
    label = item_spec.get("label")
    if label:
        lab_font = ImageFont.truetype(FONT_BOLD(), 46)
        tw = int(lab_font.getlength(label))
        tag_im = Image.new("RGBA", (tw + 52, 80), ACCENT + (255,))
        ImageDraw.Draw(tag_im).text((26, 12), label, font=lab_font, fill=TEXT + (255,))
        tag = rgba(tag_im.rotate(-ang * 0.8, resample=Image.BICUBIC, expand=True))

    return {"img": sh, "tag": tag, "cx": item_spec.get("x", W / 2), "cy": item_spec.get("y", H / 2),
            "tag_y": item_spec.get("y", H / 2) + im.height // 2 + 18, "cache": {}}


def build_items(items_spec, spec):
    out = []
    for it in items_spec or []:
        built = build_item(it)
        built["at"] = house_plan.src_to_out(spec, it.get("at", 0)) or 0.0
        out.append(built)
    return out


def draw_items(f, items, t, fs_a):
    for it in items:
        if t < it["at"] or fs_a <= 0:
            continue
        k = (t - it["at"]) / 0.45
        sc = 0.55 + 0.45 * back_out(k)
        key = round(sc, 3) if k < 1 else 1.0
        spr = it["cache"].get(key)
        if spr is None:
            im = it["img"] if key == 1.0 else it["img"].resize(
                (max(1, round(it["img"].width * sc)), max(1, round(it["img"].height * sc))), Image.BILINEAR)
            spr = rgba(im)
            it["cache"][key] = spr
        a = min(1.0, (t - it["at"]) / 0.12) * fs_a
        blend(f, spr, it["cx"] - spr.shape[1] / 2, it["cy"] - spr.shape[0] / 2 - 40 * (1 - fs_a), a)
        kt = (t - it["at"] - 0.18) / 0.25
        if kt > 0 and it["tag"] is not None:
            tag = it["tag"]
            blend(f, tag, it["cx"] - tag.shape[1] / 2, it["tag_y"] + 18 * (1 - ease_out(kt)) - 40 * (1 - fs_a),
                  ease_out(kt) * fs_a)


def build_ticker(steps):
    font = ImageFont.truetype(FONT_BOLD(), 330)
    sprites = {}
    for y in steps:
        im, xs, asc, desc = tracked_text(y, font, TEXT, -10, pad=20)
        sprites[y] = rgba(im)
    im, xs, asc, desc = tracked_text(steps[-1], font, TEXT, -10, pad=20)
    marker = (brush_marker(int(xs[-1]) + 30, int(asc * 0.42), 7), 20 - 19, 20 + asc * 0.62)
    return {"digits": sprites, "marker": marker}


def build_counter(counter_spec, spec):
    steps = house_plan.counter_steps(counter_spec)
    start_t = house_plan.src_to_out(spec, counter_spec["start"]) or 0.0
    land_t = house_plan.src_to_out(spec, counter_spec["land"]) or 0.0
    ticks = house_plan.ticker_ticks(start_t, land_t, len(steps))
    resolved = {
        "steps": steps, "start": start_t, "land": land_t, "cy": counter_spec.get("y", H / 2),
        "ticks": ticks, "sprites": build_ticker(steps),
    }
    if counter_spec.get("shrink") is not None:
        resolved["shrink"] = house_plan.src_to_out(spec, counter_spec["shrink"])
        resolved["shrink_to"] = tuple(counter_spec.get("shrink_to", (resolved["cy"], 1.0)))
    if counter_spec.get("persist") is not None:
        resolved["persist"] = house_plan.src_to_out(spec, counter_spec["persist"])
    return resolved


def draw_ticker(f, tk, t, fs_a):
    sp = tk["sprites"]
    if t < tk["start"] or fs_a <= 0:
        return
    idx = sum(1 for c in tk["ticks"] if t >= c)
    steps = tk["steps"]
    landed = t >= tk["land"]
    # ticker_ticks() deliberately excludes the final transition (it coincides
    # with "land", which gets its own impact SFX instead of a key-press), so
    # idx from the tick count alone tops out one step short. Once landed, the
    # displayed value must be the true final one - matching the approved V02
    # v5 render, which lands on the counter's actual `to` value.
    if landed:
        idx = len(steps) - 1
    spr = sp["digits"][steps[min(idx, len(steps) - 1)]]
    appear = ease_out((t - tk["start"]) / 0.2)
    bump = 1.0
    if landed:
        k = (t - tk["land"]) / 0.3
        bump = 1.0 + 0.08 * (1 - ease_out(k))
    if bump != 1.0:
        im = Image.fromarray((spr * 255).astype(np.uint8), "RGBA")
        im = im.resize((round(im.width * bump), round(im.height * bump)), Image.BILINEAR)
        spr = rgba(im)
    cy, shrink = tk["cy"], 0.0
    if tk.get("shrink") is not None and t > tk["shrink"]:
        shrink = ease_in_out((t - tk["shrink"]) / 0.5)
        to_y, to_s = tk["shrink_to"]
        cy = tk["cy"] + (to_y - tk["cy"]) * shrink
        sc_ = 1 + (to_s - 1) * shrink
        im = Image.fromarray((spr * 255).astype(np.uint8), "RGBA")
        spr = rgba(im.resize((round(im.width * sc_), round(im.height * sc_)), Image.BILINEAR))
    x = (W - spr.shape[1]) / 2
    y = cy - spr.shape[0] / 2 - 40 * (1 - fs_a)
    if shrink > 0.6:
        if "small_marker" not in sp:
            mk, mx, my = sp["marker"]
            to_s = tk["shrink_to"][1]
            im = Image.fromarray((mk * 255).astype(np.uint8), "RGBA")
            sp["small_marker"] = (rgba(im.resize((round(im.width * to_s), round(im.height * to_s)))), mx * to_s, my * to_s)
        smk, smx, smy = sp["small_marker"]
        blend(f, smk, x + smx, y + smy, fs_a * min(1.0, (shrink - 0.6) / 0.4))
    if landed and shrink == 0.0:
        mk, mx, my = sp["marker"]
        p = ease_out((t - tk["land"] - 0.15) / 0.35)
        if p > 0:
            base_w = sp["digits"][steps[-1]].shape[1]
            blend(f, mk, (W - base_w) / 2 + mx, tk["cy"] - sp["digits"][steps[-1]].shape[0] / 2 + my - 40 * (1 - fs_a),
                  fs_a, cols=mk.shape[1] * p)
    blend(f, spr, x, y, appear * fs_a)


def build_scene(mom_spec, spec, seed):
    slide_src = house_plan.fullscreen_slide_src(mom_spec)
    slide_t = house_plan.src_to_out(spec, slide_src) or 0.0
    out_t = house_plan.src_to_out(spec, mom_spec.get("until", 0)) or 0.0
    head_spec = mom_spec.get("head", {}) or {}
    head_lines = resolve_lines(head_spec.get("lines", []), spec)
    head_end = house_plan.src_to_out(spec, head_spec.get("until", mom_spec.get("until", 0))) or out_t
    items = build_items(mom_spec.get("items", []), spec)
    counter_spec = mom_spec.get("counter")
    return {
        "id": mom_spec.get("id"),
        "slide": slide_t, "out": out_t,
        # `head.top`: an explicit pixel Y for the head block's top edge, for a
        # scene whose items sit high enough that the default bottom-anchored
        # position (HEAD_BOTTOM, same as a regular headline) would collide
        # with them - e.g. the V01 renderer's single fullscreen scene pins its
        # head at a literal y=220 for exactly this reason. Omit it (as every
        # V02 scene does) to bottom-anchor at HEAD_BOTTOM like a headline.
        "head_rows": {"end": head_end,
                      "rows": headline_rows(head_lines, HEAD_BOTTOM, 99 + seed, top=head_spec.get("top"),
                                             shrink=_shrink_headlines(spec))},
        "item_sprites": items,
        "ticker": build_counter(counter_spec, spec) if counter_spec else None,
    }


def build_scenes(spec):
    return [build_scene(m, spec, i) for i, m in enumerate(spec.get("moments", []) or []) if m.get("kind") == "fullscreen"]


def punch_zoom(t, zooms):
    for a, b, z, cx, cy in zooms:
        if a <= t < b + 0.35:
            if t < a + 0.3:
                return 1 + (z - 1) * ease_in_out((t - a) / 0.3), (cx, cy)
            if t < b:
                return z, (cx, cy)
            return 1 + (z - 1) * (1 - ease_in_out((t - b) / 0.35)), (cx, cy)
    return 1.0, None


def build_zooms(spec):
    out = []
    for m in spec.get("moments", []) or []:
        if m.get("kind") != "zoom":
            continue
        a = house_plan.src_to_out(spec, m.get("at", 0)) or 0.0
        b = house_plan.src_to_out(spec, m.get("until", 0)) or 0.0
        out.append((a, b, float(m.get("zoom", 1.0)), float(m.get("cx", VID_W / 2)), float(m.get("cy", VID_H / 2))))
    return out


# ---------------------------------------------------------------------------
# "screen" moments: the live screen share fills a wide panel, the speaker
# shrinks to a small corner cam (reusing the same `spk` crop the normal
# speaker card draws, just scaled down) - see docs/STUDIO-V2.md and the
# SCREEN_* constants above for the geometry.
# ---------------------------------------------------------------------------

_FRAME_SIZE_CACHE = {}


def probe_frame_size(path):
    """(width, height) of `path`'s video stream, via ffprobe. Cached per path
    for the life of the process - only called when a spec has a screen moment,
    and then at most once per distinct source file."""
    if path not in _FRAME_SIZE_CACHE:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", str(path)],
            stdout=subprocess.PIPE, check=True,
        ).stdout.decode().strip()
        w, h = out.split("x")
        _FRAME_SIZE_CACHE[path] = (int(w), int(h))
    return _FRAME_SIZE_CACHE[path]


def build_screens(spec):
    """[{"id","t0","t1","crop","crop_to","cam"}, ...] for every "screen"
    moment, output-time + source-pixel crop rects. `crop`/`crop_to` default to
    the full native source frame (probed lazily - only when a screen moment is
    actually present, so a spec with none never shells out for this)."""
    moments = [m for m in spec.get("moments", []) or [] if m.get("kind") == "screen"]
    if not moments:
        return []
    native = probe_frame_size((spec.get("source", {}) or {}).get("file"))
    full = (0, 0, native[0], native[1])
    out = []
    for m in moments:
        t0 = house_plan.src_to_out(spec, m.get("at", 0)) or 0.0
        t1 = house_plan.src_to_out(spec, m.get("until", 0)) or 0.0
        out.append({
            "id": m.get("id"), "t0": t0, "t1": t1,
            "crop": tuple(m.get("crop") or full),
            "crop_to": tuple(m["crop_to"]) if m.get("crop_to") else None,
            "cam": m.get("cam", "bottom-right"),
        })
    return out


def screen_reader(spec, native_wh):
    """Same trim/concat/tail construction as speaker_reader(), but reads the
    FULL source frame (no crop) at native resolution - the virtual-camera
    crop/zoom happens per-frame in draw_screen_panel() instead, since it can ease
    continuously between `crop` and `crop_to`."""
    nw, nh = native_wh
    source = spec.get("source", {}) or {}
    src = source.get("file")
    tail = house_plan.DEFAULT_TAIL if spec.get("cut", {}).get("tail") is None else spec["cut"]["tail"]
    segs = house_plan.snap_segments(spec)
    base = segs[0]["snapped"][0] - 2

    parts, labels = [], []
    for k, seg in enumerate(segs):
        a, b = seg["snapped"]
        if k == len(segs) - 1:
            b += tail + 0.2
        parts.append("[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[q%d]" % (a - base, b - base, k))
        labels.append("[q%d]" % k)
    vf = ";".join(parts) + (";%sconcat=n=%d:v=1:a=0,unsharp=5:5:0.4,fps=%d[v]"
                             % ("".join(labels), len(segs), FPS))
    span = segs[-1]["snapped"][1] - base + tail + 0.2
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", "%.3f" % base, "-t", "%.3f" % span, "-i", str(src),
         "-filter_complex", vf, "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )

    def _gen():
        size, last = nw * nh * 3, None
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            last = np.frombuffer(buf, np.uint8).reshape(nh, nw, 3)
            yield last
        while True:
            yield last

    return _gen(), p


def build_screen_chains(screens):
    """Group build_screens() output (t0-sorted) into chains: consecutive
    screen moments whose gap is <= house_plan.SCREEN_ADJACENT_GAP hand over
    directly - one continuous "screen showing" span with no speaker-card
    flash at the internal boundaries (see screen_chain_alpha/_weights below).
    A moment with no close neighbour is simply a chain of its own, so this is
    a strict generalisation of the original one-moment-at-a-time behaviour."""
    if not screens:
        return []
    ordered = sorted(screens, key=lambda s: s["t0"])
    chains = [[ordered[0]]]
    for sc in ordered[1:]:
        if sc["t0"] - chains[-1][-1]["t1"] <= house_plan.SCREEN_ADJACENT_GAP:
            chains[-1].append(sc)
        else:
            chains.append([sc])
    return chains


def screen_chain_alpha(chain, t):
    """0..1..0 trapezoid over the WHOLE chain's span: SCREEN_TRANS ease in at
    the first moment's t0, ease out from the last moment's t1 - a flat 1.0
    all the way through any internal (adjacent-moment) boundaries, so the
    speaker card stays hidden for the chain's full duration. For a
    single-moment chain this is exactly the old per-moment screen_alpha()."""
    t0, t1 = chain[0]["t0"], chain[-1]["t1"]
    if t < t0 or t > t1:
        return 0.0
    a_in = ease_in_out(min(1.0, (t - t0) / SCREEN_TRANS)) if t < t0 + SCREEN_TRANS else 1.0
    a_out = ease_in_out(min(1.0, (t1 - t) / SCREEN_TRANS)) if t > t1 - SCREEN_TRANS else 1.0
    return max(0.0, min(a_in, a_out))


def _crossfade_ramp(boundary_t, t, direction):
    """direction "up": 0 before the SCREEN_CROSSFADE-wide window centred on
    `boundary_t`, eases 0->1 across it, 1 after. "down": the mirror (1->0)."""
    lo, hi = boundary_t - SCREEN_CROSSFADE / 2, boundary_t + SCREEN_CROSSFADE / 2
    if t <= lo:
        return 0.0 if direction == "up" else 1.0
    if t >= hi:
        return 1.0 if direction == "up" else 0.0
    k = ease_in_out((t - lo) / SCREEN_CROSSFADE)
    return k if direction == "up" else 1.0 - k


def screen_chain_weights(chain, t):
    """[(moment, weight), ...] for the moment(s) active at `t` within a
    chain, weights summing to ~1. Normally just the one moment covering `t`;
    during the ~SCREEN_CROSSFADE window around an internal boundary, both the
    outgoing and incoming moment are returned so their panels can be
    cross-faded instead of cutting or dropping to the speaker card."""
    n = len(chain)
    out = []
    for i, sc in enumerate(chain):
        w = 1.0
        if i > 0:
            boundary = (chain[i - 1]["t1"] + sc["t0"]) / 2
            w *= _crossfade_ramp(boundary, t, "up")
        if i < n - 1:
            boundary = (sc["t1"] + chain[i + 1]["t0"]) / 2
            w *= _crossfade_ramp(boundary, t, "down")
        if w > 0:
            out.append((sc, w))
    return out


def screen_crop_at(sc, t):
    """Current (x, y, w, h) source-pixel crop rect: `crop`, eased (in-out)
    toward `crop_to` over [t0, t1] if given - the virtual camera push/pan."""
    crop = sc["crop"]
    crop_to = sc.get("crop_to")
    if not crop_to:
        return crop
    span = sc["t1"] - sc["t0"]
    k = ease_in_out((t - sc["t0"]) / span) if span > 0 else 1.0
    return tuple(crop[i] + (crop_to[i] - crop[i]) * k for i in range(4))


def screen_panel_rect(crop):
    """(px, py, w, h) the panel is drawn at on the 1080x1920 canvas for a
    given (x, y, cw, ch) source-pixel crop - pure geometry, no drawing, so
    corner-cam placement can share it without re-deriving it."""
    x0, y0, cw, ch = crop
    aspect = (cw / ch) if ch else (SCREEN_W / SCREEN_MAXH)
    w = SCREEN_W
    h = w / aspect
    if h > SCREEN_MAXH:
        h = SCREEN_MAXH
        w = h * aspect
    w, h = max(2, round(w)), max(2, round(h))
    px = SCREEN_X + (SCREEN_W - w) / 2
    py = SCREEN_Y + (SCREEN_MAXH - h) / 2
    return px, py, w, h


def draw_screen_panel(f, scr_img, crop, alpha):
    """`scr_img`: the full native-resolution PIL frame for this instant."""
    if alpha <= 0 or scr_img is None:
        return
    x0, y0, cw, ch = crop
    px, py, w, h = screen_panel_rect(crop)
    box = (x0, y0, x0 + cw, y0 + ch)
    view = scr_img.resize((w, h), Image.LANCZOS, box=box)
    sh, mg = panel_shadow(w, h, SCREEN_R)
    blend(f, sh, px - mg, py - mg, alpha)
    blend(f, rounded(view, SCREEN_R), px, py, alpha)


def draw_corner_cam(f, spk, panel_rect, cam, alpha):
    """`spk`: the already-decoded speaker crop (VID_W x VID_H) the normal
    card would show - reused here, scaled down, as the corner cam."""
    if alpha <= 0 or cam == "none" or spk is None:
        return
    px, py, w, h = panel_rect
    cam_w = SCREEN_CAM_W
    cam_h = max(2, round(cam_w * spk.shape[0] / spk.shape[1]))
    cam_view = Image.fromarray(spk).resize((cam_w, cam_h), Image.LANCZOS)
    e = SCREEN_CAM_EDGE
    edge = Image.new("RGBA", (cam_w + 2 * e, cam_h + 2 * e), (255, 255, 255, 255))
    positions = {
        "bottom-right": (px + w - SCREEN_CAM_MARGIN - cam_w, py + h - SCREEN_CAM_MARGIN - cam_h),
        "bottom-left": (px + SCREEN_CAM_MARGIN, py + h - SCREEN_CAM_MARGIN - cam_h),
        "top-right": (px + w - SCREEN_CAM_MARGIN - cam_w, py + SCREEN_CAM_MARGIN),
        "top-left": (px + SCREEN_CAM_MARGIN, py + SCREEN_CAM_MARGIN),
    }
    cx, cy = positions.get(cam, positions["bottom-right"])
    cam_sh, cam_mg = panel_shadow(cam_w + 2 * e, cam_h + 2 * e, SCREEN_CAM_R + e, strength=0.30)
    blend(f, cam_sh, cx - e - cam_mg, cy - e - cam_mg, alpha)
    blend(f, rounded(edge, SCREEN_CAM_R + e), cx - e, cy - e, alpha)
    blend(f, rounded(cam_view, SCREEN_CAM_R), cx, cy, alpha)


def draw_screens(f, scr_img, chain, t, chain_alpha, spk):
    """Draw one screen chain at instant `t`: the active moment's panel (or,
    during a ~SCREEN_CROSSFADE window at an internal boundary, both the
    outgoing and incoming moment's panels cross-faded), and the corner cam.
    The cam is drawn once at full `chain_alpha` - not once per weighted
    moment - whenever every active moment shares the same `cam`, so it stays
    visually still instead of double-exposing during the crossfade; only a
    genuine `cam` change between adjacent moments is itself cross-faded."""
    if chain_alpha <= 0:
        return
    active = screen_chain_weights(chain, t)
    for sc, w in active:
        draw_screen_panel(f, scr_img, screen_crop_at(sc, t), chain_alpha * w)

    cams = {sc.get("cam", "bottom-right") for sc, _ in active}
    if len(cams) == 1:
        lead_sc = max(active, key=lambda p: p[1])[0]
        rect = screen_panel_rect(screen_crop_at(lead_sc, t))
        draw_corner_cam(f, spk, rect, cams.pop(), chain_alpha)
    else:
        for sc, w in active:
            rect = screen_panel_rect(screen_crop_at(sc, t))
            draw_corner_cam(f, spk, rect, sc.get("cam", "bottom-right"), chain_alpha * w)


# ---------------------------------------------------------------------------
# manuscript page
# ---------------------------------------------------------------------------

def build_page(mom_spec, spec):
    at = house_plan.src_to_out(spec, mom_spec.get("at", 0)) or 0.0
    until = house_plan.src_to_out(spec, mom_spec.get("until", 0)) or 0.0
    type_at = house_plan.src_to_out(spec, mom_spec.get("type_at", mom_spec.get("at", 0))) or 0.0
    type_end = house_plan.src_to_out(spec, mom_spec.get("type_end", mom_spec.get("until", 0))) or 0.0
    header_at = at + 0.2  # implicit - matches PAGE["header_at"] in the V02 renderer and sfx_events()
    header_text = mom_spec.get("header", "")
    main_text = mom_spec.get("text", "")
    cx, cy, angle = mom_spec.get("x", W / 2), mom_spec.get("y", H / 2), mom_spec.get("angle", 0)

    PW, PH = 940, 440
    rng = np.random.default_rng(1923)
    tex = np.asarray(
        Image.fromarray((rng.normal(128, 22, (PH // 4, PW // 4))).clip(0, 255).astype(np.uint8))
        .resize((PW, PH), Image.BILINEAR)
        .filter(ImageFilter.GaussianBlur(1.0))
    ).astype(np.float32)
    blot = np.asarray(Image.fromarray((rng.random((PH // 20, PW // 20)) * 255).astype(np.uint8))
                       .resize((PW, PH), Image.BICUBIC)).astype(np.float32)
    yy, xx = np.mgrid[0:PH, 0:PW]
    edge = np.minimum.reduce([xx, PW - 1 - xx, yy, PH - 1 - yy]).astype(np.float32)
    burn = np.clip(1 - edge / 70, 0, 1) ** 1.6
    base = np.array([234, 219, 184], np.float32)[None, None] + (tex - tex.mean())[..., None] * 1.3
    base = base - (blot - 128)[..., None] * 0.06
    base = base * (1 - 0.30 * burn[..., None]) + np.array([150, 105, 55], np.float32) * 0.30 * burn[..., None] * 0
    base = base - burn[..., None] * np.array([70, 80, 95], np.float32)
    page = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")

    pts, step = [], 22
    for x in range(0, PW, step):
        pts.append((x, rng.uniform(2, 11)))
    for y in range(0, PH, step):
        pts.append((PW - rng.uniform(2, 11), y))
    for x in range(PW, 0, -step):
        pts.append((x, PH - rng.uniform(2, 11)))
    for y in range(PH, 0, -step):
        pts.append((rng.uniform(2, 11), y))
    mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    page.putalpha(mask.filter(ImageFilter.GaussianBlur(0.8)))

    def ink_layer(text, font, color, track, layer_cy):
        asc, desc = font.getmetrics()
        xs = [font.getlength(text[:i]) + i * track for i in range(len(text) + 1)]
        x0 = (PW - xs[-1]) / 2
        m_ = Image.new("L", (PW, PH), 0)
        d = ImageDraw.Draw(m_)
        for i, ch in enumerate(text):
            d.text((x0 + xs[i], layer_cy - (asc + desc) / 2), ch, font=font, fill=255)
        m_ = m_.filter(ImageFilter.GaussianBlur(0.6))
        grain = rng.uniform(0.72, 1.0, (PH, PW))
        a = (np.asarray(m_).astype(np.float32) * grain).astype(np.uint8)
        layer = Image.new("RGBA", (PW, PH), color + (0,))
        layer.putalpha(Image.fromarray(a))
        return layer, [x0 + x for x in xs]

    header, hxs = ink_layer(header_text, _typewriter_font(30, index=0), (96, 62, 30), 3, 78)
    main, mxs = ink_layer(main_text, _typewriter_font(90, index=2), (38, 24, 12), 0, 250)
    rule = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    ImageDraw.Draw(rule).line([(150, 118), (PW - 150, 118)], fill=(120, 84, 44, 140), width=2)
    ux0, ux1 = mxs[0] - 6, mxs[-2] + 8
    under = [(ux0 + (ux1 - ux0) * k / 40, 332 + 5 * math.sin(k * 0.9) + rng.uniform(-1.5, 1.5)) for k in range(41)]
    return {
        "at": at, "end": until, "header_at": header_at, "type_at": type_at, "type_end": type_end,
        "header_text": header_text, "main_text": main_text, "cx": cx, "cy": cy, "angle": angle,
        "page": page, "header": header, "hxs": hxs, "main": main, "mxs": mxs, "rule": rule, "under": under, "cache": {},
    }


def draw_page(f, pg, t):
    if not (pg["at"] <= t < pg["end"] + 0.3):
        return
    hc = len(pg["header_text"]) if t >= pg["header_at"] + 0.7 else max(0, int(len(pg["header_text"]) * (t - pg["header_at"]) / 0.7))
    span = pg["type_end"] - pg["type_at"]
    mc = len(pg["main_text"]) if t >= pg["type_end"] else max(
        0, int(len(pg["main_text"]) * (t - pg["type_at"]) / span) + (1 if t >= pg["type_at"] else 0)) if span > 0 else len(pg["main_text"])
    up = round(ease_out((t - pg["type_end"] - 0.1) / 0.35), 2)
    key = (hc, mc, up)
    spr = pg["cache"].get(key)
    if spr is None:
        im = pg["page"].copy()
        if hc:
            im.alpha_composite(pg["header"].crop((0, 0, int(pg["hxs"][hc]), im.height)), (0, 0))
            im.alpha_composite(pg["rule"])
        if mc:
            im.alpha_composite(pg["main"].crop((0, 0, int(pg["mxs"][mc]), im.height)), (0, 0))
        if up > 0:
            n = max(2, int(len(pg["under"]) * up))
            ImageDraw.Draw(im).line(pg["under"][:n], fill=(160, 42, 30, 230), width=6, joint="curve")
        im = im.rotate(pg["angle"], resample=Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", (im.width + 60, im.height + 60), (0, 0, 0, 0))
        blk = Image.new("RGBA", im.size, (40, 30, 10, 255))
        blk.putalpha(im.getchannel("A").point(lambda v: int(v * 0.25)))
        sh.paste(blk, (36, 44), blk)
        sh = sh.filter(ImageFilter.GaussianBlur(12))
        sh.alpha_composite(im, (30, 30))
        spr = rgba(sh)
        pg["cache"][key] = spr
    k = (t - pg["at"]) / 0.45
    a = min(1.0, (t - pg["at"]) / 0.15)
    if t > pg["end"] - 0.25:
        a *= max(0.0, 1 - (t - (pg["end"] - 0.25)) / 0.25)
    dy = -70 * (1 - ease_out(k))
    blend(f, spr, pg["cx"] - spr.shape[1] / 2, pg["cy"] - spr.shape[0] / 2 + dy, a)


def build_pages(spec):
    return [build_page(m, spec) for m in spec.get("moments", []) or [] if m.get("kind") == "manuscript"]


# ---------------------------------------------------------------------------
# captions (reuses house_plan.plan()'s already-resolved t0/t1 - the "hold
# until next phrase or +0.7s" rule lives there so the plan/UI and the
# renderer never disagree about caption timing)
# ---------------------------------------------------------------------------

def build_captions(plan_captions):
    font = ImageFont.truetype(FONT_BOLD(), CAP_SIZE)
    caps = []
    for c in plan_captions:
        rows = []
        for j, line in enumerate(wrap(c["text"], font, CAP_MAXW)):
            im, _, _, _ = tracked_text(line, font, TEXT, -0.5, pad=14)
            spr = rgba(im)
            rows.append((spr, (W - spr.shape[1]) / 2, CAP_TOP + j * int(CAP_SIZE * 1.25) - 14))
        caps.append({"s": c["t0"], "e": c["t1"], "rows": rows})
    return caps


# ---------------------------------------------------------------------------
# speaker video
# ---------------------------------------------------------------------------

def speaker_reader(spec):
    """Returns (frame_generator, proc). Caller should terminate `proc` once
    done reading (the generator yields the last frame forever past the
    clip's end, so it never exhausts on its own)."""
    source = spec.get("source", {}) or {}
    src = source.get("file")
    tx, ty, tw, th = source.get("speaker_tile", house_plan.DEFAULT_SPEAKER_TILE)
    tail = house_plan.DEFAULT_TAIL if spec.get("cut", {}).get("tail") is None else spec["cut"]["tail"]
    segs = house_plan.snap_segments(spec)
    base = segs[0]["snapped"][0] - 2

    parts, labels = [], []
    for k, seg in enumerate(segs):
        a, b = seg["snapped"]
        if k == len(segs) - 1:
            b += tail + 0.2
        parts.append("[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[s%d]" % (a - base, b - base, k))
        labels.append("[s%d]" % k)
    vf = ";".join(parts) + (";%sconcat=n=%d:v=1:a=0,crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos,unsharp=5:5:0.45,fps=%d[v]"
                             % ("".join(labels), len(segs), tw, th, tx, ty, VID_W, VID_H, FPS))
    span = segs[-1]["snapped"][1] - base + tail + 2
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", "%.3f" % base, "-t", "%.3f" % span, "-i", str(src),
         "-filter_complex", vf, "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )

    def _gen():
        size, last = VID_W * VID_H * 3, None
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            last = np.frombuffer(buf, np.uint8).reshape(VID_H, VID_W, 3)
            yield last
        while True:
            yield last

    return _gen(), p


def decode_audio(path, start=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", "%.3f" % start, "-t", "%.3f" % dur]
    cmd += ["-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


# ---------------------------------------------------------------------------
# audio pipeline
# ---------------------------------------------------------------------------

def build_audio(spec, plan_, out_path):
    sound = spec.get("sound", {}) or {}
    voice_lufs = float(sound.get("voice_lufs", house_plan.DEFAULT_VOICE_LUFS))
    true_peak = float(sound.get("true_peak", house_plan.DEFAULT_TRUE_PEAK))
    source = spec.get("source", {}) or {}
    src = source.get("file")
    tail = float((spec.get("cut", {}) or {}).get("tail", house_plan.DEFAULT_TAIL))
    dur = plan_["duration"]

    segs = house_plan.snap_segments(spec)
    base = segs[0]["snapped"][0] - 1
    span = segs[-1]["snapped"][1] - base + 1
    src_audio = decode_audio(src, base, span)

    fade = int(0.012 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    pieces = []
    for seg in segs:
        a, b = seg["snapped"]
        i0, i1 = int((a - base) * SR), int((b - base) * SR)
        x = src_audio[i0:i1].copy()
        if seg.get("mute"):
            x[:] = 0
        if len(x) > 2 * fade:
            x[:fade] *= ramp
            x[-fade:] *= ramp[::-1]
        pieces.append(x)
    voice = np.concatenate(pieces + [np.zeros(int(tail * SR) + SR, np.float32)])[:int(round(dur * SR))]

    tmp = tempfile.mkdtemp(prefix="house-render-")
    try:
        (os.path.join(tmp, "v.f32"))
        with open(os.path.join(tmp, "v.f32"), "wb") as f:
            f.write(voice.tobytes())
        meas = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", os.path.join(tmp, "v.f32"),
             "-af", "loudnorm=print_format=json", "-f", "null", "-"],
            capture_output=True, text=True,
        ).stderr
        li = float(json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])["input_i"])
        target_mono = voice_lufs - 3.0  # dual-mono stereo of a `target_mono` mono file meters ~voice_lufs
        voice *= 10 ** ((target_mono - li) / 20)

        mix = voice.copy()
        for ev in plan_.get("sfx", []):
            if ev.get("muted"):
                continue
            name = ev.get("name")
            if not name:
                continue
            sfx_path = os.path.join(house_assets_dir(), "sfx", "%s.mp3" % name)
            if not os.path.exists(sfx_path):
                continue
            t = ev.get("t", 0)
            if t < 0:
                continue
            s = decode_audio(sfx_path)
            peak = np.abs(s).max()
            if peak > 1e-9:
                s = s / peak * 10 ** (ev.get("gain", 0) / 20)
            i0 = int(t * SR)
            n = min(len(s), len(mix) - i0)
            if n > 0:
                mix[i0:i0 + n] += s[:n]

        peak = float(np.abs(mix).max())
        stereo = np.repeat(mix[:, None], 2, axis=1).astype(np.float32)
        with open(os.path.join(tmp, "mix.f32"), "wb") as f:
            f.write(stereo.tobytes())
        limit = 10 ** (true_peak / 20)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", os.path.join(tmp, "mix.f32"),
             "-af", "alimiter=limit=%.5f:attack=3:release=60:level=0" % limit, str(out_path)],
            check=True,
        )
        return {"voice_input_lufs": li, "peak_dbfs": (20 * math.log10(peak) if peak > 0 else float("-inf"))}
    finally:
        for name in ("v.f32", "mix.f32"):
            try:
                os.unlink(os.path.join(tmp, name))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# compose (the per-frame compositor)
# ---------------------------------------------------------------------------

class Scene:
    """Everything a `render`/`still` run needs, built once from a spec."""

    def __init__(self, spec):
        self.spec = spec
        self.plan = house_plan.plan(spec)
        self.paper = build_paper()
        self.card, self.card_off = build_card()
        self.heads = build_headlines(spec)
        self.scenes = build_scenes(spec)
        self.pages = build_pages(spec)
        self.zooms = build_zooms(spec)
        self.screens = build_screens(spec)
        self.screen_chains = build_screen_chains(self.screens)
        self.caps = build_captions(self.plan["captions"])
        self.duration = self.plan["duration"]
        self.nframes = round(self.duration * FPS)


def compose(t, scene, spk, scr=None):
    f = scene.paper.copy()
    slide = 0.0
    for sc in scene.scenes:
        if sc["slide"] <= t < sc["out"] - 0.1:
            slide = max(slide, ease_in_out((t - sc["slide"]) / 0.5))
        elif sc["out"] - 0.1 <= t < sc["out"] + 0.4:
            slide = max(slide, 1.0 - ease_in_out((t - (sc["out"] - 0.1)) / 0.5))
    dy = slide * 1250

    # A "screen" moment replaces the normal navy speaker card with a wide
    # screen-share panel + small corner cam (see draw_screens below), so fade
    # the ordinary card out as any screen moment fades in. `screen_a` stays
    # 0.0 for every recipe without a screen moment, so the `else` branch below
    # (byte-identical to the pre-"screen" renderer) is always the one taken.
    screen_a = 0.0
    scr_img = None
    if scene.screen_chains:
        for chain in scene.screen_chains:
            screen_a = max(screen_a, screen_chain_alpha(chain, t))
        if screen_a > 0 and scr is not None:
            scr_img = Image.fromarray(scr)

    if dy < H:
        z, centre = punch_zoom(t, scene.zooms)
        if z != 1.0 and centre is not None:
            cx, cy = centre
            cw, ch = VID_W / z, VID_H / z
            x0 = min(max(cx - cw / 2, 0), VID_W - cw)
            y0 = min(max(cy - ch / 2, 0), VID_H - ch)
            spk = np.asarray(Image.fromarray(spk).resize((VID_W, VID_H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)))
        y0 = int(VID_Y + dy)
        if screen_a > 0:
            blend(f, scene.card, scene.card_off[0], scene.card_off[1] + dy, 1.0 - screen_a)
            if y0 < H:
                h = min(VID_H, H - y0)
                region = f[y0:y0 + h, VID_X:VID_X + VID_W].astype(np.float32)
                mixed = region * screen_a + spk[:h].astype(np.float32) * (1.0 - screen_a)
                f[y0:y0 + h, VID_X:VID_X + VID_W] = np.clip(mixed, 0, 255).astype(np.uint8)
        else:
            blend(f, scene.card, scene.card_off[0], scene.card_off[1] + dy)
            if y0 < H:
                h = min(VID_H, H - y0)
                f[y0:y0 + h, VID_X:VID_X + VID_W] = spk[:h]

    if scene.screen_chains:
        for chain in scene.screen_chains:
            draw_screens(f, scr_img, chain, t, screen_chain_alpha(chain, t), spk)

    for hd in scene.heads:
        first = hd["rows"][0]["at"]
        if first <= t < hd["end"]:
            draw_rows(f, hd, t, hd["end"] - 0.25)

    for pg in scene.pages:
        draw_page(f, pg, t)

    for sc in scene.scenes:
        start = min([r["at"] for r in sc["head_rows"]["rows"]] + [sc["slide"]])
        until = max(sc["out"], (sc["ticker"] or {}).get("persist", 0)) + 0.3
        if start <= t < until:
            fs_a = 1.0 - ease_out((t - (sc["out"] - 0.3)) / 0.3) if t > sc["out"] - 0.3 else 1.0
            if t < sc["head_rows"]["end"] + 0.3 and t < sc["out"] + 0.3:
                draw_rows(f, sc["head_rows"], t, min(sc["out"], sc["head_rows"]["end"]) - 0.3)
            if t < sc["out"] + 0.3:
                draw_items(f, sc["item_sprites"], t, max(0.0, fs_a))
            if sc["ticker"]:
                persist = sc["ticker"].get("persist")
                tk_a = (1.0 if t < persist - 0.25 else max(0.0, 1 - (t - (persist - 0.25)) / 0.25)) if persist else fs_a
                draw_ticker(f, sc["ticker"], t, tk_a)

    cap_a = 1.0 if slide in (0.0, 1.0) else 0.0
    for c in scene.caps:
        if c["s"] <= t < c["e"]:
            for spr, x, y in c["rows"]:
                blend(f, spr, x, y, cap_a)

    return np.clip(f, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# CLI: render / still
# ---------------------------------------------------------------------------

def _load_spec(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_progress(path, frame, total):
    if not path:
        return
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"frame": frame, "total": total}, f)
    os.replace(tmp, path)


def cmd_render(args):
    spec = _load_spec(args.spec)
    scene = Scene(spec)
    reader, reader_proc = speaker_reader(spec)
    scr_reader, scr_proc = (None, None)
    if scene.screens:
        native = probe_frame_size((spec.get("source", {}) or {}).get("file"))
        scr_reader, scr_proc = screen_reader(spec, native)

    tmp = tempfile.mkdtemp(prefix="house-render-")
    audio_path = os.path.join(tmp, "mix.wav")
    audio_info = build_audio(spec, scene.plan, audio_path)

    fps = int((spec.get("output", {}) or {}).get("fps", FPS))
    out_w = int((spec.get("output", {}) or {}).get("width", W))
    out_h = int((spec.get("output", {}) or {}).get("height", H))

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (out_w, out_h), "-r", str(fps), "-i", "-",
        "-i", audio_path, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k", "-t", "%.3f" % scene.duration, "-movflags", "+faststart", str(args.out),
    ], stdin=subprocess.PIPE)

    total = scene.nframes
    for i in range(total):
        scr_frame = next(scr_reader) if scr_reader is not None else None
        frame = compose(i / fps, scene, next(reader), scr_frame)
        enc.stdin.write(frame.tobytes())
        if i % 24 == 0 or i == total - 1:
            _write_progress(args.progress, i + 1, total)
            print("frame %d/%d" % (i + 1, total), flush=True)
    enc.stdin.close()
    enc.wait()
    try:
        reader_proc.terminate()
        reader_proc.wait(timeout=5)
    except Exception:
        pass
    if scr_proc is not None:
        try:
            scr_proc.terminate()
            scr_proc.wait(timeout=5)
        except Exception:
            pass
    _write_progress(args.progress, total, total)
    print("wrote %s (%.2fs) voice=%.1fLUFS peak=%.1fdBFS"
          % (args.out, scene.duration, audio_info["voice_input_lufs"], audio_info["peak_dbfs"]))

    try:
        os.unlink(audio_path)
        os.rmdir(tmp)
    except OSError:
        pass

    if enc.returncode:
        raise SystemExit("ffmpeg encode failed (exit %s)" % enc.returncode)


def cmd_still(args):
    spec = _load_spec(args.spec)
    scene = Scene(spec)
    t = float(args.t)

    # decode just the one needed source frame instead of running the whole
    # speaker_reader() pipeline, so `still` stays fast (< 1.5s).
    src_t = house_plan.out_to_src(spec, t)
    src = (spec.get("source", {}) or {}).get("file")
    tx, ty, tw, th = (spec.get("source", {}) or {}).get("speaker_tile", house_plan.DEFAULT_SPEAKER_TILE)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, src_t), "-i", str(src), "-frames:v", "1",
         "-vf", "crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos,unsharp=5:5:0.45" % (tw, th, tx, ty, VID_W, VID_H),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, check=True,
    ).stdout
    if len(raw) >= VID_W * VID_H * 3:
        spk = np.frombuffer(raw, np.uint8)[:VID_W * VID_H * 3].reshape(VID_H, VID_W, 3)
    else:
        spk = np.zeros((VID_H, VID_W, 3), np.uint8)

    scr = None
    if scene.screens:
        nw, nh = probe_frame_size(src)
        raw2 = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, src_t), "-i", str(src), "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, check=True,
        ).stdout
        if len(raw2) >= nw * nh * 3:
            scr = np.frombuffer(raw2, np.uint8)[:nw * nh * 3].reshape(nh, nw, 3)

    frame = compose(t, scene, spk, scr)
    im = Image.fromarray(frame)
    width = int(args.width or W)
    if width != im.width:
        height = round(im.height * width / im.width)
        im = im.resize((width, height), Image.LANCZOS)
    im.convert("RGB").save(args.out, quality=90)
    print("wrote %s" % args.out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("render")
    pr.add_argument("spec")
    pr.add_argument("out")
    pr.add_argument("--progress")
    pr.set_defaults(func=cmd_render)

    ps = sub.add_parser("still")
    ps.add_argument("spec")
    ps.add_argument("t")
    ps.add_argument("out")
    ps.add_argument("--width", type=int, default=540)
    ps.set_defaults(func=cmd_still)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
