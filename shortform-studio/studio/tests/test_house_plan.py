from __future__ import annotations

import copy
import json
import os
import subprocess
import unittest

from helpers import StudioTestCase

from studio_core import house_plan


def _minimal_spec(**overrides):
    spec = {
        "schema": 1,
        "clip": "test-clip",
        "source": {"file": "/nonexistent/source.mp4", "words": "/nonexistent/words.json",
                    "speaker_tile": [962, 272, 318, 178]},
        "cut": {"segments": [
            {"a": 10.0, "b": 14.0, "snap": False, "mute": False},
            {"a": 20.0, "b": 24.0, "snap": False, "mute": False},
        ], "tail": 0.6},
        "captions": {"mode": "manual", "phrases": [{"text": "hello there", "a": 10.5, "b": 11.5}], "hidden": False},
        "title": {"lines": [{"text": "A title", "hl": None}], "until": 10.2},
        "headlines": [],
        "moments": [],
        "sound": {"auto": True, "sfx_gain_db": 0, "muted": [], "extra": [], "voice_lufs": -17, "true_peak": -1.5},
        "look": {"preset": "house-v1"},
        "output": {"width": 1080, "height": 1920, "fps": 24},
    }
    spec.update(overrides)
    return spec


class ValidateTest(unittest.TestCase):
    def test_minimal_spec_is_valid(self):
        self.assertEqual(house_plan.validate(_minimal_spec()), [])

    def test_not_a_dict(self):
        self.assertTrue(house_plan.validate(None))
        self.assertTrue(house_plan.validate([1, 2, 3]))

    def test_missing_fields(self):
        spec = {"clip": "x"}
        errors = house_plan.validate(spec)
        self.assertTrue(any("source" in e for e in errors))
        self.assertTrue(any("cut" in e for e in errors))

    def test_bad_segment_order(self):
        spec = _minimal_spec()
        spec["cut"]["segments"][1]["b"] = spec["cut"]["segments"][1]["a"] - 1
        errors = house_plan.validate(spec)
        self.assertTrue(any("must be after" in e for e in errors))

    def test_bad_moment_kind(self):
        spec = _minimal_spec(moments=[{"id": "m1", "kind": "bogus"}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("m1" in e for e in errors))

    def test_manuscript_missing_fields(self):
        spec = _minimal_spec(moments=[{"id": "m2", "kind": "manuscript", "at": 1, "until": 2}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("manuscript needs" in e for e in errors))

    def test_screen_moment_valid(self):
        spec = _minimal_spec(moments=[{
            "id": "m4", "kind": "screen", "at": 20.1, "until": 23.0,
            "crop": [150, 150, 740, 460], "crop_to": [200, 150, 500, 310], "cam": "bottom-right",
        }])
        self.assertEqual(house_plan.validate(spec), [])

    def test_screen_missing_fields(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen"}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("screen needs" in e for e in errors))

    def test_screen_until_before_at(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 23.0, "until": 20.1}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("must be after" in e for e in errors))

    def test_screen_bad_crop(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0,
                                       "crop": [0, 0, -5, 100]}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("m4.crop" in e for e in errors))

    def test_screen_bad_cam(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0, "cam": "middle"}])
        errors = house_plan.validate(spec)
        self.assertTrue(any("m4.cam" in e for e in errors))

    def test_screen_defaults_are_valid(self):
        # crop/crop_to/cam are all optional
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0}])
        self.assertEqual(house_plan.validate(spec), [])


