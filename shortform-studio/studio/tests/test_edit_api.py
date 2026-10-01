"""v2 "the recipe" tests: recipe GET/PUT, dirty flag, words, render jobs
(success + failure, via a fake renderer), stills (via a fake still command),
asset upload, and the approve-proposal -> rough-cut -> auto-render flow.

A tiny fake `studio_core.house_plan` is installed into sys.modules so these
tests never depend on the (parallel-authored) real implementation landing
first; render/still calls out to `uv run studio_core.house_render`, so those
are exercised against a fake command (a short Python script) instead of a
real uv/numpy/Pillow toolchain.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import types
import unittest
import urllib.error
import urllib.request

from helpers import StudioTestCase

import studio_core
from studio_core import jobs, server, store


# ---------------------------------------------------------------------------
# fake house_plan -- deterministic, dependency-free stand-in for the real
# (parallel-authored) studio_core/house_plan.py
# ---------------------------------------------------------------------------

def _fake_validate(spec):
    errors = []
    if not isinstance(spec, dict):
        return ["spec must be an object"]
    if not spec.get("clip"):
        errors.append("missing clip id")
    segments = ((spec.get("cut") or {}).get("segments")) or []
    for seg in segments:
        if seg.get("a") is None or seg.get("b") is None:
            errors.append("segment missing a/b")
        elif seg["a"] >= seg["b"]:
            errors.append("segment a must be < b")
    return errors


def _fake_plan(spec):
    segments = (spec.get("cut") or {}).get("segments", [])
    duration = sum(max(0.0, s["b"] - s["a"]) for s in segments)
    return {"duration": duration, "segments": [], "captions": [], "title": None,
            "headlines": [], "moments": [], "sfx": [], "warnings": []}


def _fake_diff(old, new):
    old, new = (old or {}), (new or {})
    changes = []
    if old.get("title") != new.get("title"):
        changes.append("Text: title changed")
    if old.get("cut") != new.get("cut"):
        changes.append("Cut: segments changed")
    if old.get("captions") != new.get("captions"):
        changes.append("Captions: changed")
    if not changes:
        changes.append("Minor changes")
    return changes


def _fake_rough_cut_spec(clip_id, source_file, words_path, ranges, title):
    segments = [{"a": float(a), "b": float(b), "snap": True, "mute": False} for a, b in (ranges or [])]
    until = (ranges[0][1] if ranges else 4.0)
    return {
        "schema": 1, "clip": clip_id,
        "source": {"file": source_file, "words": words_path, "speaker_tile": None},
        "cut": {"segments": segments, "tail": 0.5},
        "captions": {"mode": "auto", "phrases": [], "hidden": False},
        "title": {"lines": [{"text": title, "hl": None}], "until": until},
        "headlines": [], "moments": [],
        "sound": {"auto": True, "sfx_gain_db": 0, "muted": [], "extra": [],
                   "voice_lufs": -17, "true_peak": -1.5},
        "look": {"preset": "house-v1"},
        "output": {"width": 1080, "height": 1920, "fps": 24},
    }


def _install_fake_house_plan():
    fake = types.ModuleType("studio_core.house_plan")
    fake.validate = _fake_validate
    fake.plan = _fake_plan
    fake.diff = _fake_diff
    fake.rough_cut_spec = _fake_rough_cut_spec
    sys.modules["studio_core.house_plan"] = fake
    return fake


class FakeHousePlanMixin:
    """Installs the fake house_plan for the duration of each test only, and
    restores whatever was there before it (the real house_plan.py, once the
    parallel worker lands it, or nothing) -- so this file never leaks a fake
    module into other test files sharing the same process.

    `from studio_core import house_plan` resolves via getattr(studio_core,
    "house_plan") first and only falls back to sys.modules if that attribute
    is unset, so once the real module has been imported anywhere in this
    process (e.g. test_house_plan.py) that package attribute -- not just
    sys.modules -- must be overridden too.
    """

    def setUp(self):
        super().setUp()
        self._orig_house_plan_sys = sys.modules.get("studio_core.house_plan")
        self._orig_house_plan_attr = getattr(studio_core, "house_plan", None)
        fake = _install_fake_house_plan()
        studio_core.house_plan = fake

    def tearDown(self):
        if self._orig_house_plan_sys is not None:
            sys.modules["studio_core.house_plan"] = self._orig_house_plan_sys
        else:
            sys.modules.pop("studio_core.house_plan", None)
        if self._orig_house_plan_attr is not None:
            studio_core.house_plan = self._orig_house_plan_attr
        else:
            if hasattr(studio_core, "house_plan"):
                delattr(studio_core, "house_plan")
        super().tearDown()


# ---------------------------------------------------------------------------
# fake renderer / still scripts
# ---------------------------------------------------------------------------

FAKE_RENDER_OK = """
import json, shutil, sys
src, spec_path, out_path, progress_path = sys.argv[1:5]
with open(progress_path, "w") as f:
    json.dump({"frame": 10, "total": 10}, f)