class MappingTest(unittest.TestCase):
    def test_seg_map_offsets(self):
        spec = _minimal_spec()
        segs = house_plan.seg_map(spec)
        self.assertEqual(segs, [(10.0, 14.0, 0.0), (20.0, 24.0, 4.0)])

    def test_src_to_out_inside_segment(self):
        spec = _minimal_spec()
        self.assertAlmostEqual(house_plan.src_to_out(spec, 12.0), 2.0)
        self.assertAlmostEqual(house_plan.src_to_out(spec, 22.0), 6.0)

    def test_src_to_out_clamps_removed_part(self):
        spec = _minimal_spec()
        # 17.0 is in the removed gap between segment 1 (ends 14) and segment 2 (starts 20)
        out = house_plan.src_to_out(spec, 17.0)
        self.assertAlmostEqual(out, 4.0)  # clamps to the start of the next kept segment

    def test_src_to_out_after_last_segment_clamps_to_end(self):
        spec = _minimal_spec()
        out = house_plan.src_to_out(spec, 999.0)
        self.assertAlmostEqual(out, 8.6)  # total kept length (8.0) + the 0.6s tail

    def test_src_to_out_within_tail_maps_one_to_one(self):
        spec = _minimal_spec()  # tail = 0.6
        out = house_plan.src_to_out(spec, 24.0 + 0.3)  # 0.3s past the last segment's b, inside the tail
        self.assertAlmostEqual(out, 8.3)

    def test_src_to_out_empty_segments_is_none(self):
        spec = _minimal_spec(cut={"segments": [], "tail": 0.6})
        self.assertIsNone(house_plan.src_to_out(spec, 5.0))

    def test_out_to_src_round_trip(self):
        spec = _minimal_spec()
        # Boundary instants shared by adjacent segments in OUTPUT time (e.g. the end
        # of segment 1 and the start of segment 2, since the removed gap between them
        # collapses to a single output instant) are intentionally not round-trippable;
        # this only checks points strictly inside a kept segment.
        for src in (10.0, 11.5, 13.9, 20.1, 23.9):
            out = house_plan.src_to_out(spec, src)
            back = house_plan.out_to_src(spec, out)
            self.assertAlmostEqual(back, src, places=3)

    def test_out_to_src_clamps_out_of_range(self):
        spec = _minimal_spec()
        self.assertAlmostEqual(house_plan.out_to_src(spec, -5), 10.0)
        self.assertAlmostEqual(house_plan.out_to_src(spec, 999), 24.6)  # last b (24.0) + the 0.6s tail


class PlanTest(unittest.TestCase):
    def test_duration_and_segments(self):
        spec = _minimal_spec()
        p = house_plan.plan(spec)
        self.assertAlmostEqual(p["duration"], 8.6)  # 4 + 4 kept + 0.6 tail
        self.assertEqual(len(p["segments"]), 2)
        self.assertEqual(p["segments"][0]["o"], 0.0)
        self.assertEqual(p["segments"][1]["o"], 4.0)

    def test_manual_captions_are_mapped(self):
        spec = _minimal_spec()
        p = house_plan.plan(spec)
        self.assertEqual(len(p["captions"]), 1)
        self.assertAlmostEqual(p["captions"][0]["t0"], 0.5)
        # a caption holds until the next one starts (or duration), capped at
        # its own word-end + 0.7s; here there's only one phrase, so it holds
        # until word-end (1.5) + 0.7 = 2.2 (well short of the 8.6s duration).
        self.assertAlmostEqual(p["captions"][0]["t1"], 2.2)

    def test_caption_hold_capped_by_next_phrase_start(self):
        spec = _minimal_spec(captions={"mode": "manual", "hidden": False, "phrases": [
            {"text": "first", "a": 10.0, "b": 10.5},
            {"text": "second", "a": 10.6, "b": 11.0},
        ]})
        p = house_plan.plan(spec)
        # word-end(0.5) + 0.7 = 1.2 would overlap the next phrase's start (0.6),
        # so the first caption's hold is capped there instead.
        self.assertAlmostEqual(p["captions"][0]["t1"], 0.6)

    def test_title_starts_at_zero(self):
        spec = _minimal_spec()
        p = house_plan.plan(spec)
        self.assertEqual(p["title"]["t0"], 0.0)
        self.assertAlmostEqual(p["title"]["t1"], 0.2)

    def test_headline_warns_when_anchored_in_removed_part(self):
        spec = _minimal_spec(headlines=[
            {"id": "h1", "until": 22.0,
             "lines": [{"text": "Removed anchor", "at": 17.0, "hl": None}]},
        ])
        p = house_plan.plan(spec)
        self.assertEqual(len(p["headlines"]), 1)
        h1 = p["headlines"][0]
        self.assertAlmostEqual(h1["lines"][0]["t"], 4.0)  # clamped to next kept segment start
        self.assertTrue(any("h1" in w and "clamped" in w for w in p["warnings"]))

    def test_headline_dim_entry(self):
        spec = _minimal_spec(headlines=[
            {"id": "h2", "until": 23.0, "lines": [
                {"text": "First", "at": 20.5, "hl": None},
                {"dim": True, "at": 21.5},
                {"text": "Second", "at": 22.0, "hl": "Second"},
            ]},
        ])
        p = house_plan.plan(spec)
        h2 = p["headlines"][0]
        self.assertEqual([l["text"] for l in h2["lines"]], ["First", "Second"])
        self.assertEqual(len(h2["dims"]), 1)

    def test_fullscreen_moment_summary_and_timing(self):
        spec = _minimal_spec(moments=[{
            "id": "m1", "kind": "fullscreen", "slide": 20.2, "until": 23.5,
            "head": {"lines": [{"text": "Head", "at": 20.3, "hl": None}], "until": 22.0},
            "items": [{"image": "/x.jpg", "frame": "photo", "label": None, "at": 20.6,
                       "x": 540, "y": 900, "scale": 1.0, "angle": 0}],
            "counter": {"from": "10", "to": "1", "start": 20.4, "land": 21.0, "y": 900},
        }])
        p = house_plan.plan(spec)
        self.assertEqual(len(p["moments"]), 1)
        m1 = p["moments"][0]
        self.assertEqual(m1["kind"], "fullscreen")
        self.assertIn("Year counter 10→1", m1["summary"])
        self.assertIn("1 image", m1["summary"])

    def test_manuscript_moment_summary(self):
        spec = _minimal_spec(moments=[{
            "id": "m2", "kind": "manuscript", "at": 20.1, "until": 23.0,
            "header": "HEADER", "text": "Rigorous testing.", "type_at": 20.5, "type_end": 20.9,
            "x": 540, "y": 470, "angle": -2,
        }])
        p = house_plan.plan(spec)
        self.assertEqual(p["moments"][0]["summary"], "Manuscript · Rigorous testing.")

    def test_zoom_moment_summary(self):
        spec = _minimal_spec(moments=[{"id": "m3", "kind": "zoom", "at": 20.1, "until": 20.5,
                                       "zoom": 1.16, "cx": 480, "cy": 190}])
        p = house_plan.plan(spec)
        self.assertIn("Zoom", p["moments"][0]["summary"])

    def test_screen_moment_summary_and_timing(self):
        spec = _minimal_spec(moments=[{
            "id": "m4", "kind": "screen", "at": 20.1, "until": 23.0,
            "crop": [150, 150, 740, 460], "crop_to": [200, 150, 500, 310], "cam": "bottom-right",
        }])
        p = house_plan.plan(spec)
        self.assertEqual(len(p["moments"]), 1)
        m4 = p["moments"][0]
        self.assertEqual(m4["kind"], "screen")
        self.assertAlmostEqual(m4["t0"], 4.1)  # second kept segment starts at output 4.0 (a=20.0); +0.1s in
        self.assertAlmostEqual(m4["t1"], 7.0)
        self.assertEqual(m4["summary"], "Screen share · corner cam · push-in")

    def test_screen_moment_summary_pull_out_and_no_cam(self):
        spec = _minimal_spec(moments=[{
            "id": "m4", "kind": "screen", "at": 20.1, "until": 23.0,
            "crop": [200, 150, 500, 310], "crop_to": [150, 150, 740, 460], "cam": "none",
        }])
        p = house_plan.plan(spec)
        self.assertEqual(p["moments"][0]["summary"], "Screen share · pull-out")

    def test_screen_moment_summary_no_crop_to_is_pan_free(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0}])
        p = house_plan.plan(spec)
        self.assertEqual(p["moments"][0]["summary"], "Screen share · corner cam")