shutil.copyfile(src, out_path)
"""

FAKE_RENDER_FAIL = """
import sys
sys.stderr.write("boom: renderer exploded\\n")
sys.exit(1)
"""

FAKE_STILL_OK = """
import sys
out_jpg = sys.argv[1]
with open(out_jpg, "wb") as f:
    f.write(b"\\xff\\xd8\\xff\\xd9")
"""

FAKE_STILL_FAIL = """
import sys
sys.stderr.write("still exploded\\n")
sys.exit(1)
"""


def _write_script(dirpath, name, code):
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


# ---------------------------------------------------------------------------
# store-level tests (no server)
# ---------------------------------------------------------------------------

class RecipeStoreTest(FakeHousePlanMixin, StudioTestCase):
    def _spec(self, clip_id, title="Hello"):
        return {
            "schema": 1, "clip": clip_id,
            "source": {"file": "/tmp/src.mp4", "words": "/tmp/words.json", "speaker_tile": None},
            "cut": {"segments": [{"a": 1.0, "b": 3.0, "snap": False, "mute": False}], "tail": 0.6},
            "captions": {"mode": "auto", "phrases": [], "hidden": False},
            "title": {"lines": [{"text": title, "hl": None}], "until": 3.0},
            "headlines": [], "moments": [],
            "sound": {"auto": True, "sfx_gain_db": 0, "muted": [], "extra": [],
                      "voice_lufs": -17, "true_peak": -1.5},
            "look": {"preset": "house-v1"},
            "output": {"width": 1080, "height": 1920, "fps": 24},
        }

    def test_get_save_snapshot_latest_snapshot_roundtrip(self):
        clip = store.create_clip(title="Recipe Clip")
        cid = clip["id"]
        self.assertIsNone(store.get_recipe(cid))
        self.assertFalse(store.recipe_exists(cid))

        spec = self._spec(cid)
        store.save_recipe(cid, spec)
        self.assertTrue(store.recipe_exists(cid))
        self.assertEqual(store.get_recipe(cid)["title"]["lines"][0]["text"], "Hello")

        self.assertIsNone(store.latest_snapshot(cid))
        store.snapshot_recipe(cid, spec, 1)
        self.assertEqual(store.latest_snapshot(cid)["title"]["lines"][0]["text"], "Hello")

        spec2 = self._spec(cid, title="World")
        store.snapshot_recipe(cid, spec2, 3)
        # highest-numbered snapshot wins
        self.assertEqual(store.latest_snapshot(cid)["title"]["lines"][0]["text"], "World")
        # bounded lookup finds the earlier one
        self.assertEqual(store.latest_snapshot(cid, max_version=1)["title"]["lines"][0]["text"], "Hello")

    def test_create_rough_cut_recipe_idempotent_unless_overwrite(self):
        rec = store.create_recording(title="Rec", file="/tmp/rec.mp4", transcript="/tmp/w.json")
        rec, p1 = store.add_proposal(rec["id"], title="A Clip", ranges=[[10.0, 20.0]])
        rec, proposal, clip = store.approve_proposal(rec["id"], p1["id"])
        cid = clip["id"]

        self.assertIsNone(store.get_recipe(cid))
        spec, created = store.create_rough_cut_recipe(cid)
        self.assertTrue(created)
        self.assertEqual(spec["cut"]["segments"][0]["a"], 10.0)

        # idempotent: calling again without overwrite returns the same recipe, created=False
        store.save_recipe(cid, dict(spec, extra_marker=True))
        spec2, created2 = store.create_rough_cut_recipe(cid)
        self.assertFalse(created2)
        self.assertTrue(spec2.get("extra_marker"))

        # overwrite=True rebuilds from the proposal
        spec3, created3 = store.create_rough_cut_recipe(cid, overwrite=True)
        self.assertTrue(created3)
        self.assertNotIn("extra_marker", spec3)


# ---------------------------------------------------------------------------
# server (HTTP) tests
# ---------------------------------------------------------------------------

class EditApiTestCase(FakeHousePlanMixin, StudioTestCase):
    def setUp(self):
        super().setUp()
        self.httpd = server.make_server(port=0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.scripts_dir = os.path.join(self._tmp, "scripts")
        os.makedirs(self.scripts_dir, exist_ok=True)
        self._orig_render_command = jobs.render_command
        self._orig_still_command = jobs.still_command

    def tearDown(self):
        jobs.render_command = self._orig_render_command
        jobs.still_command = self._orig_still_command
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def request(self, method, path, body=None, raw=None, headers=None):
        data = None
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url(path), data=data, method=method)
        if raw is not None:
            req.add_header("Content-Type", "application/octet-stream")
        else:
            req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req)
            return resp.getcode(), resp.read(), dict(resp.getheaders())
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.getheaders())

    # -- fixtures --------------------------------------------------------

    def _clip_with_recipe(self, title="Edit Clip"):
        clip = store.create_clip(title=title, workdir=os.path.join(self._tmp, "clipwork"))
        spec = {
            "schema": 1, "clip": clip["id"],
            "source": {"file": "/tmp/src.mp4", "words": "/tmp/words.json", "speaker_tile": None},
            "cut": {"segments": [{"a": 1.0, "b": 3.0, "snap": False, "mute": False}], "tail": 0.6},
            "captions": {"mode": "auto", "phrases": [], "hidden": False},
            "title": {"lines": [{"text": "Hello", "hl": None}], "until": 3.0},
            "headlines": [], "moments": [],
            "sound": {"auto": True, "sfx_gain_db": 0, "muted": [], "extra": [],
                      "voice_lufs": -17, "true_peak": -1.5},
            "look": {"preset": "house-v1"},
            "output": {"width": 1080, "height": 1920, "fps": 24},
        }
        store.save_recipe(clip["id"], spec)
        return clip, spec

    def _use_fake_render(self, video_path, code=FAKE_RENDER_OK):
        script = _write_script(self.scripts_dir, "fake_render.py", code)

        def fake_command(spec_path, out_path, progress_path):
            return [sys.executable, script, video_path, spec_path, out_path, progress_path]
        jobs.render_command = fake_command

    def _use_fake_still(self, code=FAKE_STILL_OK):
        script = _write_script(self.scripts_dir, "fake_still.py", code)

        def fake_command(spec_path, t_out, out_jpg, width):
            return [sys.executable, script, out_jpg]
        jobs.still_command = fake_command

    def _wait_until(self, predicate, timeout=10.0, interval=0.05):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(interval)
        return predicate()

    # -- recipe GET/PUT ---------------------------------------------------

    def test_get_edit_404_without_recipe(self):
        clip = store.create_clip(title="No Recipe")
        status, body, _ = self.request("GET", "/api/clips/%s/edit" % clip["id"])
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "no recipe")

    def test_get_put_roundtrip_and_plan(self):
        clip, spec = self._clip_with_recipe()
        status, body, _ = self.request("GET", "/api/clips/%s/edit" % clip["id"])
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["spec"]["title"]["lines"][0]["text"], "Hello")
        self.assertIsNotNone(data["plan"])
        self.assertIsNone(data["plan_error"])
        self.assertIsNone(data["rendered_version"])
        self.assertTrue(data["dirty"])  # never snapshotted yet
        self.assertEqual(data["job"]["state"], "idle")

        spec["title"]["lines"][0]["text"] = "Changed"
        status, body, _ = self.request("PUT", "/api/clips/%s/edit" % clip["id"], {"spec": spec})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["spec"]["title"]["lines"][0]["text"], "Changed")
        self.assertEqual(store.get_recipe(clip["id"])["title"]["lines"][0]["text"], "Changed")

    def test_put_invalid_spec_400_with_errors(self):
        clip, spec = self._clip_with_recipe()
        bad = dict(spec)
        bad["clip"] = ""  # fails fake validate()
        status, body, _ = self.request("PUT", "/api/clips/%s/edit" % clip["id"], {"spec": bad})
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertIn("errors", data)
        self.assertTrue(data["errors"])

    def test_put_missing_spec_400(self):
        clip, _spec = self._clip_with_recipe()
        status, body, _ = self.request("PUT", "/api/clips/%s/edit" % clip["id"], {})
        self.assertEqual(status, 400)

    # -- dirty flag ---------------------------------------------------------

    def test_dirty_flag_vs_snapshot(self):
        clip, spec = self._clip_with_recipe()
        store.snapshot_recipe(clip["id"], spec, 1)
        status, body, _ = self.request("GET", "/api/clips/%s/edit" % clip["id"])
        data = json.loads(body)
        self.assertFalse(data["dirty"])

        spec["title"]["lines"][0]["text"] = "Edited"
        self.request("PUT", "/api/clips/%s/edit" % clip["id"], {"spec": spec})
        status, body, _ = self.request("GET", "/api/clips/%s/edit" % clip["id"])
        data = json.loads(body)
        self.assertTrue(data["dirty"])
        self.assertIn("Text: title changed", data["changes"])

        # clip summary in /api/state agrees
        status, body, _ = self.request("GET", "/api/state")
        summary = next(c for c in json.loads(body)["clips"] if c["id"] == clip["id"])
        self.assertTrue(summary["has_recipe"])
        self.assertTrue(summary["dirty"])

    # -- words --------------------------------------------------------------

    def test_words_endpoint_from_recipe_source(self):
        clip, spec = self._clip_with_recipe()
        words_path = os.path.join(self._tmp, "words.json")
        store.write_json_atomic(words_path, {
            "word_segments": [
                {"word": "before", "start": -100.0, "end": -99.5},
                {"word": "kept1", "start": 0.5, "end": 0.9},
                {"word": "kept2", "start": 2.8, "end": 3.1},
                {"word": "far-away", "start": 500.0, "end": 500.5},
            ]
        })
        spec["source"]["words"] = words_path
        store.save_recipe(clip["id"], spec)
        status, body, _ = self.request("GET", "/api/clips/%s/words?pad=1" % clip["id"])
        self.assertEqual(status, 200)
        words = json.loads(body)["words"]
        got = [w[0] for w in words]
        self.assertIn("kept1", got)
        self.assertIn("kept2", got)
        self.assertNotIn("before", got)
        self.assertNotIn("far-away", got)

    # -- rough-cut endpoint ---------------------------------------------------

    def test_rough_cut_endpoint_requires_proposal(self):
        clip = store.create_clip(title="Orphan Clip")
        status, body, _ = self.request("POST", "/api/clips/%s/edit/rough-cut" % clip["id"])
        self.assertEqual(status, 400)

    def test_rough_cut_endpoint_builds_from_proposal(self):
        rec = store.create_recording(title="Rec2", file="/tmp/rec2.mp4", transcript="/tmp/w2.json")
        rec, p1 = store.add_proposal(rec["id"], title="Nice Clip", ranges=[[5.0, 9.0]])
        rec, proposal, clip = store.approve_proposal(rec["id"], p1["id"])
        status, body, _ = self.request("POST", "/api/clips/%s/edit/rough-cut" % clip["id"])
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["spec"]["cut"]["segments"][0]["a"], 5.0)

    # -- render job: success --------------------------------------------------

    def test_render_success_registers_version_with_diff_and_snapshot(self):
        clip, spec = self._clip_with_recipe()
        store.snapshot_recipe(clip["id"], spec, 1)  # pretend v1 was already rendered with this spec
        # bump the version count so rendered_version / notes reflect a real prior render
        info = {"duration": 1.0, "width": 270, "height": 480, "size": 100}
        store.add_clip_version(clip["id"], "/tmp/does-not-matter.mp4", kind="render", probe=info)

        video = self.make_test_video("fake-render-src.mp4", duration=1)
        self._use_fake_render(video)

        spec["title"]["lines"][0]["text"] = "Changed For Render"
        store.save_recipe(clip["id"], spec)

        status, body, _ = self.request("POST", "/api/clips/%s/render" % clip["id"], {"note": "test pass"})
        self.assertEqual(status, 200)
        job = json.loads(body)["job"]
        self.assertEqual(job["state"], "running")

        ok = self._wait_until(lambda: store.get_clip(clip["id"])["render"]["state"] in ("done", "error"))
        self.assertTrue(ok, "render did not finish in time")
        clip_after = store.get_clip(clip["id"])
        self.assertEqual(clip_after["render"]["state"], "done")

        versions = clip_after["versions"]
        newest = max(versions, key=lambda v: v["n"])
        self.assertIn("test pass", newest["notes"])
        self.assertIn("Text: title changed", newest["notes"])
        self.assertEqual(clip_after["status"], "review")

        # snapshot was written at the new version number
        snap = store.latest_snapshot(clip["id"])
        self.assertEqual(snap["title"]["lines"][0]["text"], "Changed For Render")

        # GET /render reflects the finished job
        status, body, _ = self.request("GET", "/api/clips/%s/render" % clip["id"])
        self.assertEqual(json.loads(body)["job"]["state"], "done")

    # -- render job: failure --------------------------------------------------

    def test_render_failure_sets_error_state(self):
        clip, spec = self._clip_with_recipe()
        video = self.make_test_video("unused.mp4", duration=1)
        self._use_fake_render(video, code=FAKE_RENDER_FAIL)

        status, body, _ = self.request("POST", "/api/clips/%s/render" % clip["id"], {})
        self.assertEqual(status, 200)

        ok = self._wait_until(lambda: store.get_clip(clip["id"])["render"]["state"] in ("done", "error"))
        self.assertTrue(ok)
        clip_after = store.get_clip(clip["id"])
        self.assertEqual(clip_after["render"]["state"], "error")
        self.assertTrue(clip_after["render"]["message"])
        # no new version was registered
        self.assertEqual(clip_after["versions"], [])

    def test_render_without_recipe_400(self):
        clip = store.create_clip(title="No Recipe For Render")
        status, body, _ = self.request("POST", "/api/clips/%s/render" % clip["id"], {})
        self.assertEqual(status, 400)

    # -- still ----------------------------------------------------------------

    def test_still_endpoint(self):
        clip, spec = self._clip_with_recipe()
        self._use_fake_still()
        status, body, headers = self.request("GET", "/api/clips/%s/still.jpg?t=1.23&w=360" % clip["id"])
        self.assertEqual(status, 200)
        self.assertEqual(body[:3], b"\xff\xd8\xff")
        self.assertIn("image/jpeg", headers.get("Content-Type", ""))

    def test_still_endpoint_failure_400(self):
        clip, spec = self._clip_with_recipe()
        self._use_fake_still(code=FAKE_STILL_FAIL)
        status, body, _ = self.request("GET", "/api/clips/%s/still.jpg?t=1.0" % clip["id"])
        self.assertEqual(status, 400)

    def test_still_without_recipe_400(self):
        clip = store.create_clip(title="No Recipe For Still")
        self._use_fake_still()
        status, body, _ = self.request("GET", "/api/clips/%s/still.jpg?t=0" % clip["id"])
        self.assertEqual(status, 400)

    # -- assets ----------------------------------------------------------------

    def test_asset_upload_and_bad_extension(self):
        clip = store.create_clip(title="Asset Clip", workdir=os.path.join(self._tmp, "assetwork"))
        raw = b"\xff\xd8\xff\xd9fakejpegbytes"
        status, body, _ = self.request(
            "POST", "/api/clips/%s/assets?name=book.jpg" % clip["id"], raw=raw)
        self.assertEqual(status, 200)
        path = json.loads(body)["path"]
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), raw)
        self.assertTrue(path.endswith("assets/img/book.jpg") or path.endswith("assets\\img\\book.jpg"))

        status, body, _ = self.request(
            "POST", "/api/clips/%s/assets?name=script.exe" % clip["id"], raw=raw)
        self.assertEqual(status, 400)

    def test_asset_upload_unknown_clip_404(self):
        raw = b"\xff\xd8\xff\xd9"
        status, body, _ = self.request(
            "POST", "/api/clips/does-not-exist/assets?name=a.png", raw=raw)
        self.assertEqual(status, 404)

    # -- approve proposal -> rough cut (+ auto render) --------------------------

    def test_approve_proposal_creates_recipe_and_starts_render_when_auto(self):
        video = self.make_test_video("approve-src.mp4", duration=1)
        self._use_fake_render(video)

        rec = store.create_recording(title="Approve Rec", file="/tmp/recA.mp4", transcript="/tmp/wA.json")
        status, body, _ = self.request(
            "POST", "/api/recordings/%s/proposals" % rec["id"],
            {"title": "Auto Rough Cut Clip", "ranges": [[2.0, 6.0]]})
        self.assertEqual(status, 200)
        pid = json.loads(body)["id"]

        self.assertTrue(store.get_settings().get("auto_rough_cut", True))
        status, body, _ = self.request(
            "POST", "/api/recordings/%s/proposals/%s/approve" % (rec["id"], pid))
        self.assertEqual(status, 200)
        data = json.loads(body)
        clip_id = data["clip"]["id"]

        self.assertTrue(store.recipe_exists(clip_id))
        recipe = store.get_recipe(clip_id)
        self.assertEqual(recipe["cut"]["segments"][0]["a"], 2.0)

        ok = self._wait_until(lambda: store.get_clip(clip_id)["render"]["state"] in ("done", "error"))
        self.assertTrue(ok, "auto rough-cut render did not finish in time")
        clip_after = store.get_clip(clip_id)
        self.assertEqual(clip_after["render"]["state"], "done")
        self.assertEqual(len(clip_after["versions"]), 1)
        self.assertIn("First render", clip_after["versions"][0]["notes"])
        self.assertEqual(clip_after["status"], "review")

        # idempotent: approving again does not start a second render or recipe
        render_version_before = clip_after["render"]["version"]
        status, body, _ = self.request(
            "POST", "/api/recordings/%s/proposals/%s/approve" % (rec["id"], pid))
        self.assertEqual(status, 200)
        clip_again = store.get_clip(clip_id)
        self.assertEqual(len(clip_again["versions"]), 1)
        self.assertEqual(clip_again["render"]["version"], render_version_before)

    def test_approve_proposal_no_render_when_auto_rough_cut_off(self):
        store.update_settings({"auto_rough_cut": False})
        rec = store.create_recording(title="Manual Rec", file="/tmp/recB.mp4", transcript="/tmp/wB.json")
        status, body, _ = self.request(
            "POST", "/api/recordings/%s/proposals" % rec["id"],
            {"title": "Manual Clip", "ranges": [[1.0, 3.0]]})
        pid = json.loads(body)["id"]
        status, body, _ = self.request(
            "POST", "/api/recordings/%s/proposals/%s/approve" % (rec["id"], pid))
        self.assertEqual(status, 200)
        clip_id = json.loads(body)["clip"]["id"]
        self.assertTrue(store.recipe_exists(clip_id))
        self.assertEqual(store.clip_render_state(store.get_clip(clip_id))["state"], "idle")
        self.assertEqual(store.get_clip(clip_id)["versions"], [])


if __name__ == "__main__":
    unittest.main()