class SfxEventsTest(unittest.TestCase):
    def test_fullscreen_sfx_events(self):
        spec = _minimal_spec(moments=[{
            "id": "m1", "kind": "fullscreen", "slide": 20.2, "until": 23.5,
            "head": {"lines": [{"text": "Head", "at": 20.3, "hl": "Head"}], "until": 22.0},
            "items": [
                {"image": "/x.jpg", "frame": "photo", "at": 20.6, "x": 1, "y": 1, "scale": 1, "angle": 0},
                {"image": "/y.jpg", "frame": "cutout", "at": 20.7, "x": 1, "y": 1, "scale": 1, "angle": 0},
            ],
            "counter": {"from": "10", "to": "1", "start": 20.4, "land": 21.0, "y": 900},
        }])
        p = house_plan.plan(spec)
        keys = [e["key"] for e in p["sfx"]]
        self.assertIn("m1:whoosh-in", keys)
        self.assertIn("m1:whoosh-out", keys)
        self.assertIn("m1:pop:1", keys)
        self.assertIn("m1:pop:2", keys)
        self.assertIn("m1:click:1", keys)
        self.assertIn("m1:counter:land", keys)
        self.assertTrue(any(k.startswith("m1:counter:tick:") for k in keys))
        whoosh_in = next(e for e in p["sfx"] if e["key"] == "m1:whoosh-in")
        self.assertEqual(whoosh_in["gain"], -15)
        self.assertEqual(whoosh_in["source"], "auto")

    def test_manuscript_sfx_events(self):
        spec = _minimal_spec(moments=[{
            "id": "m2", "kind": "manuscript", "at": 20.1, "until": 23.0,
            "header": "H", "text": "T", "type_at": 20.5, "type_end": 20.9,
        }])
        p = house_plan.plan(spec)
        keys = [e["key"] for e in p["sfx"]]
        self.assertIn("m2:whoosh", keys)
        self.assertIn("m2:typing:header", keys)
        self.assertIn("m2:typing", keys)

    def test_sfx_gain_adjustment_and_mute(self):
        spec = _minimal_spec(moments=[{
            "id": "m2", "kind": "manuscript", "at": 20.1, "until": 23.0,
            "header": "H", "text": "T", "type_at": 20.5, "type_end": 20.9,
        }])
        spec["sound"]["sfx_gain_db"] = -6
        spec["sound"]["muted"] = ["m2:whoosh"]
        p = house_plan.plan(spec)
        whoosh = next(e for e in p["sfx"] if e["key"] == "m2:whoosh")
        self.assertEqual(whoosh["gain"], -19 - 6)
        self.assertTrue(whoosh["muted"])

    def test_extra_sfx(self):
        spec = _minimal_spec()
        spec["sound"]["extra"] = [{"name": "pop", "at": 12.0, "gain": -13}]
        p = house_plan.plan(spec)
        extra = [e for e in p["sfx"] if e["source"] == "extra"]
        self.assertEqual(len(extra), 1)
        self.assertAlmostEqual(extra[0]["t"], 2.0)
        self.assertEqual(extra[0]["name"], "pop")

    def test_screen_sfx_events(self):
        spec = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0}])
        p = house_plan.plan(spec)
        keys = [e["key"] for e in p["sfx"]]
        self.assertIn("m4:whoosh-in", keys)
        self.assertIn("m4:whoosh-out", keys)
        whoosh_in = next(e for e in p["sfx"] if e["key"] == "m4:whoosh-in")
        whoosh_out = next(e for e in p["sfx"] if e["key"] == "m4:whoosh-out")
        self.assertEqual(whoosh_in["gain"], -15)
        self.assertEqual(whoosh_out["gain"], -17)

    def test_adjacent_screen_moments_auto_mute_inner_whoosh(self):
        # m4a (out 4.1-5.6) hands over directly to m4b (out 5.6-7.0): the
        # renderer cross-fades the panel there instead of flashing the
        # speaker card, so the shared inner whoosh pair is auto-muted.
        spec = _minimal_spec(moments=[
            {"id": "m4a", "kind": "screen", "at": 20.1, "until": 21.6},
            {"id": "m4b", "kind": "screen", "at": 21.6, "until": 23.0},
        ])
        p = house_plan.plan(spec)
        by_key = {e["key"]: e for e in p["sfx"]}
        self.assertFalse(by_key["m4a:whoosh-in"]["muted"])
        self.assertTrue(by_key["m4a:whoosh-out"]["muted"])
        self.assertTrue(by_key["m4b:whoosh-in"]["muted"])
        self.assertFalse(by_key["m4b:whoosh-out"]["muted"])

    def test_non_adjacent_screen_moments_keep_whoosh(self):
        # Gap here (10.5->11.0 out, 20.1 out) is well past SCREEN_ADJACENT_GAP,
        # so both moments keep their normal, unmuted whoosh in/out.
        spec = _minimal_spec(moments=[
            {"id": "m4a", "kind": "screen", "at": 10.0, "until": 11.0},
            {"id": "m4b", "kind": "screen", "at": 20.1, "until": 23.0},
        ])
        p = house_plan.plan(spec)
        by_key = {e["key"]: e for e in p["sfx"]}
        self.assertFalse(by_key["m4a:whoosh-out"]["muted"])
        self.assertFalse(by_key["m4b:whoosh-in"]["muted"])

    def test_screen_adjacent_gap_exactly_at_threshold_is_suppressed(self):
        # Second segment is 20.0-24.0 (out offset 4.0): a 0.5s OUTPUT gap here
        # is also exactly 0.5s of SOURCE time since both moments sit inside
        # the same kept segment (no cut in between).
        spec = _minimal_spec(moments=[
            {"id": "m4a", "kind": "screen", "at": 20.1, "until": 21.6},
            {"id": "m4b", "kind": "screen", "at": 22.1, "until": 23.0},
        ])
        p = house_plan.plan(spec)
        by_key = {e["key"]: e for e in p["sfx"]}
        self.assertTrue(by_key["m4a:whoosh-out"]["muted"])
        self.assertTrue(by_key["m4b:whoosh-in"]["muted"])

    def test_screen_adjacent_gap_just_past_threshold_is_not_suppressed(self):
        spec = _minimal_spec(moments=[
            {"id": "m4a", "kind": "screen", "at": 20.1, "until": 21.6},
            {"id": "m4b", "kind": "screen", "at": 22.15, "until": 23.0},
        ])
        p = house_plan.plan(spec)
        by_key = {e["key"]: e for e in p["sfx"]}
        self.assertFalse(by_key["m4a:whoosh-out"]["muted"])
        self.assertFalse(by_key["m4b:whoosh-in"]["muted"])

    def test_adjacent_screen_moments_explicit_mute_still_works(self):
        # Auto-suppression must not short-circuit an editor's own sound.muted
        # entries for keys it doesn't itself touch.
        spec = _minimal_spec(moments=[
            {"id": "m4a", "kind": "screen", "at": 20.1, "until": 21.6},
            {"id": "m4b", "kind": "screen", "at": 21.6, "until": 23.0},
        ])
        spec["sound"]["muted"] = ["m4a:whoosh-in"]
        p = house_plan.plan(spec)
        by_key = {e["key"]: e for e in p["sfx"]}
        self.assertTrue(by_key["m4a:whoosh-in"]["muted"])  # explicit
        self.assertTrue(by_key["m4a:whoosh-out"]["muted"])  # auto (adjacent)
        self.assertTrue(by_key["m4b:whoosh-in"]["muted"])  # auto (adjacent)
        self.assertFalse(by_key["m4b:whoosh-out"]["muted"])

    def test_auto_off_suppresses_auto_events(self):
        spec = _minimal_spec(moments=[{
            "id": "m2", "kind": "manuscript", "at": 20.1, "until": 23.0,
            "header": "H", "text": "T", "type_at": 20.5, "type_end": 20.9,
        }])
        spec["sound"]["auto"] = False
        p = house_plan.plan(spec)
        self.assertEqual(p["sfx"], [])


class AutoCaptionsTest(unittest.TestCase):
    def _words(self, entries):
        return {"word_segments": [{"word": w, "start": s, "end": e} for w, s, e in entries]}

    def test_breaks_on_pause(self):
        spec = _minimal_spec()
        words = self._words([
            ("hello", 10.0, 10.3), ("world", 10.35, 10.6),
            ("next", 11.3, 11.6),  # gap of 0.7s >= 0.45s
        ])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0]["text"], "hello world")
        self.assertEqual(phrases[1]["text"], "next")

    def test_breaks_on_break_word_after_three_words(self):
        spec = _minimal_spec()
        words = self._words([
            ("kita", 10.0, 10.2), ("dah", 10.2, 10.4), ("cakap", 10.4, 10.6),
            ("tapi", 10.6, 10.8), ("betul", 10.8, 11.0),
        ])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(phrases[0]["text"], "kita dah cakap")
        self.assertEqual(phrases[1]["text"], "tapi betul")

    def test_breaks_on_max_words(self):
        spec = _minimal_spec()
        words = self._words([(w, 10.0 + i * 0.2, 10.15 + i * 0.2) for i, w in enumerate(
            ["one", "two", "three", "four", "five", "six"])])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(len(phrases[0]["text"].split()), 5)
        self.assertEqual(phrases[1]["text"], "six")

    def test_breaks_across_segment_boundary(self):
        spec = _minimal_spec()
        words = self._words([("first", 13.8, 14.0), ("second", 20.1, 20.3)])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(len(phrases), 2)

    def test_early_asr_word_absorbed_into_next_segment(self):
        spec = _minimal_spec()
        # word starts 0.3s before segment 2 (20.0) -> should be pulled into segment 2, not dropped
        words = self._words([("early", 19.7, 20.1)])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(len(phrases), 1)
        self.assertEqual(phrases[0]["text"], "early")

    def test_word_in_removed_gap_dropped(self):
        spec = _minimal_spec()
        words = self._words([("gone", 16.0, 16.3)])  # deep inside the removed gap, not near either boundary
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(phrases, [])

    def test_muted_segment_excluded(self):
        spec = _minimal_spec()
        spec["cut"]["segments"][1]["mute"] = True
        words = self._words([("audible", 10.0, 10.3), ("silent", 20.0, 20.3)])
        phrases = house_plan.auto_captions(spec, words)
        self.assertEqual(len(phrases), 1)
        self.assertEqual(phrases[0]["text"], "audible")


class DiffTest(unittest.TestCase):
    def test_no_changes(self):
        spec = _minimal_spec()
        self.assertEqual(house_plan.diff(spec, copy.deepcopy(spec)), [])

    def test_cut_removed_and_added(self):
        old = _minimal_spec()
        new = copy.deepcopy(old)
        new["cut"]["segments"] = [{"a": 10.0, "b": 12.0, "snap": False, "mute": False}]
        bullets = house_plan.diff(old, new)
        # no transcript in the minimal spec, so the removed stretch is described by its position
        self.assertTrue(any(b.startswith("Cut: removed") and "(−" in b for b in bullets), bullets)

    def test_title_change(self):
        old = _minimal_spec()
        new = copy.deepcopy(old)
        new["title"]["lines"] = [{"text": "New title", "hl": None}]
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("A title" in b and "New title" in b for b in bullets))

    def test_moments_added(self):
        old = _minimal_spec()
        new = copy.deepcopy(old)
        new["moments"] = [{"id": "m9", "kind": "manuscript", "at": 1, "until": 2, "text": "x",
                            "type_at": 1, "type_end": 1.5}]
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("added manuscript" in b for b in bullets))

    def test_screen_moment_added(self):
        old = _minimal_spec()
        new = copy.deepcopy(old)
        new["moments"] = [{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0}]
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("added screen" in b for b in bullets))

    def test_screen_moment_removed(self):
        old = _minimal_spec(moments=[{"id": "m4", "kind": "screen", "at": 20.1, "until": 23.0}])
        new = copy.deepcopy(old)
        new["moments"] = []
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("removed m4 (screen)" in b for b in bullets))

    def test_screen_moment_kind_changed(self):
        old = _minimal_spec(moments=[{"id": "m4", "kind": "zoom", "at": 20.1, "until": 20.5, "zoom": 1.1}])
        new = copy.deepcopy(old)
        new["moments"] = [{"id": "m4", "kind": "screen", "at": 20.1, "until": 20.5}]
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("changed kind zoom" in b and "screen" in b for b in bullets))

    def test_sound_mute_toggle(self):
        old = _minimal_spec()
        new = copy.deepcopy(old)
        new["sound"]["muted"] = ["h1:click:1"]
        bullets = house_plan.diff(old, new)
        self.assertTrue(any("muted h1:click:1" in b for b in bullets))


class RoughCutSpecTest(unittest.TestCase):
    def test_shape(self):
        spec = house_plan.rough_cut_spec("v09-test", "/nonexistent/source.mp4", "/nonexistent/words.json",
                                          [(5.0, 9.0), (12.0, 16.0)], "Apa yang menarik bila buat Meta Ads dengan AI")
        errors = house_plan.validate(spec)
        self.assertEqual(errors, [])
        self.assertEqual(spec["clip"], "v09-test")
        self.assertTrue(all(s["snap"] for s in spec["cut"]["segments"]))
        self.assertEqual(spec["captions"]["mode"], "auto")
        self.assertEqual(spec["moments"], [])
        self.assertEqual(spec["headlines"], [])
        self.assertTrue(spec["sound"]["auto"])
        self.assertEqual(spec["look"]["preset"], "house-v1")
        self.assertEqual(spec["source"]["speaker_tile"], [962, 272, 318, 178])
        for line in spec["title"]["lines"]:
            self.assertLessEqual(len(line["text"]), 18)
        self.assertLessEqual(len(spec["title"]["lines"]), 3)
        # no words file present -> falls back to first-range + 4s
        self.assertAlmostEqual(spec["title"]["until"], 9.0)

    def test_title_wraps_long_text(self):
        spec = house_plan.rough_cut_spec("v10", "/nonexistent/s.mp4", "/nonexistent/w.json",
                                          [(0.0, 1.0)], "This is a genuinely quite long headline title")
        self.assertGreater(len(spec["title"]["lines"]), 1)
        for line in spec["title"]["lines"]:
            self.assertLessEqual(len(line["text"]), 18)


class SnapSegmentsTest(StudioTestCase):
    def _make_tone_silence_wav(self, path):
        # 1.0s tone, 0.3s silence, 1.0s tone - boundary near t=1.0 should snap into the quiet gap
        filt = (
            "sine=frequency=440:sample_rate=48000:duration=1.0[a];"
            "anullsrc=r=48000:cl=mono:d=0.3[b];"
            "sine=frequency=440:sample_rate=48000:duration=1.0[c];"
            "[a][b][c]concat=n=3:v=0:a=1[out]"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-filter_complex", filt, "-map", "[out]", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )

    def test_snap_moves_boundary_into_silence(self):
        wav = os.path.join(self._tmp, "tone.wav")
        try:
            self._make_tone_silence_wav(wav)
        except (OSError, subprocess.SubprocessError) as e:
            self.skipTest("ffmpeg lavfi unavailable: %s" % e)

        spec = _minimal_spec(source={"file": wav, "words": "/nonexistent/w.json", "speaker_tile": [962, 272, 318, 178]})
        # boundary placed right at the edge of the tone (t=1.02s, just inside the silence)
        spec["cut"]["segments"] = [{"a": 0.0, "b": 1.02, "snap": True, "mute": False},
                                    {"a": 1.28, "b": 2.0, "snap": True, "mute": False}]
        segs = house_plan.snap_segments(spec)
        end_a, end_b = segs[0]["snapped"][1], segs[1]["snapped"][0]
        # both boundaries should land inside the silent gap [1.0, 1.3]
        self.assertGreaterEqual(end_a, 0.95)
        self.assertLessEqual(end_a, 1.35)
        self.assertGreaterEqual(end_b, 0.95)
        self.assertLessEqual(end_b, 1.35)

    def test_no_snap_when_flag_false(self):
        spec = _minimal_spec()
        segs = house_plan.snap_segments(spec)
        for seg, orig in zip(segs, spec["cut"]["segments"]):
            self.assertEqual(seg["snapped"], [orig["a"], orig["b"]])

    def test_cache_file_written(self):
        wav = os.path.join(self._tmp, "tone2.wav")
        try:
            self._make_tone_silence_wav(wav)
        except (OSError, subprocess.SubprocessError) as e:
            self.skipTest("ffmpeg lavfi unavailable: %s" % e)
        spec = _minimal_spec(source={"file": wav, "words": "/nonexistent/w.json", "speaker_tile": [962, 272, 318, 178]})
        spec["cut"]["segments"] = [{"a": 0.0, "b": 1.02, "snap": True, "mute": False}]
        house_plan.snap_segments(spec)
        from studio_core import paths
        cache_path = os.path.join(paths.cache_dir(), "snap.json")
        self.assertTrue(os.path.exists(cache_path))
        with open(cache_path) as f:
            data = json.load(f)
        self.assertTrue(len(data) > 0)


if __name__ == "__main__":
    unittest.main()
